#!/usr/bin/env python3
"""
Aura MCP Unified Server - Enterprise Grade
Unifies Freshdesk, Intercom, Jira, and Odoo data through MCP protocol
Port: 9000 (StreamableHTTP transport)
"""

import asyncio
import inspect
import keyword
import json
import logging
import os
import sys
from datetime import datetime
from typing import Any, Dict, List, Optional, Sequence, Union

from fastmcp import FastMCP
from pydantic import BaseModel

# Import the adapters
from adapters.freshdesk_adapter import FreshdeskAdapter
from adapters.intercom_adapter import IntercomAdapter

# Import Pydantic validation enhancement
from validation.pydantic_validator import validate_tool_parameters

# =============================================================================
# DYNAMIC FUNCTION GENERATION FOR MCP COMPLIANCE
# =============================================================================

import inspect
import re
from typing import Optional

def sanitize_param_name(name: str) -> str:
    """Sanitize parameter name to be a valid Python identifier."""
    # Replace common problematic params with safe alternatives
    common_renames = {
        'id': 'item_id',
        'from': 'from_date',
        'filter': 'filter_query',
        'type': 'item_type',
        'format': 'format_type',
        'class': 'css_class',
        'import': 'import_data',
        'in': 'input_data',
        'for': 'target',
        'if': 'condition',
        'per_page': 'page_size',
        'message_type': 'msg_type',
        'event_name': 'event_type',
        'created_at_after': 'created_after',
        'away_mode_enabled': 'is_away',
        'contacts': 'contact_list',
        'contact': 'contact_data',
        'contact_id': 'contact_ref',
        'conversation_id': 'conv_id',
        'name': 'item_name',
        'title': 'item_title',
        'body': 'content_body',
        'language': 'lang_code',
        'phrase': 'search_phrase',
        'query': 'search_query',
        'model': 'model_type'
    }
    
    if name in common_renames:
        return common_renames[name]
        
    # Replace invalid chars with underscores
    sanitized = ''.join(c if c.isalnum() or c == '_' else '_' for c in name)
    
    # Ensure it starts with a letter/underscore
    if not sanitized[0].isalpha() and sanitized[0] != '_':
        sanitized = f'param_{sanitized}'
        
    # Deduplicate underscores
    sanitized = re.sub(r'_+', '_', sanitized)
    
    # Remove trailing underscores
    sanitized = sanitized.rstrip('_')
    
    # Handle Python keywords not caught by common_renames
    if keyword.iskeyword(sanitized):
        sanitized = f'param_{sanitized}'
        
    return sanitized

# DYNAMIC TOOL GENERATION - DISABLED (using static decorators instead)
# def create_explicit_tool_function(platform_name: str, tool_name: str, tool_config: dict, adapter_instance):
#     """DISABLED - Dynamic tool generation replaced with static @mcp.tool() decorators"""
#     pass

def create_explicit_tool_function(platform_name: str, tool_name: str, tool_config: dict, adapter_instance):
    """DISABLED - Dynamic tool generation replaced with static @mcp.tool() decorators"""
    logger.warning(f"Dynamic tool generation disabled for {platform_name}.{tool_name} - using static decorators")
    return None

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler('/app/logs/mcp_server.log')
    ]
)
logger = logging.getLogger(__name__)

# Initialize FastMCP server
mcp = FastMCP(
    name="Aura-MCP-Unified-Server"
)

# Health check is now handled by the backend proxy

# Global adapter instances
freshdesk_adapter = None
intercom_adapter = None
active_adapters = {}

class MCPServerConfig:
    """Configuration for MCP server"""
    
    # Environment variables (all required)
    FRESHDESK_DOMAIN = os.getenv("FRESHDESK_DOMAIN")
    FRESHDESK_API_KEY = os.getenv("FRESHDESK_API_KEY")
    INTERCOM_ACCESS_TOKEN = os.getenv("INTERCOM_ACCESS_TOKEN")
    POSTGRES_USER = os.getenv("POSTGRES_USER")
    POSTGRES_PASSWORD = os.getenv("POSTGRES_PASSWORD")
    POSTGRES_HOST = os.getenv("POSTGRES_HOST")
    POSTGRES_PORT = os.getenv("POSTGRES_PORT")
    POSTGRES_DB = os.getenv("POSTGRES_DB")
    
    @property
    def POSTGRES_CONNECTION_STRING(self):
        return f"postgresql://{self.POSTGRES_USER}:{self.POSTGRES_PASSWORD}@{self.POSTGRES_HOST}:{self.POSTGRES_PORT}/{self.POSTGRES_DB}"
    
    # Port configuration
    MCP_SERVER_PORT = 9000
    BACKEND_PROXY_PORT = 9100
    REACT_CLIENT_PORT = 9200
    FRESHDESK_WEBHOOK_PORT = 9300
    INTERCOM_WEBHOOK_PORT = 9400
    RATE_LIMITER_PORT = 9500
    
    # Rate limiting configuration
    RATE_LIMIT_REQUESTS_PER_MINUTE = 100
    FRESHDESK_RATE_LIMIT = 600  # requests per minute
    INTERCOM_RATE_LIMIT = 9000  # requests per minute
    
    @classmethod
    def validate(cls):
        """Validate required environment variables"""
        required_vars = [
            ("FRESHDESK_DOMAIN", cls.FRESHDESK_DOMAIN),
            ("FRESHDESK_API_KEY", cls.FRESHDESK_API_KEY),
            ("INTERCOM_ACCESS_TOKEN", cls.INTERCOM_ACCESS_TOKEN),
        ]
        
        # PostgreSQL is optional for MVP
        optional_vars = [
            ("POSTGRES_USER", cls.POSTGRES_USER),
            ("POSTGRES_PASSWORD", cls.POSTGRES_PASSWORD),
            ("POSTGRES_HOST", cls.POSTGRES_HOST),
            ("POSTGRES_PORT", cls.POSTGRES_PORT),
            ("POSTGRES_DB", cls.POSTGRES_DB),
        ]
        
        missing_required = [var_name for var_name, var_value in required_vars if not var_value]
        
        if missing_required:
            error_msg = f"❌ Missing required environment variables: {', '.join(missing_required)}"
            logger.error(error_msg)
            raise ValueError(error_msg)
        
        missing_optional = [var_name for var_name, var_value in optional_vars if not var_value]
        if missing_optional:
            logger.warning(f"⚠️  Optional environment variables missing: {', '.join(missing_optional)} (PostgreSQL features disabled)")
        
        logger.info("✅ All required environment variables are present")

class UnifiedCustomer(BaseModel):
    """Unified customer model across platforms"""
    unified_id: str
    email: Optional[str] = None
    phone: Optional[str] = None  
    name: Optional[str] = None
    company_name: Optional[str] = None
    freshdesk_id: Optional[int] = None
    intercom_id: Optional[str] = None
    created_at: datetime
    updated_at: datetime
    platform_data: Dict[str, Any] = {}

class UnifiedTicket(BaseModel):
    """Unified ticket/conversation model across platforms"""
    unified_id: str
    subject: Optional[str] = None
    description: Optional[str] = None
    status: str
    priority: str
    customer_unified_id: str
    agent_name: Optional[str] = None
    freshdesk_ticket_id: Optional[int] = None
    intercom_conversation_id: Optional[str] = None
    created_at: datetime
    updated_at: datetime
    platform_data: Dict[str, Any] = {}

# =============================================================================
# ADAPTER INITIALIZATION
# =============================================================================

async def initialize_adapters():
    """Initialize all platform adapters with configuration"""
    global freshdesk_adapter, intercom_adapter, active_adapters
    
    # Clear any existing adapters
    active_adapters.clear()
    freshdesk_adapter = None
    intercom_adapter = None
    
    logger.info("🔧 Initializing platform adapters...")
    
    # Initialize Freshdesk adapter
    if MCPServerConfig.FRESHDESK_DOMAIN and MCPServerConfig.FRESHDESK_API_KEY:
        try:
            logger.info("📄 Initializing Freshdesk adapter...")
            freshdesk_adapter = FreshdeskAdapter(
                domain=MCPServerConfig.FRESHDESK_DOMAIN,
                api_key=MCPServerConfig.FRESHDESK_API_KEY
            )
            active_adapters["freshdesk"] = freshdesk_adapter
            logger.info(f"✅ Freshdesk adapter initialized - Domain: {MCPServerConfig.FRESHDESK_DOMAIN}")
            
            # Test connection
            try:
                test_result = await freshdesk_adapter.test_connection()
                if test_result:
                    logger.info("✅ Freshdesk connection test passed")
                else:
                    logger.error("❌ Freshdesk connection test failed")
                    # Don't fail the whole initialization, just log the error
            except Exception as e:
                logger.error(f"❌ Freshdesk connection test error: {e}")
                # Don't fail the whole initialization, just log the error
                
        except Exception as e:
            logger.error(f"❌ Failed to initialize Freshdesk adapter: {e}")
            # Don't raise, continue with other adapters
    else:
        logger.warning("⚠️  Freshdesk adapter not initialized - missing domain or API key")
    
    # Initialize Intercom adapter
    if MCPServerConfig.INTERCOM_ACCESS_TOKEN:
        try:
            logger.info("📄 Initializing Intercom adapter...")
            intercom_adapter = IntercomAdapter(
                access_token=MCPServerConfig.INTERCOM_ACCESS_TOKEN
            )
            active_adapters["intercom"] = intercom_adapter
            logger.info("✅ Intercom adapter initialized")
            
            # Test connection
            try:
                test_result = await intercom_adapter.test_connection()
                if test_result:
                    logger.info("✅ Intercom connection test passed")
                else:
                    logger.error("❌ Intercom connection test failed")
            except Exception as e:
                logger.error(f"❌ Intercom connection test error: {e}")
                
        except Exception as e:
            logger.error(f"❌ Failed to initialize Intercom adapter: {e}")
            # Don't raise, continue with other adapters
    else:
        logger.warning("⚠️  Intercom adapter not initialized - missing access token")
    
    logger.info(f"🎯 Successfully initialized {len(active_adapters)}/{2} platform adapters")
    
    if not active_adapters:
        logger.warning("⚠️  No adapters were successfully initialized. Check your configuration and logs.")
    
    return len(active_adapters) > 0

