#!/usr/bin/env python3
"""
Standard MCP Server for n8n Workflow Automation Integration
Implements official MCP protocol with JSON-RPC over stdio transport
"""

import asyncio
import logging
import os
import sys
import json
from typing import Any, Dict, List, Optional
import httpx

# Add shared MCP base to path
sys.path.append('/app/shared/mcp-base')
from mcp_server_base import MCPServerBase, MCPTool, MCPResource

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class N8nClient:
    """Standard n8n API client for MCP server"""
    
    def __init__(self, base_url: str, api_key: str = ""):
        self.base_url = base_url.rstrip('/')
        self.api_key = api_key
        
    async def _make_request(self, method: str, endpoint: str, **kwargs) -> Dict[str, Any]:
        """Make authenticated request to n8n API"""
        url = f"{self.base_url}/api/v1{endpoint}"
        
        headers = {"Content-Type": "application/json"}
        if self.api_key:
            headers["X-N8N-API-KEY"] = self.api_key
        
        async with httpx.AsyncClient() as client:
            response = await client.request(
                method=method,
                url=url,
                headers=headers,
                **kwargs
            )
            response.raise_for_status()
            return response.json() if response.content else {}
    
    async def list_workflows(self, active: Optional[bool] = None) -> List[Dict[str, Any]]:
        """List workflows"""
        params = {}
        if active is not None:
            params["active"] = str(active).lower()
            
        try:
            result = await self._make_request("GET", "/workflows", params=params)
            return result.get("data", []) if isinstance(result, dict) else result
        except Exception as e:
            logger.error(f"Error listing workflows: {e}")
            return []
    
    async def get_workflow(self, workflow_id: str) -> Dict[str, Any]:
        """Get workflow details by ID"""
        try:
            return await self._make_request("GET", f"/workflows/{workflow_id}")
        except Exception as e:
            logger.error(f"Error getting workflow {workflow_id}: {e}")
            raise
    
    async def execute_workflow(self, workflow_id: str, input_data: Optional[Dict] = None) -> Dict[str, Any]:
        """Execute a workflow"""
        data = {}
        if input_data:
            data = input_data
            
        try:
            return await self._make_request("POST", f"/workflows/{workflow_id}/execute", json=data)
        except Exception as e:
            logger.error(f"Error executing workflow {workflow_id}: {e}")
            raise
    
    async def get_executions(self, workflow_id: Optional[str] = None, limit: int = 20) -> List[Dict[str, Any]]:
        """Get workflow executions"""
        params = {"limit": min(limit, 100)}
        if workflow_id:
            params["workflowId"] = workflow_id
            
        try:
            result = await self._make_request("GET", "/executions", params=params)
            return result.get("data", []) if isinstance(result, dict) else result
        except Exception as e:
            logger.error(f"Error getting executions: {e}")
            return []
    
    async def get_execution(self, execution_id: str) -> Dict[str, Any]:
        """Get execution details by ID"""
        try:
            return await self._make_request("GET", f"/executions/{execution_id}")
        except Exception as e:
            logger.error(f"Error getting execution {execution_id}: {e}")
            raise
    
    async def activate_workflow(self, workflow_id: str) -> Dict[str, Any]:
        """Activate a workflow"""
        try:
            return await self._make_request("POST", f"/workflows/{workflow_id}/activate")
        except Exception as e:
            logger.error(f"Error activating workflow {workflow_id}: {e}")
            raise
    
    async def deactivate_workflow(self, workflow_id: str) -> Dict[str, Any]:
        """Deactivate a workflow"""
        try:
            return await self._make_request("POST", f"/workflows/{workflow_id}/deactivate")
        except Exception as e:
            logger.error(f"Error deactivating workflow {workflow_id}: {e}")
            raise

