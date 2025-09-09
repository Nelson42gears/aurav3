"""
Gemini Client with MCP Tool Integration
Enables natural language conversations with automatic MCP tool execution
"""

import os
import json
import asyncio
import logging
import time
from datetime import datetime
from typing import Dict, Any, Optional, List, AsyncGenerator
import google.generativeai as genai
from mcp.client.session import ClientSession
from mcp.client.sse import sse_client
import gemini_tools
from gemini_tools import generate_all_functions, create_tool_mapping

logger = logging.getLogger(__name__)

class ToolFilter:
    """Intelligent tool filtering to reduce Gemini timeout issues by limiting tools to 5-12 per query"""
    
    def __init__(self):
        self.keyword_categories = {
            'ticket': {
                'keywords': ['ticket', 'issue', 'problem', 'bug', 'support', 'case', 'incident', 'request', 'complaint', 'inquiry', 'freshdesk', 'list', 'show', 'get'],
                'max_tools': 12,
                'priority_tools': [
                    'list_tickets', 'search_tickets', 'get_ticket', 'create_ticket', 'update_ticket',
                    'freshdesk_list_tickets', 'freshdesk_search_tickets', 'freshdesk_get_ticket',
                    'freshdesk_create_ticket', 'freshdesk_update_ticket', 'freshdesk_delete_ticket',
                    'unified_search'
                ]
            },
            'customer': {
                'keywords': ['customer', 'contact', 'user', 'client', 'company', 'person', 'profile', 'account', 'organization', 'freshdesk', 'intercom', 'list', 'show', 'get', 'display'],
                'max_tools': 10,
                'priority_tools': [
                    'list_contacts', 'search_contacts', 'get_contact', 'create_contact', 'update_contact',
                    'list_companies', 'search_companies', 'get_company', 'create_company',
                    'unified_search', 'get_customer_journey'
                ]
            },
            'conversation': {
                'keywords': ['conversation', 'chat', 'message', 'talk', 'reply', 'discuss', 'communicate', 'dialogue', 'exchange', 'intercom', 'list', 'show', 'get'],
                'max_tools': 8,
                'priority_tools': [
                    'list_conversations', 'search_conversations', 'get_conversation', 'create_conversation',
                    'reply_conversation', 'assign_conversation', 'close_conversation', 'unified_search'
                ]
            },
            'search': {
                'keywords': ['search', 'find', 'lookup', 'query', 'locate', 'discover', 'filter', 'browse', 'explore', 'freshdesk', 'intercom', 'platform', 'list', 'show', 'display', 'get', 'fetch', 'retrieve'],
                'max_tools': 8,
                'priority_tools': [
                    'unified_search', 'search_tickets', 'search_contacts', 'search_conversations',
                    'search_companies', 'freshdesk_search_tickets', 'intercom_search_contacts',
                    'intercom_search_conversations'
                ]
            },
            'admin': {
                'keywords': ['admin', 'team', 'agent', 'staff', 'manage', 'configure', 'settings', 'permission', 'role'],
                'max_tools': 10,
                'priority_tools': [
                    'list_admins', 'get_admin', 'list_teams', 'get_team', 'list_agents',
                    'get_agent', 'set_admin_away', 'list_admin_activities', 'get_team_permissions',
                    'health_check'
                ]
            },
            'meta': {
                'keywords': ['tools', 'available', 'functions', 'features', 'capabilities', 'list', 'show', 'get', 'display', 'fetch', 'retrieve', 'freshdesk', 'intercom', 'platform'],
                'max_tools': 3,
                'priority_tools': [
                    'list_platform_tools', 'health_check', 'unified_search'
                ]
            },
            'article': {
                'keywords': ['article', 'knowledge', 'help', 'documentation', 'guide', 'faq', 'tutorial', 'manual', 'wiki'],
                'max_tools': 8,
                'priority_tools': [
                    'list_articles', 'search_articles', 'get_article', 'create_article', 'update_article',
                    'list_collections', 'get_collection', 'help_center_settings'
                ]
            },
            'note': {
                'keywords': ['note', 'comment', 'annotation', 'remark', 'memo', 'observation', 'feedback'],
                'max_tools': 6,
                'priority_tools': [
                    'list_notes', 'create_note', 'get_note', 'list_comments', 'create_comment',
                    'unified_search'
                ]
            },
            'tag': {
                'keywords': ['tag', 'segment', 'label', 'category', 'group', 'classification', 'organize'],
                'max_tools': 8,
                'priority_tools': [
                    'list_tags', 'create_tag', 'delete_tag', 'tag_objects', 'list_segments',
                    'create_segment', 'update_segment', 'delete_segment'
                ]
            },
            'event': {
                'keywords': ['event', 'activity', 'log', 'history', 'timeline', 'tracking', 'audit', 'record'],
                'max_tools': 6,
                'priority_tools': [
                    'list_events', 'create_event', 'event_summaries', 'event_metadata',
                    'list_admin_activities', 'get_activity_logs'
                ]
            },
            'status': {
                'keywords': ['status', 'priority', 'urgent', 'high', 'low', 'open', 'closed', 'pending', 'resolved'],
                'max_tools': 10,
                'priority_tools': [
                    'list_tickets', 'search_tickets', 'update_ticket', 'get_ticket',
                    'list_conversations', 'assign_conversation', 'close_conversation',
                    'set_admin_away', 'unified_search', 'health_check'
                ]
            },
            'email': {
                'keywords': ['email', 'notify', 'send', 'forward', 'alert', 'mail', 'notification', 'message'],
                'max_tools': 8,
                'priority_tools': [
                    'create_outbound_email', 'forward_ticket', 'reply_ticket', 'email_message',
                    'create_message', 'reply_to_message', 'create_conversation', 'unified_search'
                ]
            },
            'report': {
                'keywords': ['report', 'analytics', 'stats', 'metrics', 'dashboard', 'generate', 'analysis', 'summary', 'insights'],
                'max_tools': 8,
                'priority_tools': [
                    'event_summaries', 'event_metadata', 'list_admin_activities', 'get_activity_logs',
                    'help_center_settings', 'get_team_permissions', 'unified_search', 'health_check'
                ]
            },
            'export': {
                'keywords': ['export', 'download', 'backup', 'extract', 'save', 'dump', 'archive'],
                'max_tools': 6,
                'priority_tools': [
                    'list_tickets', 'list_contacts', 'list_conversations', 'list_articles',
                    'event_summaries', 'unified_search'
                ]
            },
            'import': {
                'keywords': ['import', 'upload', 'bulk', 'batch', 'load', 'create', 'add'],
                'max_tools': 8,
                'priority_tools': [
                    'create_ticket', 'create_contact', 'create_conversation', 'create_article',
                    'create_note', 'create_tag', 'create_segment', 'unified_search'
                ]
            },
            'time': {
                'keywords': ['time', 'timer', 'track', 'hours', 'billing', 'duration', 'schedule'],
                'max_tools': 6,
                'priority_tools': [
                    'list_events', 'create_event', 'event_summaries', 'list_admin_activities',
                    'get_activity_logs', 'unified_search'
                ]
            }
        }
        
        # Essential tools always included (fallback)
        self.essential_tools = [
            'health_check', 'unified_search', 'list_platform_tools', 
            'get_customer_journey', 'get_rate_limit_status'
        ]
    
    def filter_tools_by_query(self, query: str, all_tools: List[Dict]) -> List[Dict]:
        """Filter tools based on query keywords to reduce from 113 to 5-12 tools"""
        logger.info(f"🎯 TOOL FILTERING: Starting with {len(all_tools)} tools")
        logger.info(f"📝 TOOL FILTERING: Query = '{query}'")
        
        if not query or not all_tools:
            logger.info("⚠️ TOOL FILTERING: Empty query or tools, using essential tools")
            return self._get_essential_tools(all_tools)
        
        query_lower = query.lower()
        query_words = query_lower.split()
        logger.info(f"🔤 TOOL FILTERING: Query words = {query_words}")
        
        # Find matching category - prioritize meta category for tool discovery queries
        best_category = None
        best_score = 0
        
        logger.info("🔍 TOOL FILTERING: Checking keyword categories...")
        
        # Check meta category first for tool discovery queries
        meta_keywords = ['tools', 'available', 'functions', 'features', 'capabilities', 'list', 'show', 'get', 'display', 'fetch', 'retrieve']
        meta_matches = [keyword for keyword in meta_keywords if keyword in query_lower]
        logger.info(f"🔍 META CHECK: query='{query_lower}', keywords={meta_keywords[:5]}..., matches={meta_matches}")
        if meta_matches:
            logger.info(f"🎯 META QUERY DETECTED: matches = {meta_matches}")
            best_category = 'meta'
            best_score = len(meta_matches)
        else:
            # Regular category matching
            for category_name, category_data in self.keyword_categories.items():
                if category_name == 'meta':  # Skip meta since we already checked it
                    continue
                keywords = category_data['keywords']
                matches = [keyword for keyword in keywords if keyword in query_lower]
                score = len(matches)
                logger.info(f"📂 TOOL FILTERING: Category '{category_name}' -> keywords: {keywords[:3]}... -> matches: {matches} -> score: {score}")
                
                if score > best_score:
                    best_score = score
                    best_category = category_name
        
        logger.info(f"🏆 TOOL FILTERING: Best category = '{best_category}', score = {best_score}")
        
        if best_category and best_score > 0:
            logger.info(f"✅ TOOL FILTERING: Using category '{best_category}' with {best_score} matches")
            return self._get_category_tools(best_category, all_tools)
        else:
            logger.info("❌ TOOL FILTERING: No category matched, falling back to essential tools")
            logger.info(f"🔍 TOOL FILTERING: Available categories: {list(self.keyword_categories.keys())}")
            return self._get_essential_tools(all_tools)
    
    def _get_category_tools(self, category: str, all_tools: List[Dict]) -> List[Dict]:
        """Get tools for a specific category"""
        category_data = self.keyword_categories[category]
        max_tools = category_data['max_tools']
        priority_tools = category_data['priority_tools']
        
        # Create tool name lookup
        tool_lookup = {tool.get('name', ''): tool for tool in all_tools}
        
        selected_tools = []
        
        # First, add priority tools that exist
        for priority_tool in priority_tools:
            if priority_tool in tool_lookup and len(selected_tools) < max_tools:
                selected_tools.append(tool_lookup[priority_tool])
        
        # Then add related tools by name matching
        if len(selected_tools) < max_tools:
            category_keywords = category_data['keywords']
            for tool in all_tools:
                if len(selected_tools) >= max_tools:
                    break
                
                tool_name = tool.get('name', '').lower()
                if tool not in selected_tools:
                    # Check if tool name contains category keywords
                    if any(keyword in tool_name for keyword in category_keywords):
                        selected_tools.append(tool)
        
        # Always include essential tools if space allows
        for essential_tool in self.essential_tools:
            if essential_tool in tool_lookup and len(selected_tools) < max_tools:
                if tool_lookup[essential_tool] not in selected_tools:
                    selected_tools.append(tool_lookup[essential_tool])
        
        logger.info(f"🎯 Selected {len(selected_tools)} tools for category '{category}'")
        logger.info(f"🔧 Selected tool names: {[tool.get('name', 'unnamed') for tool in selected_tools]}")
        
        # Debug: Check if list_platform_tools is included
        tool_names = [tool.get('name', 'unnamed') for tool in selected_tools]
        if 'list_platform_tools' in tool_names:
            logger.info("✅ list_platform_tools IS included in filtered tools")
        else:
            logger.warning("❌ list_platform_tools NOT included in filtered tools")
            logger.info(f"🔍 Priority tools for {category}: {self.keyword_categories[category]['priority_tools']}")
        
        return selected_tools[:max_tools]
    
    def _get_essential_tools(self, all_tools: List[Dict]) -> List[Dict]:
        """Get essential tools for fallback scenarios"""
        logger.info(f"🔧 ESSENTIAL TOOLS: Processing {len(all_tools)} available tools")
        logger.info(f"🔧 ESSENTIAL TOOLS: Target essential tools = {self.essential_tools}")
        
        tool_lookup = {tool.get('name', ''): tool for tool in all_tools}
        logger.info(f"🔧 ESSENTIAL TOOLS: Available tool names = {list(tool_lookup.keys())[:10]}...")
        
        selected_tools = []
        for essential_tool in self.essential_tools:
            if essential_tool in tool_lookup:
                selected_tools.append(tool_lookup[essential_tool])
                logger.info(f"✅ ESSENTIAL TOOLS: Found '{essential_tool}'")
            else:
                logger.warning(f"❌ ESSENTIAL TOOLS: Missing '{essential_tool}'")
        
        logger.info(f"🎯 ESSENTIAL TOOLS: Selected {len(selected_tools)} tools (fallback)")
        return selected_tools

