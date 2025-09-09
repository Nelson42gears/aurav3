#!/usr/bin/env python3
"""
Production-Grade MCP Server Base Class
Implements MCP Protocol Specification 2025-06-18
Follows latest protocol requirements and security best practices
"""

import asyncio
import json
import logging
import os
import time
from abc import ABC, abstractmethod
from datetime import datetime
from typing import Any, Dict, List, Optional, Union
from dataclasses import dataclass, asdict
from fastapi import FastAPI, HTTPException, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
import uvicorn

# MCP Protocol Types (Following 2025-06-18 Specification)
@dataclass
class MCPRequest:
    """MCP JSON-RPC Request following 2025-06-18 spec"""
    jsonrpc: str = "2.0"
    id: Union[str, int, None] = None
    method: str = ""
    params: Optional[Dict[str, Any]] = None

@dataclass
class MCPResponse:
    """MCP JSON-RPC Response following 2025-06-18 spec"""
    jsonrpc: str = "2.0"
    id: Union[str, int, None] = None
    result: Optional[Dict[str, Any]] = None
    error: Optional[Dict[str, Any]] = None

@dataclass
class MCPTool:
    """MCP Tool definition following 2025-06-18 spec"""
    name: str
    description: str
    inputSchema: Dict[str, Any]
    title: Optional[str] = None  # Added in 2025-06-18 for human-friendly names

@dataclass
class MCPResource:
    """MCP Resource definition following 2025-06-18 spec"""
    uri: str
    name: str
    description: str
    mimeType: Optional[str] = None
    title: Optional[str] = None  # Added in 2025-06-18

@dataclass
class MCPServerCapabilities:
    """MCP Server Capabilities following 2025-06-18 spec"""
    tools: Optional[Dict[str, Any]] = None
    resources: Optional[Dict[str, Any]] = None
    prompts: Optional[Dict[str, Any]] = None
    logging: Optional[Dict[str, Any]] = None