class N8nMcpServer(MCPServerBase):
    """Production n8n MCP Server"""

    def __init__(self):
        super().__init__(
            name="n8n MCP Server",
            port=int(os.getenv("N8N_MCP_PORT", 3001))
        )
        self.n8n_client = None

    async def initialize_server(self):
        """Initialize n8n MCP server"""
        base_url = os.getenv("N8N_BASE_URL", "http://localhost:5678")
        api_key = os.getenv("N8N_API_KEY", "")
        self.n8n_client = N8nClient(base_url, api_key)
        logger.info(f"n8n client initialized for URL: {base_url}")

        await self._register_tools()
        await self._register_resources()

        logger.info("n8n MCP server initialized successfully")

    async def _register_tools(self):
        """Register n8n MCP tools"""
        tools_to_register = [
            (MCPTool(name="list_workflows", title="List n8n Workflows", description="List n8n workflows with optional filters", inputSchema={"type": "object", "properties": {"active_only": {"type": "boolean", "description": "If true, only return active workflows"}}}), self._tool_list_workflows),
            (MCPTool(name="get_workflow_details", title="Get Workflow Details", description="Get detailed information about a specific workflow", inputSchema={"type": "object", "properties": {"workflow_id": {"type": "string", "description": "The n8n workflow ID"}}, "required": ["workflow_id"]}), self._tool_get_workflow_details),
            (MCPTool(name="execute_workflow", title="Execute Workflow", description="Execute an n8n workflow", inputSchema={"type": "object", "properties": {"workflow_id": {"type": "string", "description": "The n8n workflow ID to execute"}, "input_data": {"type": "string", "description": "JSON string of input data for the workflow", "default": "{}"}}, "required": ["workflow_id"]}), self._tool_execute_workflow),
            (MCPTool(name="get_workflow_executions", title="Get Workflow Executions", description="Get recent workflow executions", inputSchema={"type": "object", "properties": {"workflow_id": {"type": "string", "description": "Optional specific workflow ID to filter by"}, "limit": {"type": "integer", "description": "Number of executions to retrieve (max 50)", "default": 10}}}), self._tool_get_workflow_executions),
            (MCPTool(name="get_execution_details", title="Get Execution Details", description="Get detailed information about a specific execution", inputSchema={"type": "object", "properties": {"execution_id": {"type": "string", "description": "The n8n execution ID"}}, "required": ["execution_id"]}), self._tool_get_execution_details),
            (MCPTool(name="activate_workflow", title="Activate Workflow", description="Activate an n8n workflow", inputSchema={"type": "object", "properties": {"workflow_id": {"type": "string", "description": "The n8n workflow ID to activate"}}, "required": ["workflow_id"]}), self._tool_activate_workflow),
            (MCPTool(name="deactivate_workflow", title="Deactivate Workflow", description="Deactivate an n8n workflow", inputSchema={"type": "object", "properties": {"workflow_id": {"type": "string", "description": "The n8n workflow ID to deactivate"}}, "required": ["workflow_id"]}), self._tool_deactivate_workflow),
        ]
        for tool, handler in tools_to_register:
            self.register_tool(tool, handler)

    async def _register_resources(self):
        """Register n8n MCP resources"""
        resources_to_register = [
            (MCPResource(uri="n8n://workflows", name="workflows_overview", title="n8n Workflows Overview", description="Overview of n8n workflows", mimeType="application/json"), self._resource_workflows_overview),
            (MCPResource(uri="n8n://status", name="connection_status", title="n8n Connection Status", description="Current n8n connection status", mimeType="application/json"), self._resource_connection_status),
        ]
        for resource, handler in resources_to_register:
            self.register_resource(resource, handler)

    # Tool implementations
    async def _tool_list_workflows(self, arguments: Dict[str, Any]) -> str:
        if not self.n8n_client: return "Error: n8n client not initialized."
        try:
            active_only = arguments.get("active_only", False)
            workflows = await self.n8n_client.list_workflows(active=active_only if active_only else None)
            if not workflows: return "No workflows found in n8n."
            results = [f"{'🟢 Active' if w.get('active') else '⚪ Inactive'} {w.get('name', 'Unnamed')} (ID: {w.get('id')}) - Updated: {w.get('updatedAt', 'Unknown')}" for w in workflows]
            return f"Found {len(workflows)} workflows:\n" + "\n".join(results)
        except Exception as e:
            logger.error(f"Error in list_workflows tool: {e}")
            return f"Error listing workflows: {str(e)}"

    async def _tool_get_workflow_details(self, arguments: Dict[str, Any]) -> str:
        if not self.n8n_client: return "Error: n8n client not initialized."
        try:
            workflow_id = arguments["workflow_id"]
            workflow = await self.n8n_client.get_workflow(workflow_id)
            status = "🟢 Active" if workflow.get("active") else "⚪ Inactive"
            return (f"Workflow Details for ID: {workflow_id}\n"
                    f"📝 Name: {workflow.get('name', 'Unnamed')}\n"
                    f"{status} Status: {'Active' if workflow.get('active') else 'Inactive'}\n"
                    f"🔗 Nodes: {len(workflow.get('nodes', []))}\n"
                    f"🔄 Connections: {len(workflow.get('connections', {}))}\n"
                    f"📅 Created: {workflow.get('createdAt', 'Unknown')}\n"
                    f"🔄 Updated: {workflow.get('updatedAt', 'Unknown')}\n"
                    f"🏷️ Tags: {', '.join(workflow.get('tags', []))}")
        except Exception as e:
            logger.error(f"Error in get_workflow_details tool: {e}")
            return f"Error getting workflow details: {str(e)}"

    async def _tool_execute_workflow(self, arguments: Dict[str, Any]) -> str:
        if not self.n8n_client: return "Error: n8n client not initialized."
        try:
            workflow_id = arguments["workflow_id"]
            input_data_str = arguments.get("input_data", "{}")
            data = json.loads(input_data_str) if input_data_str != "{}" else None
            result = await self.n8n_client.execute_workflow(workflow_id, data)
            return (f"🚀 Workflow executed successfully!\n"
                    f"Workflow ID: {workflow_id}\n"
                    f"Execution ID: {result.get('executionId', 'Unknown')}\n"
                    f"Status: {result.get('status', 'Unknown')}\n"
                    f"Started: {result.get('startedAt', 'Unknown')}")
        except Exception as e:
            logger.error(f"Error in execute_workflow tool: {e}")
            return f"Error executing workflow: {str(e)}"

    async def _tool_get_workflow_executions(self, arguments: Dict[str, Any]) -> str:
        if not self.n8n_client: return "Error: n8n client not initialized."
        try:
            workflow_id = arguments.get("workflow_id")
            limit = min(arguments.get("limit", 10), 50)
            executions = await self.n8n_client.get_executions(workflow_id, limit)
            if not executions: return "No executions found."
            status_emoji = {"success": "✅", "error": "❌", "running": "🔄", "waiting": "⏳"}
            results = [f"{status_emoji.get(e.get('status'), '❓')} Execution {e.get('id')} [{e.get('status', 'unknown')}] - Workflow: {e.get('workflowName', 'Unknown')} - {e.get('startedAt', 'Unknown time')}" for e in executions]
            return f"Recent {len(results)} executions:\n" + "\n".join(results)
        except Exception as e:
            logger.error(f"Error in get_workflow_executions tool: {e}")
            return f"Error getting executions: {str(e)}"

    async def _tool_get_execution_details(self, arguments: Dict[str, Any]) -> str:
        if not self.n8n_client: return "Error: n8n client not initialized."
        try:
            execution_id = arguments["execution_id"]
            execution = await self.n8n_client.get_execution(execution_id)
            status_emoji = {"success": "✅", "error": "❌", "running": "🔄", "waiting": "⏳"}
            return (f"Execution Details for ID: {execution_id}\n"
                    f"{status_emoji.get(execution.get('status'), '❓')} Status: {execution.get('status', 'Unknown')}\n"
                    f"📝 Workflow: {execution.get('workflowName', 'Unknown')}\n"
                    f"🆔 Workflow ID: {execution.get('workflowId', 'Unknown')}\n"
                    f"🚀 Started: {execution.get('startedAt', 'Unknown')}\n"
                    f"🏁 Finished: {execution.get('stoppedAt', 'Not finished')}\n"
                    f"⏱️ Duration: {execution.get('duration', 'Unknown')} ms\n"
                    f"🔢 Mode: {execution.get('mode', 'Unknown')}")
        except Exception as e:
            logger.error(f"Error in get_execution_details tool: {e}")
            return f"Error getting execution details: {str(e)}"

    async def _tool_activate_workflow(self, arguments: Dict[str, Any]) -> str:
        if not self.n8n_client: return "Error: n8n client not initialized."
        try:
            workflow_id = arguments["workflow_id"]
            result = await self.n8n_client.activate_workflow(workflow_id)
            return (f"🟢 Workflow activated successfully!\n"
                    f"Workflow ID: {workflow_id}\n"
                    f"Status: Active\n"
                    f"Result: {result.get('message', 'Activation completed')}")
        except Exception as e:
            logger.error(f"Error in activate_workflow tool: {e}")
            return f"Error activating workflow: {str(e)}"

    async def _tool_deactivate_workflow(self, arguments: Dict[str, Any]) -> str:
        if not self.n8n_client: return "Error: n8n client not initialized."
        try:
            workflow_id = arguments["workflow_id"]
            result = await self.n8n_client.deactivate_workflow(workflow_id)
            return (f"⚪ Workflow deactivated successfully!\n"
                    f"Workflow ID: {workflow_id}\n"
                    f"Status: Inactive\n"
                    f"Result: {result.get('message', 'Deactivation completed')}")
        except Exception as e:
            logger.error(f"Error in deactivate_workflow tool: {e}")
            return f"Error deactivating workflow: {str(e)}"

    # Resource implementations
    async def _resource_workflows_overview(self) -> str:
        if not self.n8n_client: return '{"error": "n8n client not initialized"}'
        try:
            workflows = await self.n8n_client.list_workflows()
            active_count = sum(1 for w in workflows if w.get("active"))
            return json.dumps({"total_workflows": len(workflows), "active_workflows": active_count})
        except Exception as e:
            return f'{{"error": "Error accessing workflows: {str(e)}"}}'

    async def _resource_connection_status(self) -> str:
        if not self.n8n_client: return '{"status": "not_connected", "reason": "missing configuration"}'
        try:
            await self.n8n_client.list_workflows()
            return '{"status": "connected", "reason": "operational"}'
        except Exception as e:
            return f'{{"status": "error", "reason": "{str(e)}"}}'

    # Abstract method implementations
    async def call_tool(self, tool_name: str, arguments: Dict[str, Any]) -> str:
        handler = getattr(self, f"_tool_{tool_name}", None)
        if handler:
            return await handler(arguments)
        return f"Tool not found: {tool_name}"

    async def read_resource(self, uri: str) -> str:
        resource_key = uri.replace("://", "_").replace("/", "_")
        handler = None
        if uri == "n8n://status":
            handler = self._resource_connection_status
        elif uri == "n8n://workflows":
            handler = self._resource_workflows_overview
            

async def main():
    """Run the n8n MCP server."""
    server = N8nMcpServer()
    await server.initialize_server()
    await server.run()

if __name__ == "__main__":
    asyncio.run(main())