# =============================================================================
# UNIFIED MCP TOOLS - High Level
# =============================================================================

@mcp.tool()
async def health_check() -> str:
    """
    Get comprehensive health status of the MCP server and all integrated platforms.
    
    Returns:
        str: Detailed health status including adapter status, rate limits, and connection tests
    """
    try:
        health_data = {
            "server": {
                "name": "Aura MCP Unified Server",
                "version": "1.0.0",
                "status": "healthy",
                "timestamp": datetime.now().isoformat(),
                "uptime": "active"
            },
            "adapters": {},
            "rate_limits": {},
            "total_tools": 0
        }
        
        for platform, adapter in active_adapters.items():
            # Get adapter health
            health_data["adapters"][platform] = {
                "status": "connected",
                "total_tools": len(adapter.get_tools()),
                "tools_registered": len([tool for tool in adapter.get_tools() if tool])
            }
            
            # Get rate limit status
            if hasattr(adapter, 'rate_limiter'):
                platform_stats = await adapter.rate_limiter.get_platform_stats(platform)
                if platform in platform_stats:
                    rate_status = platform_stats[platform]
                    health_data["rate_limits"][platform] = {
                        "requests_made": rate_status["current_usage"],
                        "limit": rate_status["limit_per_minute"],
                        "remaining": rate_status["remaining"],
                        "usage_percentage": rate_status["usage_percentage"]
                    }
        
        health_data["total_tools"] = sum(len(adapter.get_tools()) for adapter in active_adapters.values()) + 5  # +5 for unified tools
        
        return json.dumps(health_data, indent=2, default=str)
        
    except Exception as e:
        logger.error(f"Health check error: {e}")
        return f"❌ Health check failed: {str(e)}"

@mcp.tool()
def unified_search(query: str, platforms: str = "all") -> str:
    """
    Search across multiple platforms simultaneously for customers, tickets, conversations, and articles.
    
    Args:
        query (str): Search query (email, name, ticket ID, or keyword)
        platforms (str): Comma-separated platforms to search ("freshdesk", "intercom", or "all")
    
    Returns:
        str: Unified search results from all specified platforms
    """
    try:
        if not query.strip():
            return "❌ Search query cannot be empty"
        
        search_platforms = []
        if platforms == "all":
            search_platforms = list(active_adapters.keys())
        else:
            search_platforms = [p.strip() for p in platforms.split(",") if p.strip() in active_adapters]
        
        if not search_platforms:
            return f"❌ No valid platforms specified. Available: {list(active_adapters.keys())}"
        
        unified_results = {
            "query": query,
            "searched_platforms": search_platforms,
            "results": {},
            "total_matches": 0,
            "timestamp": datetime.now().isoformat()
        }
        
        for platform in search_platforms:
            adapter = active_adapters[platform]
            try:
                # Use adapter's unified search capability
                platform_results = adapter.unified_search(query)
                unified_results["results"][platform] = platform_results
                
                # Count matches
                if isinstance(platform_results, dict) and "matches" in platform_results:
                    unified_results["total_matches"] += len(platform_results["matches"])
                    
            except Exception as e:
                unified_results["results"][platform] = {"error": str(e)}
                logger.error(f"Search error on {platform}: {e}")
        
        return json.dumps(unified_results, indent=2, default=str)
        
    except Exception as e:
        logger.error(f"Unified search error: {e}")
        return f"❌ Unified search failed: {str(e)}"

@mcp.tool()
def get_customer_journey(identifier: str, identifier_type: str = "email") -> str:
    """
    Get complete customer journey across all platforms.
    
    Args:
        identifier (str): Customer identifier (email, phone, or customer ID)
        identifier_type (str): Type of identifier ("email", "phone", "id")
    
    Returns:
        str: Complete customer journey with unified timeline
    """
    try:
        journey = {
            "customer_identifier": identifier,
            "identifier_type": identifier_type,
            "platforms": {},
            "unified_timeline": [],
            "summary": {
                "total_interactions": 0,
                "first_contact": None,
                "last_contact": None,
                "platforms_found": []
            }
        }
        
        for platform, adapter in active_adapters.items():
            try:
                # Get customer data from each platform
                customer_data = adapter.get_customer_journey(identifier, identifier_type)
                journey["platforms"][platform] = customer_data
                
                if customer_data and "timeline" in customer_data:
                    journey["unified_timeline"].extend(customer_data["timeline"])
                    journey["summary"]["platforms_found"].append(platform)
                    
            except Exception as e:
                journey["platforms"][platform] = {"error": str(e)}
                logger.error(f"Customer journey error on {platform}: {e}")
        
        # Sort unified timeline by date
        journey["unified_timeline"].sort(key=lambda x: x.get("timestamp", ""))
        
        # Calculate summary stats
        journey["summary"]["total_interactions"] = len(journey["unified_timeline"])
        if journey["unified_timeline"]:
            journey["summary"]["first_contact"] = journey["unified_timeline"][0].get("timestamp")
            journey["summary"]["last_contact"] = journey["unified_timeline"][-1].get("timestamp")
        
        return json.dumps(journey, indent=2, default=str)
        
    except Exception as e:
        logger.error(f"Customer journey error: {e}")
        return f"❌ Customer journey failed: {str(e)}"

@mcp.tool()
def list_platform_tools() -> str:
    """
    List all available tools from all connected platforms.
    
    Returns:
        str: Categorized list of all available platform tools
    """
    try:
        tools_catalog = {
            "total_platforms": len(active_adapters),
            "total_tools": 0,
            "platforms": {}
        }
        
        for platform, adapter in active_adapters.items():
            platform_tools = adapter.get_tools()
            tools_catalog["platforms"][platform] = {
                "total_tools": len(platform_tools),
                "categories": {},
                "tools": platform_tools
            }
            
            # Categorize tools
            for tool in platform_tools:
                category = tool.split('_')[0] if '_' in tool else 'general'
                if category not in tools_catalog["platforms"][platform]["categories"]:
                    tools_catalog["platforms"][platform]["categories"][category] = []
                tools_catalog["platforms"][platform]["categories"][category].append(tool)
            
            tools_catalog["total_tools"] += len(platform_tools)
        
        # Add unified tools
        unified_tools = ["health_check", "unified_search", "get_customer_journey", "list_platform_tools", "get_rate_limit_status"]
        tools_catalog["unified_tools"] = {
            "total": len(unified_tools),
            "tools": unified_tools
        }
        tools_catalog["total_tools"] += len(unified_tools)
        
        return json.dumps(tools_catalog, indent=2)
        
    except Exception as e:
        logger.error(f"List platform tools error: {e}")
        return f"❌ List platform tools failed: {str(e)}"

@mcp.tool()
async def get_rate_limit_status() -> str:
    """
    Get current rate limit status for all integrated platforms.
    
    Returns:
        str: Detailed rate limit information and current usage for all platforms
    """
    try:
        rate_status = {
            "timestamp": datetime.now().isoformat(),
            "platforms": {},
            "global_limits": {
                "server_limit": MCPServerConfig.RATE_LIMIT_REQUESTS_PER_MINUTE,
                "freshdesk_limit": MCPServerConfig.FRESHDESK_RATE_LIMIT,
                "intercom_limit": MCPServerConfig.INTERCOM_RATE_LIMIT
            }
        }
        
        for platform, adapter in active_adapters.items():
            if hasattr(adapter, 'rate_limiter'):
                platform_stats = await adapter.rate_limiter.get_platform_stats(platform)
                if platform in platform_stats:
                    limiter_status = platform_stats[platform]
                    rate_status["platforms"][platform] = {
                        "requests_made": limiter_status["current_usage"],
                        "limit_per_minute": limiter_status["limit_per_minute"],
                        "remaining": limiter_status["remaining"],
                        "usage_percentage": limiter_status["usage_percentage"],
                        "violations": limiter_status.get("violations", 0),
                        "status": "healthy" if limiter_status["remaining"] > 10 else "approaching_limit"
                    }
                else:
                    rate_status["platforms"][platform] = {"status": "rate_limiter_no_data"}
            else:
                rate_status["platforms"][platform] = {"status": "rate_limiter_not_configured"}
        
        return json.dumps(rate_status, indent=2)
        
    except Exception as e:
        logger.error(f"Rate limit status error: {e}")
        return f"❌ Rate limit status failed: {str(e)}"

# =============================================================================
# DYNAMIC TOOL GENERATION FROM ADAPTERS
# =============================================================================

# =============================================================================
# STATIC TOOL DEFINITIONS - FRESHDESK
# =============================================================================

@mcp.tool()
async def freshdesk_list_tickets(per_page: int = 10, page: int = 1) -> str:
    """List all tickets from Freshdesk"""
    return await adapters['freshdesk'].execute_tool("list_tickets", {"per_page": per_page, "page": page})