class MCPServerBase(ABC):
    """
    Production-grade MCP Server Base Class
    Implements MCP Protocol 2025-06-18 specification
    """
    
    def __init__(self, name: str, version: str = "1.0.0", port: int = 8000):
        self.name = name
        self.version = version
        self.port = port
        self.app = FastAPI(
            title=f"MCP Server: {name}",
            description=f"Production MCP server for {name} integration",
            version=version,
            docs_url="/docs",
            openapi_url="/openapi.json"
        )
        
        # Protocol configuration
        self.protocol_version = "2025-06-18"
        self.capabilities = MCPServerCapabilities()
        self.tools: Dict[str, MCPTool] = {}
        self.resources: Dict[str, MCPResource] = {}
        
        # Initialize logging
        self._setup_logging()
        
        # Setup FastAPI middleware and routes
        self._setup_middleware()
        self._setup_routes()
        
        self.logger.info(f"MCP Server {name} v{version} initialized")

    def _setup_logging(self):
        """Setup structured logging for production"""
        log_level = os.getenv("LOG_LEVEL", "INFO").upper()
        log_format = os.getenv("LOG_FORMAT", "json")
        
        if log_format == "json":
            logging.basicConfig(
                level=getattr(logging, log_level),
                format='{"timestamp": "%(asctime)s", "level": "%(levelname)s", "server": "%(name)s", "message": "%(message)s"}'
            )
        else:
            logging.basicConfig(
                level=getattr(logging, log_level),
                format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
            )
        
        self.logger = logging.getLogger(f"mcp.{self.name}")

    def _setup_middleware(self):
        """Setup FastAPI middleware for production"""
        # CORS middleware
        self.app.add_middleware(
            CORSMiddleware,
            allow_origins=["*"],  # Configure for production
            allow_credentials=True,
            allow_methods=["GET", "POST", "OPTIONS"],
            allow_headers=["*"],
        )

    def _setup_routes(self):
        """Setup MCP protocol routes following 2025-06-18 specification"""
        
        @self.app.get("/health")
        async def health_check():
            """Health check endpoint"""
            return {
                "status": "healthy",
                "server": self.name,
                "version": self.version,
                "protocol_version": self.protocol_version,
                "timestamp": datetime.utcnow().isoformat()
            }

        @self.app.post("/")
        async def mcp_json_rpc(request: Request, response: Response):
            """
            Main MCP JSON-RPC endpoint
            Handles all MCP protocol requests following 2025-06-18 spec
            """
            # Set required MCP-Protocol-Version header (Required in 2025-06-18)
            response.headers["MCP-Protocol-Version"] = self.protocol_version
            
            try:
                body = await request.json()
                self.logger.debug(f"Received MCP request: {body}")
                
                # Validate JSON-RPC format
                if body.get("jsonrpc") != "2.0":
                    return self._error_response(
                        request_id=body.get("id"),
                        code=-32600,
                        message="Invalid JSON-RPC version"
                    )
                
                method = body.get("method")
                params = body.get("params", {})
                request_id = body.get("id")
                
                # Route to appropriate handler
                if method == "initialize":
                    result = await self._handle_initialize(params)
                elif method == "tools/list":
                    result = await self._handle_tools_list(params)
                elif method == "tools/call":
                    result = await self._handle_tools_call(params)
                elif method == "resources/list":
                    result = await self._handle_resources_list(params)
                elif method == "resources/read":
                    result = await self._handle_resources_read(params)
                elif method == "ping":
                    result = {"status": "pong"}
                else:
                    return self._error_response(
                        request_id=request_id,
                        code=-32601,
                        message=f"Method not found: {method}"
                    )
                
                return self._success_response(request_id, result)
                
            except json.JSONDecodeError:
                return self._error_response(
                    request_id=None,
                    code=-32700,
                    message="Parse error"
                )
            except Exception as e:
                self.logger.error(f"Error handling MCP request: {e}")
                return self._error_response(
                    request_id=body.get("id") if 'body' in locals() else None,
                    code=-32603,
                    message=f"Internal error: {str(e)}"
                )

    async def _handle_initialize(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Handle MCP initialize request"""
        client_info = params.get("clientInfo", {})
        protocol_version = params.get("protocolVersion")
        
        self.logger.info(f"Initializing MCP session with client: {client_info}")
        
        # Validate protocol version
        if protocol_version and protocol_version != self.protocol_version:
            self.logger.warning(f"Protocol version mismatch: client={protocol_version}, server={self.protocol_version}")
        
        return {
            "protocolVersion": self.protocol_version,
            "capabilities": asdict(self.capabilities),
            "serverInfo": {
                "name": self.name,
                "version": self.version
            },
            "_meta": {
                "initialized_at": datetime.utcnow().isoformat()
            }
        }

    async def _handle_tools_list(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Handle tools/list request"""
        tools = [asdict(tool) for tool in self.tools.values()]
        return {"tools": tools}

    async def _handle_tools_call(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Handle tools/call request"""
        tool_name = params.get("name")
        arguments = params.get("arguments", {})
        
        if tool_name not in self.tools:
            raise ValueError(f"Tool not found: {tool_name}")
        
        # Call the tool implementation
        result = await self.call_tool(tool_name, arguments)
        
        return {
            "content": [
                {
                    "type": "text",
                    "text": result
                }
            ]
        }

    async def _handle_resources_list(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Handle resources/list request"""
        resources = [asdict(resource) for resource in self.resources.values()]
        return {"resources": resources}

    async def _handle_resources_read(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Handle resources/read request"""
        uri = params.get("uri")
        
        if uri not in self.resources:
            raise ValueError(f"Resource not found: {uri}")
        
        # Read the resource implementation
        content = await self.read_resource(uri)
        
        return {
            "contents": [
                {
                    "uri": uri,
                    "mimeType": self.resources[uri].mimeType or "text/plain",
                    "text": content
                }
            ]
        }

    def _success_response(self, request_id: Union[str, int, None], result: Dict[str, Any]) -> Dict[str, Any]:
        """Create successful JSON-RPC response"""
        return {
            "jsonrpc": "2.0",
            "id": request_id,
            "result": result
        }

    def _error_response(self, request_id: Union[str, int, None], code: int, message: str) -> Dict[str, Any]:
        """Create error JSON-RPC response"""
        return {
            "jsonrpc": "2.0",
            "id": request_id,
            "error": {
                "code": code,
                "message": message
            }
        }

    def register_tool(self, tool: MCPTool, handler_func):
        """Register a tool with its handler function"""
        self.tools[tool.name] = tool
        setattr(self, f"_tool_{tool.name}", handler_func)
        self.logger.info(f"Registered tool: {tool.name}")

    def register_resource(self, resource: MCPResource, handler_func):
        """Register a resource with its handler function"""
        self.resources[resource.uri] = resource
        setattr(self, f"_resource_{resource.uri.replace('/', '_')}", handler_func)
        self.logger.info(f"Registered resource: {resource.uri}")

    @abstractmethod
    async def initialize_server(self):
        """Initialize server-specific configuration (to be implemented by subclasses)"""
        pass

    @abstractmethod
    async def call_tool(self, tool_name: str, arguments: Dict[str, Any]) -> str:
        """Handle tool calls (to be implemented by subclasses)"""
        pass

    @abstractmethod
    async def read_resource(self, uri: str) -> str:
        """Handle resource reads (to be implemented by subclasses)"""
        pass

    async def run(self, host: str = "0.0.0.0"):
        """Run the MCP server"""
        await self.initialize_server()
        
        # Set server capabilities
        self.capabilities = MCPServerCapabilities(
            tools={"listChanged": True} if self.tools else None,
            resources={"subscribe": False, "listChanged": True} if self.resources else None
        )
        
        self.logger.info(f"Starting MCP server {self.name} on {host}:{self.port}")
        self.logger.info(f"Protocol version: {self.protocol_version}")
        self.logger.info(f"Tools available: {list(self.tools.keys())}")
        self.logger.info(f"Resources available: {list(self.resources.keys())}")
        
        config = uvicorn.Config(
            app=self.app,
            host=host,
            port=self.port,
            log_level=os.getenv("LOG_LEVEL", "info").lower(),
            access_log=True
        )
        server = uvicorn.Server(config)
        await server.serve()

if __name__ == "__main__":
    # This base class cannot be run directly
    print("MCPServerBase is an abstract base class. Use a concrete implementation.")
