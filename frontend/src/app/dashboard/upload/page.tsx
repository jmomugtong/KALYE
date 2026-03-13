'use client';

import dynamic from 'next/dynamic';
import { useState, useCallback, type DragEvent, type ChangeEvent } from 'react';
import { uploadImage } from '@/lib/api';

const LocationPicker = dynamic(() => import('@/components/Map/LocationPicker'), {
  ssr: false,
  loading: () => <div className="h-48 bg-muted rounded-md animate-pulse" />,
});

interface UploadItem {
  id: string;
  fileName: string;
  status: 'pending' | 'uploading' | 'complete' | 'error';
  progress: number;
  error?: string;
  detectionsCreated?: number;
  aiCaption?: string;
  sidewalkCoverage?: number;
  inferenceSource?: string;
}

export default function UploadPage() {
  const [isDragOver, setIsDragOver] = useState(false);
  const [uploads, setUploads] = useState<UploadItem[]>([]);
  const [lat, setLat] = useState<number | null>(null);
  const [lng, setLng] = useState<number | null>(null);
  const [useCurrentLocation, setUseCurrentLocation] = useState(false);

  const handleGetLocation = useCallback(() => {
    if (!navigator.geolocation) return;
    setUseCurrentLocation(true);
    navigator.geolocation.getCurrentPosition(
      (pos) => {
        setLat(pos.coords.latitude);
        setLng(pos.coords.longitude);
      },
      () => setUseCurrentLocation(false)
    );
  }, []);

  const doUpload = useCallback(async (files: File[]) => {
    if (lat === null || lng === null) {
      alert('Please set a location first — use GPS or click on the map.');
      return;
    }

    for (const file of files) {
      const id = Math.random().toString(36).slice(2);
      const item: UploadItem = { id, fileName: file.name, status: 'uploading', progress: 0 };

      setUploads((prev) => [...prev, item]);

      try {
        const result = await uploadImage(file, lat, lng, (progress) => {
          setUploads((prev) =>
            prev.map((u) => (u.id === id ? { ...u, progress } : u))
          );
        });

        setUploads((prev) =>
          prev.map((u) =>
            u.id === id
              ? {
                  ...u,
                  status: 'complete',
                  progress: 100,
                  detectionsCreated: result.detections_created,
                  aiCaption: result.ai_caption,
                  sidewalkCoverage: result.sidewalk_coverage_pct,
                  inferenceSource: result.inference_source,
                }
              : u
          )
        );
      } catch (err) {
        setUploads((prev) =>
          prev.map((u) =>
            u.id === id
              ? { ...u, status: 'error', error: err instanceof Error ? err.message : 'Upload failed' }
              : u
          )
        );
      }
    }
  }, [lat, lng]);

  const handleDragOver = useCallback((e: DragEvent) => {
    e.preventDefault();
    setIsDragOver(true);
  }, []);

  const handleDragLeave = useCallback((e: DragEvent) => {
    e.preventDefault();
    setIsDragOver(false);
  }, []);

  const handleDrop = useCallback((e: DragEvent) => {
    e.preventDefault();
    setIsDragOver(false);
    const files = Array.from(e.dataTransfer.files).filter((f) => f.type.startsWith('image/'));
    if (files.length > 0) doUpload(files);
  }, [doUpload]);

  const handleFileSelect = useCallback((e: ChangeEvent<HTMLInputElement>) => {
    const files = e.target.files ? Array.from(e.target.files) : [];
    if (files.length > 0) doUpload(files);
  }, [doUpload]);

  return (
    <div className="p-6 max-w-4xl mx-auto space-y-6">
      <header>
        <h1 className="text-2xl font-semibold">Upload Street Imagery</h1>
        <p className="text-sm text-muted-foreground mt-1">
          Upload photos for AI-powered walkability analysis. Set the location first, then upload.
        </p>
      </header>

      {/* Step 1: Location */}
      <div className="rounded-lg border border-border bg-card p-5 space-y-3">
        <div className="flex items-center justify-between">
          <div>
            <h2 className="text-base font-medium">1. Set Location</h2>
            <p className="text-xs text-muted-foreground">Click on the map or use GPS</p>
          </div>
          <button
            onClick={handleGetLocation}
            className="px-3 py-1.5 rounded-md border border-input text-sm hover:bg-accent transition-colors"
          >
            {useCurrentLocation ? 'Updating...' : 'Use My GPS'}
          </button>
        </div>

        <div className="h-56 rounded-md overflow-hidden border border-border">
          <LocationPicker
            lat={lat}
            lng={lng}
            onChange={(newLat, newLng) => { setLat(newLat); setLng(newLng); }}
          />
        </div>

        {lat !== null && lng !== null && (
          <p className="text-xs text-green-600 font-medium">
            Location set: {lat.toFixed(6)}, {lng.toFixed(6)}
          </p>
        )}
      </div>

      {/* Step 2: Upload */}
      <div className="rounded-lg border border-border bg-card p-5 space-y-3">
        <h2 className="text-base font-medium">2. Upload Photos</h2>

        <div
          onDragOver={handleDragOver}
          onDragLeave={handleDragLeave}
          onDrop={handleDrop}
          className={`border-2 border-dashed rounded-lg p-10 text-center transition-colors ${
            isDragOver
              ? 'border-primary bg-primary/5'
              : lat === null
              ? 'border-border opacity-50 cursor-not-allowed'
              : 'border-border hover:border-primary/50'
          }`}
        >
          <div className="space-y-3">
            <div className="w-12 h-12 rounded-full bg-primary/10 flex items-center justify-center mx-auto">
              <svg className="w-6 h-6 text-primary" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2}
                  d="M4 16l4.586-4.586a2 2 0 012.828 0L16 16m-2-2l1.586-1.586a2 2 0 012.828 0L20 14m-6-6h.01M6 20h12a2 2 0 002-2V6a2 2 0 00-2-2H6a2 2 0 00-2 2v12a2 2 0 002 2z" />
              </svg>
            </div>
            <p className="text-base font-medium">
              {lat === null ? 'Set location first (Step 1)' : 'Drag and drop images here, or click to browse'}
            </p>
            <p className="text-sm text-muted-foreground">JPEG, PNG, WebP. Max 10MB per file.</p>
            {lat !== null && (
              <label className="inline-flex items-center justify-center rounded-md bg-primary px-6 py-2 text-sm font-medium text-primary-foreground shadow hover:bg-primary/90 cursor-pointer transition-colors">
                Select Files
                <input
                  type="file"
                  accept="image/*"
                  multiple
                  onChange={handleFileSelect}
                  className="sr-only"
                />
              </label>
            )}
          </div>
        </div>
      </div>

      {/* Upload results */}
      {uploads.length > 0 && (
        <div className="space-y-3">
          <h2 className="text-lg font-medium">Results</h2>
          {uploads.map((upload) => (
            <div key={upload.id} className="flex items-center gap-4 rounded-md border border-border p-4">
              <div className="flex-1 min-w-0">
                <p className="text-sm font-medium truncate">{upload.fileName}</p>
                <p className="text-xs text-muted-foreground">
                  {upload.status === 'uploading' && `${upload.progress}% uploaded`}
                  {upload.status === 'complete' && (
                    <span className="text-green-600">
                      {upload.detectionsCreated || 0} issue(s) detected
                      {upload.inferenceSource === 'claude_vision' ? ' ✦ Claude Vision AI' :
                       upload.inferenceSource === 'local_cpu' ? ' · Local CPU AI' :
                       upload.inferenceSource === 'colab_t4_gpu' ? ' · Colab T4 GPU' :
                       ' · Simulated'}
                    </span>
                  )}
                  {upload.status === 'error' && (
                    <span className="text-destructive">{upload.error}</span>
                  )}
                </p>
                {upload.status === 'complete' && upload.aiCaption && (
                  <p className="text-xs text-blue-600 mt-0.5">AI: {upload.aiCaption}</p>
                )}
                {upload.status === 'complete' && upload.sidewalkCoverage !== undefined && upload.sidewalkCoverage !== null && (
                  <p className="text-xs text-muted-foreground mt-0.5">Sidewalk coverage: {upload.sidewalkCoverage}%</p>
                )}
              </div>
              <div className="w-32">
                <div className="h-2 rounded-full bg-muted overflow-hidden">
                  <div
                    className={`h-full rounded-full transition-all ${
                      upload.status === 'error'
                        ? 'bg-destructive'
                        : upload.status === 'complete'
                        ? 'bg-green-500'
                        : 'bg-primary'
                    }`}
                    style={{ width: `${upload.progress}%` }}
                  />
                </div>
              </div>
            </div>
          ))}

          <p className="text-xs text-muted-foreground">
            Detections appear on the{' '}
            <a href="/explore" className="text-primary hover:underline" target="_blank" rel="noopener">
              public map
            </a>{' '}
            immediately after upload.
          </p>
        </div>
      )}
    </div>
  );
}
