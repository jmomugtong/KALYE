'use client';

import { Marker } from 'react-map-gl';
import { getMarkerColor } from '@/src/lib/mapbox';
import type { Detection } from '@/src/types/detection';

interface DetectionMarkerProps {
  detection: Detection;
  onClick: (detection: Detection) => void;
}

export default function DetectionMarker({
  detection,
  onClick,
}: DetectionMarkerProps) {
  const color = getMarkerColor(detection.type);

  return (
    <Marker
      longitude={detection.longitude}
      latitude={detection.latitude}
      anchor="bottom"
      onClick={(e) => {
        e.originalEvent.stopPropagation();
        onClick(detection);
      }}
    >
      <button
        type="button"
        aria-label={`${detection.type} detection`}
        className="cursor-pointer transition-transform hover:scale-110"
      >
        <svg
          width="24"
          height="32"
          viewBox="0 0 24 32"
          fill="none"
          xmlns="http://www.w3.org/2000/svg"
        >
          <path
            d="M12 0C5.373 0 0 5.373 0 12c0 9 12 20 12 20s12-11 12-20c0-6.627-5.373-12-12-12z"
            fill={color}
          />
          <circle cx="12" cy="12" r="5" fill="white" />
        </svg>
      </button>
    </Marker>
  );
}
