type MessageCallback = (data: unknown) => void;
type ErrorCallback = (error: Event) => void;

export class WebSocketClient {
  private ws: WebSocket | null = null;
  private messageCallbacks: MessageCallback[] = [];
  private errorCallbacks: ErrorCallback[] = [];
  private reconnectAttempts = 0;
  private maxReconnectAttempts = 5;
  private reconnectDelay = 1000;
  private imageId: string | null = null;
  private token: string | null = null;

  connect(imageId: string, token: string): void {
    this.imageId = imageId;
    this.token = token;
    this.reconnectAttempts = 0;
    this.establishConnection();
  }

  private establishConnection(): void {
    if (!this.imageId || !this.token) return;

    const wsUrl = process.env.NEXT_PUBLIC_WS_URL || 'ws://localhost:8000';
    this.ws = new WebSocket(
      `${wsUrl}/ws/detections/${this.imageId}?token=${this.token}`
    );

    this.ws.onopen = () => {
      this.reconnectAttempts = 0;
    };

    this.ws.onmessage = (event: MessageEvent) => {
      try {
        const data = JSON.parse(event.data as string);
        this.messageCallbacks.forEach((cb) => cb(data));
      } catch {
        this.messageCallbacks.forEach((cb) => cb(event.data));
      }
    };

    this.ws.onerror = (event: Event) => {
      this.errorCallbacks.forEach((cb) => cb(event));
    };

    this.ws.onclose = () => {
      if (this.reconnectAttempts < this.maxReconnectAttempts) {
        this.reconnectAttempts++;
        const delay = this.reconnectDelay * Math.pow(2, this.reconnectAttempts - 1);
        setTimeout(() => this.establishConnection(), delay);
      }
    };
  }

  disconnect(): void {
    if (this.ws) {
      this.ws.close();
      this.ws = null;
    }
    this.messageCallbacks = [];
    this.errorCallbacks = [];
    this.imageId = null;
    this.token = null;
    this.reconnectAttempts = this.maxReconnectAttempts; // prevent reconnect
  }

  onMessage(callback: MessageCallback): () => void {
    this.messageCallbacks.push(callback);
    return () => {
      this.messageCallbacks = this.messageCallbacks.filter(
        (cb) => cb !== callback
      );
    };
  }

  onError(callback: ErrorCallback): () => void {
    this.errorCallbacks.push(callback);
    return () => {
      this.errorCallbacks = this.errorCallbacks.filter(
        (cb) => cb !== callback
      );
    };
  }

  get isConnected(): boolean {
    return this.ws?.readyState === WebSocket.OPEN;
  }
}

// Singleton instance
export const wsClient = new WebSocketClient();
