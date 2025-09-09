// Server-Sent Events (SSE) client for real-time streaming
export interface SSEMessage {
  id?: string;
  event?: string;
  data: string;
  retry?: number;
}

export interface SSEOptions {
  onMessage?: (message: SSEMessage) => void;
  onError?: (error: Event) => void;
  onOpen?: (event: Event) => void;
  onClose?: () => void;
  reconnect?: boolean;
  reconnectInterval?: number;
  maxReconnectAttempts?: number;
}

export class SSEClient {
  private eventSource: EventSource | null = null;
  private url: string;
  private options: SSEOptions;
  private reconnectAttempts = 0;
  private isConnected = false;
  private reconnectTimer: number | null = null;

  constructor(url: string, options: SSEOptions = {}) {
    this.url = url;
    this.options = {
      reconnect: true,
      reconnectInterval: 3000,
      maxReconnectAttempts: 5,
      ...options,
    };
  }

  connect(): void {
    if (this.eventSource) {
      this.disconnect();
    }

    try {
      this.eventSource = new EventSource(this.url);

      this.eventSource.onopen = (event) => {
        this.isConnected = true;
        this.reconnectAttempts = 0;
        this.options.onOpen?.(event);
      };

      this.eventSource.onmessage = (event) => {
        const message: SSEMessage = {
          id: event.lastEventId,
          data: event.data,
        };
        this.options.onMessage?.(message);
      };

      this.eventSource.onerror = (event) => {
        this.isConnected = false;
        this.options.onError?.(event);

        if (this.options.reconnect && this.reconnectAttempts < (this.options.maxReconnectAttempts || 5)) {
          this.scheduleReconnect();
        }
      };

      // Listen for custom events
      this.eventSource.addEventListener('tool-call', (event) => {
        const message: SSEMessage = {
          event: 'tool-call',
          data: (event as MessageEvent).data,
        };
        this.options.onMessage?.(message);
      });

      this.eventSource.addEventListener('error', (event) => {
        const message: SSEMessage = {
          event: 'error',
          data: (event as MessageEvent).data,
        };
        this.options.onMessage?.(message);
      });

    } catch (error) {
      console.error('Failed to create EventSource:', error);
      this.options.onError?.(error as Event);
    }
  }

  private scheduleReconnect(): void {
    if (this.reconnectTimer) {
      clearTimeout(this.reconnectTimer);
    }

    this.reconnectTimer = setTimeout(() => {
      this.reconnectAttempts++;
      console.log(`Attempting to reconnect (${this.reconnectAttempts}/${this.options.maxReconnectAttempts})...`);
      this.connect();
    }, this.options.reconnectInterval);
  }

  disconnect(): void {
    if (this.reconnectTimer) {
      clearTimeout(this.reconnectTimer);
      this.reconnectTimer = null;
    }

    if (this.eventSource) {
      this.eventSource.close();
      this.eventSource = null;
    }

    this.isConnected = false;
    this.options.onClose?.();
  }

  getConnectionState(): 'connecting' | 'connected' | 'disconnected' {
    if (!this.eventSource) return 'disconnected';
    
    switch (this.eventSource.readyState) {
      case EventSource.CONNECTING:
        return 'connecting';
      case EventSource.OPEN:
        return 'connected';
      case EventSource.CLOSED:
        return 'disconnected';
      default:
        return 'disconnected';
    }
  }

  isConnectionOpen(): boolean {
    return this.isConnected && this.eventSource?.readyState === EventSource.OPEN;
  }
}
