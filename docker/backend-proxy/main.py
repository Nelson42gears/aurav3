from fastapi import FastAPI, Request, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse, JSONResponse
from mcp.client.session import ClientSession
from mcp.client.sse import sse_client
import os
import json
import logging
import asyncio
import time
from datetime import datetime
from typing import Dict, Any, Optional, List
from contextlib import asynccontextmanager
from gemini_client import GeminiMCPClient, get_client
from pydantic import BaseModel

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Enterprise-grade application lifespan management"""
    logger = logging.getLogger(__name__)
    
    # Startup phase
    try:
        logger.info('🚀 Initializing Aura MCP System...')
        
        # Initialize Gemini client
        gemini_client = get_client()
        await gemini_client.initialize_tools()
        
        # Store in app state (enterprise pattern)
        app.state.gemini_client = gemini_client
        app.state.services_ready = True
        app.state.tool_count = len(gemini_client.available_functions) if hasattr(gemini_client, 'available_functions') else 0
        app.state.initialization_time = time.time()
        
        logger.info(f'✅ System ready - {app.state.tool_count} tools available')
        
    except Exception as e:
        logger.error(f'❌ Startup failed: {e}')
        # Graceful degradation
        app.state.gemini_client = None
        app.state.services_ready = False
        app.state.initialization_error = str(e)
        # Continue startup - don't fail completely
    
    yield  # Application runs here
    
    # Shutdown phase
    logger.info('🔄 Graceful shutdown initiated...')
    if hasattr(app.state, 'gemini_client') and app.state.gemini_client:
        app.state.gemini_client = None
    logger.info('✅ Shutdown complete')

app = FastAPI(lifespan=lifespan, title="Aura MCP System", version="1.0.0")

# CORS Configuration
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production, replace with specific origins
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Environment variables
MCP_SERVER_URL = os.getenv("MCP_SERVER_URL", "http://mcp-unified-server:9000")
API_TOKEN = os.getenv("API_TOKEN", "your-secure-token")

# Logging configuration
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Global clients
mcp_client = None

class HealthCheck(BaseModel):
    status: str = "ok"


@app.get("/health", response_model=HealthCheck)
async def health_check():
    """Simple health check for Docker health monitoring"""
    return HealthCheck()

class HealthCheckDetailed(BaseModel):
    status: str
    timestamp: str
    server: str
    version: str
    checks: Dict[str, Any]

class ChatRequest(BaseModel):
    message: str
    conversation_id: Optional[str] = None

class ChatResponse(BaseModel):
    response: str
    conversation_id: str
    timestamp: str
    tool_calls: Optional[List[Dict]] = None

@app.get("/health/detailed", response_model=HealthCheckDetailed)
async def detailed_health_check():
    """Detailed health check that verifies MCP server, services, and unified customer system"""
    health_data = {
        "status": "healthy",
        "timestamp": datetime.now().isoformat(),
        "server": "Aura Backend Proxy",
        "version": "1.0.0",
        "checks": {
            "mcp_server": {
                "status": "pending",
                "endpoint": f"{MCP_SERVER_URL}/sse",
                "error": None,
                "response_time_ms": None
            },
            "database": {
                "status": "pending",
                "connected": False,
                "error": None,
                "response_time_ms": None
            },
            "unified_customer_system": {
                "status": "pending",
                "unified_customers_count": None,
                "error": None,
                "response_time_ms": None
            },
            "storage": {
                "status": "pending",
                "writable": False,
                "error": None,
                "response_time_ms": None
            }
        }
    }
    
    # Test MCP server connectivity via backend proxy health endpoint
    start_time = datetime.now()
    try:
        result = await handle_mcp_request("health", None, "GET")
        response_time = (datetime.now() - start_time).total_seconds() * 1000
        health_data["checks"]["mcp_server"]["response_time_ms"] = round(response_time, 2)
        health_data["checks"]["mcp_server"]["status"] = "healthy"
        
    except Exception as e:
        health_data["checks"]["mcp_server"]["status"] = "unhealthy"
        health_data["checks"]["mcp_server"]["error"] = str(e)
        health_data["status"] = "degraded"
    
    # Test unified customer system
    start_time = datetime.now()
    try:
        from unified_customer_models import get_unified_manager
        manager = await get_unified_manager()
        
        # Test database connection
        async with manager.pool.acquire() as conn:
            result = await conn.fetchval("SELECT COUNT(*) FROM unified_customers")
            
        response_time = (datetime.now() - start_time).total_seconds() * 1000
        health_data["checks"]["unified_customer_system"]["response_time_ms"] = round(response_time, 2)
        health_data["checks"]["unified_customer_system"]["status"] = "healthy"
        health_data["checks"]["unified_customer_system"]["unified_customers_count"] = result
        health_data["checks"]["database"]["status"] = "healthy"
        health_data["checks"]["database"]["connected"] = True
        
    except Exception as e:
        health_data["checks"]["unified_customer_system"]["status"] = "unhealthy"
        health_data["checks"]["unified_customer_system"]["error"] = str(e)
        health_data["checks"]["database"]["status"] = "unhealthy"
        health_data["checks"]["database"]["error"] = str(e)
        health_data["status"] = "degraded"
    
    return JSONResponse(content=health_data)

# =============================================================================
# CHAT ENDPOINTS
# =============================================================================

@app.post("/api/chat")
async def chat_endpoint(chat_request: ChatRequest, request: Request):
    """Chat endpoint with Gemini and MCP tool integration"""
    logger.info(f"🎯 CHAT ENDPOINT: Received request")
    logger.info(f"📝 Message: {chat_request.message}")
    logger.info(f"🗨️ Conversation ID: {chat_request.conversation_id}")
    
    # Check service readiness
    if not hasattr(request.app.state, 'services_ready') or not request.app.state.services_ready:
        logger.error("❌ CHAT ENDPOINT: Services not ready")
        raise HTTPException(status_code=503, detail="Services not ready")
    
    try:
        gemini_client = request.app.state.gemini_client
        if not gemini_client:
            logger.error("❌ CHAT ENDPOINT: Gemini client not available")
            raise HTTPException(status_code=503, detail="Gemini client not available")
        
        logger.info(f"🤖 CHAT ENDPOINT: Calling Gemini client")
        
        # Process chat with Gemini
        response = await gemini_client.chat(
            message=chat_request.message,
            conversation_id=chat_request.conversation_id
        )
        
        logger.info(f"✅ CHAT ENDPOINT: Gemini response received")
        logger.info(f"📊 Response length: {len(response.get('response', ''))}")
        logger.info(f"🔧 Tool calls: {len(response.get('tool_calls', []))}")
        
        return {
            "response": response.get("response", ""),
            "conversation_id": response.get("conversation_id", ""),
            "timestamp": datetime.now().isoformat(),
            "tool_calls": response.get("tool_calls", [])
        }
    except Exception as e:
        logger.error(f"❌ CHAT ENDPOINT ERROR: {type(e).__name__}: {e}")
        import traceback
        logger.error(f"🔍 CHAT ENDPOINT TRACEBACK: {traceback.format_exc()}")
        raise HTTPException(status_code=500, detail=f"Chat failed: {str(e)}")

@app.post("/api/chat/stream")
async def chat_stream_endpoint(request: ChatRequest):
    """Streaming chat endpoint"""
    # Check service readiness
    if not hasattr(request.app.state, 'services_ready') or not request.app.state.services_ready:
        raise HTTPException(status_code=503, detail="Services not ready - system initializing")
    
    if not request.app.state.gemini_client:
        error_detail = getattr(request.app.state, 'initialization_error', 'Gemini client not initialized')
        raise HTTPException(status_code=500, detail=error_detail)
    
    async def generate_stream():
        try:
            async for chunk in request.app.state.gemini_client.chat_stream(
                message=request.message,
                conversation_id=request.conversation_id
            ):
                yield f"data: {json.dumps({'chunk': chunk})}\n\n"
        except Exception as e:
            yield f"data: {json.dumps({'error': str(e)})}\n\n"
        finally:
            yield "data: [DONE]\n\n"
    
    return StreamingResponse(
        generate_stream(),
        media_type="text/plain",
        headers={"Cache-Control": "no-cache", "Connection": "keep-alive"}
    )

@app.get("/api/conversations")
async def list_conversations(request: Request):
    """List all conversation IDs"""
    if not hasattr(request.app.state, 'services_ready') or not request.app.state.services_ready:
        raise HTTPException(status_code=503, detail="Services not ready - system initializing")
    
    if not request.app.state.gemini_client:
        error_detail = getattr(request.app.state, 'initialization_error', 'Gemini client not initialized')
        raise HTTPException(status_code=500, detail=error_detail)
    
    conversations = request.app.state.gemini_client.list_conversations()
    return {"conversations": conversations}

@app.get("/api/conversations/{conversation_id}")
async def get_conversation(conversation_id: str, request: Request):
    """Get conversation history"""
    if not hasattr(request.app.state, 'services_ready') or not request.app.state.services_ready:
        raise HTTPException(status_code=503, detail="Services not ready - system initializing")
    
    if not request.app.state.gemini_client:
        error_detail = getattr(request.app.state, 'initialization_error', 'Gemini client not initialized')
        raise HTTPException(status_code=500, detail=error_detail)
    
    history = request.app.state.gemini_client.get_conversation_history(conversation_id)
    return {"conversation_id": conversation_id, "history": history}

@app.delete("/api/conversations/{conversation_id}")
async def clear_conversation(conversation_id: str, request: Request):
    """Clear conversation history"""
    if not hasattr(request.app.state, 'services_ready') or not request.app.state.services_ready:
        raise HTTPException(status_code=503, detail="Services not ready - system initializing")
    
    if not request.app.state.gemini_client:
        error_detail = getattr(request.app.state, 'initialization_error', 'Gemini client not initialized')
        raise HTTPException(status_code=500, detail=error_detail)
    
    request.app.state.gemini_client.clear_conversation(conversation_id)
    return {"message": f"Conversation {conversation_id} cleared"}

# Parameter mapping for API endpoints to MCP methods
PARAMETER_MAPPING = {
    "search_tickets": "search_tickets",
    "get_ticket": "view_ticket", 
    "create_ticket": "create_ticket",
    "update_ticket": "update_ticket",
    "list_contacts": "list_contacts",
    "get_contact": "get_contact",
    "create_contact": "create_contact",
    "health": "health_check",
    "health_check": "health_check",
    "list_tools": "list_platform_tools",
    "list_platform_tools": "list_platform_tools",
    "unified_search": "unified_search",
    "get_customer_journey": "get_customer_journey",
    "get_rate_limit_status": "get_rate_limit_status",
    # Fix Freshdesk tool mappings
    "freshdesk/tickets": "freshdesk_list_tickets",
    "tickets": "freshdesk_list_tickets",
    "list_tickets": "freshdesk_list_tickets"
}

def map_api_path_to_mcp_method(path: str) -> str:
    """Map API endpoint path to MCP method name"""
    # Remove leading/trailing slashes and convert to method name
    clean_path = path.strip('/')
    
    # Direct mapping if exists
    if clean_path in PARAMETER_MAPPING:
        return PARAMETER_MAPPING[clean_path]
    
    # Default mapping: convert path to snake_case method name
    method_name = clean_path.replace('-', '_').replace('/', '_')
    return method_name

async def handle_mcp_request(path: str, request: Request, method: str = 'POST'):
    """Handle MCP request forwarding using FastMCP Client"""
    
    # Map API path to MCP method
    method_name = map_api_path_to_mcp_method(path)
    logger.info(f"🔄 MCP SESSION: Processing {method} /{path}")
    logger.info(f"📍 MCP SESSION: Mapped method: {method_name}")
    
    # Extract parameters based on request method
    params = {}
    if method == 'GET':
        params = dict(request.query_params)
    elif method == 'POST':
        try:
            body = await request.body()
            if body:
                params = json.loads(body)
        except json.JSONDecodeError:
            params = {}
    
    logger.info(f"📤 MCP SESSION: Tool call '{method_name}' with params: {json.dumps(params, indent=2)}")
    
    try:
        logger.info(f"🔗 MCP SESSION: Creating SSE connection to {MCP_SERVER_URL}/sse")
        # Use MCP client with proper context manager
        async with sse_client(f"{MCP_SERVER_URL}/sse") as (read, write):
            logger.info(f"✅ MCP SESSION: SSE connection established")
            async with ClientSession(read, write) as session:
                logger.info(f"🔧 MCP SESSION: Initializing session...")
                await session.initialize()
                logger.info(f"✅ MCP SESSION: Session initialized successfully")
                
                logger.info(f"🚀 MCP SESSION: Calling tool '{method_name}'...")
                result = await session.call_tool(method_name, params)
                logger.info(f"✅ MCP SESSION: Tool call completed")
        
        logger.info(f"🔍 MCP SESSION: Processing result...")
        logger.info(f"🔍 MCP SESSION: Result type: {type(result)}")
        logger.info(f"🔍 MCP SESSION: Has content: {hasattr(result, 'content')}")
        
        # Extract text content from FastMCP result
        if hasattr(result, 'content') and result.content:
            logger.info(f"🔍 MCP SESSION: Content length: {len(result.content)}")
            if hasattr(result.content[0], 'text'):
                text_content = result.content[0].text
                logger.info(f"🔍 MCP SESSION: Text content length: {len(text_content) if text_content else 0}")
                if text_content and text_content.strip():
                    try:
                        result_data = json.loads(text_content)
                        logger.info(f"✅ MCP SESSION: JSON parsed successfully")
                    except json.JSONDecodeError:
                        result_data = text_content
                        logger.info(f"⚠️ MCP SESSION: Using raw text content")
                else:
                    result_data = {"error": "Empty response from MCP tool"}
                    logger.warning(f"❌ MCP SESSION: Empty text content")
            else:
                result_data = str(result.content[0])
                logger.info(f"⚠️ MCP SESSION: Using string conversion of content")
        else:
            result_data = result if result else {"error": "No result from MCP tool"}
            logger.warning(f"❌ MCP SESSION: No content in result")
            
        logger.info(f"✅ MCP SESSION: Final result processed")
        if hasattr(result, 'content'):
            logger.debug(f"🔍 Result content: {result.content}")
            if result.content and len(result.content) > 0:
                logger.debug(f"🔍 First content item: {result.content[0]}")
                logger.debug(f"🔍 First content type: {type(result.content[0])}")
                if hasattr(result.content[0], 'text'):
                    logger.debug(f"🔍 Text content: '{result.content[0].text}'")
        
        # Return the tool result content
        return JSONResponse(content={
            "success": True,
            "result": result_data,
            "tool": method_name,
            "timestamp": datetime.now().isoformat()
        })
        
    except Exception as e:
        error_msg = f"MCP tool call failed: {str(e)}"
        logger.error(f"❌ {error_msg}")
        
        return JSONResponse(
            status_code=500,
            content={
                "success": False,
                "error": error_msg,
                "tool": method_name,
                "timestamp": datetime.now().isoformat()
            }
        )

# Include unified customer API routes
try:
    from unified_customer_api import router as unified_router
    app.include_router(unified_router)
    logger.info("✅ Unified customer API routes loaded")
except ImportError as e:
    logger.warning(f"⚠️ Unified customer API not available: {e}")

# Enhanced system status endpoint
@app.get('/api/system/status')
async def system_status(request: Request):
    """Comprehensive system status check"""
    status = 'healthy' if getattr(request.app.state, 'services_ready', False) else 'degraded'
    
    response = {
        'status': status,
        'services': {
            'gemini_client': hasattr(request.app.state, 'gemini_client') and request.app.state.gemini_client is not None,
            'tools_available': getattr(request.app.state, 'tool_count', 0)
        },
        'initialization_time': getattr(request.app.state, 'initialization_time', None),
        'timestamp': time.time()
    }
    
    # Add error info if present
    if hasattr(request.app.state, 'initialization_error'):
        response['error'] = request.app.state.initialization_error
    
    return response

# Debug endpoint for Gemini status
@app.get("/api/debug/gemini-status")
async def gemini_status(request: Request):
    """Debug endpoint to check Gemini client status"""
    return {
        "client_exists": hasattr(request.app.state, 'gemini_client') and request.app.state.gemini_client is not None,
        "client_type": str(type(request.app.state.gemini_client)) if hasattr(request.app.state, 'gemini_client') and request.app.state.gemini_client else None,
        "tools_count": getattr(request.app.state, 'tool_count', 0),
        "tools_initialized": getattr(request.app.state, 'services_ready', False),
        "initialization_status": "ready" if getattr(request.app.state, 'services_ready', False) else "failed"
    }

# API Routes
# MCP API endpoints
@app.post("/api/{path:path}")
async def handle_post_request(path: str, request: Request):
    return await handle_mcp_request(path, request, 'POST')

@app.get("/api/{path:path}")
async def handle_get_request(path: str, request: Request):
    return await handle_mcp_request(path, request, 'GET')

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=9100,
        reload=True,
        log_level="info"
    )