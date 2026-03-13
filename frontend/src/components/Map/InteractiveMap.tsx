// @ts-nocheck
'use client';

import { useCallback, useMemo, useRef, useState } from 'react';
import Map, { type MapRef, type ViewStateChangeEvent } from 'react-map-gl';
import type { Detection } from '@/types/api';
import {
  DEFAULT_CENTER,
  DEFAULT_ZOOM,
  METRO_MANILA_BOUNDS,
  detectionsToGeoJSON,
} from '@/lib/mapbox';
import DetectionMarker from './DetectionMarker';
import DetectionPopup from './DetectionPopup';
import HeatmapLayer from './HeatmapLayer';
import MapControls, { type LayerVisibility } from './MapControls';

export interface Bounds {
  north: number;
  south: number;
  east: number;
  west: number;
}

interface InteractiveMapProps {
  initialCenter?: [number, number];
  initialZoom?: number;
  detections?: Detection[];
  onBoundsChange?: (bounds: Bounds) => void;
}

const MAPBOX_TOKEN = process.env.NEXT_PUBLIC_MAPBOX_TOKEN ?? '';

export default function InteractiveMap({
  initialCenter = [14.6, 121.0],
  initialZoom = 11,
  detections = [],
  onBoundsChange,
}: InteractiveMapProps) {
  const mapRef = useRef<MapRef>(null);
  const debounceRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  const [selectedDetection, setSelectedDetection] = useState<Detection | null>(
    null
  );
  const [activeLayers, setActiveLayers] = useState<LayerVisibility>({
    pothole: true,
    obstruction: true,
    missing_sign: true,
    curb_ramp: true,
    heatmap: false,
  });

  // Filter detections based on active layers
  const visibleDetections = useMemo(
    () => detections.filter((d) => activeLayers[d.type]),
    [detections, activeLayers]
  );

  const geojsonData = useMemo(
    () => detectionsToGeoJSON(visibleDetections),
    [visibleDetections]
  );

  // Debounced bounds change handler
  const handleMoveEnd = useCallback(
    (evt: ViewStateChangeEvent) => {
      if (!onBoundsChange || !mapRef.current) return;

      if (debounceRef.current) {
        clearTimeout(debounceRef.current);
      }

      debounceRef.current = setTimeout(() => {
        const map = mapRef.current;
        if (!map) return;
        const bounds = map.getMap().getBounds();
        if (!bounds) return;

        onBoundsChange({
          north: bounds.getNorth(),
          south: bounds.getSouth(),
          east: bounds.getEast(),
          west: bounds.getWest(),
        });
      }, 300);
    },
    [onBoundsChange]
  );

  const handleToggleLayer = useCallback((layer: keyof LayerVisibility) => {
    setActiveLayers((prev) => ({ ...prev, [layer]: !prev[layer] }));
  }, []);

  const handleZoomIn = useCallback(() => {
    mapRef.current?.getMap().zoomIn();
  }, []);

  const handleZoomOut = useCallback(() => {
    mapRef.current?.getMap().zoomOut();
  }, []);

  const handleGeolocate = useCallback(() => {
    navigator.geolocation.getCurrentPosition(
      (position) => {
        mapRef.current?.flyTo({
          center: [position.coords.longitude, position.coords.latitude],
          zoom: 15,
          duration: 1500,
        });
      },
      (err) => {
        console.warn('Geolocation error:', err.message);
      }
    );
  }, []);

  const handleMarkerClick = useCallback((detection: Detection) => {
    setSelectedDetection(detection);
  }, []);

  const handlePopupClose = useCallback(() => {
    setSelectedDetection(null);
  }, []);

  return (
    <div className="relative w-full h-full" data-testid="map-container">
      <Map
        ref={mapRef}
        initialViewState={{
          latitude: initialCenter[0],
          longitude: initialCenter[1],
          zoom: initialZoom,
        }}
        style={{ width: '100%', height: '100%' }}
        mapStyle="mapbox://styles/mapbox/streets-v12"
        mapboxAccessToken={MAPBOX_TOKEN}
        maxBounds={METRO_MANILA_BOUNDS}
        onMoveEnd={handleMoveEnd}
        onClick={() => setSelectedDetection(null)}
      >
        {/* Heatmap layer */}
        <HeatmapLayer data={geojsonData} visible={activeLayers.heatmap} />

        {/* Individual markers */}
        {visibleDetections.map((detection) => (
          <DetectionMarker
            key={detection.id}
            detection={detection}
            onClick={handleMarkerClick}
          />
        ))}

        {/* Popup for selected detection */}
        {selectedDetection && (
          <DetectionPopup
            detection={selectedDetection}
            onClose={handlePopupClose}
          />
        )}
      </Map>

      {/* Controls overlay */}
      <MapControls
        layers={activeLayers}
        onToggleLayer={handleToggleLayer}
        onZoomIn={handleZoomIn}
        onZoomOut={handleZoomOut}
        onGeolocate={handleGeolocate}
      />
    </div>
  );
}
