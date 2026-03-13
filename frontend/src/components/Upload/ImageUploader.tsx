// @ts-nocheck
'use client';

import React, { useState, useCallback, useMemo } from 'react';
import { useDropzone, type FileRejection } from 'react-dropzone';
import { useUpload } from '@/hooks/useUpload';
import FilePreview from './FilePreview';
import UploadProgress from './UploadProgress';

const ACCEPTED_TYPES: Record<string, string[]> = {
  'image/jpeg': ['.jpg', '.jpeg'],
  'image/png': ['.png'],
};
const MAX_FILE_SIZE = 10 * 1024 * 1024; // 10 MB
const MAX_FILES = 10;

export type UploaderVisualState = 'idle' | 'dragging' | 'uploading' | 'complete' | 'error';

export default function ImageUploader() {
  const [errors, setErrors] = useState<string[]>([]);
  const {
    files,
    isUploading,
    overallProgress,
    addFiles,
    removeFile,
    uploadFiles,
  } = useUpload({
    onAllComplete: () => {
      setErrors([]);
    },
  });

  const onDrop = useCallback(
    (accepted: File[], rejected: FileRejection[]) => {
      setErrors([]);

      const currentCount = files.length;
      if (currentCount + accepted.length > MAX_FILES) {
        setErrors([`Maximum ${MAX_FILES} files allowed. You already have ${currentCount}.`]);
        return;
      }

      if (rejected.length > 0) {
        const rejectionErrors = rejected.map((r) => {
          const reasons = r.errors.map((e) => {
            if (e.code === 'file-too-large') return `${r.file.name}: exceeds 10 MB limit`;
            if (e.code === 'file-invalid-type') return `${r.file.name}: only JPEG and PNG allowed`;
            return `${r.file.name}: ${e.message}`;
          });
          return reasons.join('; ');
        });
        setErrors(rejectionErrors);
      }

      if (accepted.length > 0) {
        addFiles(accepted);
      }
    },
    [files.length, addFiles],
  );

  const { getRootProps, getInputProps, isDragActive } = useDropzone({
    onDrop,
    accept: ACCEPTED_TYPES,
    maxSize: MAX_FILE_SIZE,
    maxFiles: MAX_FILES,
    disabled: isUploading,
  });

  const visualState: UploaderVisualState = useMemo(() => {
    if (isDragActive) return 'dragging';
    if (isUploading) return 'uploading';
    if (errors.length > 0) return 'error';
    if (files.length > 0 && files.every((f) => f.status === 'complete')) return 'complete';
    return 'idle';
  }, [isDragActive, isUploading, errors, files]);

  const dropzoneClasses = useMemo(() => {
    const base =
      'relative flex flex-col items-center justify-center rounded-lg border-2 border-dashed p-8 text-center transition-colors cursor-pointer';
    switch (visualState) {
      case 'dragging':
        return `${base} border-blue-400 bg-blue-50`;
      case 'uploading':
        return `${base} border-gray-300 bg-gray-50 cursor-not-allowed`;
      case 'complete':
        return `${base} border-green-400 bg-green-50`;
      case 'error':
        return `${base} border-red-400 bg-red-50`;
      default:
        return `${base} border-gray-300 bg-white hover:border-gray-400 hover:bg-gray-50`;
    }
  }, [visualState]);

  const handleUploadClick = useCallback(() => {
    if (!isUploading && files.some((f) => f.status === 'pending')) {
      uploadFiles();
    }
  }, [isUploading, files, uploadFiles]);

  const hasPending = files.some((f) => f.status === 'pending');

  return (
    <div data-testid="image-uploader" className="mx-auto max-w-2xl space-y-4">
      {/* Drop zone */}
      <div {...getRootProps()} className={dropzoneClasses} data-testid="drop-zone">
        <input {...getInputProps()} data-testid="file-input" />

        <svg
          xmlns="http://www.w3.org/2000/svg"
          width="40"
          height="40"
          viewBox="0 0 24 24"
          fill="none"
          stroke="currentColor"
          strokeWidth="1.5"
          strokeLinecap="round"
          strokeLinejoin="round"
          className="mb-3 text-gray-400"
        >
          <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4" />
          <polyline points="17 8 12 3 7 8" />
          <line x1="12" y1="3" x2="12" y2="15" />
        </svg>

        {isDragActive ? (
          <p className="text-sm font-medium text-blue-600">Drop images here...</p>
        ) : (
          <>
            <p className="text-sm font-medium text-gray-700">
              Drag &amp; drop street images here, or click to browse
            </p>
            <p className="mt-1 text-xs text-gray-500">
              JPEG or PNG, up to 10 MB each, max {MAX_FILES} files
            </p>
          </>
        )}
      </div>

      {/* Errors */}
      {errors.length > 0 && (
        <div data-testid="upload-errors" className="rounded-md bg-red-50 p-3">
          {errors.map((err, i) => (
            <p key={i} className="text-sm text-red-700">
              {err}
            </p>
          ))}
        </div>
      )}

      {/* File previews */}
      {files.length > 0 && (
        <div data-testid="file-previews" className="space-y-2">
          {files.map((f) => (
            <FilePreview
              key={f.id}
              file={f.file}
              fileId={f.id}
              status={f.status}
              progress={f.progress}
              error={f.error}
              onRemove={removeFile}
            />
          ))}
        </div>
      )}

      {/* Upload progress */}
      {isUploading && (
        <UploadProgress files={files} overallProgress={overallProgress} />
      )}

      {/* Upload button */}
      {files.length > 0 && (
        <button
          type="button"
          data-testid="upload-button"
          onClick={handleUploadClick}
          disabled={isUploading || !hasPending}
          className="w-full rounded-lg bg-blue-600 px-4 py-2.5 text-sm font-semibold text-white shadow-sm transition hover:bg-blue-700 disabled:cursor-not-allowed disabled:opacity-50"
        >
          {isUploading
            ? `Uploading... ${overallProgress}%`
            : files.every((f) => f.status === 'complete')
              ? 'All uploads complete'
              : `Upload ${files.filter((f) => f.status === 'pending').length} file(s)`}
        </button>
      )}
    </div>
  );
}
