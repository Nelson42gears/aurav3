import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { apiClient, type ToolCallRequest } from '../lib/api';
import { queryKeys } from '../lib/queryClient';

// Health check hook
export const useHealthCheck = () => {
  return useQuery({
    queryKey: queryKeys.health,
    queryFn: () => apiClient.healthCheck(),
    refetchInterval: 30000, // Refetch every 30 seconds
    retry: 3,
  });
};

// Tools list hook
export const useTools = () => {
  return useQuery({
    queryKey: queryKeys.tools,
    queryFn: () => apiClient.getTools(),
    staleTime: 5 * 60 * 1000, // 5 minutes
  });
};

// Tool call mutation
export const useCallTool = () => {
  const queryClient = useQueryClient();
  
  return useMutation({
    mutationFn: (request: ToolCallRequest) => apiClient.callTool(request),
    onSuccess: () => {
      // Invalidate and refetch any related queries if needed
      queryClient.invalidateQueries({ queryKey: queryKeys.tools });
    },
  });
};

// Freshdesk tickets hook
export const useFreshdeskTickets = (params?: Record<string, any>) => {
  return useQuery({
    queryKey: queryKeys.freshdesk.tickets(params),
    queryFn: () => apiClient.freshdeskTickets(params),
    enabled: !!params, // Only run when params are provided
  });
};

// Intercom conversations hook
export const useIntercomConversations = (params?: Record<string, any>) => {
  return useQuery({
    queryKey: queryKeys.intercom.conversations(params),
    queryFn: () => apiClient.intercomConversations(params),
    enabled: !!params, // Only run when params are provided
  });
};
