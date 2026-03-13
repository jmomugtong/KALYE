'use client';

import { useEffect } from 'react';
import { MapContainer, TileLayer, CircleMarker, Popup, useMap } from 'react-leaflet';
import type { MockDetection } from '@/app/dashboard/page';
import 'leaflet/dist/leaflet.css';

const TYPE_COLORS: Record<string, string> = {
  pothole: '#ef4444',
  obstruction: '#f59e0b',
  missing_sign: '#8b5cf6',
  curb_ramp: '#3b82f6',
};

// Metro Manila center (Makati-BGC area)
const CENTER: [number, number] = [14.5547, 121.0350];
const ZOOM = 13;

function InvalidateSize() {
  const map = useMap();
  useEffect(() => {
    // Fix Leaflet rendering in flex containers
    setTimeout(() => map.invalidateSize(), 100);
  }, [map]);
  return null;
}

interface LeafletMapProps {
  detections: MockDetection[];
}

export default function LeafletMap({ detections }: LeafletMapProps) {
  return (
    <MapContainer
      center={CENTER}
      zoom={ZOOM}
      className="absolute inset-0 z-0"
      zoomControl={false}
      attributionControl={true}
    >
      <InvalidateSize />
      <TileLayer
        attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors'
        url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
      />

      {detections.map((d) => (
        <CircleMarker
          key={d.id}
          center={[d.lat, d.lng]}
          radius={10}
          pathOptions={{
            fillColor: TYPE_COLORS[d.type],
            color: '#fff',
            weight: 2,
            opacity: 1,
            fillOpacity: 0.85,
          }}
        >
          <Popup>
            <div className="text-sm min-w-[180px]">
              <p className="font-semibold text-base mb-1">{d.label}</p>
              <p className="text-gray-600">{d.address}</p>
              <div className="mt-2 space-y-1 text-xs text-gray-500">
                <p>Barangay: <span className="text-gray-800 font-medium">{d.barangay}</span></p>
                <p>Confidence: <span className="text-gray-800 font-medium">{(d.confidence * 100).toFixed(0)}%</span></p>
                <p>Status: <span className="text-yellow-600 font-medium">Pending Review</span></p>
              </div>
            </div>
          </Popup>
        </CircleMarker>
      ))}
    </MapContainer>
  );
}
