import React from 'react';
import { useSSE } from '../hooks/useSSE';
import clsx from 'clsx';

interface SSEStatusProps {
  className?: string;
}

export const SSEStatus: React.FC<SSEStatusProps> = ({ className }) => {
  const { connectionState, messageCount } = useSSE('/api/sse', {
    autoConnect: true,
    onMessage: (message) => {
      console.log('SSE Message:', message);
    },
    onError: (error) => {
      console.error('SSE Error:', error);
    },
  });

  const getStatusColor = () => {
    switch (connectionState) {
      case 'connected': return 'bg-green-500';
      case 'connecting': return 'bg-yellow-500';
      case 'disconnected': 
      default: 
        return 'bg-red-500';
    }
  };

  const getStatusText = () => {
    switch (connectionState) {
      case 'connected': return 'Connected';
      case 'connecting': return 'Connecting...';
      case 'disconnected': return 'Disconnected';
      default: return 'Unknown';
    }
  };

  return (
    <div className={clsx('flex items-center space-x-2', className)}>
      <div className="flex items-center space-x-1.5">
        <div className={clsx('w-2 h-2 rounded-full', getStatusColor())} />
        <span className="text-xs">{getStatusText()}</span>
      </div>
      {messageCount > 0 && (
        <span className="text-xs bg-blue-100 text-blue-700 px-1.5 py-0.5 rounded">
          {messageCount}
        </span>
      )}
    </div>
  );
};