@mcp.tool()
async def freshdesk_create_ticket(name: str, email: str, subject: str, description: str, status: int = 2, priority: int = 1) -> str:
    """Create a new support ticket in Freshdesk"""
    return await adapters['freshdesk'].execute_tool("create_ticket", {
        "name": name, "email": email, "subject": subject, "description": description, 
        "status": status, "priority": priority
    })

@mcp.tool()
async def freshdesk_view_ticket(ticket_id: str) -> str:
    """Retrieve a specific ticket by ID from Freshdesk"""
    return await adapters['freshdesk'].execute_tool("view_ticket", {"id": ticket_id})

@mcp.tool()
async def freshdesk_update_ticket(ticket_id: str, subject: str = None, description: str = None, status: int = None, priority: int = None) -> str:
    """Update an existing ticket in Freshdesk"""
    params = {"id": ticket_id}
    if subject: params["subject"] = subject
    if description: params["description"] = description
    if status: params["status"] = status
    if priority: params["priority"] = priority
    return await adapters['freshdesk'].execute_tool("update_ticket", params)

@mcp.tool()
async def freshdesk_delete_ticket(ticket_id: str) -> str:
    """Delete a ticket from Freshdesk"""
    return await adapters['freshdesk'].execute_tool("delete_ticket", {"id": ticket_id})

@mcp.tool()
async def freshdesk_list_contacts(per_page: int = 10, page: int = 1) -> str:
    """List all contacts from Freshdesk"""
    return await adapters['freshdesk'].execute_tool("list_contacts", {"per_page": per_page, "page": page})

@mcp.tool()
async def freshdesk_create_contact(name: str, email: str, phone: str = None, company_id: str = None) -> str:
    """Create a new contact in Freshdesk"""
    params = {"name": name, "email": email}
    if phone: params["phone"] = phone
    if company_id: params["company_id"] = company_id
    return await adapters['freshdesk'].execute_tool("create_contact", params)

@mcp.tool()
async def freshdesk_view_contact(contact_id: str) -> str:
    """Retrieve a specific contact by ID from Freshdesk"""
    return await adapters['freshdesk'].execute_tool("view_contact", {"id": contact_id})

@mcp.tool()
async def freshdesk_add_note_to_ticket(ticket_id: str, body: str, private: bool = True) -> str:
    """Add a note to an existing ticket in Freshdesk"""
    params = {"id": ticket_id, "body": body, "private": private}
    return await adapters['freshdesk'].execute_tool("add_note_to_ticket", params)

@mcp.tool()
async def freshdesk_filter_tickets(query: str) -> str:
    """Filter tickets using advanced search in Freshdesk"""
    return await adapters['freshdesk'].execute_tool("filter_tickets", {"query": query})

@mcp.tool()
async def freshdesk_create_company(name: str, description: str = None, website: str = None) -> str:
    """Create a new company in Freshdesk"""
    params = {"name": name}
    if description: params["description"] = description
    if website: params["website"] = website
    return await adapters['freshdesk'].execute_tool("create_company", params)

@mcp.tool()
async def freshdesk_view_company(company_id: str) -> str:
    """Retrieve a specific company by ID from Freshdesk"""
    return await adapters['freshdesk'].execute_tool("view_company", {"id": company_id})

@mcp.tool()
async def freshdesk_list_companies(per_page: int = 10, page: int = 1) -> str:
    """List all companies from Freshdesk"""
    return await adapters['freshdesk'].execute_tool("list_companies", {"per_page": per_page, "page": page})

@mcp.tool()
async def freshdesk_update_company(company_id: str, name: str = None, description: str = None, website: str = None) -> str:
    """Update an existing company in Freshdesk"""
    params = {"id": company_id}
    if name: params["name"] = name
    if description: params["description"] = description
    if website: params["website"] = website
    return await adapters['freshdesk'].execute_tool("update_company", params)

@mcp.tool()
async def freshdesk_delete_company(company_id: str) -> str:
    """Delete a company from Freshdesk"""
    return await adapters['freshdesk'].execute_tool("delete_company", {"id": company_id})

@mcp.tool()
async def freshdesk_list_agents(per_page: int = 10, page: int = 1) -> str:
    """List all agents from Freshdesk"""
    return await adapters['freshdesk'].execute_tool("list_agents", {"per_page": per_page, "page": page})

@mcp.tool()
async def freshdesk_create_agent(name: str, email: str, phone: str = None) -> str:
    """Create a new agent in Freshdesk"""
    params = {"name": name, "email": email}
    if phone: params["phone"] = phone
    return await adapters['freshdesk'].execute_tool("create_agent", params)

@mcp.tool()
async def freshdesk_view_agent(agent_id: str) -> str:
    """Retrieve a specific agent by ID from Freshdesk"""
    return await adapters['freshdesk'].execute_tool("view_agent", {"id": agent_id})

@mcp.tool()
async def freshdesk_update_agent(agent_id: str, name: str = None, email: str = None, phone: str = None) -> str:
    """Update an existing agent in Freshdesk"""
    params = {"id": agent_id}
    if name: params["name"] = name
    if email: params["email"] = email
    if phone: params["phone"] = phone
    return await adapters['freshdesk'].execute_tool("update_agent", params)

@mcp.tool()
async def freshdesk_delete_agent(agent_id: str) -> str:
    """Delete an agent from Freshdesk"""
    return await adapters['freshdesk'].execute_tool("delete_agent", {"id": agent_id})

@mcp.tool()
async def freshdesk_list_groups(per_page: int = 10, page: int = 1) -> str:
    """List all groups from Freshdesk"""
    return await adapters['freshdesk'].execute_tool("list_groups", {"per_page": per_page, "page": page})

@mcp.tool()
async def freshdesk_create_group(name: str, description: str = None) -> str:
    """Create a new group in Freshdesk"""
    params = {"name": name}
    if description: params["description"] = description
    return await adapters['freshdesk'].execute_tool("create_group", params)

@mcp.tool()
async def freshdesk_view_group(group_id: str) -> str:
    """Retrieve a specific group by ID from Freshdesk"""
    return await adapters['freshdesk'].execute_tool("view_group", {"id": group_id})

@mcp.tool()
async def freshdesk_update_group(group_id: str, name: str = None, description: str = None) -> str:
    """Update an existing group in Freshdesk"""
    params = {"id": group_id}
    if name: params["name"] = name
    if description: params["description"] = description
    return await adapters['freshdesk'].execute_tool("update_group", params)

@mcp.tool()
async def freshdesk_delete_group(group_id: str) -> str:
    """Delete a group from Freshdesk"""
    return await adapters['freshdesk'].execute_tool("delete_group", {"id": group_id})

@mcp.tool()
async def freshdesk_create_comment(ticket_id: str, body: str, private: bool = False) -> str:
    """Create a comment on a ticket in Freshdesk"""
    params = {"id": ticket_id, "body": body, "private": private}
    return await adapters['freshdesk'].execute_tool("create_comment", params)

@mcp.tool()
async def freshdesk_create_reply(ticket_id: str, body: str, from_email: str = None) -> str:
    """Create a reply to a ticket in Freshdesk"""
    params = {"id": ticket_id, "body": body}
    if from_email: params["from_email"] = from_email
    return await adapters['freshdesk'].execute_tool("create_reply", params)

@mcp.tool()
async def freshdesk_list_time_entries(ticket_id: str = None, per_page: int = 10, page: int = 1) -> str:
    """List time entries from Freshdesk"""
    params = {"per_page": per_page, "page": page}
    if ticket_id: params["ticket_id"] = ticket_id
    return await adapters['freshdesk'].execute_tool("list_time_entries", params)

@mcp.tool()
async def freshdesk_create_time_entry(ticket_id: str, time_spent: str, note: str = None) -> str:
    """Create a time entry for a ticket in Freshdesk"""
    params = {"ticket_id": ticket_id, "time_spent": time_spent}
    if note: params["note"] = note
    return await adapters['freshdesk'].execute_tool("create_time_entry", params)

@mcp.tool()
async def freshdesk_view_time_entry(time_entry_id: str) -> str:
    """Retrieve a specific time entry by ID from Freshdesk"""
    return await adapters['freshdesk'].execute_tool("view_time_entry", {"id": time_entry_id})

@mcp.tool()
async def freshdesk_update_time_entry(time_entry_id: str, time_spent: str = None, note: str = None) -> str:
    """Update an existing time entry in Freshdesk"""
    params = {"id": time_entry_id}
    if time_spent: params["time_spent"] = time_spent
    if note: params["note"] = note
    return await adapters['freshdesk'].execute_tool("update_time_entry", params)

@mcp.tool()
async def freshdesk_delete_time_entry(time_entry_id: str) -> str:
    """Delete a time entry from Freshdesk"""
    return await adapters['freshdesk'].execute_tool("delete_time_entry", {"id": time_entry_id})

@mcp.tool()
async def freshdesk_filter_contacts(query: str) -> str:
    """Filter contacts using advanced search in Freshdesk"""
    return await adapters['freshdesk'].execute_tool("filter_contacts", {"query": query})

@mcp.tool()
async def freshdesk_filter_companies(query: str) -> str:
    """Filter companies using advanced search in Freshdesk"""
    return await adapters['freshdesk'].execute_tool("filter_companies", {"query": query})

@mcp.tool()
async def freshdesk_merge_tickets(primary_ticket_id: str, secondary_ticket_id: str) -> str:
    """Merge two tickets in Freshdesk"""
    return await adapters['freshdesk'].execute_tool("merge_tickets", {"primary_ticket_id": primary_ticket_id, "secondary_ticket_id": secondary_ticket_id})

