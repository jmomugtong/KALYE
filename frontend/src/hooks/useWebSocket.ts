'use client';

import { useEffect, useRef, useCallback, useState } from 'react';
import { WebSocketClient } from '@/lib/websocket';
import { useAuth } from '@/hooks/useAuth';

interface UseWebSocketOptions {
  imageId: string | null;
  onMessage?: (data: unknown) => void;
  onError?: (error: Event) => void;
  autoConnect?: boolean;
}

interface UseWebSocketReturn {
  isConnected: boolean;
  connect: () => void;
  disconnect: () => void;
}

export function useWebSocket({
  imageId,
  onMessage,
  onError,
  autoConnect = true,
}: UseWebSocketOptions): UseWebSocketReturn {
  const { tokens } = useAuth();
  const wsClientRef = useRef<WebSocketClient | null>(null);
  const [isConnected, setIsConnected] = useState(false);

  const connect = useCallback(() => {
    if (!imageId || !tokens?.accessToken) return;

    if (!wsClientRef.current) {
      wsClientRef.current = new WebSocketClient();
    }

    wsClientRef.current.connect(imageId, tokens.accessToken);
    setIsConnected(true);
  }, [imageId, tokens?.accessToken]);

  const disconnect = useCallback(() => {
    wsClientRef.current?.disconnect();
    setIsConnected(false);
  }, []);

  useEffect(() => {
    if (!autoConnect || !imageId || !tokens?.accessToken) return;

    const client = new WebSocketClient();
    wsClientRef.current = client;

    client.connect(imageId, tokens.accessToken);
    setIsConnected(true);

    const unsubMessage = onMessage ? client.onMessage(onMessage) : undefined;
    const unsubError = onError ? client.onError(onError) : undefined;

    return () => {
      unsubMessage?.();
      unsubError?.();
      client.disconnect();
      setIsConnected(false);
    };
  }, [imageId, tokens?.accessToken, autoConnect, onMessage, onError]);

  return {
    isConnected,
    connect,
    disconnect,
  };
}
