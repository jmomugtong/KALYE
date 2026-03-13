'use client';

import dynamic from 'next/dynamic';
import { useState } from 'react';

// Leaflet must be loaded client-side only (no SSR)
const MapView = dynamic(() => import('@/components/Map/LeafletMap'), {
  ssr: false,
  loading: () => (
    <div className="absolute inset-0 flex items-center justify-center bg-muted">
      <p className="text-sm text-muted-foreground">Loading map...</p>
    </div>
  ),
});

export interface MockDetection {
  id: string;
  type: 'pothole' | 'obstruction' | 'missing_sign' | 'curb_ramp';
  label: string;
  lat: number;
  lng: number;
  confidence: number;
  barangay: string;
  address: string;
}

// Real coordinates scattered across Makati, BGC, Pasig, Mandaluyong
const MOCK_DETECTIONS: MockDetection[] = [
  { id: '1', type: 'pothole', label: 'Pothole', lat: 14.5547, lng: 121.0244, confidence: 0.92, barangay: 'Poblacion', address: 'Makati Ave cor. Jupiter St' },
  { id: '2', type: 'obstruction', label: 'Sidewalk Obstruction', lat: 14.5515, lng: 121.0195, confidence: 0.87, barangay: 'Bel-Air', address: 'Bel-Air Village Gate 3' },
  { id: '3', type: 'pothole', label: 'Pothole', lat: 14.5607, lng: 121.0268, confidence: 0.78, barangay: 'San Antonio', address: 'Jupiter St near Salcedo Village' },
  { id: '4', type: 'missing_sign', label: 'Missing Pedestrian Sign', lat: 14.5673, lng: 121.0369, confidence: 0.85, barangay: 'Guadalupe Nuevo', address: 'EDSA cor. Guadalupe Bridge' },
  { id: '5', type: 'curb_ramp', label: 'Missing Curb Ramp', lat: 14.5362, lng: 121.0503, confidence: 0.91, barangay: 'Fort Bonifacio', address: 'BGC 5th Ave cor. 28th St' },
  { id: '6', type: 'pothole', label: 'Pothole', lat: 14.5428, lng: 121.0562, confidence: 0.83, barangay: 'Taguig CBD', address: 'McKinley Pkwy near Venice Piazza' },
  { id: '7', type: 'obstruction', label: 'Vendor Obstruction', lat: 14.5793, lng: 121.0000, confidence: 0.76, barangay: 'Mandaluyong', address: 'Shaw Blvd cor. EDSA' },
  { id: '8', type: 'missing_sign', label: 'Missing Crosswalk Sign', lat: 14.5857, lng: 121.0615, confidence: 0.88, barangay: 'Ortigas Center', address: 'ADB Ave near Megamall' },
  { id: '9', type: 'curb_ramp', label: 'Damaged Curb Ramp', lat: 14.5475, lng: 121.0138, confidence: 0.79, barangay: 'Legaspi Village', address: 'Legaspi St cor. Dela Rosa' },
  { id: '10', type: 'pothole', label: 'Pothole Cluster', lat: 14.5730, lng: 121.0589, confidence: 0.94, barangay: 'Kapitolyo', address: 'Kapitolyo Rd near United St' },
  { id: '11', type: 'obstruction', label: 'Construction Barrier', lat: 14.5321, lng: 121.0448, confidence: 0.81, barangay: 'BGC', address: '7th Ave cor. 32nd St' },
  { id: '12', type: 'pothole', label: 'Pothole', lat: 14.5643, lng: 121.0150, confidence: 0.77, barangay: 'Bangkal', address: 'Chino Roces Ave' },
  { id: '13', type: 'missing_sign', label: 'Missing Speed Limit', lat: 14.5500, lng: 121.0400, confidence: 0.82, barangay: 'Pinagkaisahan', address: 'Buendia Ave Extension' },
  { id: '14', type: 'curb_ramp', label: 'No Wheelchair Ramp', lat: 14.5565, lng: 121.0315, confidence: 0.90, barangay: 'Salcedo Village', address: 'Valero St near Salcedo Park' },
  { id: '15', type: 'obstruction', label: 'Parked Vehicle on Sidewalk', lat: 14.5395, lng: 121.0530, confidence: 0.86, barangay: 'Fort Bonifacio', address: 'Burgos Circle, BGC' },
];

type LayerKey = 'pothole' | 'obstruction' | 'missing_sign' | 'curb_ramp';

const TYPE_LABELS: Record<string, string> = {
  pothole: 'Potholes',
  obstruction: 'Obstructions',
  missing_sign: 'Missing Signs',
  curb_ramp: 'Curb Ramps',
};

const TYPE_COLORS: Record<string, string> = {
  pothole: '#ef4444',
  obstruction: '#f59e0b',
  missing_sign: '#8b5cf6',
  curb_ramp: '#3b82f6',
};

export default function DashboardPage() {
  const [layers, setLayers] = useState<Record<LayerKey, boolean>>({
    pothole: true,
    obstruction: true,
    missing_sign: true,
    curb_ramp: true,
  });

  const visible = MOCK_DETECTIONS.filter((d) => layers[d.type]);

  const toggleLayer = (key: LayerKey) => {
    setLayers((prev) => ({ ...prev, [key]: !prev[key] }));
  };

  return (
    <div className="h-full flex flex-col">
      <header className="border-b border-border px-6 py-4 flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-semibold">Map Overview</h1>
          <p className="text-sm text-muted-foreground">
            Walkability detections across Metro Manila &middot; {visible.length} active detections
          </p>
        </div>
        <div className="flex items-center gap-2 text-xs">
          <span className="px-2 py-1 rounded bg-green-500/10 text-green-600 font-medium">Live</span>
          <span className="px-2 py-1 rounded bg-blue-500/10 text-blue-600 font-medium">{visible.length} Detections</span>
        </div>
      </header>

      <div className="flex-1 relative overflow-hidden">
        <MapView detections={visible} />

        {/* Layer controls */}
        <div className="absolute top-4 right-4 z-[1000] bg-white/95 backdrop-blur rounded-lg shadow-lg border border-border p-3 space-y-2 w-48">
          <p className="text-xs font-semibold text-muted-foreground uppercase tracking-wider">Layers</p>
          {(Object.keys(TYPE_LABELS) as LayerKey[]).map((key) => (
            <label key={key} className="flex items-center gap-2 text-sm cursor-pointer">
              <input
                type="checkbox"
                checked={layers[key]}
                onChange={() => toggleLayer(key)}
                className="rounded border-gray-300"
              />
              <span
                className="w-2.5 h-2.5 rounded-full"
                style={{ backgroundColor: TYPE_COLORS[key] }}
              />
              {TYPE_LABELS[key]}
            </label>
          ))}
        </div>
      </div>

      {/* Score legend */}
      <div className="border-t border-border px-6 py-3 flex items-center gap-6 text-sm">
        <span className="font-medium">Walkability Score:</span>
        <span className="flex items-center gap-1.5">
          <span className="w-3 h-3 rounded-full bg-green-500" />
          High (70-100)
        </span>
        <span className="flex items-center gap-1.5">
          <span className="w-3 h-3 rounded-full bg-yellow-500" />
          Medium (40-69)
        </span>
        <span className="flex items-center gap-1.5">
          <span className="w-3 h-3 rounded-full bg-red-500" />
          Low (0-39)
        </span>
      </div>
    </div>
  );
}
