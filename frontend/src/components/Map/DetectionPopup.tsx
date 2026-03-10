'use client';

import { Popup } from 'react-map-gl';
import { getMarkerColor } from '@/src/lib/mapbox';
import type { Detection } from '@/src/types/detection';

interface DetectionPopupProps {
  detection: Detection;
  onClose: () => void;
}

const TYPE_LABELS: Record<string, string> = {
  pothole: 'Pothole',
  obstruction: 'Obstruction',
  missing_sign: 'Missing Sign',
  curb_ramp: 'Curb Ramp Issue',
};

export default function DetectionPopup({
  detection,
  onClose,
}: DetectionPopupProps) {
  const color = getMarkerColor(detection.type);
  const label = TYPE_LABELS[detection.type] ?? detection.type;
  const confidencePct = Math.round(detection.confidence * 100);
  const formattedDate = new Date(detection.timestamp).toLocaleDateString(
    'en-PH',
    {
      year: 'numeric',
      month: 'short',
      day: 'numeric',
      hour: '2-digit',
      minute: '2-digit',
    }
  );

  return (
    <Popup
      longitude={detection.longitude}
      latitude={detection.latitude}
      anchor="top"
      onClose={onClose}
      closeOnClick={false}
      className="detection-popup"
    >
      <div className="p-2 min-w-[200px]">
        {/* Type badge */}
        <span
          className="inline-block rounded-full px-2 py-0.5 text-xs font-semibold text-white mb-2"
          style={{ backgroundColor: color }}
        >
          {label}
        </span>

        {/* Confidence */}
        <p className="text-sm text-gray-700 mb-1">
          <span className="font-medium">Confidence:</span> {confidencePct}%
        </p>

        {/* Location */}
        <p className="text-sm text-gray-700 mb-1">
          <span className="font-medium">Location:</span>{' '}
          {detection.latitude.toFixed(5)}, {detection.longitude.toFixed(5)}
          {detection.barangay && (
            <span className="block text-xs text-gray-500">
              {detection.barangay}
            </span>
          )}
        </p>

        {/* Timestamp */}
        <p className="text-sm text-gray-700 mb-1">
          <span className="font-medium">Detected:</span> {formattedDate}
        </p>

        {/* Description */}
        {detection.description && (
          <p className="text-xs text-gray-500 mt-1">{detection.description}</p>
        )}

        {/* Close button */}
        <button
          type="button"
          onClick={onClose}
          className="mt-2 w-full text-center text-xs text-gray-400 hover:text-gray-600 transition-colors"
        >
          Close
        </button>
      </div>
    </Popup>
  );
}
