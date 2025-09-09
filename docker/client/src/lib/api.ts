// API client for backend proxy communication
const API_BASE_URL = '/api';

export interface ApiResponse<T = any> {
  success: boolean;
  data?: T;
  error?: string;
  message?: string;
}

export interface HealthCheckResponse {
  status: string;
  timestamp: string;
  services: {
    mcp_server: string;
    backend_proxy: string;
  };
}

export interface ToolCallRequest {
  tool_name: string;
  parameters: Record<string, any>;
}

export interface ToolCallResponse {
  result: any;
  success: boolean;
  error?: string;
}

export interface ChatRequest {
  message: string;
  conversation_id?: string;
}

export interface ChatResponse {
  response: string;
  conversation_id: string;
  timestamp: string;
  tool_calls?: any[];
}

export interface ConversationHistory {
  conversation_id: string;
  history: Array<{
    role: string;
    content: string;
    timestamp: string;
    tool_calls?: any[];
  }>;
}

class ApiClient {
  private async request<T>(
    endpoint: string,
    options: RequestInit = {}
  ): Promise<ApiResponse<T>> {
    try {
      const response = await fetch(`${API_BASE_URL}${endpoint}`, {
        headers: {
          'Content-Type': 'application/json',
          ...options.headers,
        },
        ...options,
      });

      const data = await response.json();

      if (!response.ok) {
        return {
          success: false,
          error: data.error || `HTTP ${response.status}`,
          data,
        };
      }

      return {
        success: true,
        data,
      };
    } catch (error) {
      return {
        success: false,
        error: error instanceof Error ? error.message : 'Unknown error',
      };
    }
  }

  // Health check endpoint
  async healthCheck(): Promise<ApiResponse<HealthCheckResponse>> {
    return this.request<HealthCheckResponse>('/health');
  }

  // MCP tools endpoint
  async getTools(): Promise<ApiResponse<any[]>> {
    return this.request<any[]>('/tools');
  }

  // Call MCP tool
  async callTool(request: ToolCallRequest): Promise<ApiResponse<ToolCallResponse>> {
    return this.request<ToolCallResponse>('/call-tool', {
      method: 'POST',
      body: JSON.stringify(request),
    });
  }

  // Freshdesk endpoints
  async freshdeskTickets(params?: Record<string, any>): Promise<ApiResponse<any>> {
    const queryString = params ? `?${new URLSearchParams(params).toString()}` : '';
    return this.request(`/freshdesk/tickets${queryString}`);
  }

  // Chat endpoints
  async sendChatMessage(request: ChatRequest): Promise<ApiResponse<ChatResponse>> {
    return this.request<ChatResponse>('/chat', {
      method: 'POST',
      body: JSON.stringify(request),
    });
  }

  // Stream chat response
  async streamChatResponse(request: ChatRequest): Promise<ReadableStream<Uint8Array> | null> {
    try {
      const response = await fetch(`${API_BASE_URL}/chat/stream`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify(request),
      });

      if (!response.ok) {
        throw new Error(`HTTP ${response.status}`);
      }

      return response.body;
    } catch (error) {
      console.error('Stream chat error:', error);
      return null;
    }
  }

  // Get conversation history
  async getConversationHistory(conversationId: string): Promise<ApiResponse<ConversationHistory>> {
    return this.request<ConversationHistory>(`/conversations/${conversationId}`);
  }

  // List conversations
  async listConversations(): Promise<ApiResponse<{ conversations: string[] }>> {
    return this.request<{ conversations: string[] }>('/conversations');
  }

  // Clear conversation
  async clearConversation(conversationId: string): Promise<ApiResponse<{ message: string }>> {
    return this.request<{ message: string }>(`/conversations/${conversationId}`, {
      method: 'DELETE',
    });
  }

  // Legacy endpoints (keeping for compatibility)
  async intercomConversations(params?: Record<string, any>): Promise<ApiResponse<any>> {
    const queryString = params ? `?${new URLSearchParams(params).toString()}` : '';
    return this.request(`/intercom/conversations${queryString}`);
  }
}

export const apiClient = new ApiClient();