class ConversationManager:
    def __init__(self):
        self.conversations = {}
    
    def get_conversation(self, conversation_id: str) -> List[Dict]:
        """Get conversation history"""
        return self.conversations.get(conversation_id, [])
    
    def add_message(self, conversation_id: str, role: str, content: str, tool_calls: List[Dict] = None):
        """Add message to conversation"""
        if conversation_id not in self.conversations:
            self.conversations[conversation_id] = []
        
        message = {
            "role": role,
            "content": content,
            "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S"),
            "tool_calls": tool_calls or []
        }
        self.conversations[conversation_id].append(message)
    
    def clear_conversation(self, conversation_id: str):
        """Clear conversation history"""
        if conversation_id in self.conversations:
            del self.conversations[conversation_id]

class ToolExecutor:
    def __init__(self, mcp_server_url: str = "http://mcp-unified-server:9000"):
        self.mcp_server_url = mcp_server_url
        # Parameter translation mapping
        self.parameter_translation_map = {
            'limit': 'per_page',
            'query': 'filter',
            'search': 'filter',
            'count': 'per_page',
            'max_results': 'per_page',
            'search_term': 'filter'
        }
        
    def _translate_parameters(self, tool_name: str, parameters: Dict) -> Dict:
        """Translate Gemini parameters to MCP-expected parameters"""
        translated = {}
        
        for key, value in parameters.items():
            # Check if parameter needs translation
            if key in self.parameter_translation_map:
                translated_key = self.parameter_translation_map[key]
                translated[translated_key] = value
                logger.info(f"Parameter translation for {tool_name}: {key} -> {translated_key}")
            else:
                # Keep original parameter
                translated[key] = value
        
        return translated
        
    async def execute_tool(self, tool_name: str, parameters: Dict) -> str:
        """Execute MCP tool with parameter translation and return result as string"""
        try:
            # Map Gemini tool name to MCP tool name if needed
            mcp_tool_name = tool_name
            if tool_name.startswith('freshdesk.') or tool_name.startswith('intercom.'):
                mcp_tool_name = tool_name.split('.', 1)[1]
            
            # Translate parameters before calling MCP tool
            translated_parameters = self._translate_parameters(mcp_tool_name, parameters)
            
            async with sse_client(f"{self.mcp_server_url}/sse") as (read, write):
                async with ClientSession(read, write) as session:
                    await session.initialize()
                    
                    result = await session.call_tool(mcp_tool_name, translated_parameters)
                    
                    if hasattr(result, 'content') and result.content:
                        # Extract text content from result
                        content = result.content[0]
                        if hasattr(content, 'text'):
                            return content.text
                        else:
                            return str(content)
                    else:
                        return f"Tool {tool_name} executed successfully but returned no content"
                        
        except Exception as e:
            error_msg = f"Error calling tool '{tool_name}': {str(e)}"
            logger.error(error_msg)
            return error_msg

