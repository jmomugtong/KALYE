'use client';

import { useEffect } from 'react';
import { MapContainer, TileLayer, CircleMarker, Popup, useMap } from 'react-leaflet';
import type { PublicDetection } from '@/app/explore/page';
import 'leaflet/dist/leaflet.css';

const TYPE_COLORS: Record<string, string> = {
  pothole: '#ef4444',
  sidewalk_obstruction: '#f59e0b',
  missing_sign: '#8b5cf6',
  curb_ramp: '#3b82f6',
  broken_sidewalk: '#f97316',
  flooding: '#06b6d4',
  missing_ramp: '#ec4899',
};

const TYPE_LABELS: Record<string, string> = {
  pothole: 'Pothole',
  sidewalk_obstruction: 'Sidewalk Obstruction',
  missing_sign: 'Missing Sign',
  curb_ramp: 'Curb Ramp Issue',
  broken_sidewalk: 'Broken Sidewalk',
  flooding: 'Flooding',
  missing_ramp: 'Missing Ramp',
};

// Default: Metro Manila (Makati area). Will auto-fit to detections if any.
const DEFAULT_CENTER: [number, number] = [14.5547, 121.0350];
const DEFAULT_ZOOM = 14;

function FitBounds({ detections }: { detections: PublicDetection[] }) {
  const map = useMap();

  useEffect(() => {
    // Fix Leaflet sizing in flex containers
    setTimeout(() => map.invalidateSize(), 100);

    if (detections.length > 0) {
      const lats = detections.map((d) => d.latitude);
      const lngs = detections.map((d) => d.longitude);
      const bounds: [[number, number], [number, number]] = [
        [Math.min(...lats) - 0.002, Math.min(...lngs) - 0.002],
        [Math.max(...lats) + 0.002, Math.max(...lngs) + 0.002],
      ];
      map.fitBounds(bounds, { padding: [50, 50], maxZoom: 16 });
    }
  }, [map, detections]);

  return null;
}

function formatDate(iso: string) {
  return new Date(iso).toLocaleDateString('en-PH', {
    year: 'numeric',
    month: 'short',
    day: 'numeric',
  });
}

interface PublicMapProps {
  detections: PublicDetection[];
}

export default function PublicMap({ detections }: PublicMapProps) {
  return (
    <MapContainer
      center={DEFAULT_CENTER}
      zoom={DEFAULT_ZOOM}
      className="absolute inset-0 z-0"
      zoomControl={true}
      attributionControl={true}
    >
      <FitBounds detections={detections} />
      <TileLayer
        attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors'
        url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
      />

      {detections.map((d) => (
        <CircleMarker
          key={d.detection_id}
          center={[d.latitude, d.longitude]}
          radius={9}
          pathOptions={{
            fillColor: TYPE_COLORS[d.detection_type] || '#6b7280',
            color: '#fff',
            weight: 2,
            opacity: 1,
            fillOpacity: 0.85,
          }}
        >
          <Popup>
            <div className="text-sm min-w-[200px]">
              <div className="flex items-center gap-2 mb-2">
                <span
                  className="w-3 h-3 rounded-full flex-shrink-0"
                  style={{ backgroundColor: TYPE_COLORS[d.detection_type] }}
                />
                <span className="font-semibold">
                  {TYPE_LABELS[d.detection_type] || d.detection_type}
                </span>
              </div>
              {d.caption && (
                <p className="text-gray-600 mb-2">{d.caption}</p>
              )}
              <div className="space-y-1 text-xs text-gray-500">
                <p>
                  Confidence:{' '}
                  <span className="text-gray-800 font-medium">
                    {(d.confidence_score * 100).toFixed(0)}%
                  </span>
                </p>
                <p>
                  Reported:{' '}
                  <span className="text-gray-800 font-medium">
                    {formatDate(d.created_at)}
                  </span>
                </p>
                <p className="text-[10px] text-gray-400 font-mono">
                  {d.latitude.toFixed(5)}, {d.longitude.toFixed(5)}
                </p>
              </div>
            </div>
          </Popup>
        </CircleMarker>
      ))}
    </MapContainer>
  );
}