@mcp.tool()
async def freshdesk_merge_contacts(primary_contact_id: str, secondary_contact_id: str) -> str:
    """Merge two contacts in Freshdesk"""
    return await adapters['freshdesk'].execute_tool("merge_contacts", {"primary_contact_id": primary_contact_id, "secondary_contact_id": secondary_contact_id})

@mcp.tool()
async def freshdesk_add_watcher(ticket_id: str, user_id: str) -> str:
    """Add a watcher to a ticket in Freshdesk"""
    return await adapters['freshdesk'].execute_tool("add_watcher", {"ticket_id": ticket_id, "user_id": user_id})

@mcp.tool()
async def freshdesk_remove_watcher(ticket_id: str, user_id: str) -> str:
    """Remove a watcher from a ticket in Freshdesk"""
    return await adapters['freshdesk'].execute_tool("remove_watcher", {"ticket_id": ticket_id, "user_id": user_id})

@mcp.tool()
async def freshdesk_list_conversations(per_page: int = 10, page: int = 1) -> str:
    """List all conversations from Freshdesk"""
    return await adapters['freshdesk'].execute_tool("list_conversations", {"per_page": per_page, "page": page})

@mcp.tool()
async def freshdesk_update_conversation(conversation_id: str, status: str = None) -> str:
    """Update a conversation in Freshdesk"""
    params = {"id": conversation_id}
    if status: params["status"] = status
    return await adapters['freshdesk'].execute_tool("update_conversation", params)

@mcp.tool()
async def freshdesk_delete_conversation(conversation_id: str) -> str:
    """Delete a conversation from Freshdesk"""
    return await adapters['freshdesk'].execute_tool("delete_conversation", {"id": conversation_id})

@mcp.tool()
async def freshdesk_bulk_update_tickets(ticket_ids: str, status: int = None, priority: int = None) -> str:
    """Bulk update multiple tickets in Freshdesk"""
    params = {"ticket_ids": ticket_ids}
    if status: params["status"] = status
    if priority: params["priority"] = priority
    return await adapters['freshdesk'].execute_tool("bulk_update_tickets", params)

@mcp.tool()
async def freshdesk_bulk_delete_tickets(ticket_ids: str) -> str:
    """Bulk delete multiple tickets in Freshdesk"""
    return await adapters['freshdesk'].execute_tool("bulk_delete_tickets", {"ticket_ids": ticket_ids})

@mcp.tool()
async def freshdesk_archive_tickets(ticket_ids: str) -> str:
    """Archive multiple tickets in Freshdesk"""
    return await adapters['freshdesk'].execute_tool("archive_tickets", {"ticket_ids": ticket_ids})

@mcp.tool()
async def freshdesk_restore_contact(contact_id: str) -> str:
    """Restore a deleted contact in Freshdesk"""
    return await adapters['freshdesk'].execute_tool("restore_contact", {"id": contact_id})

@mcp.tool()
async def freshdesk_make_agent(contact_id: str) -> str:
    """Convert a contact to an agent in Freshdesk"""
    return await adapters['freshdesk'].execute_tool("make_agent", {"id": contact_id})

@mcp.tool()
async def freshdesk_send_invite(agent_id: str) -> str:
    """Send an invite to an agent in Freshdesk"""
    return await adapters['freshdesk'].execute_tool("send_invite", {"id": agent_id})

@mcp.tool()
async def freshdesk_list_solution_articles(per_page: int = 10, page: int = 1) -> str:
    """List all solution articles from Freshdesk"""
    return await adapters['freshdesk'].execute_tool("list_solution_articles", {"per_page": per_page, "page": page})

@mcp.tool()
async def freshdesk_create_solution_article(title: str, description: str, folder_id: str) -> str:
    """Create a new solution article in Freshdesk"""
    return await adapters['freshdesk'].execute_tool("create_solution_article", {"title": title, "description": description, "folder_id": folder_id})

@mcp.tool()
async def freshdesk_view_solution_article(article_id: str) -> str:
    """Retrieve a specific solution article by ID from Freshdesk"""
    return await adapters['freshdesk'].execute_tool("view_solution_article", {"id": article_id})

@mcp.tool()
async def freshdesk_update_solution_article(article_id: str, title: str = None, description: str = None) -> str:
    """Update an existing solution article in Freshdesk"""
    params = {"id": article_id}
    if title: params["title"] = title
    if description: params["description"] = description
    return await adapters['freshdesk'].execute_tool("update_solution_article", params)

@mcp.tool()
async def freshdesk_delete_solution_article(article_id: str) -> str:
    """Delete a solution article from Freshdesk"""
    return await adapters['freshdesk'].execute_tool("delete_solution_article", {"id": article_id})

@mcp.tool()
async def freshdesk_list_solution_categories(per_page: int = 10, page: int = 1) -> str:
    """List all solution categories from Freshdesk"""
    return await adapters['freshdesk'].execute_tool("list_solution_categories", {"per_page": per_page, "page": page})

@mcp.tool()
async def freshdesk_create_solution_category(name: str, description: str = None) -> str:
    """Create a new solution category in Freshdesk"""
    params = {"name": name}
    if description: params["description"] = description
    return await adapters['freshdesk'].execute_tool("create_solution_category", params)

@mcp.tool()
async def freshdesk_view_solution_category(category_id: str) -> str:
    """Retrieve a specific solution category by ID from Freshdesk"""
    return await adapters['freshdesk'].execute_tool("view_solution_category", {"id": category_id})

@mcp.tool()
async def freshdesk_update_solution_category(category_id: str, name: str = None, description: str = None) -> str:
    """Update an existing solution category in Freshdesk"""
    params = {"id": category_id}
    if name: params["name"] = name
    if description: params["description"] = description
    return await adapters['freshdesk'].execute_tool("update_solution_category", params)

@mcp.tool()
async def freshdesk_delete_solution_category(category_id: str) -> str:
    """Delete a solution category from Freshdesk"""
    return await adapters['freshdesk'].execute_tool("delete_solution_category", {"id": category_id})

@mcp.tool()
async def freshdesk_list_solution_folders(category_id: str, per_page: int = 10, page: int = 1) -> str:
    """List all solution folders from a category in Freshdesk"""
    return await adapters['freshdesk'].execute_tool("list_solution_folders", {"category_id": category_id, "per_page": per_page, "page": page})

@mcp.tool()
async def freshdesk_create_solution_folder(name: str, category_id: str, description: str = None) -> str:
    """Create a new solution folder in Freshdesk"""
    params = {"name": name, "category_id": category_id}
    if description: params["description"] = description
    return await adapters['freshdesk'].execute_tool("create_solution_folder", params)

@mcp.tool()
async def freshdesk_view_solution_folder(folder_id: str) -> str:
    """Retrieve a specific solution folder by ID from Freshdesk"""
    return await adapters['freshdesk'].execute_tool("view_solution_folder", {"id": folder_id})

@mcp.tool()
async def freshdesk_update_solution_folder(folder_id: str, name: str = None, description: str = None) -> str:
    """Update an existing solution folder in Freshdesk"""
    params = {"id": folder_id}
    if name: params["name"] = name
    if description: params["description"] = description
    return await adapters['freshdesk'].execute_tool("update_solution_folder", params)

@mcp.tool()
async def freshdesk_delete_solution_folder(folder_id: str) -> str:
    """Delete a solution folder from Freshdesk"""
    return await adapters['freshdesk'].execute_tool("delete_solution_folder", {"id": folder_id})

@mcp.tool()
async def freshdesk_list_forums(per_page: int = 10, page: int = 1) -> str:
    """List all forums from Freshdesk"""
    return await adapters['freshdesk'].execute_tool("list_forums", {"per_page": per_page, "page": page})

@mcp.tool()
async def freshdesk_create_forum(name: str, description: str = None) -> str:
    """Create a new forum in Freshdesk"""
    params = {"name": name}
    if description: params["description"] = description
    return await adapters['freshdesk'].execute_tool("create_forum", params)

@mcp.tool()
async def freshdesk_list_forum_categories(forum_id: str, per_page: int = 10, page: int = 1) -> str:
    """List all forum categories from Freshdesk"""
    return await adapters['freshdesk'].execute_tool("list_forum_categories", {"forum_id": forum_id, "per_page": per_page, "page": page})

@mcp.tool()
async def freshdesk_create_forum_category(name: str, forum_id: str, description: str = None) -> str:
    """Create a new forum category in Freshdesk"""
    params = {"name": name, "forum_id": forum_id}
    if description: params["description"] = description
    return await adapters['freshdesk'].execute_tool("create_forum_category", params)

@mcp.tool()
async def freshdesk_list_topics(category_id: str, per_page: int = 10, page: int = 1) -> str:
    """List all topics from a forum category in Freshdesk"""
    return await adapters['freshdesk'].execute_tool("list_topics", {"category_id": category_id, "per_page": per_page, "page": page})

@mcp.tool()
async def freshdesk_create_topic(title: str, message: str, category_id: str) -> str:
    """Create a new topic in a forum category in Freshdesk"""
    return await adapters['freshdesk'].execute_tool("create_topic", {"title": title, "message": message, "category_id": category_id})

@mcp.tool()
async def freshdesk_view_topic(topic_id: str) -> str:
    """Retrieve a specific topic by ID from Freshdesk"""
    return await adapters['freshdesk'].execute_tool("view_topic", {"id": topic_id})

@mcp.tool()
async def freshdesk_update_topic(topic_id: str, title: str = None, message: str = None) -> str:
    """Update an existing topic in Freshdesk"""
    params = {"id": topic_id}
    if title: params["title"] = title
    if message: params["message"] = message
    return await adapters['freshdesk'].execute_tool("update_topic", params)

