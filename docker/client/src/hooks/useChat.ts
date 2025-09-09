import { useState, useCallback, useRef } from 'react';
import { apiClient } from '../lib/api';
import type { ChatMessage } from '../components/ChatInterface';

export interface ChatState {
  messages: ChatMessage[];
  isLoading: boolean;
  error: string | null;
}

export interface ChatActions {
  sendMessage: (content: string) => Promise<void>;
  addMessage: (message: Omit<ChatMessage, 'id' | 'timestamp'>) => string;
  updateMessage: (id: string, updates: Partial<ChatMessage>) => void;
  clearMessages: () => void;
  retryLastMessage: () => Promise<void>;
}

export const useChat = (): ChatState & ChatActions => {
  const [messages, setMessages] = useState<ChatMessage[]>([
    {
      id: '1',
      type: 'system',
      content: 'Welcome to Aura! I can help you with natural language queries using 196 MCP tools across Freshdesk, Intercom, and more.',
      timestamp: new Date(),
    }
  ]);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [conversationId, setConversationId] = useState<string | null>(null);
  
  const lastUserMessageRef = useRef<string>('');

  const addMessage = useCallback((message: Omit<ChatMessage, 'id' | 'timestamp'>): string => {
    const newMessage: ChatMessage = {
      ...message,
      id: Date.now().toString() + Math.random().toString(36).substr(2, 9),
      timestamp: new Date(),
    };
    setMessages(prev => [...prev, newMessage]);
    return newMessage.id;
  }, []);

  const updateMessage = useCallback((id: string, updates: Partial<ChatMessage>) => {
    setMessages(prev => prev.map(msg => 
      msg.id === id ? { ...msg, ...updates } : msg
    ));
  }, []);

  const clearMessages = useCallback(() => {
    setMessages([{
      id: '1',
      type: 'system',
      content: 'Chat cleared. How can I help you?',
      timestamp: new Date(),
    }]);
    setError(null);
    setConversationId(null);
  }, []);

  const sendMessage = useCallback(async (content: string): Promise<void> => {
    if (!content.trim() || isLoading) return;

    const userMessage = content.trim();
    lastUserMessageRef.current = userMessage;
    setIsLoading(true);
    setError(null);

    // Add user message
    addMessage({
      type: 'user',
      content: userMessage,
    });

    try {
      // Call Gemini chat API
      const response = await apiClient.sendChatMessage({
        message: userMessage,
        conversation_id: conversationId || undefined,
      });

      if (response.success && response.data) {
        // Set conversation ID if this is a new conversation
        if (!conversationId && response.data.conversation_id) {
          setConversationId(response.data.conversation_id);
        }

        // Add assistant response
        addMessage({
          type: 'assistant',
          content: response.data.response,
          toolCall: response.data.tool_calls && response.data.tool_calls.length > 0 
            ? {
                name: response.data.tool_calls[0].name || 'unknown',
                parameters: response.data.tool_calls[0].parameters || {},
                result: response.data.tool_calls[0].result,
              }
            : undefined,
        });
      } else {
        setError(response.error || 'Failed to get response');
        addMessage({
          type: 'assistant',
          content: `Sorry, I encountered an error: ${response.error || 'Unknown error'}`,
        });
      }
    } catch (error) {
      setError(error instanceof Error ? error.message : 'Unknown error');
      addMessage({
        type: 'assistant',
        content: `Sorry, I encountered an error: ${error instanceof Error ? error.message : 'Unknown error'}`,
      });
    } finally {
      setIsLoading(false);
    }
  }, [isLoading, addMessage, conversationId]);

  const retryLastMessage = useCallback(async (): Promise<void> => {
    if (!lastUserMessageRef.current || isLoading) return;
    await sendMessage(lastUserMessageRef.current);
  }, [sendMessage, isLoading]);

  return {
    messages,
    isLoading,
    error,
    sendMessage,
    addMessage,
    updateMessage,
    clearMessages,
    retryLastMessage,
  };
};
