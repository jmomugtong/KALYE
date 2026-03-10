'use client';

import React from 'react';
import type { UploadFileState } from '@/src/hooks/useUpload';
import { useWebSocket, type ProcessingStep } from '@/src/hooks/useWebSocket';

export interface UploadProgressProps {
  files: UploadFileState[];
  overallProgress: number;
  wsUrl?: string;
}

const STEP_LABELS: Record<ProcessingStep, string> = {
  uploading: 'Uploading',
  detecting: 'Detecting objects',
  segmenting: 'Segmenting surfaces',
  captioning: 'Generating captions',
  complete: 'Complete',
};

const STEP_ORDER: ProcessingStep[] = [
  'uploading',
  'detecting',
  'segmenting',
  'captioning',
  'complete',
];

function StepIndicator({ currentStep }: { currentStep: ProcessingStep }) {
  const currentIndex = STEP_ORDER.indexOf(currentStep);

  return (
    <div className="flex items-center gap-1">
      {STEP_ORDER.map((step, index) => {
        let stepClass = 'bg-gray-300';
        if (index < currentIndex) stepClass = 'bg-green-500';
        else if (index === currentIndex) stepClass = 'bg-blue-500';

        return (
          <div key={step} className="flex items-center gap-1">
            <div
              className={`h-2.5 w-2.5 rounded-full ${stepClass}`}
              title={STEP_LABELS[step]}
            />
            {index < STEP_ORDER.length - 1 && (
              <div
                className={`h-0.5 w-4 ${
                  index < currentIndex ? 'bg-green-500' : 'bg-gray-300'
                }`}
              />
            )}
          </div>
        );
      })}
    </div>
  );
}

export default function UploadProgress({
  files,
  overallProgress,
  wsUrl,
}: UploadProgressProps) {
  const { isConnected, getUpdate } = useWebSocket({
    url: wsUrl,
    autoConnect: files.some((f) => f.status === 'uploading' || f.status === 'complete'),
  });

  if (files.length === 0) return null;

  return (
    <div data-testid="upload-progress" className="space-y-4 rounded-lg border border-gray-200 bg-white p-4">
      {/* Overall progress */}
      <div>
        <div className="mb-1 flex items-center justify-between text-sm">
          <span className="font-medium text-gray-700">Overall Progress</span>
          <span className="text-gray-500">{overallProgress}%</span>
        </div>
        <div className="h-2.5 w-full overflow-hidden rounded-full bg-gray-200">
          <div
            className="h-full rounded-full bg-blue-600 transition-all duration-300"
            style={{ width: `${overallProgress}%` }}
          />
        </div>
      </div>

      {/* WebSocket connection indicator */}
      <div className="flex items-center gap-1.5 text-xs text-gray-400">
        <span
          className={`inline-block h-1.5 w-1.5 rounded-full ${
            isConnected ? 'bg-green-500' : 'bg-gray-400'
          }`}
        />
        {isConnected ? 'Live updates connected' : 'Waiting for connection'}
      </div>

      {/* Per-file progress */}
      <div className="space-y-3">
        {files.map((fileState) => {
          const wsUpdate = getUpdate(fileState.id);
          const currentStep: ProcessingStep =
            wsUpdate?.step ?? (fileState.status === 'uploading' ? 'uploading' : 'uploading');

          return (
            <div key={fileState.id} className="space-y-1">
              <div className="flex items-center justify-between text-xs">
                <span className="max-w-[200px] truncate font-medium text-gray-600">
                  {fileState.file.name}
                </span>
                <span className="text-gray-400">
                  {wsUpdate ? STEP_LABELS[wsUpdate.step] : STEP_LABELS[currentStep]}
                </span>
              </div>

              {/* File progress bar */}
              <div className="h-1.5 w-full overflow-hidden rounded-full bg-gray-200">
                <div
                  className={`h-full rounded-full transition-all duration-200 ${
                    fileState.status === 'error' ? 'bg-red-500' : 'bg-blue-500'
                  }`}
                  style={{ width: `${wsUpdate?.progress ?? fileState.progress}%` }}
                />
              </div>

              {/* Step indicator when ws data available */}
              {wsUpdate && <StepIndicator currentStep={wsUpdate.step} />}

              {/* Error message */}
              {fileState.error && (
                <p className="text-xs text-red-600">{fileState.error}</p>
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
}
