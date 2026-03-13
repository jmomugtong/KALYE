// @ts-nocheck
'use client';

import { Layer, Source } from 'react-map-gl';
import type { FeatureCollection, Point } from 'geojson';
import type { HeatmapPaint } from 'mapbox-gl';

interface HeatmapLayerProps {
  data: FeatureCollection<Point>;
  visible: boolean;
  radius?: number;
  intensity?: number;
}

const HEATMAP_PAINT: HeatmapPaint = {
  // Increase weight based on confidence property
  'heatmap-weight': [
    'interpolate',
    ['linear'],
    ['get', 'confidence'],
    0,
    0,
    1,
    1,
  ],
  // Increase intensity as zoom level increases
  'heatmap-intensity': ['interpolate', ['linear'], ['zoom'], 0, 1, 15, 3],
  // Color ramp: green -> yellow -> red
  'heatmap-color': [
    'interpolate',
    ['linear'],
    ['heatmap-density'],
    0,
    'rgba(0,0,0,0)',
    0.2,
    '#22c55e',
    0.4,
    '#84cc16',
    0.6,
    '#eab308',
    0.8,
    '#f97316',
    1,
    '#dc2626',
  ],
  // Radius increases with zoom
  'heatmap-radius': ['interpolate', ['linear'], ['zoom'], 0, 2, 15, 20],
  // Fade out at high zoom to reveal individual markers
  'heatmap-opacity': ['interpolate', ['linear'], ['zoom'], 13, 1, 16, 0],
};

export default function HeatmapLayer({
  data,
  visible,
  radius,
  intensity,
}: HeatmapLayerProps) {
  const paint: HeatmapPaint = {
    ...HEATMAP_PAINT,
    ...(radius != null && { 'heatmap-radius': radius }),
    ...(intensity != null && { 'heatmap-intensity': intensity }),
  };

  return (
    <Source id="detections-heatmap" type="geojson" data={data}>
      <Layer
        id="detections-heatmap-layer"
        type="heatmap"
        paint={paint}
        layout={{ visibility: visible ? 'visible' : 'none' }}
      />
    </Source>
  );
}
