import { useState, useCallback, useRef } from 'react';
import axios, { AxiosProgressEvent, CancelTokenSource } from 'axios';

export type FileStatus = 'pending' | 'uploading' | 'complete' | 'error';

export interface UploadFileState {
  file: File;
  id: string;
  progress: number;
  status: FileStatus;
  error?: string;
}

export interface UseUploadOptions {
  endpoint?: string;
  onComplete?: (fileId: string) => void;
  onError?: (fileId: string, error: string) => void;
  onAllComplete?: () => void;
}

export function useUpload(options: UseUploadOptions = {}) {
  const {
    endpoint = '/api/v1/images/upload',
    onComplete,
    onError,
    onAllComplete,
  } = options;

  const [files, setFiles] = useState<UploadFileState[]>([]);
  const [isUploading, setIsUploading] = useState(false);
  const cancelTokensRef = useRef<Map<string, CancelTokenSource>>(new Map());

  const addFiles = useCallback((newFiles: File[]) => {
    const fileStates: UploadFileState[] = newFiles.map((file) => ({
      file,
      id: `${file.name}-${Date.now()}-${Math.random().toString(36).slice(2, 9)}`,
      progress: 0,
      status: 'pending' as FileStatus,
    }));
    setFiles((prev) => [...prev, ...fileStates]);
    return fileStates;
  }, []);

  const removeFile = useCallback((fileId: string) => {
    const cancelToken = cancelTokensRef.current.get(fileId);
    if (cancelToken) {
      cancelToken.cancel('Upload cancelled by user');
      cancelTokensRef.current.delete(fileId);
    }
    setFiles((prev) => prev.filter((f) => f.id !== fileId));
  }, []);

  const clearFiles = useCallback(() => {
    cancelTokensRef.current.forEach((token) => token.cancel('Cleared'));
    cancelTokensRef.current.clear();
    setFiles([]);
  }, []);

  const updateFileState = useCallback(
    (fileId: string, update: Partial<UploadFileState>) => {
      setFiles((prev) =>
        prev.map((f) => (f.id === fileId ? { ...f, ...update } : f)),
      );
    },
    [],
  );

  const uploadSingleFile = useCallback(
    async (fileState: UploadFileState, location?: { lat: number; lng: number }) => {
      const cancelSource = axios.CancelToken.source();
      cancelTokensRef.current.set(fileState.id, cancelSource);

      updateFileState(fileState.id, { status: 'uploading', progress: 0 });

      const formData = new FormData();
      formData.append('file', fileState.file);
      if (location) {
        formData.append('latitude', String(location.lat));
        formData.append('longitude', String(location.lng));
      }

      try {
        await axios.post(endpoint, formData, {
          cancelToken: cancelSource.token,
          headers: { 'Content-Type': 'multipart/form-data' },
          onUploadProgress: (event: AxiosProgressEvent) => {
            if (event.total) {
              const pct = Math.round((event.loaded * 100) / event.total);
              updateFileState(fileState.id, { progress: pct });
            }
          },
        });

        updateFileState(fileState.id, { status: 'complete', progress: 100 });
        onComplete?.(fileState.id);
      } catch (err: unknown) {
        if (axios.isCancel(err)) return;
        const message =
          err instanceof Error ? err.message : 'Upload failed';
        updateFileState(fileState.id, { status: 'error', error: message });
        onError?.(fileState.id, message);
      } finally {
        cancelTokensRef.current.delete(fileState.id);
      }
    },
    [endpoint, updateFileState, onComplete, onError],
  );

  const uploadFiles = useCallback(
    async (location?: { lat: number; lng: number }) => {
      const pending = files.filter((f) => f.status === 'pending');
      if (pending.length === 0) return;

      setIsUploading(true);
      try {
        await Promise.all(pending.map((f) => uploadSingleFile(f, location)));
        onAllComplete?.();
      } finally {
        setIsUploading(false);
      }
    },
    [files, uploadSingleFile, onAllComplete],
  );

  const overallProgress = files.length === 0
    ? 0
    : Math.round(files.reduce((sum, f) => sum + f.progress, 0) / files.length);

  return {
    files,
    isUploading,
    overallProgress,
    addFiles,
    removeFile,
    clearFiles,
    uploadFiles,
  };
}
