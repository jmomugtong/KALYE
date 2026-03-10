'use client';

import { useState, useCallback, type DragEvent, type ChangeEvent } from 'react';
import { useUpload } from '@/hooks/useUpload';

export default function UploadPage() {
  const [isDragOver, setIsDragOver] = useState(false);
  const { uploadFiles, uploads, isUploading } = useUpload();

  const handleDragOver = useCallback((e: DragEvent) => {
    e.preventDefault();
    setIsDragOver(true);
  }, []);

  const handleDragLeave = useCallback((e: DragEvent) => {
    e.preventDefault();
    setIsDragOver(false);
  }, []);

  const handleDrop = useCallback(
    (e: DragEvent) => {
      e.preventDefault();
      setIsDragOver(false);
      const files = Array.from(e.dataTransfer.files).filter((f) =>
        f.type.startsWith('image/')
      );
      if (files.length > 0) {
        uploadFiles(files);
      }
    },
    [uploadFiles]
  );

  const handleFileSelect = useCallback(
    (e: ChangeEvent<HTMLInputElement>) => {
      const files = e.target.files ? Array.from(e.target.files) : [];
      if (files.length > 0) {
        uploadFiles(files);
      }
    },
    [uploadFiles]
  );

  return (
    <div className="p-6 max-w-4xl mx-auto space-y-6">
      <header>
        <h1 className="text-2xl font-semibold">Upload Street Imagery</h1>
        <p className="text-sm text-muted-foreground mt-1">
          Upload photos for AI-powered walkability analysis
        </p>
      </header>

      {/* Drop zone */}
      <div
        onDragOver={handleDragOver}
        onDragLeave={handleDragLeave}
        onDrop={handleDrop}
        className={`border-2 border-dashed rounded-lg p-12 text-center transition-colors ${
          isDragOver
            ? 'border-primary bg-primary/5'
            : 'border-border hover:border-primary/50'
        }`}
      >
        <div className="space-y-4">
          <div className="w-12 h-12 rounded-full bg-primary/10 flex items-center justify-center mx-auto">
            <svg
              className="w-6 h-6 text-primary"
              fill="none"
              stroke="currentColor"
              viewBox="0 0 24 24"
            >
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                strokeWidth={2}
                d="M4 16l4.586-4.586a2 2 0 012.828 0L16 16m-2-2l1.586-1.586a2 2 0 012.828 0L20 14m-6-6h.01M6 20h12a2 2 0 002-2V6a2 2 0 00-2-2H6a2 2 0 00-2 2v12a2 2 0 002 2z"
              />
            </svg>
          </div>
          <div>
            <p className="text-lg font-medium">
              Drag and drop images here, or click to browse
            </p>
            <p className="text-sm text-muted-foreground mt-1">
              Supports JPEG, PNG, WebP. Max 10MB per file.
            </p>
          </div>
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
        </div>
      </div>

      {/* Upload progress */}
      {uploads.length > 0 && (
        <div className="space-y-3">
          <h2 className="text-lg font-medium">Uploads</h2>
          {uploads.map((upload) => (
            <div
              key={upload.id}
              className="flex items-center gap-4 rounded-md border border-border p-4"
            >
              <div className="flex-1 min-w-0">
                <p className="text-sm font-medium truncate">{upload.fileName}</p>
                <p className="text-xs text-muted-foreground">
                  {upload.status === 'uploading' && `${upload.progress}% uploaded`}
                  {upload.status === 'processing' && 'Processing with AI...'}
                  {upload.status === 'complete' && 'Analysis complete'}
                  {upload.status === 'error' && upload.error}
                </p>
              </div>
              <div className="w-32">
                <div className="h-2 rounded-full bg-muted overflow-hidden">
                  <div
                    className={`h-full rounded-full transition-all ${
                      upload.status === 'error'
                        ? 'bg-destructive'
                        : upload.status === 'complete'
                        ? 'bg-score-high'
                        : 'bg-primary'
                    }`}
                    style={{ width: `${upload.progress}%` }}
                  />
                </div>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
