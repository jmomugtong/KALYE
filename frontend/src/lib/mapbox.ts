import type { Detection, DetectionType } from '@/src/types/detection';
import type { FeatureCollection, Point } from 'geojson';
import type { LngLatBoundsLike } from 'react-map-gl';

/** Metro Manila bounding box: [sw_lng, sw_lat, ne_lng, ne_lat] */
export const METRO_MANILA_BOUNDS: LngLatBoundsLike = [
  [120.9, 14.35],
  [121.15, 14.78],
];

export const DEFAULT_CENTER: [number, number] = [121.0, 14.6];
export const DEFAULT_ZOOM = 11;

const MARKER_COLORS: Record<DetectionType, string> = {
  pothole: '#dc2626',
  obstruction: '#f97316',
  missing_sign: '#facc15',
  curb_ramp: '#3b82f6',
};

export function getMarkerColor(type: string): string {
  return MARKER_COLORS[type as DetectionType] ?? '#6b7280';
}

export function detectionsToGeoJSON(
  detections: Detection[]
): FeatureCollection<Point> {
  return {
    type: 'FeatureCollection',
    features: detections.map((d) => ({
      type: 'Feature' as const,
      id: d.id,
      geometry: {
        type: 'Point' as const,
        coordinates: [d.longitude, d.latitude],
      },
      properties: {
        id: d.id,
        type: d.type,
        confidence: d.confidence,
        timestamp: d.timestamp,
        description: d.description ?? '',
        barangay: d.barangay ?? '',
        severity: d.severity ?? 'medium',
        imageUrl: d.imageUrl ?? '',
        color: getMarkerColor(d.type),
      },
    })),
  };
}
