"""
Gemini Tools Schema Generator
Converts MCP tool definitions to Gemini function calling schemas
"""

import json
import asyncio
from typing import List, Dict, Any, Optional
from mcp.client.session import ClientSession
from mcp.client.sse import sse_client
import logging

logger = logging.getLogger(__name__)

class GeminiToolsGenerator:
    def __init__(self, mcp_server_url: str = "http://mcp-unified-server:9000"):
        self.mcp_server_url = mcp_server_url
        self.mcp_client = None
        self.tool_mapping = {}
        
    async def get_mcp_tools(self) -> List[Dict]:
        """Fetch all available MCP tools using MCP session protocol"""
        all_tools = []
        
        logger.info("🔍 Starting MCP tool fetching via MCP session...")
        
        try:
            # Use MCP session to call list_platform_tools directly
            data = None
            async with sse_client(f"{self.mcp_server_url}/sse") as (read, write):
                async with ClientSession(read, write) as session:
                    await session.initialize()
                    
                    # Call list_platform_tools MCP tool directly
                    result = await session.call_tool('list_platform_tools', {})
                    
                    if hasattr(result, 'content') and result.content:
                        content = result.content[0]
                        if hasattr(content, 'text'):
                            import json
                            data = json.loads(content.text)
                    else:
                        logger.error("❌ No content returned from list_platform_tools")
                        return []
            
            # Process the data outside the async context managers to avoid cancellation
            if data:
                platforms = data.get('platforms', {})
                total_expected = data.get('total_tools', 0)
                
                logger.info(f"📊 MCP session shows {total_expected} total tools available")
                
                # Process each platform's tools
                for platform_name, platform_data in platforms.items():
                    platform_tools = platform_data.get('tools', [])
                    logger.info(f"📋 Processing {len(platform_tools)} tools from {platform_name}")
                    
                    for tool in platform_tools:
                        # Handle both string tool names and dict tool objects
                        if isinstance(tool, str):
                            tool_name = tool
                            actual_parameters = self._get_tool_parameters(platform_name, tool_name)
                        elif isinstance(tool, dict):
                            tool_name = tool.get('name')
                            actual_parameters = tool.get('parameters', {})
                        else:
                            continue
                            
                        if not tool_name:
                            continue
                        
                        # Determine platform from context
                        platform = platform_name if platform_name != 'unified_tools' else 'unified'
                        
                        tool_data = {
                            "name": tool_name,
                            "description": f"Execute {tool_name} tool" if isinstance(tool, str) else tool.get('description', f"Execute {tool_name} tool"),
                            "parameters": actual_parameters,
                            "platform": platform,
                            "tool_id": f"{platform}.{tool_name}" if platform != "unified" else tool_name,
                            "category": self._categorize_tool(tool_name)
                        }
                        all_tools.append(tool_data)
                
                # Process unified tools separately
                unified_tools = data.get('unified_tools', {}).get('tools', [])
                logger.info(f"📋 Processing {len(unified_tools)} unified tools")
                
                for tool_name in unified_tools:
                    # Get unified tool parameters
                    actual_parameters = self._get_unified_tool_parameters(tool_name)
                    
                    tool_data = {
                        "name": tool_name,
                        "description": f"Execute {tool_name} unified tool",
                        "parameters": actual_parameters,
                        "platform": "unified",
                        "tool_id": tool_name,
                        "category": self._categorize_tool(tool_name)
                    }
                    all_tools.append(tool_data)
            else:
                logger.error("❌ No data received from MCP session")
                return []
                        
        except Exception as e:
            logger.error(f"❌ Failed to fetch tools via MCP session: {type(e).__name__}: {e}")
            logger.error("🚨 No fallback available - MCP connection required")
            return []
        
        # Summary analysis
        logger.info(f"🎯 TOOL FETCHING SUMMARY:")
        logger.info(f"  📊 Total tools fetched: {len(all_tools)}")
        
        # Group by platform for analysis
        platform_counts = {}
        for tool in all_tools:
            platform = tool.get('platform', 'unknown')
            platform_counts[platform] = platform_counts.get(platform, 0) + 1
        
        for platform, count in platform_counts.items():
            logger.info(f"  - {platform}: {count} tools")
            
        logger.info(f"Fetched {len(all_tools)} MCP tools via direct API")
        return all_tools
    
    def _categorize_tool(self, tool_name: str) -> str:
        """Categorize tool based on its name"""
        if not isinstance(tool_name, str):
            return "unknown"
            
        tool_lower = tool_name.lower()
        if any(word in tool_lower for word in ['create', 'add', 'new']):
            return "create"
        elif any(word in tool_lower for word in ['list', 'get', 'view', 'search', 'find']):
            return "read"
        elif any(word in tool_lower for word in ['update', 'edit', 'modify']):
            return "update"
        elif any(word in tool_lower for word in ['delete', 'remove']):
            return "delete"
        else:
            return "action"
    
    
    def _get_unified_tool_description(self, tool_name: str) -> str:
        """Get description for unified tools"""
        descriptions = {
            "health_check": "Get comprehensive health status of the MCP server and all integrated platforms",
            "unified_search": "Search across multiple platforms simultaneously for customers, tickets, conversations, and articles",
            "get_customer_journey": "Get complete customer journey across all platforms",
            "list_platform_tools": "List all available tools from all connected platforms",
            "get_rate_limit_status": "Get current rate limit status for all integrated platforms"
        }
        return descriptions.get(tool_name, f"Execute {tool_name} tool")
    
    def _get_tool_description(self, platform: str, tool_name: str) -> str:
        """Get enhanced descriptions for platform tools with type safety"""
        if not isinstance(tool_name, str):
            return f"{platform} tool operation"
            
        tool_lower = tool_name.lower()
        
        # Enhanced descriptions for common tools
        if "ticket" in tool_lower:
            if "list" in tool_lower or "search" in tool_lower:
                return f"Search and retrieve {platform} support tickets with filters for status, priority, date, customer, etc."
            elif "create" in tool_lower:
                return f"Create a new support ticket in {platform} with customer details, subject, description, priority"
            elif "update" in tool_lower:
                return f"Update an existing {platform} support ticket with new status, priority, or notes"
            else:
                return f"Manage {platform} support tickets"
        
        elif "customer" in tool_lower or "contact" in tool_lower:
            if "list" in tool_lower or "search" in tool_lower:
                return f"Search {platform} customers/contacts by name, email, phone, company, or other criteria"
            elif "create" in tool_lower:
                return f"Create a new customer/contact record in {platform}"
            else:
                return f"Manage {platform} customer/contact data"
        
        elif "conversation" in tool_lower:
            if "list" in tool_lower or "search" in tool_lower:
                return f"Search {platform} conversations/chats by customer, date, status, or content"
            else:
                return f"Manage {platform} conversations"
        
        elif "company" in tool_lower:
            return f"Manage {platform} company/organization data"
        
        elif "agent" in tool_lower or "admin" in tool_lower:
            return f"Manage {platform} agents/administrators"
        
        else:
            return f"{platform.title()} operation: {tool_name.replace('_', ' ')}"
    
    async def _fetch_adapter_parameters(self, tool_name: str) -> Dict:
        """Fetch actual parameter schema from adapter configuration via MCP call"""
        try:
            # Call the MCP server to get tool configuration details
            async with sse_client(f"{self.mcp_server_url}/sse") as (read, write):
                async with ClientSession(read, write) as session:
                    await session.initialize()
                    
                    # Try to get tool details - some MCP servers support this
                    try:
                        # Use list_platform_tools to get detailed tool configs
                        result = await session.call_tool('list_platform_tools', {})
                        if hasattr(result, 'content') and result.content:
                            content = result.content[0]
                            if hasattr(content, 'text'):
                                import json
                                tool_configs = json.loads(content.text)
                                
                                # Find our tool in the configurations
                                for platform_tools in tool_configs.values():
                                    if isinstance(platform_tools, dict) and tool_name in platform_tools:
                                        tool_config = platform_tools[tool_name]
                                        return self._convert_adapter_config_to_schema(tool_config)
                    except:
                        pass  # Fall through to manual mapping
                    
                    # Manual mapping based on known adapter configurations
                    return self._get_known_adapter_parameters(tool_name)
                    
        except Exception as e:
            logger.warning(f"Failed to fetch adapter parameters for {tool_name}: {e}")
            return self._get_fallback_parameters(tool_name)
    
    def _convert_adapter_config_to_schema(self, tool_config: Dict) -> Dict:
        """Convert adapter tool config to parameter schema"""
        parameters = tool_config.get('parameters', [])
        required = tool_config.get('required', [])
        
        properties = {}
        for param in parameters:
            properties[param] = {
                'type': 'string',  # Default type
                'description': f'Parameter: {param}'
            }
            
            # Set specific types for known parameters
            if param in ['page', 'per_page', 'limit', 'id']:
                properties[param]['type'] = 'integer'
        
        return {
            'type': 'object',
            'properties': properties,
            'required': required
        }
    
    def _get_known_adapter_parameters(self, tool_name: str) -> Dict:
        """Get known parameter schemas for common adapter tools"""
        # Known Freshdesk tool parameters based on adapter configs
        freshdesk_params = {
            'freshdesk_list_tickets': {
                'type': 'object',
                'properties': {
                    'filter': {'type': 'string', 'description': 'Search filter criteria'},
                    'page': {'type': 'integer', 'description': 'Page number'},
                    'per_page': {'type': 'integer', 'description': 'Results per page'},
                    'order_by': {'type': 'string', 'description': 'Field to order by'},
                    'order_type': {'type': 'string', 'description': 'Order direction (asc/desc)'},
                    'updated_since': {'type': 'string', 'description': 'Filter by update date'},
                    'include': {'type': 'string', 'description': 'Additional data to include'}
                },
                'required': []
            },
            'freshdesk_list_contacts': {
                'type': 'object',
                'properties': {
                    'email': {'type': 'string', 'description': 'Contact email'},
                    'phone': {'type': 'string', 'description': 'Contact phone'},
                    'mobile': {'type': 'string', 'description': 'Contact mobile'},
                    'company_id': {'type': 'integer', 'description': 'Company ID'},
                    'view_id': {'type': 'integer', 'description': 'View ID'},
                    'state': {'type': 'string', 'description': 'Contact state'},
                    'page': {'type': 'integer', 'description': 'Page number'},
                    'per_page': {'type': 'integer', 'description': 'Results per page'}
                },
                'required': []
            },
            'intercom_list_conversations': {
                'type': 'object',
                'properties': {
                    'per_page': {'type': 'integer', 'description': 'Results per page'},
                    'starting_after': {'type': 'string', 'description': 'Pagination cursor'},
                    'display_as': {'type': 'string', 'description': 'Display format'},
                    'order': {'type': 'string', 'description': 'Sort order'}
                },
                'required': []
            }
        }
        
        if tool_name in freshdesk_params:
            return freshdesk_params[tool_name]
        
        # Fallback to generic parameters
        return self._get_fallback_parameters(tool_name)
    
    def _determine_platform(self, tool_name: str) -> str:
        """Determine platform from tool name"""
        tool_lower = tool_name.lower()
        if 'freshdesk' in tool_lower:
            return 'freshdesk'
        elif 'intercom' in tool_lower:
            return 'intercom'
        elif tool_name in ['health_check', 'unified_search', 'get_customer_journey', 'list_platform_tools', 'get_rate_limit_status']:
            return 'unified'
        else:
            # Try to infer from tool patterns
            if any(word in tool_lower for word in ['ticket', 'agent', 'group']):
                return 'freshdesk'
            elif any(word in tool_lower for word in ['conversation', 'admin']):
                return 'intercom'
            return 'unknown'
    
    def _get_fallback_parameters(self, tool_name: str) -> Dict:
        """Get fallback parameters when actual schema is unavailable"""
        tool_lower = tool_name.lower()
        
        # Use actual MCP parameter names instead of generic ones
        if "list" in tool_lower or "search" in tool_lower:
            if "ticket" in tool_lower:
                return {
                    "type": "object",
                    "properties": {
                        "filter": {"type": "string", "description": "Search filter criteria"},
                        "per_page": {"type": "integer", "description": "Number of results per page (default: 30)"},
                        "page": {"type": "integer", "description": "Page number (default: 1)"}
                    },
                    "required": []
                }
            elif "contact" in tool_lower:
                return {
                    "type": "object",
                    "properties": {
                        "email": {"type": "string", "description": "Contact email"},
                        "per_page": {"type": "integer", "description": "Number of results per page (default: 30)"},
                        "page": {"type": "integer", "description": "Page number (default: 1)"}
                    },
                    "required": []
                }
            elif "conversation" in tool_lower:
                return {
                    "type": "object",
                    "properties": {
                        "per_page": {"type": "integer", "description": "Number of results per page (default: 20)"},
                        "starting_after": {"type": "string", "description": "Cursor for pagination"}
                    },
                    "required": []
                }
        
        # Default fallback
        return {"type": "object", "properties": {}, "required": []}
    
    def _get_tool_parameters(self, platform: str, tool_name: str) -> Dict:
        """Get tool parameters based on platform and tool name"""
        if platform == "unified":
            return self._get_unified_tool_parameters(tool_name)
        elif platform in ["freshdesk", "intercom"]:
            return self._get_known_adapter_parameters(tool_name)
        else:
            return self._get_fallback_parameters(tool_name)
    
    def _get_unified_tool_parameters(self, tool_name: str) -> Dict:
        """Get parameters for unified tools"""
        parameters = {
            "health_check": {"type": "object", "properties": {}, "required": []},
            "unified_search": {
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "Search query"},
                    "platforms": {"type": "string", "description": "Platforms to search (default: all)"}
                },
                "required": ["query"]
            },
            "get_customer_journey": {
                "type": "object", 
                "properties": {
                    "identifier": {"type": "string", "description": "Customer identifier (email, ID, etc.)"},
                    "identifier_type": {"type": "string", "description": "Type of identifier (email, id, phone)"}
                },
                "required": ["identifier"]
            },
            "list_platform_tools": {"type": "object", "properties": {}, "required": []},
            "get_rate_limit_status": {"type": "object", "properties": {}, "required": []}
        }
        return parameters.get(tool_name, {"type": "object", "properties": {}, "required": []})
    
    def convert_to_gemini_function(self, mcp_tool: Dict):
        """Convert MCP tool definition to Gemini function schema"""
        tool_name = mcp_tool.get('name', 'unknown')
        tool_id = mcp_tool.get('tool_id', tool_name)
        platform = mcp_tool.get('platform', 'unknown')
        
        logger.info(f"🔄 Converting tool: {tool_name} (ID: {tool_id}, Platform: {platform})")
        
        try:
            import google.generativeai as genai
            
            # Validate required fields
            if not tool_name or not tool_id:
                logger.error(f"❌ FAILED - Missing required fields: name={tool_name}, tool_id={tool_id}")
                return None
            
            # Convert parameters to proper Gemini Schema format
            params_dict = mcp_tool.get("parameters", {})
            logger.debug(f"📋 Tool {tool_name} parameters: {params_dict}")
            
            # Create Schema object for Gemini
            properties = {}
            for prop_name, prop_def in params_dict.get("properties", {}).items():
                prop_type = prop_def.get("type", "string").upper()
                logger.debug(f"  - Property {prop_name}: type={prop_type}")
                
                # Map string types to Gemini enum values
                type_mapping = {
                    "STRING": genai.protos.Type.STRING,
                    "INTEGER": genai.protos.Type.INTEGER,
                    "NUMBER": genai.protos.Type.NUMBER,
                    "BOOLEAN": genai.protos.Type.BOOLEAN,
                    "OBJECT": genai.protos.Type.OBJECT,
                    "ARRAY": genai.protos.Type.ARRAY
                }
                
                if prop_type not in type_mapping:
                    logger.warning(f"⚠️  Unknown parameter type '{prop_type}' for {tool_name}.{prop_name}, defaulting to STRING")
                
                properties[prop_name] = genai.protos.Schema(
                    type=type_mapping.get(prop_type, genai.protos.Type.STRING),
                    description=prop_def.get("description", f"Parameter: {prop_name}")
                )
            
            parameters_schema = genai.protos.Schema(
                type=genai.protos.Type.OBJECT,
                properties=properties,
                required=params_dict.get("required", [])
            )
            
            # Build Gemini function declaration
            description = mcp_tool.get("description", f"Execute {tool_name} tool")
            if len(description) > 1024:
                logger.warning(f"⚠️  Description too long for {tool_name}, truncating from {len(description)} chars")
                description = description[:1021] + "..."
            
            gemini_function = genai.protos.FunctionDeclaration(
                name=tool_id,
                description=description,
                parameters=parameters_schema
            )
            
            # Store mapping for execution
            self.tool_mapping[tool_id] = {
                "platform": platform,
                "original_name": tool_name,
                "mcp_tool_name": tool_name if platform == "unified" else f"{platform}.{tool_name}"
            }
            
            logger.info(f"✅ SUCCESS - Converted {tool_name} with {len(properties)} parameters")
            return gemini_function
            
        except KeyError as e:
            logger.error(f"❌ FAILED - Missing key in tool {tool_name}: {e}")
            logger.debug(f"Tool data: {mcp_tool}")
            return None
        except Exception as e:
            logger.error(f"❌ FAILED - Exception converting tool {tool_name}: {type(e).__name__}: {e}")
            logger.debug(f"Tool data: {mcp_tool}")
            return None
    
    def _convert_parameters(self, mcp_params: Dict) -> Dict:
        """Convert MCP parameters to Gemini function parameters format"""
        if not mcp_params or mcp_params.get("type") != "object":
            return {"type": "object", "properties": {}, "required": []}
        
        gemini_params = {
            "type": "object",
            "properties": {},
            "required": mcp_params.get("required", [])
        }
        
        # Convert each property
        for prop_name, prop_def in mcp_params.get("properties", {}).items():
            gemini_params["properties"][prop_name] = {
                "type": prop_def.get("type", "string"),
                "description": prop_def.get("description", f"Parameter: {prop_name}")
            }
            
            # Add enum values if present
            if "enum" in prop_def:
                gemini_params["properties"][prop_name]["enum"] = prop_def["enum"]
        
        return gemini_params
    
    async def generate_all_functions(self):
        """Generate all Gemini functions from MCP tools"""
        mcp_tools = await self.get_mcp_tools()
        gemini_functions = []
        
        logger.info(f"🚀 Starting conversion of {len(mcp_tools)} MCP tools to Gemini functions")
        
        success_count = 0
        failure_count = 0
        failures_by_platform = {"freshdesk": 0, "intercom": 0, "unified": 0, "unknown": 0}
        failures_by_reason = {"missing_fields": 0, "key_error": 0, "schema_error": 0, "other": 0}
        
        for i, tool in enumerate(mcp_tools, 1):
            tool_name = tool.get('name', f'tool_{i}')
            platform = tool.get('platform', 'unknown')
            
            logger.info(f"📝 [{i}/{len(mcp_tools)}] Processing: {tool_name} ({platform})")
            
            gemini_func = self.convert_to_gemini_function(tool)
            if gemini_func:
                gemini_functions.append(gemini_func)
                success_count += 1
            else:
                failure_count += 1
                failures_by_platform[platform] = failures_by_platform.get(platform, 0) + 1
                
                # Categorize failure reason based on recent logs
                if not tool.get('name') or not tool.get('tool_id'):
                    failures_by_reason["missing_fields"] += 1
                elif 'KeyError' in str(tool):
                    failures_by_reason["key_error"] += 1
                else:
                    failures_by_reason["other"] += 1
        
        # Detailed summary logging
        logger.info(f"🎯 CONVERSION SUMMARY:")
        total_tools = len(mcp_tools)
        if total_tools > 0:
            logger.info(f"  ✅ Successful: {success_count}/{total_tools} ({success_count/total_tools*100:.1f}%)")
            logger.info(f"  ❌ Failed: {failure_count}/{total_tools} ({failure_count/total_tools*100:.1f}%)")
        else:
            logger.info(f"  ✅ Successful: {success_count}/0 (no tools to convert)")
            logger.info(f"  ❌ Failed: {failure_count}/0 (no tools to convert)")
        
        logger.info(f"📊 FAILURES BY PLATFORM:")
        for platform, count in failures_by_platform.items():
            if count > 0:
                logger.info(f"  - {platform}: {count} failures")
        
        logger.info(f"🔍 FAILURE REASONS:")
        for reason, count in failures_by_reason.items():
            if count > 0:
                logger.info(f"  - {reason}: {count} tools")
        
        logger.info(f"Generated {len(gemini_functions)} Gemini functions from {len(mcp_tools)} MCP tools")
        return gemini_functions
    
    def create_tool_mapping(self, mcp_tools: List[Dict]) -> Dict[str, str]:
        """Create mapping from Gemini function names to MCP tool names"""
        mapping = {}
        for tool in mcp_tools:
            tool_id = tool.get('tool_id', tool['name'])
            mapping[tool_id] = tool['name']
        return mapping

# Global instance
_generator = None

def get_generator() -> GeminiToolsGenerator:
    """Get singleton generator instance"""
    global _generator
    if _generator is None:
        _generator = GeminiToolsGenerator()
    return _generator

async def generate_all_functions():
    """Generate all Gemini functions"""
    generator = get_generator()
    return await generator.generate_all_functions()

async def create_tool_mapping() -> Dict[str, str]:
    """Create tool mapping"""
    generator = get_generator()
    mcp_tools = await generator.get_mcp_tools()
    return generator.create_tool_mapping(mcp_tools)
