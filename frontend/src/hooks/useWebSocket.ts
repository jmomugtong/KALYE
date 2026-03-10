import { useState, useEffect, useRef, useCallback } from 'react';

export type ProcessingStep =
  | 'uploading'
  | 'detecting'
  | 'segmenting'
  | 'captioning'
  | 'complete';

export interface ProcessingUpdate {
  fileId: string;
  step: ProcessingStep;
  progress: number;
  message?: string;
}

export interface UseWebSocketOptions {
  url?: string;
  autoConnect?: boolean;
}

export function useWebSocket(options: UseWebSocketOptions = {}) {
  const {
    url = `${typeof window !== 'undefined' && window.location.protocol === 'https:' ? 'wss' : 'ws'}://${typeof window !== 'undefined' ? window.location.host : 'localhost:8000'}/ws/processing`,
    autoConnect = false,
  } = options;

  const [isConnected, setIsConnected] = useState(false);
  const [updates, setUpdates] = useState<Map<string, ProcessingUpdate>>(new Map());
  const wsRef = useRef<WebSocket | null>(null);
  const reconnectTimeoutRef = useRef<NodeJS.Timeout | null>(null);

  const connect = useCallback(() => {
    if (wsRef.current?.readyState === WebSocket.OPEN) return;

    try {
      const ws = new WebSocket(url);

      ws.onopen = () => {
        setIsConnected(true);
      };

      ws.onmessage = (event) => {
        try {
          const update: ProcessingUpdate = JSON.parse(event.data);
          setUpdates((prev) => {
            const next = new Map(prev);
            next.set(update.fileId, update);
            return next;
          });
        } catch {
          // ignore malformed messages
        }
      };

      ws.onclose = () => {
        setIsConnected(false);
        wsRef.current = null;
        // Auto-reconnect after 3 seconds
        reconnectTimeoutRef.current = setTimeout(() => {
          connect();
        }, 3000);
      };

      ws.onerror = () => {
        ws.close();
      };

      wsRef.current = ws;
    } catch {
      // WebSocket creation can throw in non-browser environments
    }
  }, [url]);

  const disconnect = useCallback(() => {
    if (reconnectTimeoutRef.current) {
      clearTimeout(reconnectTimeoutRef.current);
      reconnectTimeoutRef.current = null;
    }
    wsRef.current?.close();
    wsRef.current = null;
    setIsConnected(false);
  }, []);

  const getUpdate = useCallback(
    (fileId: string): ProcessingUpdate | undefined => updates.get(fileId),
    [updates],
  );

  const clearUpdates = useCallback(() => {
    setUpdates(new Map());
  }, []);

  useEffect(() => {
    if (autoConnect) {
      connect();
    }
    return () => {
      disconnect();
    };
  }, [autoConnect, connect, disconnect]);

  return {
    isConnected,
    updates,
    connect,
    disconnect,
    getUpdate,
    clearUpdates,
  };
}
