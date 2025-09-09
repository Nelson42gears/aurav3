import React, { useState } from 'react';
import { ChatInterface } from './ChatInterface';
import { ApiTester } from './ApiTester';
import { Sidebar } from './Sidebar';

type ViewMode = 'chat' | 'tester';

export const Layout: React.FC = () => {
  const [currentView, setCurrentView] = useState<ViewMode>('chat');

  const handleNewChat = () => {
    setCurrentView('chat');
  };

  return (
    <div className="h-screen flex flex-col bg-gray-50">
      {/* Top Header */}
      <header className="bg-white border-b border-gray-200 h-16 flex items-center px-6">
        <h1 className="text-xl font-semibold text-gray-800">Aura</h1>
      </header>

      <div className="flex flex-1 overflow-hidden">
        {/* Left Sidebar */}
        <Sidebar 
          currentView={currentView}
          onViewChange={setCurrentView}
          onNewChat={handleNewChat}
        />

        {/* Main Content Area */}
        <main className="flex-1 flex flex-col overflow-hidden bg-white">
          <div className="flex-1 overflow-y-auto">
            {currentView === 'chat' && <ChatInterface />}
            {currentView === 'tester' && <ApiTester />}
          </div>
        </main>
      </div>
    </div>
  );
};
