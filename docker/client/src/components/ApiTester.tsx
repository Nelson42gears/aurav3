import React, { useState } from 'react';
import { useHealthCheck, useTools, useCallTool } from '../hooks/useApi';
import type { ToolCallRequest } from '../lib/api';

export const ApiTester: React.FC = () => {
  const [selectedTool, setSelectedTool] = useState<string>('');
  const [toolParams, setToolParams] = useState<string>('{}');
  const [testResults, setTestResults] = useState<any[]>([]);

  const { data: healthData, isLoading: healthLoading, error: healthError } = useHealthCheck();
  const { data: toolsData, isLoading: toolsLoading, error: toolsError } = useTools();
  const callToolMutation = useCallTool();

  const addTestResult = (test: string, result: any, success: boolean) => {
    const newResult = {
      id: Date.now(),
      test,
      result,
      success,
      timestamp: new Date().toISOString(),
    };
    setTestResults(prev => [newResult, ...prev.slice(0, 9)]); // Keep last 10 results
  };

  const handleToolCall = async () => {
    if (!selectedTool) return;

    try {
      const params = JSON.parse(toolParams);
      const request: ToolCallRequest = {
        tool_name: selectedTool,
        parameters: params,
      };

      const result = await callToolMutation.mutateAsync(request);
      addTestResult(`Tool Call: ${selectedTool}`, result, result.success);
    } catch (error) {
      addTestResult(`Tool Call: ${selectedTool}`, { error: error instanceof Error ? error.message : 'Unknown error' }, false);
    }
  };

  const testBackendConnection = async () => {
    try {
      const response = await fetch('/api/health');
      const data = await response.json();
      addTestResult('Backend Connection', { status: response.status, data }, response.ok);
    } catch (error) {
      addTestResult('Backend Connection', { error: error instanceof Error ? error.message : 'Unknown error' }, false);
    }
  };

  return (
    <div className="p-6 max-w-4xl mx-auto">
      <h1 className="text-3xl font-bold mb-6">Backend API Tester</h1>

      {/* Health Check Section */}
      <div className="mb-8 p-4 border rounded-lg">
        <h2 className="text-xl font-semibold mb-4">Health Check</h2>
        {healthLoading && <div className="text-blue-600">Loading health status...</div>}
        {healthError && <div className="text-red-600">Health check failed: {healthError.message}</div>}
        {healthData && (
          <div className={`p-3 rounded ${healthData.success ? 'bg-green-100 text-green-800' : 'bg-red-100 text-red-800'}`}>
            <div className="font-medium">Status: {healthData.success ? 'Healthy' : 'Unhealthy'}</div>
            {healthData.data && (
              <pre className="mt-2 text-sm overflow-auto">
                {JSON.stringify(healthData.data, null, 2)}
              </pre>
            )}
          </div>
        )}
        <button
          onClick={testBackendConnection}
          className="mt-3 px-4 py-2 bg-blue-500 text-white rounded hover:bg-blue-600"
        >
          Test Direct Connection
        </button>
      </div>

      {/* Tools Section */}
      <div className="mb-8 p-4 border rounded-lg">
        <h2 className="text-xl font-semibold mb-4">Available Tools</h2>
        {toolsLoading && <div className="text-blue-600">Loading tools...</div>}
        {toolsError && <div className="text-red-600">Failed to load tools: {toolsError.message}</div>}
        {toolsData && (
          <div>
            <div className="mb-4">
              <span className="font-medium">
                Total Tools: {toolsData.success ? (toolsData.data?.length || 0) : 'N/A'}
              </span>
            </div>
            {toolsData.success && toolsData.data && (
              <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-2 max-h-40 overflow-auto">
                {toolsData.data.slice(0, 20).map((tool: any, index: number) => (
                  <div key={index} className="p-2 bg-gray-100 rounded text-sm">
                    {typeof tool === 'string' ? tool : tool.name || JSON.stringify(tool)}
                  </div>
                ))}
                {toolsData.data.length > 20 && (
                  <div className="p-2 text-gray-500 text-sm">
                    ... and {toolsData.data.length - 20} more
                  </div>
                )}
              </div>
            )}
          </div>
        )}
      </div>

      {/* Tool Call Section */}
      <div className="mb-8 p-4 border rounded-lg">
        <h2 className="text-xl font-semibold mb-4">Test Tool Call</h2>
        <div className="space-y-4">
          <div>
            <label className="block text-sm font-medium mb-1">Tool Name:</label>
            <input
              type="text"
              value={selectedTool}
              onChange={(e) => setSelectedTool(e.target.value)}
              placeholder="e.g., freshdesk_get_tickets"
              className="w-full p-2 border rounded"
            />
          </div>
          <div>
            <label className="block text-sm font-medium mb-1">Parameters (JSON):</label>
            <textarea
              value={toolParams}
              onChange={(e) => setToolParams(e.target.value)}
              placeholder='{"limit": 5}'
              className="w-full p-2 border rounded h-20"
            />
          </div>
          <button
            onClick={handleToolCall}
            disabled={!selectedTool || callToolMutation.isPending}
            className="px-4 py-2 bg-green-500 text-white rounded hover:bg-green-600 disabled:bg-gray-400"
          >
            {callToolMutation.isPending ? 'Calling...' : 'Call Tool'}
          </button>
        </div>
      </div>

      {/* Test Results Section */}
      <div className="p-4 border rounded-lg">
        <h2 className="text-xl font-semibold mb-4">Test Results</h2>
        {testResults.length === 0 ? (
          <div className="text-gray-500">No test results yet</div>
        ) : (
          <div className="space-y-3 max-h-96 overflow-auto">
            {testResults.map((result) => (
              <div
                key={result.id}
                className={`p-3 rounded border-l-4 ${
                  result.success ? 'border-green-500 bg-green-50' : 'border-red-500 bg-red-50'
                }`}
              >
                <div className="flex justify-between items-start mb-2">
                  <span className="font-medium">{result.test}</span>
                  <span className="text-xs text-gray-500">
                    {new Date(result.timestamp).toLocaleTimeString()}
                  </span>
                </div>
                <pre className="text-sm overflow-auto max-h-32 bg-white p-2 rounded">
                  {JSON.stringify(result.result, null, 2)}
                </pre>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
};
