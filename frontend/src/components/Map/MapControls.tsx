'use client';

import { useCallback } from 'react';

export interface LayerVisibility {
  pothole: boolean;
  obstruction: boolean;
  missing_sign: boolean;
  curb_ramp: boolean;
  heatmap: boolean;
}

interface MapControlsProps {
  layers: LayerVisibility;
  onToggleLayer: (layer: keyof LayerVisibility) => void;
  onZoomIn: () => void;
  onZoomOut: () => void;
  onGeolocate?: () => void;
}

const LAYER_OPTIONS: { key: keyof LayerVisibility; label: string; color: string }[] = [
  { key: 'pothole', label: 'Potholes', color: '#dc2626' },
  { key: 'obstruction', label: 'Obstructions', color: '#f97316' },
  { key: 'missing_sign', label: 'Missing Signs', color: '#facc15' },
  { key: 'curb_ramp', label: 'ADA Issues', color: '#3b82f6' },
  { key: 'heatmap', label: 'Heatmap', color: '#8b5cf6' },
];

export default function MapControls({
  layers,
  onToggleLayer,
  onZoomIn,
  onZoomOut,
  onGeolocate,
}: MapControlsProps) {
  const handleGeolocate = useCallback(() => {
    if (!navigator.geolocation) {
      console.warn('Geolocation is not supported by this browser.');
      return;
    }
    onGeolocate?.();
  }, [onGeolocate]);

  return (
    <div className="absolute top-4 right-4 z-10 flex flex-col gap-2">
      {/* Layer toggles */}
      <div className="bg-white rounded-lg shadow-lg p-3 min-w-[180px]">
        <h3 className="text-xs font-semibold text-gray-500 uppercase tracking-wide mb-2">
          Layers
        </h3>
        {LAYER_OPTIONS.map(({ key, label, color }) => (
          <label
            key={key}
            className="flex items-center gap-2 py-1 cursor-pointer text-sm text-gray-700 hover:text-gray-900"
          >
            <input
              type="checkbox"
              checked={layers[key]}
              onChange={() => onToggleLayer(key)}
              className="rounded border-gray-300"
            />
            <span
              className="inline-block w-3 h-3 rounded-full"
              style={{ backgroundColor: color }}
            />
            {label}
          </label>
        ))}
      </div>

      {/* Zoom controls */}
      <div className="bg-white rounded-lg shadow-lg flex flex-col">
        <button
          type="button"
          onClick={onZoomIn}
          aria-label="Zoom in"
          className="px-3 py-2 text-lg font-bold text-gray-600 hover:bg-gray-100 rounded-t-lg transition-colors"
        >
          +
        </button>
        <hr className="border-gray-200" />
        <button
          type="button"
          onClick={onZoomOut}
          aria-label="Zoom out"
          className="px-3 py-2 text-lg font-bold text-gray-600 hover:bg-gray-100 rounded-b-lg transition-colors"
        >
          &minus;
        </button>
      </div>

      {/* Geolocation */}
      <button
        type="button"
        onClick={handleGeolocate}
        aria-label="Go to my location"
        className="bg-white rounded-lg shadow-lg p-2 text-gray-600 hover:bg-gray-100 transition-colors flex items-center justify-center"
      >
        <svg
          width="20"
          height="20"
          viewBox="0 0 24 24"
          fill="none"
          stroke="currentColor"
          strokeWidth="2"
          strokeLinecap="round"
          strokeLinejoin="round"
        >
          <circle cx="12" cy="12" r="4" />
          <line x1="12" y1="2" x2="12" y2="6" />
          <line x1="12" y1="18" x2="12" y2="22" />
          <line x1="2" y1="12" x2="6" y2="12" />
          <line x1="18" y1="12" x2="22" y2="12" />
        </svg>
      </button>
    </div>
  );
}