@mcp.tool()
async def freshdesk_delete_topic(topic_id: str) -> str:
    """Delete a topic from Freshdesk"""
    return await adapters['freshdesk'].execute_tool("delete_topic", {"id": topic_id})

@mcp.tool()
async def freshdesk_monitor_topic(topic_id: str) -> str:
    """Monitor a topic for updates in Freshdesk"""
    return await adapters['freshdesk'].execute_tool("monitor_topic", {"id": topic_id})

@mcp.tool()
async def freshdesk_list_ratings(per_page: int = 10, page: int = 1) -> str:
    """List all ratings from Freshdesk"""
    return await adapters['freshdesk'].execute_tool("list_ratings", {"per_page": per_page, "page": page})

@mcp.tool()
async def freshdesk_create_rating(ticket_id: str, rating: int, feedback: str = None) -> str:
    """Create a rating for a ticket in Freshdesk"""
    params = {"ticket_id": ticket_id, "rating": rating}
    if feedback: params["feedback"] = feedback
    return await adapters['freshdesk'].execute_tool("create_rating", params)

@mcp.tool()
async def freshdesk_view_ratings(ticket_id: str) -> str:
    """View ratings for a specific ticket in Freshdesk"""
    return await adapters['freshdesk'].execute_tool("view_ratings", {"ticket_id": ticket_id})

@mcp.tool()
async def freshdesk_list_mailboxes(per_page: int = 10, page: int = 1) -> str:
    """List all mailboxes from Freshdesk"""
    return await adapters['freshdesk'].execute_tool("list_mailboxes", {"per_page": per_page, "page": page})

@mcp.tool()
async def freshdesk_create_mailbox(name: str, email: str) -> str:
    """Create a new mailbox in Freshdesk"""
    return await adapters['freshdesk'].execute_tool("create_mailbox", {"name": name, "email": email})

@mcp.tool()
async def freshdesk_view_mailbox(mailbox_id: str) -> str:
    """Retrieve a specific mailbox by ID from Freshdesk"""
    return await adapters['freshdesk'].execute_tool("view_mailbox", {"id": mailbox_id})

@mcp.tool()
async def freshdesk_update_mailbox(mailbox_id: str, name: str = None, email: str = None) -> str:
    """Update an existing mailbox in Freshdesk"""
    params = {"id": mailbox_id}
    if name: params["name"] = name
    if email: params["email"] = email
    return await adapters['freshdesk'].execute_tool("update_mailbox", params)

@mcp.tool()
async def freshdesk_delete_mailbox(mailbox_id: str) -> str:
    """Delete a mailbox from Freshdesk"""
    return await adapters['freshdesk'].execute_tool("delete_mailbox", {"id": mailbox_id})

@mcp.tool()
async def freshdesk_mailbox_settings(mailbox_id: str) -> str:
    """Get mailbox settings from Freshdesk"""
    return await adapters['freshdesk'].execute_tool("mailbox_settings", {"id": mailbox_id})

@mcp.tool()
async def freshdesk_list_sla_policies(per_page: int = 10, page: int = 1) -> str:
    """List all SLA policies from Freshdesk"""
    return await adapters['freshdesk'].execute_tool("list_sla_policies", {"per_page": per_page, "page": page})

@mcp.tool()
async def freshdesk_view_sla_policy(policy_id: str) -> str:
    """Retrieve a specific SLA policy by ID from Freshdesk"""
    return await adapters['freshdesk'].execute_tool("view_sla_policy", {"id": policy_id})

@mcp.tool()
async def freshdesk_list_business_hours(per_page: int = 10, page: int = 1) -> str:
    """List all business hours from Freshdesk"""
    return await adapters['freshdesk'].execute_tool("list_business_hours", {"per_page": per_page, "page": page})

@mcp.tool()
async def freshdesk_view_business_hour(business_hour_id: str) -> str:
    """Retrieve specific business hours by ID from Freshdesk"""
    return await adapters['freshdesk'].execute_tool("view_business_hour", {"id": business_hour_id})

@mcp.tool()
async def freshdesk_view_current_agent() -> str:
    """Get current agent information from Freshdesk"""
    return await adapters['freshdesk'].execute_tool("view_current_agent", {})

@mcp.tool()
async def freshdesk_view_email_configs() -> str:
    """Get email configurations from Freshdesk"""
    return await adapters['freshdesk'].execute_tool("view_email_configs", {})

@mcp.tool()
async def freshdesk_agent_groups(agent_id: str) -> str:
    """Get groups for a specific agent in Freshdesk"""
    return await adapters['freshdesk'].execute_tool("agent_groups", {"id": agent_id})

@mcp.tool()
async def freshdesk_agent_skills(agent_id: str) -> str:
    """Get skills for a specific agent in Freshdesk"""
    return await adapters['freshdesk'].execute_tool("agent_skills", {"id": agent_id})

@mcp.tool()
async def freshdesk_company_fields() -> str:
    """Get company custom fields from Freshdesk"""
    return await adapters['freshdesk'].execute_tool("company_fields", {})

@mcp.tool()
async def freshdesk_create_note(ticket_id: str, body: str, private: bool = True) -> str:
    """Create a note on a ticket in Freshdesk"""
    params = {"ticket_id": ticket_id, "body": body, "private": private}
    return await adapters['freshdesk'].execute_tool("create_note", params)

@mcp.tool()
async def freshdesk_create_outbound_email(to_email: str, subject: str, description: str) -> str:
    """Create an outbound email in Freshdesk"""
    return await adapters['freshdesk'].execute_tool("create_outbound_email", {"to_email": to_email, "subject": subject, "description": description})

@mcp.tool()
async def freshdesk_create_bcc_email(ticket_id: str, bcc_email: str) -> str:
    """Add a BCC email to a ticket in Freshdesk"""
    return await adapters['freshdesk'].execute_tool("create_bcc_email", {"ticket_id": ticket_id, "bcc_email": bcc_email})

@mcp.tool()
async def freshdesk_forward_ticket(ticket_id: str, email: str) -> str:
    """Forward a ticket to an email address in Freshdesk"""
    return await adapters['freshdesk'].execute_tool("forward_ticket", {"ticket_id": ticket_id, "email": email})

@mcp.tool()
async def freshdesk_reply_to_forward(ticket_id: str, body: str) -> str:
    """Reply to a forwarded ticket in Freshdesk"""
    return await adapters['freshdesk'].execute_tool("reply_to_forward", {"ticket_id": ticket_id, "body": body})

@mcp.tool()
async def freshdesk_reply_ticket(ticket_id: str, body: str) -> str:
    """Reply to a ticket in Freshdesk"""
    return await adapters['freshdesk'].execute_tool("reply_ticket", {"ticket_id": ticket_id, "body": body})

@mcp.tool()
async def freshdesk_toggle_timer(time_entry_id: str) -> str:
    """Toggle timer for a time entry in Freshdesk"""
    return await adapters['freshdesk'].execute_tool("toggle_timer", {"id": time_entry_id})

@mcp.tool()
async def freshdesk_get_associated_tickets(contact_id: str) -> str:
    """Get tickets associated with a contact in Freshdesk"""
    return await adapters['freshdesk'].execute_tool("get_associated_tickets", {"contact_id": contact_id})

@mcp.tool()
async def freshdesk_create_child_ticket(parent_ticket_id: str, name: str, email: str, subject: str, description: str) -> str:
    """Create a child ticket for an existing ticket in Freshdesk"""
    return await adapters['freshdesk'].execute_tool("create_child_ticket", {"parent_ticket_id": parent_ticket_id, "name": name, "email": email, "subject": subject, "description": description})

@mcp.tool()
async def freshdesk_create_ticket_with_attachments(name: str, email: str, subject: str, description: str, attachments: str) -> str:
    """Create a ticket with file attachments in Freshdesk"""
    return await adapters['freshdesk'].execute_tool("create_ticket_with_attachments", {"name": name, "email": email, "subject": subject, "description": description, "attachments": attachments})

@mcp.tool()
async def freshdesk_create_contact_with_avatar(name: str, email: str, avatar_url: str) -> str:
    """Create a contact with avatar in Freshdesk"""
    return await adapters['freshdesk'].execute_tool("create_contact_with_avatar", {"name": name, "email": email, "avatar_url": avatar_url})

@mcp.tool()
async def freshdesk_list_comments(ticket_id: str, per_page: int = 10, page: int = 1) -> str:
    """List all comments for a ticket in Freshdesk"""
    return await adapters['freshdesk'].execute_tool("list_comments", {"ticket_id": ticket_id, "per_page": per_page, "page": page})

@mcp.tool()
async def freshdesk_create_tracker(name: str, description: str = None) -> str:
    """Create a new tracker in Freshdesk"""
    params = {"name": name}
    if description: params["description"] = description
    return await adapters['freshdesk'].execute_tool("create_tracker", params)

# =============================================================================
# STATIC TOOL DEFINITIONS - INTERCOM (Core Tools)
# =============================================================================

# Conversation Management
@mcp.tool()
async def intercom_list_conversations(per_page: int = 10, page: int = 1) -> str:
    """List all conversations from Intercom"""
    return await adapters['intercom'].execute_tool("list_conversations", {"per_page": per_page, "page": page})

@mcp.tool()
async def intercom_create_conversation(contact_id: str, message: str, message_type: str = "comment") -> str:
    """Create a new conversation in Intercom"""
    params = {"contact_id": contact_id, "message": message, "message_type": message_type}
    return await adapters['intercom'].execute_tool("create_conversation", params)