class GeminiMCPClient:
    def __init__(self):
        self.api_key = os.getenv("GEMINI_API_KEY")
        if not self.api_key:
            raise ValueError("GEMINI_API_KEY environment variable is required")
        
        # Initialize Gemini
        genai.configure(api_key=self.api_key)
        self.model = genai.GenerativeModel('gemini-1.5-pro')
        
        # Initialize components
        self.conversation_manager = ConversationManager()
        self.tool_executor = ToolExecutor()
        self.tool_filter = ToolFilter()  # NEW: Tool filtering to solve timeout issues
        self.available_functions = []
        self.all_available_functions = []  # Store all functions for filtering
        self.tool_mapping = {}
        
        # Initialize tools (will be done async)
        self._tools_initialized = False
    
    async def initialize_tools(self):
        """Initialize MCP tools as Gemini functions"""
        if self._tools_initialized:
            return
            
        try:
            # Generate all Gemini functions from MCP tools
            self.all_available_functions = await generate_all_functions()
            self.tool_mapping = await create_tool_mapping()
            self.tool_executor.tool_mapping = self.tool_mapping
            
            # Initially set available_functions to all functions (will be filtered per query)
            self.available_functions = self.all_available_functions
            
            logger.info(f"Initialized {len(self.all_available_functions)} total Gemini functions")
            logger.info("🔧 Tool filtering enabled - will reduce to 5-12 tools per query")
            self._tools_initialized = True
            
        except Exception as e:
            logger.error(f"Failed to initialize tools: {e}")
            self.available_functions = []
            self.all_available_functions = []
    
    async def chat(self, message: str, conversation_id: str = None) -> Dict:
        """Process chat message and return response with Gemini function calling"""
        if not self._tools_initialized:
            await self.initialize_tools()

        if not conversation_id:
            conversation_id = f"chat_{time.strftime('%Y%m%d_%H%M%S')}"

        try:
            # Simple greeting response for now
            simple_greetings = ['hello', 'hi', 'hey', 'good morning', 'good afternoon', 'good evening']
            is_greeting = any(greeting in message.lower().strip() for greeting in simple_greetings)

            if is_greeting:
                response_text = "Hello! I'm Aura, your AI assistant. How can I help you today?"
                self.conversation_manager.add_message(conversation_id, "user", message)
                self.conversation_manager.add_message(conversation_id, "assistant", response_text, [])
                return {
                    "response": response_text,
                    "conversation_id": conversation_id,
                    "tool_calls": []
                }

            # CRITICAL: Filter tools based on query to solve timeout issue
            if self.all_available_functions:
                # Convert function objects to dict format for filtering
                all_tools_dict = []
                for func in self.all_available_functions:
                    if hasattr(func, 'name'):
                        tool_dict = {
                            'name': func.name,
                            'description': getattr(func, 'description', ''),
                            'function_obj': func  # Keep reference to original function
                        }
                        all_tools_dict.append(tool_dict)
                
                # Filter tools based on query
                filtered_tools_dict = self.tool_filter.filter_tools_by_query(message, all_tools_dict)
                
                # Extract function objects from filtered results
                filtered_functions = [tool['function_obj'] for tool in filtered_tools_dict if 'function_obj' in tool]
                
                logger.info(f"🎯 TOOL FILTERING: Reduced from {len(self.all_available_functions)} to {len(filtered_functions)} tools")
            else:
                filtered_functions = []
            
            # Generate response - use filtered tools for non-greeting requests
            full_prompt = message
            if is_greeting or not filtered_functions:
                logger.info("📝 Simple greeting or no tools - responding without function calling")
                response = self.model.generate_content(full_prompt)
            else:
                logger.info(f"🔧 Calling Gemini with {len(filtered_functions)} filtered tools (was {len(self.all_available_functions)})")
                response = self.model.generate_content(
                    full_prompt,
                    tools=filtered_functions
                )
            
            tool_calls = []
            response_text = ""
            tool_result = None  # Initialize to prevent UnboundLocalError
            
            # Debug: Log the response structure
            logger.info(f"Gemini response type: {type(response)}")
            logger.info(f"Gemini response has candidates: {hasattr(response, 'candidates')}")
            if hasattr(response, 'candidates'):
                logger.info(f"Number of candidates: {len(response.candidates)}")
            
            # Handle function calls if present
            if hasattr(response, 'candidates') and response.candidates:
                candidate = response.candidates[0]
                logger.info(f"Candidate content type: {type(candidate.content) if hasattr(candidate, 'content') else 'No content'}")
                
                if hasattr(candidate, 'content') and hasattr(candidate.content, 'parts'):
                    logger.info(f"Number of parts: {len(candidate.content.parts)}")
                    logger.info(f"Candidate finish_reason: {candidate.finish_reason}")
                    
                    # Log the actual function call data if present
                    for i, part in enumerate(candidate.content.parts):
                        logger.info(f"Part {i}: type={type(part)}")
                        if hasattr(part, 'function_call'):
                            logger.info(f"Part {i} has function_call: {part.function_call}")
                        if hasattr(part, 'text'):
                            logger.info(f"Part {i} has text: {part.text[:100]}...")
                    
                    # Check for function calls first
                    for part in candidate.content.parts:
                        if hasattr(part, 'function_call'):
                            logger.info(f"Found function call: {part.function_call.name}")
                            logger.info(f"Function call args: {dict(part.function_call.args)}")
                            
                            # Execute the function call
                            function_name = part.function_call.name
                            function_args = dict(part.function_call.args)
                            
                            # Call the MCP tool
                            tool_result = await self.tool_executor.execute_tool(function_name, function_args)
                            
                            tool_calls.append({
                                "name": function_name,
                                "arguments": function_args,
                                "result": tool_result
                            })
                            
                            # Generate follow-up response based on tool result
                            if tool_result:
                                follow_up_prompt = f"""Based on the following tool execution result, please provide a helpful, natural language response to the user:

Tool: {function_name}
Arguments: {function_args}
Result: {tool_result}

Please provide a helpful, natural language response based on this data."""
                                
                                follow_up_response = self.model.generate_content(follow_up_prompt)
                                response_text = follow_up_response.text
                        elif hasattr(part, 'text'):
                            response_text = part.text
                            logger.info(f"📝 Gemini returned text response (no function call): {response_text[:100]}...")
            
            # Fallback to direct text response if no function calls
            if not response_text and hasattr(response, 'text'):
                response_text = response.text
                logger.info(f"📝 Using fallback text response: {response_text[:100]}...")
            
            # Log final result
            logger.info(f"🎯 Final response length: {len(response_text)}, Tool calls made: {len(tool_calls)}")
            if not tool_calls:
                logger.warning(f"⚠️ No function calls triggered for query: '{message}'")
                logger.info(f"Available functions count: {len(self.available_functions)}")
                if self.available_functions:
                    # Handle both dict and FunctionDeclaration objects
                    sample_names = []
                    for f in self.available_functions[:5]:
                        if isinstance(f, dict):
                            sample_names.append(f.get('name', 'unknown'))
                        else:
                            sample_names.append(getattr(f, 'name', 'unknown'))
                    logger.info(f"Sample function names: {sample_names}")
            
            # Store conversation
            self.conversation_manager.add_message(conversation_id, "user", message)
            self.conversation_manager.add_message(conversation_id, "assistant", response_text, tool_calls)
            
            return {
                "response": response_text,
                "conversation_id": conversation_id,
                "tool_calls": tool_calls
            }
            
        except Exception as e:
            logger.error(f"Chat failed: {e}")
            return {
                "response": f"❌ I encountered an error: {str(e)}",
                "conversation_id": conversation_id,
                "tool_calls": []
            }
    
    async def chat_stream(self, message: str, conversation_id: str = None) -> AsyncGenerator[str, None]:
        """Stream chat response"""
        if not self._tools_initialized:
            await self.initialize_tools()
        
        if not conversation_id:
            conversation_id = f"chat_{time.strftime('%Y%m%d_%H%M%S')}"
        
        try:
            # Simple streaming response for now
            response = await self.chat(message, conversation_id)
            
            # Simulate streaming by yielding chunks
            words = response.split()
            for i, word in enumerate(words):
                if i == 0:
                    yield word
                else:
                    yield f" {word}"
                await asyncio.sleep(0.05)  # Small delay for streaming effect
                
        except Exception as e:
            yield f"❌ Error: {str(e)}"
    
    def get_conversation_history(self, conversation_id: str) -> List[Dict]:
        """Get conversation history"""
        return self.conversation_manager.get_conversation(conversation_id)
    
    def clear_conversation(self, conversation_id: str):
        """Clear conversation"""
        self.conversation_manager.clear_conversation(conversation_id)
    
    def list_conversations(self) -> List[str]:
        """List all conversation IDs"""
        return list(self.conversation_manager.conversations.keys())

# Global client instance
_client = None

def get_client() -> GeminiMCPClient:
    """Get singleton client instance"""
    global _client
    if _client is None:
        _client = GeminiMCPClient()
    return _client
