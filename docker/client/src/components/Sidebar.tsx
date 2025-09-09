import React, { useState } from 'react';
import { SSEStatus } from './SSEStatus';
import clsx from 'clsx';

interface SidebarProps {
  currentView: 'chat' | 'tester';
  onViewChange: (view: 'chat' | 'tester') => void;
  onNewChat: () => void;
  chatHistory?: ChatHistoryItem[];
}

interface ChatHistoryItem {
  id: string;
  title: string;
  timestamp: Date;
  isActive?: boolean;
}

export const Sidebar: React.FC<SidebarProps> = ({ 
  currentView, 
  onViewChange, 
  onNewChat,
  chatHistory = []
}) => {
  const [isCollapsed, setIsCollapsed] = useState(false);

  const formatDate = (date: Date) => {
    const now = new Date();
    const diffTime = Math.abs(now.getTime() - date.getTime());
    const diffDays = Math.ceil(diffTime / (1000 * 60 * 60 * 24));
    
    if (diffDays === 1) return 'Yesterday';
    if (diffDays <= 7) return `${diffDays} days ago`;
    return date.toLocaleDateString();
  };

  return (
    <div className={clsx(
      'bg-gray-50 border-r border-gray-200 flex flex-col transition-all duration-300 h-full',
      isCollapsed ? 'w-16' : 'w-64'
    )}>
      {/* Collapse Button */}
      <div className="p-4 border-b border-gray-200 flex justify-end">
        <button
          onClick={() => setIsCollapsed(!isCollapsed)}
          className="p-1.5 hover:bg-gray-200 rounded-lg"
        >
          <svg className="w-5 h-5 text-gray-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} 
              d={isCollapsed ? "M9 5l7 7-7 7" : "M15 19l-7-7 7-7"} />
          </svg>
        </button>
      </div>

      {/* New Chat Button */}
      <div className="p-4">
        <button
          onClick={onNewChat}
          className={clsx(
            'w-full bg-blue-500 hover:bg-blue-600 text-white rounded-lg transition-colors flex items-center justify-center gap-2',
            isCollapsed ? 'p-2' : 'px-4 py-2.5'
          )}
        >
          <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 4v16m8-8H4" />
          </svg>
          {!isCollapsed && <span>New Chat</span>}
        </button>
      </div>

      {/* Navigation */}
      {!isCollapsed && (
        <div className="px-4 mb-4">
          <div className="bg-white rounded-lg p-1 border border-gray-200">
            <button
              onClick={() => onViewChange('chat')}
              className={clsx(
                'w-full px-3 py-2 rounded-md text-sm font-medium transition-colors',
                currentView === 'chat'
                  ? 'bg-blue-50 text-blue-600'
                  : 'text-gray-600 hover:bg-gray-100'
              )}
            >
              Chat
            </button>
            <button
              onClick={() => onViewChange('tester')}
              className={clsx(
                'w-full px-3 py-2 rounded-md text-sm font-medium transition-colors',
                currentView === 'tester'
                  ? 'bg-blue-50 text-blue-600'
                  : 'text-gray-600 hover:bg-gray-100'
              )}
            >
              API Tester
            </button>
          </div>
        </div>
      )}

      {/* Chat History */}
      {!isCollapsed && chatHistory.length > 0 && (
        <div className="flex-1 overflow-y-auto">
          <div className="px-4 py-2">
            <h3 className="text-xs font-medium text-gray-500 uppercase tracking-wider mb-2">
              Recent Chats
            </h3>
          </div>
          <div className="px-2">
            {chatHistory.map((chat) => (
              <button
                key={chat.id}
                className={clsx(
                  "w-full text-left p-2 rounded-lg text-sm transition-colors mb-1",
                  chat.isActive ? 'bg-blue-50 text-blue-600' : 'text-gray-700 hover:bg-gray-100'
                )}
              >
                <div className="flex items-center justify-between">
                  <span className="truncate">{chat.title}</span>
                  <span className="text-xs text-gray-400 ml-2 whitespace-nowrap">
                    {formatDate(chat.timestamp)}
                  </span>
                </div>
              </button>
            ))}
          </div>
        </div>
      )}

      {/* Footer */}
      <div className="p-4 border-t border-gray-200">
        <div className="flex items-center space-x-3">
          <div className="w-8 h-8 bg-blue-100 rounded-full flex items-center justify-center">
            <span className="text-sm font-medium text-blue-600">A</span>
          </div>
          {!isCollapsed && (
            <div className="flex-1 min-w-0">
              <p className="text-sm font-medium text-gray-900">Aura</p>
              <SSEStatus className="text-xs text-gray-500" />
            </div>
          )}
        </div>
      </div>
    </div>
  );
};