@mcp.tool()
async def intercom_view_conversation(conversation_id: str) -> str:
    """Retrieve a specific conversation by ID from Intercom"""
    return await adapters['intercom'].execute_tool("view_conversation", {"id": conversation_id})

@mcp.tool()
async def intercom_reply_conversation(conversation_id: str, message: str, message_type: str = "comment") -> str:
    """Reply to a conversation in Intercom"""
    params = {"id": conversation_id, "message": message, "message_type": message_type}
    return await adapters['intercom'].execute_tool("reply_conversation", params)

@mcp.tool()
async def intercom_close_conversation(conversation_id: str) -> str:
    """Close a conversation in Intercom"""
    return await adapters['intercom'].execute_tool("close_conversation", {"id": conversation_id})

@mcp.tool()
async def intercom_search_conversations(query: str, per_page: int = 10) -> str:
    """Search conversations in Intercom"""
    return await adapters['intercom'].execute_tool("search_conversations", {"query": query, "per_page": per_page})

# Contact Management
@mcp.tool()
async def intercom_list_contacts(per_page: int = 10, page: int = 1) -> str:
    """List all contacts from Intercom"""
    return await adapters['intercom'].execute_tool("list_contacts", {"per_page": per_page, "page": page})

@mcp.tool()
async def intercom_create_contact(email: str, name: str = None, phone: str = None) -> str:
    """Create a new contact in Intercom"""
    params = {"email": email}
    if name: params["name"] = name
    if phone: params["phone"] = phone
    return await adapters['intercom'].execute_tool("create_contact", params)

@mcp.tool()
async def intercom_view_contact(contact_id: str) -> str:
    """Retrieve a specific contact by ID from Intercom"""
    return await adapters['intercom'].execute_tool("view_contact", {"id": contact_id})

@mcp.tool()
async def intercom_update_contact(contact_id: str, name: str = None, email: str = None, phone: str = None) -> str:
    """Update an existing contact in Intercom"""
    params = {"id": contact_id}
    if name: params["name"] = name
    if email: params["email"] = email
    if phone: params["phone"] = phone
    return await adapters['intercom'].execute_tool("update_contact", params)

@mcp.tool()
async def intercom_delete_contact(contact_id: str) -> str:
    """Delete a contact from Intercom"""
    return await adapters['intercom'].execute_tool("delete_contact", {"id": contact_id})

@mcp.tool()
async def intercom_search_contacts(query: str, per_page: int = 10) -> str:
    """Search contacts in Intercom"""
    return await adapters['intercom'].execute_tool("search_contacts", {"query": query, "per_page": per_page})

# Company Management
@mcp.tool()
async def intercom_list_companies(per_page: int = 10, page: int = 1) -> str:
    """List all companies from Intercom"""
    return await adapters['intercom'].execute_tool("list_companies", {"per_page": per_page, "page": page})

@mcp.tool()
async def intercom_create_company(name: str, company_id: str, website: str = None, industry: str = None) -> str:
    """Create a new company in Intercom"""
    params = {"name": name, "company_id": company_id}
    if website: params["website"] = website
    if industry: params["industry"] = industry
    return await adapters['intercom'].execute_tool("create_company", params)

@mcp.tool()
async def intercom_view_company(company_id: str) -> str:
    """Retrieve a specific company by ID from Intercom"""
    return await adapters['intercom'].execute_tool("view_company", {"id": company_id})

# Admin Management
@mcp.tool()
async def intercom_list_admins() -> str:
    """List all admins from Intercom"""
    return await adapters['intercom'].execute_tool("list_admins", {})

@mcp.tool()
async def intercom_retrieve_admin(admin_id: str) -> str:
    """Retrieve a specific admin by ID from Intercom"""
    return await adapters['intercom'].execute_tool("retrieve_admin", {"id": admin_id})

@mcp.tool()
async def intercom_set_admin_away(admin_id: str, away_mode_enabled: bool = True) -> str:
    """Set admin away status in Intercom"""
    return await adapters['intercom'].execute_tool("set_admin_away", {"id": admin_id, "away_mode_enabled": away_mode_enabled})

@mcp.tool()
async def intercom_list_away_reasons() -> str:
    """List all away reasons from Intercom"""
    return await adapters['intercom'].execute_tool("list_away_reasons", {})

@mcp.tool()
async def intercom_get_team_permissions(admin_id: str) -> str:
    """Get team permissions for an admin in Intercom"""
    return await adapters['intercom'].execute_tool("get_team_permissions", {"id": admin_id})

@mcp.tool()
async def intercom_list_admin_activities(admin_id: str, per_page: int = 10, page: int = 1) -> str:
    """List admin activities from Intercom"""
    return await adapters['intercom'].execute_tool("list_admin_activities", {"admin_id": admin_id, "per_page": per_page, "page": page})

# Message Management
@mcp.tool()
async def intercom_list_messages(conversation_id: str, per_page: int = 10, page: int = 1) -> str:
    """List all messages from a conversation in Intercom"""
    return await adapters['intercom'].execute_tool("list_messages", {"conversation_id": conversation_id, "per_page": per_page, "page": page})

@mcp.tool()
async def intercom_create_message(conversation_id: str, message_type: str, body: str) -> str:
    """Create a message in a conversation in Intercom"""
    return await adapters['intercom'].execute_tool("create_message", {"conversation_id": conversation_id, "message_type": message_type, "body": body})

@mcp.tool()
async def intercom_reply_to_message(conversation_id: str, message: str, message_type: str = "comment") -> str:
    """Reply to a message in Intercom"""
    return await adapters['intercom'].execute_tool("reply_to_message", {"conversation_id": conversation_id, "message": message, "message_type": message_type})

@mcp.tool()
async def intercom_email_message(to_email: str, subject: str, body: str) -> str:
    """Send an email message via Intercom"""
    return await adapters['intercom'].execute_tool("email_message", {"to_email": to_email, "subject": subject, "body": body})

@mcp.tool()
async def intercom_group_message(user_ids: str, message: str) -> str:
    """Send a group message in Intercom"""
    return await adapters['intercom'].execute_tool("group_message", {"user_ids": user_ids, "message": message})

@mcp.tool()
async def intercom_message_attachments(message_id: str) -> str:
    """Get attachments for a message in Intercom"""
    return await adapters['intercom'].execute_tool("message_attachments", {"id": message_id})

@mcp.tool()
async def intercom_attach_file(conversation_id: str, file_url: str) -> str:
    """Attach a file to a conversation in Intercom"""
    return await adapters['intercom'].execute_tool("attach_file", {"conversation_id": conversation_id, "file_url": file_url})

# Conversation Actions
@mcp.tool()
async def intercom_assign_conversation(conversation_id: str, admin_id: str) -> str:
    """Assign a conversation to an admin in Intercom"""
    return await adapters['intercom'].execute_tool("assign_conversation", {"conversation_id": conversation_id, "admin_id": admin_id})

@mcp.tool()
async def intercom_open_conversation(conversation_id: str) -> str:
    """Open a conversation in Intercom"""
    return await adapters['intercom'].execute_tool("open_conversation", {"id": conversation_id})

@mcp.tool()
async def intercom_snooze_conversation(conversation_id: str, snooze_until: str) -> str:
    """Snooze a conversation in Intercom"""
    return await adapters['intercom'].execute_tool("snooze_conversation", {"conversation_id": conversation_id, "snooze_until": snooze_until})

@mcp.tool()
async def intercom_list_conversation_parts(conversation_id: str, per_page: int = 10, page: int = 1) -> str:
    """List conversation parts from Intercom"""
    return await adapters['intercom'].execute_tool("list_conversation_parts", {"conversation_id": conversation_id, "per_page": per_page, "page": page})

@mcp.tool()
async def intercom_redact_conversation_part(conversation_id: str, part_id: str) -> str:
    """Redact a conversation part in Intercom"""
    return await adapters['intercom'].execute_tool("redact_conversation_part", {"conversation_id": conversation_id, "part_id": part_id})

@mcp.tool()
async def intercom_customer_initiated_conversation(contact_id: str, message: str) -> str:
    """Create a customer-initiated conversation in Intercom"""
    return await adapters['intercom'].execute_tool("customer_initiated_conversation", {"contact_id": contact_id, "message": message})

@mcp.tool()
async def intercom_admin_initiated_conversation(admin_id: str, contact_id: str, message: str) -> str:
    """Create an admin-initiated conversation in Intercom"""
    return await adapters['intercom'].execute_tool("admin_initiated_conversation", {"admin_id": admin_id, "contact_id": contact_id, "message": message})

@mcp.tool()
async def intercom_view_admin(admin_id: str) -> str:
    """Retrieve a specific admin by ID from Intercom"""
    return await adapters['intercom'].execute_tool("view_admin", {"id": admin_id})

# Segment Management
@mcp.tool()
async def intercom_list_segments() -> str:
    """List all segments from Intercom"""
    return await adapters['intercom'].execute_tool("list_segments", {})

@mcp.tool()
async def intercom_view_segment(segment_id: str) -> str:
    """Retrieve a specific segment by ID from Intercom"""
    return await adapters['intercom'].execute_tool("view_segment", {"id": segment_id})

@mcp.tool()
async def intercom_create_segment(name: str, conditions: str) -> str:
    """Create a new segment in Intercom"""
    return await adapters['intercom'].execute_tool("create_segment", {"name": name, "conditions": conditions})

@mcp.tool()
async def intercom_update_segment(segment_id: str, name: str = None, conditions: str = None) -> str:
    """Update a segment in Intercom"""
    params = {"id": segment_id}
    if name: params["name"] = name
    if conditions: params["conditions"] = conditions
    return await adapters['intercom'].execute_tool("update_segment", params)

