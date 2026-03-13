'use client';

import dynamic from 'next/dynamic';
import Link from 'next/link';
import { useEffect, useState } from 'react';
import { apiClient } from '@/lib/api';

const PublicMap = dynamic(() => import('@/components/Map/PublicMap'), {
  ssr: false,
  loading: () => (
    <div className="absolute inset-0 flex items-center justify-center bg-muted">
      <p className="text-sm text-muted-foreground">Loading map...</p>
    </div>
  ),
});

export interface PublicDetection {
  detection_id: string;
  image_id: string;
  detection_type: string;
  confidence_score: number;
  latitude: number;
  longitude: number;
  caption: string | null;
  created_at: string;
}

const TYPE_LABELS: Record<string, string> = {
  pothole: 'Potholes',
  sidewalk_obstruction: 'Obstructions',
  missing_sign: 'Missing Signs',
  curb_ramp: 'Curb Ramps',
  broken_sidewalk: 'Broken Sidewalk',
  flooding: 'Flooding',
  missing_ramp: 'Missing Ramp',
};

const TYPE_COLORS: Record<string, string> = {
  pothole: '#ef4444',
  sidewalk_obstruction: '#f59e0b',
  missing_sign: '#8b5cf6',
  curb_ramp: '#3b82f6',
  broken_sidewalk: '#f97316',
  flooding: '#06b6d4',
  missing_ramp: '#ec4899',
};

export default function ExplorePage() {
  const [detections, setDetections] = useState<PublicDetection[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // Active layer filters
  const [activeLayers, setActiveLayers] = useState<Set<string>>(new Set(Object.keys(TYPE_LABELS)));

  useEffect(() => {
    async function fetchDetections() {
      try {
        const res = await apiClient.get('/api/v1/detections/', { params: { limit: 500 } });
        setDetections(res.data.detections);
      } catch (err) {
        setError('Could not load detections');
        console.error(err);
      } finally {
        setLoading(false);
      }
    }
    fetchDetections();
  }, []);

  const toggleLayer = (type: string) => {
    setActiveLayers((prev) => {
      const next = new Set(prev);
      if (next.has(type)) next.delete(type);
      else next.add(type);
      return next;
    });
  };

  const visible = detections.filter((d) => activeLayers.has(d.detection_type));

  // Count by type
  const counts: Record<string, number> = {};
  for (const d of detections) {
    counts[d.detection_type] = (counts[d.detection_type] || 0) + 1;
  }

  return (
    <div className="h-screen flex flex-col">
      {/* Top bar */}
      <header className="border-b border-border px-6 py-3 flex items-center justify-between bg-white">
        <div className="flex items-center gap-4">
          <Link href="/" className="text-2xl font-bold text-primary">KALYE</Link>
          <span className="text-sm text-muted-foreground hidden sm:inline">
            Community Walkability Map
          </span>
        </div>
        <div className="flex items-center gap-3 text-sm">
          <span className="text-muted-foreground">
            {loading ? 'Loading...' : `${detections.length} reports`}
          </span>
          <Link
            href="/login"
            className="px-3 py-1.5 rounded-md bg-primary text-primary-foreground text-xs font-medium hover:bg-primary/90 transition-colors"
          >
            Contribute
          </Link>
        </div>
      </header>

      <div className="flex-1 relative overflow-hidden">
        {error ? (
          <div className="absolute inset-0 flex items-center justify-center bg-muted">
            <div className="text-center space-y-2">
              <p className="text-sm text-destructive">{error}</p>
              <p className="text-xs text-muted-foreground">Make sure the API is running on port 8002</p>
            </div>
          </div>
        ) : (
          <PublicMap detections={visible} />
        )}

        {/* Layer filter panel */}
        <div className="absolute top-4 right-4 z-[1000] bg-white/95 backdrop-blur rounded-lg shadow-lg border border-border p-4 space-y-2 w-52">
          <p className="text-xs font-semibold text-muted-foreground uppercase tracking-wider mb-2">
            Filter Issues
          </p>
          {Object.entries(TYPE_LABELS).map(([key, label]) => (
            <label key={key} className="flex items-center gap-2 text-sm cursor-pointer">
              <input
                type="checkbox"
                checked={activeLayers.has(key)}
                onChange={() => toggleLayer(key)}
                className="rounded border-gray-300"
              />
              <span
                className="w-2.5 h-2.5 rounded-full flex-shrink-0"
                style={{ backgroundColor: TYPE_COLORS[key] }}
              />
              <span className="flex-1">{label}</span>
              <span className="text-xs text-muted-foreground">{counts[key] || 0}</span>
            </label>
          ))}
        </div>

        {/* Info box */}
        <div className="absolute bottom-4 left-4 z-[1000] bg-white/95 backdrop-blur rounded-lg shadow-lg border border-border p-4 max-w-xs">
          <p className="text-sm font-semibold mb-1">How it works</p>
          <p className="text-xs text-muted-foreground leading-relaxed">
            Community members upload street photos with GPS location.
            AI analyzes each image to detect potholes, obstructions,
            missing signs, and accessibility issues. Results appear
            here in real time.
          </p>
        </div>
      </div>
    </div>
  );
}
