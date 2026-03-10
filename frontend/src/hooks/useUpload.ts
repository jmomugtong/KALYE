'use client';

import { useState, useCallback } from 'react';
import { uploadImage } from '@/lib/api';

export interface UploadItem {
  id: string;
  fileName: string;
  progress: number;
  status: 'uploading' | 'processing' | 'complete' | 'error';
  error?: string;
  responseId?: string;
}

export function useUpload() {
  const [uploads, setUploads] = useState<UploadItem[]>([]);
  const [isUploading, setIsUploading] = useState(false);

  const updateUpload = useCallback(
    (id: string, updates: Partial<UploadItem>) => {
      setUploads((prev) =>
        prev.map((u) => (u.id === id ? { ...u, ...updates } : u))
      );
    },
    []
  );

  const uploadFiles = useCallback(
    async (files: File[]) => {
      setIsUploading(true);

      const newUploads: UploadItem[] = files.map((file) => ({
        id: `${Date.now()}-${Math.random().toString(36).slice(2)}`,
        fileName: file.name,
        progress: 0,
        status: 'uploading' as const,
      }));

      setUploads((prev) => [...prev, ...newUploads]);

      const promises = files.map(async (file, index) => {
        const uploadItem = newUploads[index];
        try {
          const response = await uploadImage(file, undefined, undefined, (progress) => {
            updateUpload(uploadItem.id, { progress });
          });

          updateUpload(uploadItem.id, {
            status: 'processing',
            progress: 100,
            responseId: response.id,
          });

          // Mark as complete (actual completion would come via WebSocket)
          updateUpload(uploadItem.id, {
            status: 'complete',
          });
        } catch (err) {
          updateUpload(uploadItem.id, {
            status: 'error',
            error: err instanceof Error ? err.message : 'Upload failed',
          });
        }
      });

      await Promise.allSettled(promises);
      setIsUploading(false);
    },
    [updateUpload]
  );

  const clearCompleted = useCallback(() => {
    setUploads((prev) => prev.filter((u) => u.status !== 'complete'));
  }, []);

  const clearAll = useCallback(() => {
    setUploads([]);
  }, []);

  return {
    uploads,
    isUploading,
    uploadFiles,
    clearCompleted,
    clearAll,
  };
}
