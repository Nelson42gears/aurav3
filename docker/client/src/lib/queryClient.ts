import { QueryClient } from '@tanstack/react-query';

export const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      staleTime: 1000 * 60 * 5, // 5 minutes
      gcTime: 1000 * 60 * 10, // 10 minutes (formerly cacheTime)
      retry: (failureCount, error: any) => {
        // Don't retry on 4xx errors
        if (error?.status >= 400 && error?.status < 500) {
          return false;
        }
        // Retry up to 3 times for other errors
        return failureCount < 3;
      },
      retryDelay: (attemptIndex) => Math.min(1000 * 2 ** attemptIndex, 30000),
    },
    mutations: {
      retry: 1,
      onError: (error) => {
        console.error('Mutation error:', error);
      },
    },
  },
});

// Query keys factory for consistent key management
export const queryKeys = {
  health: ['health'] as const,
  tools: ['tools'] as const,
  freshdesk: {
    all: ['freshdesk'] as const,
    tickets: (params?: Record<string, any>) => ['freshdesk', 'tickets', params] as const,
    ticket: (id: string) => ['freshdesk', 'ticket', id] as const,
  },
  intercom: {
    all: ['intercom'] as const,
    conversations: (params?: Record<string, any>) => ['intercom', 'conversations', params] as const,
    conversation: (id: string) => ['intercom', 'conversation', id] as const,
  },
  toolCall: (toolName: string, params: Record<string, any>) => 
    ['tool-call', toolName, params] as const,
} as const;
