"""DBSCAN clustering and heatmap generation for detection points."""

from collections import defaultdict
from typing import List

import numpy as np
from sklearn.cluster import DBSCAN


# Earth radius in metres
_EARTH_RADIUS_M = 6_371_000


class DetectionClusterer:
    """Cluster detections spatially using DBSCAN with haversine metric."""

    def cluster_detections(
        self,
        detections: List[dict],
        eps_meters: float = 100,
        min_samples: int = 3,
    ) -> List[dict]:
        """Cluster *detections* (each must have ``lat`` and ``lon`` keys).

        Returns a list of cluster dicts, each containing:
          - cluster_id (int, -1 for noise)
          - center_lat / center_lon
          - count
          - detections (list of original dicts with ``cluster_id`` added)
        """
        if not detections:
            return []

        coords = np.array([[d["lat"], d["lon"]] for d in detections])
        coords_rad = np.radians(coords)

        eps_rad = eps_meters / _EARTH_RADIUS_M

        db = DBSCAN(
            eps=eps_rad,
            min_samples=min_samples,
            metric="haversine",
            algorithm="ball_tree",
        )
        labels = db.fit_predict(coords_rad)

        # Group detections by cluster label
        clusters: dict[int, list[dict]] = defaultdict(list)
        for detection, label in zip(detections, labels):
            det = {**detection, "cluster_id": int(label)}
            clusters[int(label)].append(det)

        results: List[dict] = []
        for cluster_id, members in sorted(clusters.items()):
            lats = [m["lat"] for m in members]
            lons = [m["lon"] for m in members]
            results.append(
                {
                    "cluster_id": cluster_id,
                    "center_lat": float(np.mean(lats)),
                    "center_lon": float(np.mean(lons)),
                    "count": len(members),
                    "detections": members,
                }
            )

        return results

    def generate_heatmap_data(
        self,
        detections: List[dict],
        grid_size: float = 0.001,
    ) -> List[dict]:
        """Aggregate detections into a regular lat/lon grid.

        *grid_size* is in decimal degrees (~111 m at the equator for 0.001).

        Returns a list of dicts with keys: grid_lat, grid_lon, count, avg_confidence.
        """
        if not detections:
            return []

        grid: dict[tuple[float, float], list[dict]] = defaultdict(list)

        for d in detections:
            lat_key = round(d["lat"] / grid_size) * grid_size
            lon_key = round(d["lon"] / grid_size) * grid_size
            grid[(lat_key, lon_key)].append(d)

        results: List[dict] = []
        for (lat_key, lon_key), members in grid.items():
            confidences = [
                m["confidence_score"]
                for m in members
                if "confidence_score" in m
            ]
            results.append(
                {
                    "grid_lat": round(lat_key, 6),
                    "grid_lon": round(lon_key, 6),
                    "count": len(members),
                    "avg_confidence": (
                        round(float(np.mean(confidences)), 4)
                        if confidences
                        else None
                    ),
                }
            )

        # Sort by density descending for easier consumption
        results.sort(key=lambda r: r["count"], reverse=True)
        return results