@mcp.tool()
async def intercom_delete_segment(segment_id: str) -> str:
    """Delete a segment from Intercom"""
    return await adapters['intercom'].execute_tool("delete_segment", {"id": segment_id})

# Tag Management
@mcp.tool()
async def intercom_list_tags() -> str:
    """List all tags from Intercom"""
    return await adapters['intercom'].execute_tool("list_tags", {})

@mcp.tool()
async def intercom_create_tag(name: str) -> str:
    """Create a new tag in Intercom"""
    return await adapters['intercom'].execute_tool("create_tag", {"name": name})

@mcp.tool()
async def intercom_delete_tag(tag_id: str) -> str:
    """Delete a tag from Intercom"""
    return await adapters['intercom'].execute_tool("delete_tag", {"id": tag_id})

@mcp.tool()
async def intercom_tag_contact(contact_id: str, tag_id: str) -> str:
    """Tag a contact in Intercom"""
    return await adapters['intercom'].execute_tool("tag_contact", {"contact_id": contact_id, "tag_id": tag_id})

@mcp.tool()
async def intercom_untag_contact(contact_id: str, tag_id: str) -> str:
    """Remove a tag from a contact in Intercom"""
    return await adapters['intercom'].execute_tool("untag_contact", {"contact_id": contact_id, "tag_id": tag_id})

@mcp.tool()
async def intercom_tag_conversation(conversation_id: str, tag_id: str) -> str:
    """Tag a conversation in Intercom"""
    return await adapters['intercom'].execute_tool("tag_conversation", {"conversation_id": conversation_id, "tag_id": tag_id})

@mcp.tool()
async def intercom_untag_conversation(conversation_id: str, tag_id: str) -> str:
    """Remove a tag from a conversation in Intercom"""
    return await adapters['intercom'].execute_tool("untag_conversation", {"conversation_id": conversation_id, "tag_id": tag_id})

# Team Management
@mcp.tool()
async def intercom_list_teams() -> str:
    """List all teams from Intercom"""
    return await adapters['intercom'].execute_tool("list_teams", {})

@mcp.tool()
async def intercom_view_team(team_id: str) -> str:
    """Retrieve a specific team by ID from Intercom"""
    return await adapters['intercom'].execute_tool("view_team", {"id": team_id})

@mcp.tool()
async def intercom_create_team(name: str) -> str:
    """Create a new team in Intercom"""
    return await adapters['intercom'].execute_tool("create_team", {"name": name})

@mcp.tool()
async def intercom_update_team(team_id: str, name: str) -> str:
    """Update a team in Intercom"""
    return await adapters['intercom'].execute_tool("update_team", {"id": team_id, "name": name})

@mcp.tool()
async def intercom_delete_team(team_id: str) -> str:
    """Delete a team from Intercom"""
    return await adapters['intercom'].execute_tool("delete_team", {"id": team_id})

# Event Management
@mcp.tool()
async def intercom_list_events(contact_id: str, per_page: int = 10, page: int = 1) -> str:
    """List events for a contact from Intercom"""
    return await adapters['intercom'].execute_tool("list_events", {"contact_id": contact_id, "per_page": per_page, "page": page})

@mcp.tool()
async def intercom_create_event(contact_id: str, event_name: str, metadata: str = None) -> str:
    """Create an event for a contact in Intercom"""
    params = {"contact_id": contact_id, "event_name": event_name}
    if metadata: params["metadata"] = metadata
    return await adapters['intercom'].execute_tool("create_event", params)

@mcp.tool()
async def intercom_track_event(contact_id: str, event_name: str, created_at: str = None, metadata: str = None) -> str:
    """Track an event for a contact in Intercom"""
    params = {"contact_id": contact_id, "event_name": event_name}
    if created_at: params["created_at"] = created_at
    if metadata: params["metadata"] = metadata
    return await adapters['intercom'].execute_tool("track_event", params)

# Data Attributes
@mcp.tool()
async def intercom_list_data_attributes() -> str:
    """List all data attributes from Intercom"""
    return await adapters['intercom'].execute_tool("list_data_attributes", {})

@mcp.tool()
async def intercom_create_data_attribute(name: str, model: str, data_type: str) -> str:
    """Create a data attribute in Intercom"""
    return await adapters['intercom'].execute_tool("create_data_attribute", {"name": name, "model": model, "data_type": data_type})

@mcp.tool()
async def intercom_update_data_attribute(data_attribute_id: str, name: str = None, description: str = None) -> str:
    """Update a data attribute in Intercom"""
    params = {"id": data_attribute_id}
    if name: params["name"] = name
    if description: params["description"] = description
    return await adapters['intercom'].execute_tool("update_data_attribute", params)

# Article Management
@mcp.tool()
async def intercom_list_articles() -> str:
    """List all articles from Intercom"""
    return await adapters['intercom'].execute_tool("list_articles", {})

@mcp.tool()
async def intercom_view_article(article_id: str) -> str:
    """Retrieve a specific article by ID from Intercom"""
    return await adapters['intercom'].execute_tool("view_article", {"id": article_id})

@mcp.tool()
async def intercom_create_article(title: str, body: str, author_id: str) -> str:
    """Create a new article in Intercom"""
    return await adapters['intercom'].execute_tool("create_article", {"title": title, "body": body, "author_id": author_id})

@mcp.tool()
async def intercom_update_article(article_id: str, title: str = None, body: str = None) -> str:
    """Update an article in Intercom"""
    params = {"id": article_id}
    if title: params["title"] = title
    if body: params["body"] = body
    return await adapters['intercom'].execute_tool("update_article", params)

@mcp.tool()
async def intercom_delete_article(article_id: str) -> str:
    """Delete an article from Intercom"""
    return await adapters['intercom'].execute_tool("delete_article", {"id": article_id})

# Collection Management
@mcp.tool()
async def intercom_list_collections() -> str:
    """List all collections from Intercom"""
    return await adapters['intercom'].execute_tool("list_collections", {})

@mcp.tool()
async def intercom_view_collection(collection_id: str) -> str:
    """Retrieve a specific collection by ID from Intercom"""
    return await adapters['intercom'].execute_tool("view_collection", {"id": collection_id})

@mcp.tool()
async def intercom_create_collection(name: str, description: str = None) -> str:
    """Create a new collection in Intercom"""
    params = {"name": name}
    if description: params["description"] = description
    return await adapters['intercom'].execute_tool("create_collection", params)

@mcp.tool()
async def intercom_update_collection(collection_id: str, name: str = None, description: str = None) -> str:
    """Update a collection in Intercom"""
    params = {"id": collection_id}
    if name: params["name"] = name
    if description: params["description"] = description
    return await adapters['intercom'].execute_tool("update_collection", params)

@mcp.tool()
async def intercom_delete_collection(collection_id: str) -> str:
    """Delete a collection from Intercom"""
    return await adapters['intercom'].execute_tool("delete_collection", {"id": collection_id})

# Note Management
@mcp.tool()
async def intercom_list_notes(contact_id: str) -> str:
    """List notes for a contact from Intercom"""
    return await adapters['intercom'].execute_tool("list_notes", {"contact_id": contact_id})

@mcp.tool()
async def intercom_create_note(contact_id: str, body: str) -> str:
    """Create a note for a contact in Intercom"""
    return await adapters['intercom'].execute_tool("create_note", {"contact_id": contact_id, "body": body})

@mcp.tool()
async def intercom_view_note(note_id: str) -> str:
    """Retrieve a specific note by ID from Intercom"""
    return await adapters['intercom'].execute_tool("view_note", {"id": note_id})

# Subscription Management
@mcp.tool()
async def intercom_list_subscription_types() -> str:
    """List all subscription types from Intercom"""
    return await adapters['intercom'].execute_tool("list_subscription_types", {})

@mcp.tool()
async def intercom_create_subscription(contact_id: str, subscription_type_id: str) -> str:
    """Create a subscription for a contact in Intercom"""
    return await adapters['intercom'].execute_tool("create_subscription", {"contact_id": contact_id, "subscription_type_id": subscription_type_id})

@mcp.tool()
async def intercom_delete_subscription(contact_id: str, subscription_type_id: str) -> str:
    """Delete a subscription for a contact in Intercom"""
    return await adapters['intercom'].execute_tool("delete_subscription", {"contact_id": contact_id, "subscription_type_id": subscription_type_id})

# Visitor Management
@mcp.tool()
async def intercom_list_visitors(per_page: int = 10, page: int = 1) -> str:
    """List all visitors from Intercom"""
    return await adapters['intercom'].execute_tool("list_visitors", {"per_page": per_page, "page": page})

@mcp.tool()
async def intercom_view_visitor(visitor_id: str) -> str:
    """Retrieve a specific visitor by ID from Intercom"""
    return await adapters['intercom'].execute_tool("view_visitor", {"id": visitor_id})

@mcp.tool()
async def intercom_update_visitor(visitor_id: str, name: str = None, email: str = None) -> str:
    """Update a visitor in Intercom"""
    params = {"id": visitor_id}
    if name: params["name"] = name
    if email: params["email"] = email
    return await adapters['intercom'].execute_tool("update_visitor", params)

@mcp.tool()
async def intercom_convert_visitor(visitor_id: str, contact_id: str = None) -> str:
    """Convert a visitor to a contact in Intercom"""
    params = {"visitor_id": visitor_id}
    if contact_id: params["contact_id"] = contact_id
    return await adapters['intercom'].execute_tool("convert_visitor", params)

