'use client';

import React, { useEffect, useState } from 'react';
import type { FileStatus } from '@/hooks/useUpload';
import type { GPSCoordinates } from '@/lib/exif-extractor';
import { extractGPS } from '@/lib/exif-extractor';

export interface FilePreviewProps {
  file: File;
  fileId: string;
  status: FileStatus;
  progress: number;
  error?: string;
  onRemove: (fileId: string) => void;
}

function formatFileSize(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

const statusConfig: Record<FileStatus, { label: string; color: string }> = {
  pending: { label: 'Pending', color: 'bg-gray-400' },
  uploading: { label: 'Uploading', color: 'bg-blue-500' },
  processing: { label: 'Processing', color: 'bg-yellow-500' },
  complete: { label: 'Complete', color: 'bg-green-500' },
  error: { label: 'Error', color: 'bg-red-500' },
};

export default function FilePreview({
  file,
  fileId,
  status,
  progress,
  error,
  onRemove,
}: FilePreviewProps) {
  const [previewUrl, setPreviewUrl] = useState<string | null>(null);
  const [gps, setGps] = useState<GPSCoordinates | null>(null);

  useEffect(() => {
    const url = URL.createObjectURL(file);
    setPreviewUrl(url);
    return () => URL.revokeObjectURL(url);
  }, [file]);

  useEffect(() => {
    extractGPS(file).then(setGps).catch(() => setGps(null));
  }, [file]);

  const { label, color } = statusConfig[status];

  return (
    <div
      data-testid={`file-preview-${fileId}`}
      className="relative flex items-center gap-3 rounded-lg border border-gray-200 bg-white p-3 shadow-sm"
    >
      {/* Thumbnail */}
      <div className="h-16 w-16 flex-shrink-0 overflow-hidden rounded-md bg-gray-100">
        {previewUrl && (
          <img
            src={previewUrl}
            alt={file.name}
            className="h-full w-full object-cover"
          />
        )}
      </div>

      {/* Info */}
      <div className="min-w-0 flex-1">
        <p className="truncate text-sm font-medium text-gray-900">{file.name}</p>
        <p className="text-xs text-gray-500">{formatFileSize(file.size)}</p>
        {gps && (
          <p className="text-xs text-gray-400">
            GPS: {gps.lat.toFixed(5)}, {gps.lng.toFixed(5)}
          </p>
        )}
        {error && <p className="text-xs text-red-600">{error}</p>}

        {/* Progress bar during upload */}
        {status === 'uploading' && (
          <div className="mt-1 h-1.5 w-full overflow-hidden rounded-full bg-gray-200">
            <div
              className="h-full rounded-full bg-blue-500 transition-all duration-200"
              style={{ width: `${progress}%` }}
            />
          </div>
        )}
      </div>

      {/* Status indicator */}
      <div className="flex items-center gap-2">
        <span className="flex items-center gap-1 text-xs text-gray-500">
          <span className={`inline-block h-2 w-2 rounded-full ${color}`} />
          {label}
        </span>

        {/* Remove button */}
        <button
          type="button"
          data-testid={`remove-${fileId}`}
          onClick={() => onRemove(fileId)}
          disabled={status === 'uploading'}
          className="flex h-6 w-6 items-center justify-center rounded-full text-gray-400 transition hover:bg-gray-100 hover:text-gray-600 disabled:cursor-not-allowed disabled:opacity-50"
          aria-label={`Remove ${file.name}`}
        >
          <svg
            xmlns="http://www.w3.org/2000/svg"
            width="14"
            height="14"
            viewBox="0 0 24 24"
            fill="none"
            stroke="currentColor"
            strokeWidth="2"
            strokeLinecap="round"
            strokeLinejoin="round"
          >
            <line x1="18" y1="6" x2="6" y2="18" />
            <line x1="6" y1="6" x2="18" y2="18" />
          </svg>
        </button>
      </div>
    </div>
  );
}
