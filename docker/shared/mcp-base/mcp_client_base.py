#!/usr/bin/env python3
"""
Production-Grade MCP Client Base Class
Implements MCP Protocol Specification 2025-06-18
HTTP Transport with proper session management
"""

import asyncio
import json
import logging
import os
import time
from typing import Any, Dict, List, Optional, Union
from dataclasses import dataclass, asdict
from datetime import datetime
import httpx

@dataclass
class MCPServerConnection:
    """MCP Server Connection Configuration"""
    name: str
    url: str
    timeout: int = 30
    max_retries: int = 3
    retry_delay: float = 1.0

@dataclass  
class MCPSession:
    """MCP Session Management"""
    server_name: str
    session_id: str
    protocol_version: str
    capabilities: Dict[str, Any]
    tools: List[Dict[str, Any]]
    resources: List[Dict[str, Any]]
    connected_at: datetime
    last_activity: datetime

class MCPClientBase:
    """
    Production-grade MCP Client Base Class
    Implements HTTP transport with proper session management
    Following MCP Protocol 2025-06-18 specification
    """
    
    def __init__(self, client_name: str = "MCP-Client", client_version: str = "1.0.0"):
        self.client_name = client_name
        self.client_version = client_version
        self.protocol_version = "2025-06-18"
        
        # Session management
        self.sessions: Dict[str, MCPSession] = {}
        self.connections: Dict[str, MCPServerConnection] = {}
        
        # HTTP client configuration
        self.http_timeout = httpx.Timeout(30.0, connect=10.0)
        self.http_limits = httpx.Limits(max_keepalive_connections=20, max_connections=100)
        
        # Setup logging
        self._setup_logging()
        
        self.logger.info(f"MCP Client {client_name} v{client_version} initialized")

    def _setup_logging(self):
        """Setup structured logging for production"""
        log_level = os.getenv("LOG_LEVEL", "INFO").upper()
        logging.basicConfig(
            level=getattr(logging, log_level),
            format='{"timestamp": "%(asctime)s", "level": "%(levelname)s", "client": "%(name)s", "message": "%(message)s"}'
        )
        self.logger = logging.getLogger(f"mcp.client.{self.client_name}")

    def add_server(self, connection: MCPServerConnection):
        """Add MCP server connection configuration"""
        self.connections[connection.name] = connection
        self.logger.info(f"Added MCP server configuration: {connection.name} -> {connection.url}")

    async def connect_to_server(self, server_name: str) -> bool:
        """
        Connect to MCP server using HTTP transport
        Implements proper MCP protocol initialization
        """
        if server_name not in self.connections:
            self.logger.error(f"Server configuration not found: {server_name}")
            return False

        connection = self.connections[server_name]
        
        try:
            async with httpx.AsyncClient(
                timeout=self.http_timeout,
                limits=self.http_limits
            ) as client:
                
                # Step 1: Initialize MCP session
                init_request = {
                    "jsonrpc": "2.0",
                    "id": f"init_{int(time.time())}",
                    "method": "initialize",
                    "params": {
                        "protocolVersion": self.protocol_version,
                        "capabilities": {
                            "tools": {"listChanged": True},
                            "resources": {"listChanged": True}
                        },
                        "clientInfo": {
                            "name": self.client_name,
                            "version": self.client_version
                        }
                    }
                }

                self.logger.debug(f"Sending initialize request to {server_name}: {init_request}")
                
                response = await client.post(
                    connection.url,
                    json=init_request,
                    headers={"Content-Type": "application/json"}
                )
                
                if response.status_code != 200:
                    self.logger.error(f"HTTP error connecting to {server_name}: {response.status_code}")
                    return False

                init_result = response.json()
                
                if "error" in init_result:
                    self.logger.error(f"MCP error initializing {server_name}: {init_result['error']}")
                    return False

                # Extract session information
                result = init_result.get("result", {})
                server_info = result.get("serverInfo", {})
                server_capabilities = result.get("capabilities", {})
                
                # Step 2: Discover tools and resources
                tools = await self._discover_tools(client, connection.url)
                resources = await self._discover_resources(client, connection.url)

                # Step 3: Create session
                session = MCPSession(
                    server_name=server_name,
                    session_id=f"{server_name}_{int(time.time())}",
                    protocol_version=result.get("protocolVersion", self.protocol_version),
                    capabilities=server_capabilities,
                    tools=tools,
                    resources=resources,
                    connected_at=datetime.utcnow(),
                    last_activity=datetime.utcnow()
                )

                self.sessions[server_name] = session
                
                self.logger.info(f"✅ Successfully connected to MCP server: {server_name}")
                self.logger.info(f"   Server: {server_info.get('name', 'Unknown')} v{server_info.get('version', 'Unknown')}")
                self.logger.info(f"   Tools: {len(tools)}")
                self.logger.info(f"   Resources: {len(resources)}")
                
                return True

        except httpx.TimeoutException:
            self.logger.error(f"Timeout connecting to MCP server: {server_name}")
            return False
        except httpx.ConnectError:
            self.logger.error(f"Connection error to MCP server: {server_name}")
            return False
        except Exception as e:
            self.logger.error(f"Unexpected error connecting to {server_name}: {e}")
            return False

    async def _discover_tools(self, client: httpx.AsyncClient, server_url: str) -> List[Dict[str, Any]]:
        """Discover available tools from MCP server"""
        try:
            tools_request = {
                "jsonrpc": "2.0",
                "id": f"tools_{int(time.time())}",
                "method": "tools/list",
                "params": {}
            }

            response = await client.post(
                server_url,
                json=tools_request,
                headers={
                    "Content-Type": "application/json",
                    "MCP-Protocol-Version": self.protocol_version  # Required in 2025-06-18
                }
            )

            if response.status_code == 200:
                result = response.json()
                if "result" in result:
                    return result["result"].get("tools", [])

        except Exception as e:
            self.logger.warning(f"Error discovering tools: {e}")

        return []

    async def _discover_resources(self, client: httpx.AsyncClient, server_url: str) -> List[Dict[str, Any]]:
        """Discover available resources from MCP server"""
        try:
            resources_request = {
                "jsonrpc": "2.0",
                "id": f"resources_{int(time.time())}",
                "method": "resources/list",
                "params": {}
            }

            response = await client.post(
                server_url,
                json=resources_request,
                headers={
                    "Content-Type": "application/json",
                    "MCP-Protocol-Version": self.protocol_version  # Required in 2025-06-18
                }
            )

            if response.status_code == 200:
                result = response.json()
                if "result" in result:
                    return result["result"].get("resources", [])

        except Exception as e:
            self.logger.warning(f"Error discovering resources: {e}")

        return []

    async def call_tool(self, server_name: str, tool_name: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """Call a tool on a specific MCP server"""
        if server_name not in self.sessions:
            raise ValueError(f"No active session for server: {server_name}")

        connection = self.connections[server_name]
        
        try:
            async with httpx.AsyncClient(
                timeout=self.http_timeout,
                limits=self.http_limits
            ) as client:
                
                call_request = {
                    "jsonrpc": "2.0",
                    "id": f"call_{tool_name}_{int(time.time())}",
                    "method": "tools/call",
                    "params": {
                        "name": tool_name,
                        "arguments": arguments
                    }
                }

                response = await client.post(
                    connection.url,
                    json=call_request,
                    headers={
                        "Content-Type": "application/json",
                        "MCP-Protocol-Version": self.protocol_version
                    }
                )

                if response.status_code != 200:
                    raise ValueError(f"HTTP error: {response.status_code}")

                result = response.json()
                
                if "error" in result:
                    raise ValueError(f"MCP error: {result['error']}")

                # Update session activity
                self.sessions[server_name].last_activity = datetime.utcnow()
                
                return result.get("result", {})

        except Exception as e:
            self.logger.error(f"Error calling tool {tool_name} on {server_name}: {e}")
            raise

    async def read_resource(self, server_name: str, uri: str) -> Dict[str, Any]:
        """Read a resource from a specific MCP server"""
        if server_name not in self.sessions:
            raise ValueError(f"No active session for server: {server_name}")

        connection = self.connections[server_name]
        
        try:
            async with httpx.AsyncClient(
                timeout=self.http_timeout,
                limits=self.http_limits
            ) as client:
                
                read_request = {
                    "jsonrpc": "2.0",
                    "id": f"read_{int(time.time())}",
                    "method": "resources/read",
                    "params": {
                        "uri": uri
                    }
                }

                response = await client.post(
                    connection.url,
                    json=read_request,
                    headers={
                        "Content-Type": "application/json",
                        "MCP-Protocol-Version": self.protocol_version
                    }
                )

                if response.status_code != 200:
                    raise ValueError(f"HTTP error: {response.status_code}")

                result = response.json()
                
                if "error" in result:
                    raise ValueError(f"MCP error: {result['error']}")

                # Update session activity
                self.sessions[server_name].last_activity = datetime.utcnow()
                
                return result.get("result", {})

        except Exception as e:
            self.logger.error(f"Error reading resource {uri} from {server_name}: {e}")
            raise

    async def ping_server(self, server_name: str) -> bool:
        """Ping MCP server to check connectivity"""
        if server_name not in self.connections:
            return False

        connection = self.connections[server_name]
        
        try:
            async with httpx.AsyncClient(timeout=httpx.Timeout(5.0)) as client:
                ping_request = {
                    "jsonrpc": "2.0",
                    "id": f"ping_{int(time.time())}",
                    "method": "ping",
                    "params": {}
                }

                response = await client.post(
                    connection.url,
                    json=ping_request,
                    headers={"Content-Type": "application/json"}
                )

                return response.status_code == 200

        except:
            return False

    def get_session_info(self, server_name: str) -> Optional[MCPSession]:
        """Get session information for a server"""
        return self.sessions.get(server_name)

    def get_all_tools(self) -> Dict[str, List[Dict[str, Any]]]:
        """Get all available tools from all connected servers"""
        all_tools = {}
        for server_name, session in self.sessions.items():
            all_tools[server_name] = session.tools
        return all_tools

    def get_all_resources(self) -> Dict[str, List[Dict[str, Any]]]:
        """Get all available resources from all connected servers"""
        all_resources = {}
        for server_name, session in self.sessions.items():
            all_resources[server_name] = session.resources
        return all_resources

    async def disconnect_from_server(self, server_name: str):
        """Disconnect from MCP server"""
        if server_name in self.sessions:
            del self.sessions[server_name]
            self.logger.info(f"Disconnected from MCP server: {server_name}")

    async def disconnect_all(self):
        """Disconnect from all MCP servers"""
        for server_name in list(self.sessions.keys()):
            await self.disconnect_from_server(server_name)
        self.logger.info("Disconnected from all MCP servers")

if __name__ == "__main__":
    print("MCPClientBase is a base class. Use a concrete implementation.")