# Count and Statistics
@mcp.tool()
async def intercom_count_conversations() -> str:
    """Get conversation count from Intercom"""
    return await adapters['intercom'].execute_tool("count_conversations", {})

@mcp.tool()
async def intercom_count_contacts() -> str:
    """Get contact count from Intercom"""
    return await adapters['intercom'].execute_tool("count_contacts", {})

@mcp.tool()
async def intercom_count_companies() -> str:
    """Get company count from Intercom"""
    return await adapters['intercom'].execute_tool("count_companies", {})

@mcp.tool()
async def intercom_count_admins() -> str:
    """Get admin count from Intercom"""
    return await adapters['intercom'].execute_tool("count_admins", {})

# Search Operations
@mcp.tool()
async def intercom_search_contacts(query: str, per_page: int = 10, page: int = 1) -> str:
    """Search contacts in Intercom"""
    return await adapters['intercom'].execute_tool("search_contacts", {"query": query, "per_page": per_page, "page": page})

@mcp.tool()
async def intercom_search_conversations(query: str, per_page: int = 10, page: int = 1) -> str:
    """Search conversations in Intercom"""
    return await adapters['intercom'].execute_tool("search_conversations", {"query": query, "per_page": per_page, "page": page})

@mcp.tool()
async def intercom_search_companies(query: str, per_page: int = 10, page: int = 1) -> str:
    """Search companies in Intercom"""
    return await adapters['intercom'].execute_tool("search_companies", {"query": query, "per_page": per_page, "page": page})

# Export Operations
@mcp.tool()
async def intercom_export_contacts(segment_id: str = None) -> str:
    """Export contacts from Intercom"""
    params = {}
    if segment_id: params["segment_id"] = segment_id
    return await adapters['intercom'].execute_tool("export_contacts", params)

@mcp.tool()
async def intercom_export_conversations(start_time: str, end_time: str) -> str:
    """Export conversations from Intercom"""
    return await adapters['intercom'].execute_tool("export_conversations", {"start_time": start_time, "end_time": end_time})

# Bulk Operations
@mcp.tool()
async def intercom_bulk_create_contacts(contacts_data: str) -> str:
    """Bulk create contacts in Intercom"""
    return await adapters['intercom'].execute_tool("bulk_create_contacts", {"contacts_data": contacts_data})

@mcp.tool()
async def intercom_bulk_update_contacts(contacts_data: str) -> str:
    """Bulk update contacts in Intercom"""
    return await adapters['intercom'].execute_tool("bulk_update_contacts", {"contacts_data": contacts_data})

@mcp.tool()
async def intercom_bulk_delete_contacts(contact_ids: str) -> str:
    """Bulk delete contacts in Intercom"""
    return await adapters['intercom'].execute_tool("bulk_delete_contacts", {"contact_ids": contact_ids})

# =============================================================================
# REGISTRATION FUNCTION (SIMPLIFIED)
# =============================================================================

def register_adapter_tools():
    """Static tools are automatically registered via @mcp.tool() decorators"""
    logger.info("📋 Static tool registration complete via decorators")
    
    # Count registered tools
    if hasattr(mcp, '_tool_manager') and hasattr(mcp._tool_manager, '_tools'):
        total_tools = len(mcp._tool_manager._tools)
        logger.info(f"🔧 Total Tools Registered: {total_tools}")
    else:
        logger.info("🔧 Tool count unavailable")

# =============================================================================
# RESOURCES - Configuration and Documentation
# =============================================================================

@mcp.resource("config://server")
def get_server_config() -> str:
    """Server configuration and environment details"""
    config = {
        "server_name": "Aura MCP Unified Server",
        "version": "1.0.0",
        "transport": "streamable-http",
        "ports": {
            "mcp_server": MCPServerConfig.MCP_SERVER_PORT,
            "backend_proxy": MCPServerConfig.BACKEND_PROXY_PORT,
            "react_client": MCPServerConfig.REACT_CLIENT_PORT,
            "freshdesk_webhook": MCPServerConfig.FRESHDESK_WEBHOOK_PORT,
            "intercom_webhook": MCPServerConfig.INTERCOM_WEBHOOK_PORT,
            "rate_limiter": MCPServerConfig.RATE_LIMITER_PORT
        },
        "active_adapters": list(active_adapters.keys()),
        "integrations": {
            "freshdesk": {
                "domain": MCPServerConfig.FRESHDESK_DOMAIN,
                "api_configured": bool(MCPServerConfig.FRESHDESK_API_KEY),
                "tools_available": len(freshdesk_adapter.all_tools) if freshdesk_adapter else 0
            },
            "intercom": {
                "api_configured": bool(MCPServerConfig.INTERCOM_ACCESS_TOKEN),
                "tools_available": len(intercom_adapter.all_tools) if intercom_adapter else 0
            },
            "postgresql": {
                "database": MCPServerConfig.POSTGRES_DB,
                "host": MCPServerConfig.POSTGRES_HOST,
                "configured": bool(MCPServerConfig.POSTGRES_USER)
            }
        },
        "total_tools_available": sum(len(adapter.all_tools) for adapter in active_adapters.values()) + 5
    }
    return json.dumps(config, indent=2)

@mcp.resource("docs://tools")
def get_tools_documentation() -> str:
    """Complete tools documentation for all integrated platforms"""
    docs = {
        "title": "Aura MCP Unified Server - API Tools Documentation",
        "platforms": {},
        "unified_features": [
            "health_check", "unified_search", "get_customer_journey",
            "list_platform_tools", "get_rate_limit_status"
        ],
        "total_tools": 0
    }
    
    for platform, adapter in active_adapters.items():
        platform_docs = {
            "total_tools": len(adapter.get_tools()),
            "rate_limit": adapter.rate_limiter.limit if hasattr(adapter, 'rate_limiter') else "unknown",
            "categories": {},
            "tools": []
        }
        
        for tool in adapter.get_tools():
            category = tool.get("category", "general")
            if category not in platform_docs["categories"]:
                platform_docs["categories"][category] = []
            
            platform_docs["categories"][category].append({
                "name": tool["name"],
                "description": tool.get("description", ""),
                "parameters": tool.get("parameters", {})
            })
            
            platform_docs["tools"].append(tool["name"])
        
        docs["platforms"][platform] = platform_docs
        docs["total_tools"] += len(adapter.all_tools)
    
    return json.dumps(docs, indent=2)

# =============================================================================
# MAIN SERVER FUNCTION
# =============================================================================

async def main():
    """Main server startup function"""
    try:
        logger.info("🚀 Starting Aura MCP Unified Server...")
        
        # Validate configuration
        MCPServerConfig.validate()
        
        # Initialize adapters
        initialization_success = await initialize_adapters()
        
        # Only proceed if we have active adapters
        if not initialization_success or not active_adapters:
            logger.error("❌ No active adapters found. Check your configuration and logs.")
            # Wait a bit to allow logs to be flushed
            await asyncio.sleep(1)
            return
        
        # Register dynamic tools from adapters - DISABLED (using static decorators instead)
        logger.info("🛠️  Static tools registered via @mcp.tool() decorators")
        # register_adapter_tools()  # Disabled - using static decorators
        
        # Log startup information
        total_tools = 0
        for platform, adapter in active_adapters.items():
            if hasattr(adapter, 'all_tools'):
                try:
                    tools = list(adapter.all_tools.keys())
                    tool_count = len(tools)
                    total_tools += tool_count
                    logger.info(f"🔧 {platform.title()} registered {tool_count} tools")
                except Exception as e:
                    logger.error(f"❌ Failed to get tools from {platform}: {e}")
        
        # Add core tools
        total_tools += 5  # Core tools: health_check, unified_search, get_customer_journey, list_platform_tools, get_rate_limit_status
        
        logger.info(f"📡 Server: Aura MCP Unified Server v1.0.0")
        logger.info(f"🚢 Transport: SSE")
        logger.info(f"🔌 Port: {MCPServerConfig.MCP_SERVER_PORT}")
        logger.info(f"🢂 Active Platforms: {', '.join(active_adapters.keys())}")
        logger.info(f"🔧 Total Tools Available: {total_tools}")
        logger.info(f"⚡ Rate Limits: Freshdesk={MCPServerConfig.FRESHDESK_RATE_LIMIT}/min, Intercom={MCPServerConfig.INTERCOM_RATE_LIMIT}/min")
        logger.info(f"🏥 Health Endpoint: http://localhost:{MCPServerConfig.MCP_SERVER_PORT}/health")
        
        # Log adapter-specific information
        if freshdesk_adapter:
            tools = len(freshdesk_adapter.all_tools) if freshdesk_adapter else 'not available'
            logger.info(f"🎫 Freshdesk: {MCPServerConfig.FRESHDESK_DOMAIN} ({tools} tools)")
        
        if intercom_adapter:
            tools = len(intercom_adapter.all_tools) if intercom_adapter else 'not available'
            logger.info(f"💬 Intercom: Configured ({tools} tools)")
        
        logger.info("✅ Server initialization complete - ready for connections!")
        
        # Start the MCP server with SSE transport
        await mcp.run_async(
            transport="sse",
            host="0.0.0.0",  # Allow connections from Docker network
            port=MCPServerConfig.MCP_SERVER_PORT
        )
        
    except Exception as e:
        logger.error(f"❌ Server startup failed: {e}")
        raise

if __name__ == "__main__":
    # Ensure required directories exist
    os.makedirs("/app/logs", exist_ok=True)
    
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("🛑 Server shutdown requested by user")
    except Exception as e:
        logger.error(f"💥 Server crashed: {e}")
        sys.exit(1)