import { useEffect, useRef, useState, useCallback } from 'react';
import { SSEClient, type SSEMessage, type SSEOptions } from '../lib/sse';

export interface SSEState {
  connectionState: 'connecting' | 'connected' | 'disconnected';
  error: string | null;
  lastMessage: SSEMessage | null;
  messageCount: number;
}

export interface SSEHookOptions extends Omit<SSEOptions, 'onMessage' | 'onError' | 'onOpen' | 'onClose'> {
  autoConnect?: boolean;
  onMessage?: (message: SSEMessage) => void;
  onError?: (error: Event) => void;
  onConnectionChange?: (state: 'connecting' | 'connected' | 'disconnected') => void;
}

export const useSSE = (url: string, options: SSEHookOptions = {}) => {
  const [state, setState] = useState<SSEState>({
    connectionState: 'disconnected',
    error: null,
    lastMessage: null,
    messageCount: 0,
  });

  const clientRef = useRef<SSEClient | null>(null);
  const { autoConnect = false, onMessage, onError, onConnectionChange, ...sseOptions } = options;

  const updateConnectionState = useCallback((connectionState: 'connecting' | 'connected' | 'disconnected') => {
    setState(prev => ({ ...prev, connectionState, error: connectionState === 'connected' ? null : prev.error }));
    onConnectionChange?.(connectionState);
  }, [onConnectionChange]);

  const handleMessage = useCallback((message: SSEMessage) => {
    setState(prev => ({
      ...prev,
      lastMessage: message,
      messageCount: prev.messageCount + 1,
    }));
    onMessage?.(message);
  }, [onMessage]);

  const handleError = useCallback((error: Event) => {
    setState(prev => ({
      ...prev,
      error: 'Connection error occurred',
      connectionState: 'disconnected',
    }));
    onError?.(error);
  }, [onError]);

  const connect = useCallback(() => {
    if (clientRef.current) {
      clientRef.current.disconnect();
    }

    updateConnectionState('connecting');

    clientRef.current = new SSEClient(url, {
      ...sseOptions,
      onMessage: handleMessage,
      onError: handleError,
      onOpen: () => updateConnectionState('connected'),
      onClose: () => updateConnectionState('disconnected'),
    });

    clientRef.current.connect();
  }, [url, sseOptions, handleMessage, handleError, updateConnectionState]);

  const disconnect = useCallback(() => {
    if (clientRef.current) {
      clientRef.current.disconnect();
      clientRef.current = null;
    }
    updateConnectionState('disconnected');
  }, [updateConnectionState]);

  const reconnect = useCallback(() => {
    disconnect();
    setTimeout(connect, 100);
  }, [connect, disconnect]);

  // Auto-connect on mount if enabled
  useEffect(() => {
    if (autoConnect) {
      connect();
    }

    return () => {
      if (clientRef.current) {
        clientRef.current.disconnect();
      }
    };
  }, [autoConnect, connect]);

  // Update connection state periodically
  useEffect(() => {
    const interval = setInterval(() => {
      if (clientRef.current) {
        const currentState = clientRef.current.getConnectionState();
        setState(prev => {
          if (prev.connectionState !== currentState) {
            onConnectionChange?.(currentState);
            return { ...prev, connectionState: currentState };
          }
          return prev;
        });
      }
    }, 1000);

    return () => clearInterval(interval);
  }, [onConnectionChange]);

  return {
    ...state,
    connect,
    disconnect,
    reconnect,
    isConnected: state.connectionState === 'connected',
  };
};
