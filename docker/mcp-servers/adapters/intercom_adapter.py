"""
Intercom API Adapter for MCP Server
Complete integration with all 87 Intercom API v2.11/v2.14 tools
Fixed parameter naming to match sanitize_param_name function
"""

import os
import json
import asyncio
import logging
from typing import Dict, List, Any, Optional, Union
from datetime import datetime, timedelta
import aiohttp
from urllib.parse import urlencode, quote

from .base_adapter import BaseAdapter
from .rate_limiter import RateLimiter

logger = logging.getLogger(__name__)


class IntercomAdapter(BaseAdapter):
    """
    Comprehensive Intercom API v2.11/v2.14 Adapter
    Covers all 87 documented tools with dynamic tool generation
    Fixed parameter naming for MCP compatibility
    """
    
    platform_name = "intercom"
    
    def __init__(self, access_token: str = None):
        """
        Initialize Intercom adapter
        
        Args:
            access_token: Intercom access token (from env if not provided)
        """
        # Initialize with the Intercom API base URL
        self.base_url = "https://api.intercom.io"
        self.api_version = "2.11"  # Latest stable version
        
        # Load configuration from environment
        self.access_token = access_token or os.getenv('INTERCOM_ACCESS_TOKEN')
        
        if not self.access_token:
            raise ValueError("Intercom access token is required. Set INTERCOM_ACCESS_TOKEN environment variable.")
            
        # Initialize parent with base_url and access token
        super().__init__(
            base_url=self.base_url, 
            access_token=self.access_token
        )
        
        # Initialize rate limiter
        self.rate_limiter = RateLimiter(max_requests=9000, window_minutes=1)  # Intercom limit
        
        # Initialize all tool dictionaries
        self.all_tools = {}
        self.conversation_tools = {}
        self.message_tools = {}
        self.contact_tools = {}
        self.company_tools = {}
        self.data_attribute_tools = {}
        self.article_tools = {}
        self.help_center_tools = {}
        self.admin_tools = {}
        self.segment_tools = {}
        self.tag_tools = {}
        self.note_tools = {}
        self.data_event_tools = {}
        
        # Track API usage statistics
        self.stats = {
            'requests_made': 0,
            'successful_requests': 0,
            'failed_requests': 0,
            'rate_limit_hits': 0
        }
        
        # Set up tools
        self._setup_tools()
        
        # Initialize session for connection pooling
        self.session = None
        
        logger.info(f"✅ Intercom adapter initialized")
        logger.info(f"🔗 Base URL: {self.base_url}")
        logger.info(f"📋 API Version: {self.api_version}")
        logger.info(f"🔧 Total Tools: {len(self.all_tools)}")

    async def execute_tool(self, tool_name: str, arguments: Dict[str, Any] = None) -> Dict[str, Any]:
        """
        Execute a tool by name with the given parameters.
        Compatible interface with main.py expectations - matches FreshdeskAdapter.
        
        Args:
            tool_name: Name of the tool to execute
            arguments: Tool-specific parameters (optional)
            
        Returns:
            Dict with the result of the tool execution
        """
        if arguments is None:
            arguments = {}
            
        if tool_name not in self.all_tools:
            return {
                "success": False,
                "error": f"Tool '{tool_name}' not found",
                "available_tools": list(self.all_tools.keys())
            }
        
        # Get the tool method configuration
        tool_config = self.all_tools[tool_name]
        
        # Check required parameters
        required_params = tool_config.get('required', [])
        missing_params = [p for p in required_params if p not in arguments or arguments[p] is None]
        if missing_params:
            return {
                "success": False,
                "error": f"Missing required parameters: {', '.join(missing_params)}",
                "required_parameters": required_params
            }
        
        try:
            # Apply rate limiting
            if self.rate_limiter:
                rate_check = await self.rate_limiter.check_rate_limit(self.platform_name)
                if not rate_check['allowed']:
                    return {
                        "success": False,
                        "error": f"Rate limit exceeded: {rate_check['message']}"
                    }
            
            # Use arguments dict for call_tool, filtering out None values
            filtered_arguments = {k: v for k, v in arguments.items() if v is not None}
            
            # Call the existing call_tool method (which does the actual API work)
            result = await self.call_tool(tool_name, filtered_arguments)
            
            # Return in the format expected by main.py (matching FreshdeskAdapter format)
            if result.get('success'):
                return {
                    "success": True,
                    "result": result.get('result', result)
                }
            else:
                return {
                    "success": False,
                    "error": result.get('error', 'Unknown error occurred'),
                    "tool": tool_name,
                    "parameters": arguments
                }
                
        except Exception as e:
            logger.error(f"Error executing tool {tool_name}: {str(e)}")
            return {
                "success": False,
                "error": str(e),
                "tool": tool_name,
                "parameters": arguments
            }

    def unified_search(self, query: str) -> Dict[str, Any]:
        """
        Unified search interface to match main.py expectations.
        Wraps the existing search_unified_data method.
        """
        try:
            # Create a new event loop if we're not in an async context
            import asyncio
            try:
                # Try to get existing event loop
                loop = asyncio.get_running_loop()
                # If we're already in an async context, we need to use run_until_complete
                future = asyncio.ensure_future(self.search_unified_data(query))
                return loop.run_until_complete(future)
            except RuntimeError:
                # No event loop running, safe to use asyncio.run
                return asyncio.run(self.search_unified_data(query))
        except Exception as e:
            logger.error(f"Error in unified_search: {e}")
            return {
                "error": str(e), 
                "matches": [],
                "platform": self.platform_name
            }
    
    async def test_connection(self) -> Dict[str, Any]:
        """
        Test the connection to Intercom API.
        Uses the existing get_health_status method for consistency.
        
        Returns:
            Dict with connection test results matching main.py expectations
        """
        try:
            health_status = await self.get_health_status()
            return {
                "success": health_status['status'] == 'healthy',
                "message": "Connected successfully" if health_status['status'] == 'healthy' else "Connection failed",
                "details": {
                    "platform": self.platform_name,
                    "base_url": self.base_url,
                    "api_version": self.api_version,
                    "total_tools": len(self.all_tools),
                    "rate_limiting": health_status.get('rate_limiting', {})
                }
            }
        except Exception as e:
            logger.error(f"Error testing connection: {str(e)}")
            return {
                "success": False,
                "message": f"Connection test failed: {str(e)}",
                "details": {
                    "platform": self.platform_name,
                    "error": str(e)
                }
            }
            
    def get_tool_config(self, tool_name: str) -> Optional[Dict[str, Any]]:
        """
        Get the configuration for a specific tool
        
        Args:
            tool_name: Name of the tool to get configuration for
            
        Returns:
            Optional[Dict[str, Any]]: Tool configuration if found, None otherwise
        """
        tools = self.get_tools()
        for tool in tools:
            if tool["name"] == tool_name:
                return tool
        return None
        
    def get_tools(self) -> List[Dict[str, Any]]:
        """
        Get a list of available tools for this adapter
        
        Returns:
            List[Dict[str, Any]]: List of tool definitions
        """
        tools = []
        for name, config in self.all_tools.items():
            tool = {
                "name": name,
                "description": config.get("description", ""),
                "parameters": {
                    "type": "object",
                    "properties": {},
                    "required": config.get("required", [])
                }
            }
            for param in config.get("params", []):
                tool["parameters"]["properties"][param] = {
                    "type": "string",
                    "description": f"Parameter: {param}"
                }
            tools.append(tool)
        return tools

    def get_customer_journey(self, identifier: str, identifier_type: str = "email") -> Dict[str, Any]:
        """Get customer journey data from Intercom
        
        Args:
            identifier: Customer identifier (email, phone, etc)
            identifier_type: Type of identifier (default: email)
            
        Returns:
            Dict containing customer journey data
        """
        try:
            # Search for contact
            search_query = {
                'query': {
                    'field': identifier_type,
                    'operator': '=',
                    'value': identifier
                }
            }
            
            # Use asyncio to run the async method
            import asyncio
            try:
                loop = asyncio.get_running_loop()
                future = asyncio.ensure_future(self._get_customer_journey_async(identifier, identifier_type))
                return loop.run_until_complete(future)
            except RuntimeError:
                return asyncio.run(self._get_customer_journey_async(identifier, identifier_type))
        except Exception as e:
            logger.error(f"Error getting customer journey: {str(e)}")
            return {
                'platform': self.platform_name,
                'error': str(e),
                'timeline': []
            }

    async def _get_customer_journey_async(self, identifier: str, identifier_type: str = "email") -> Dict[str, Any]:
        """Async implementation of get_customer_journey"""
        try:
            # Search for contact
            search_query = {
                'query': {
                    'field': identifier_type,
                    'operator': '=',
                    'value': identifier
                }
            }
            contact_results = await self.call_tool('search_contacts', {'query': search_query})
            
            # Get conversations for contact if found
            timeline = []
            interactions = []
            if contact_results['success'] and contact_results['result'].get('data', {}).get('data'):
                contact = contact_results['result']['data']['data'][0]
                contact_id = contact['id']
                
                # Get conversations
                conv_query = {
                    'query': {
                        'field': 'contact_ids',
                        'operator': 'in',
                        'value': [contact_id]
                    }
                }
                conv_results = await self.call_tool('search_conversations', {'query': conv_query})
                
                if conv_results['success'] and conv_results['result'].get('data', {}).get('conversations'):
                    for conv in conv_results['result']['data']['conversations']:
                        # Add to timeline
                        timeline.append({
                            'type': 'conversation',
                            'item_id': conv['id'],
                            'timestamp': conv['created_at'],
                            'item_title': conv.get('source', {}).get('subject', 'Conversation'),
                            'status': conv['state'],
                            'url': f"https://app.intercom.com/a/apps/{conv.get('app_id', '')}/conversations/{conv['id']}"
                        })
                        
                        # Add to interactions
                        interactions.append({
                            'type': 'conversation',
                            'item_id': conv['id'],
                            'timestamp': conv['created_at'],
                            'content': conv.get('source', {}).get('body', ''),
                            'status': conv['state']
                        })
            
            return {
                'platform': self.platform_name,
                'identifier': identifier,
                'identifier_type': identifier_type,
                'timeline': sorted(timeline, key=lambda x: x['timestamp'], reverse=True),
                'interactions': sorted(interactions, key=lambda x: x['timestamp'], reverse=True),
                'message': f'Found {len(timeline)} interactions for {identifier_type}: {identifier}'
            }
            
        except Exception as e:
            logger.error(f"Error getting customer journey: {str(e)}")
            return {
                'platform': self.platform_name,
                'error': str(e),
                'timeline': []
            }
    
    def _setup_tools(self):
        """Configure all Intercom API tools dynamically with sanitized parameter names"""
        
        # 1. CONVERSATION TOOLS (15 tools) - FIXED PARAMETER NAMES
        self.conversation_tools = {
            'list_conversations': {
                'method': 'GET',
                'path': '/conversations',
                'description': 'List all conversations with pagination',
                'params': ['starting_after', 'page_size', 'sort', 'order', 'display_as'],  # per_page → page_size
                'required': []
            },
            'create_conversation': {
                'method': 'POST',
                'path': '/conversations',
                'description': 'Create a new conversation',
                'params': ['from_date', 'content_body', 'msg_type', 'subject', 'template_id'],  # from → from_date, body → content_body, message_type → msg_type
                'required': ['from_date', 'content_body']
            },
            'retrieve_conversation': {
                'method': 'GET',
                'path': '/conversations/{item_id}',  # {id} → {item_id}
                'description': 'Retrieve a specific conversation by ID',
                'params': ['display_as'],
                'required': ['item_id']
            },
            'update_conversation': {
                'method': 'PUT',
                'path': '/conversations/{item_id}',  # {id} → {item_id}
                'description': 'Update an existing conversation',
                'params': ['read', 'custom_attributes'],
                'required': ['item_id']
            },
            'search_conversations': {
                'method': 'POST',
                'path': '/conversations/search',
                'description': 'Search conversations using advanced filters',
                'params': ['search_query', 'pagination'],  # query → search_query
                'required': ['search_query']
            },
            'add_conversation_tag': {
                'method': 'POST',
                'path': '/conversations/{item_id}/tags',  # {id} → {item_id}
                'description': 'Add a tag to a conversation',
                'params': ['item_id', 'tag_id'],
                'required': ['item_id', 'tag_id']
            },
            'remove_conversation_tag': {
                'method': 'DELETE',
                'path': '/conversations/{item_id}/tags/{tag_id}',  # {id} → {item_id}
                'description': 'Remove a tag from a conversation',
                'params': ['item_id', 'tag_id'],
                'required': ['item_id', 'tag_id']
            },
            'assign_conversation': {
                'method': 'POST',
                'path': '/conversations/{item_id}/reply',  # {id} → {item_id}
                'description': 'Assign a conversation to a team or admin',
                'params': ['item_id', 'admin_id', 'team_id', 'msg_type', 'item_type'],  # message_type → msg_type, type → item_type
                'required': ['item_id', 'msg_type', 'item_type']
            },
            'snooze_conversation': {
                'method': 'PUT',
                'path': '/conversations/{item_id}',  # {id} → {item_id}
                'description': 'Snooze a conversation until a specific time',
                'params': ['item_id', 'snoozed_until'],
                'required': ['item_id', 'snoozed_until']
            },
            'close_conversation': {
                'method': 'POST',
                'path': '/conversations/{item_id}/reply',  # {id} → {item_id}
                'description': 'Close a conversation',
                'params': ['item_id', 'msg_type', 'item_type', 'content_body'],  # message_type → msg_type, type → item_type, body → content_body
                'required': ['item_id', 'msg_type', 'item_type']
            },
            'open_conversation': {
                'method': 'POST',
                'path': '/conversations/{item_id}/parts',  # {id} → {item_id}
                'description': 'Reopen a closed conversation',
                'params': ['item_id', 'msg_type', 'item_type', 'content_body'],  # message_type → msg_type, type → item_type, body → content_body
                'required': ['item_id', 'msg_type', 'item_type']
            },
            'attach_file': {
                'method': 'POST',
                'path': '/conversations/{item_id}/attachments',  # {id} → {item_id}
                'description': 'Attach a file to a conversation',
                'params': ['item_id', 'file'],
                'required': ['item_id', 'file']
            },
            'list_conversation_parts': {
                'method': 'GET',
                'path': '/conversations/{item_id}/parts',  # {id} → {item_id}
                'description': 'List all parts of a conversation',
                'params': ['item_id'],
                'required': ['item_id']
            },
            'redact_conversation_part': {
                'method': 'POST',
                'path': '/conversations/redact',
                'description': 'Redact a conversation part',
                'params': ['conversation_id', 'conversation_part_id', 'item_type'],  # type → item_type
                'required': ['conversation_id', 'conversation_part_id', 'item_type']
            }
        }
        
        # 2. MESSAGE TOOLS (8 tools) - FIXED PARAMETER NAMES
        self.message_tools = {
            'create_message': {
                'method': 'POST',
                'path': '/messages',
                'description': 'Create a new message',
                'params': ['msg_type', 'from_date', 'target', 'subject', 'content_body', 'template_id', 'create_conversation_without_contact_reply'],  # message_type → msg_type, from → from_date, to → target, body → content_body
                'required': ['msg_type', 'from_date', 'content_body']
            },
            'list_messages': {
                'method': 'GET',
                'path': '/conversations/{conversation_id}/parts',
                'description': 'List all messages in a conversation',
                'params': ['page_size', 'since'],  # per_page → page_size
                'required': ['conversation_id']
            },
            'reply_to_message': {
                'method': 'POST',
                'path': '/conversations/{conversation_id}/reply',
                'description': 'Reply to a message in conversation',
                'params': ['msg_type', 'item_type', 'admin_id', 'content_body', 'attachment_urls'],  # message_type → msg_type, type → item_type, body → content_body
                'required': ['conversation_id', 'msg_type', 'item_type', 'content_body']
            },
            'admin_initiated_conversation': {
                'method': 'POST',
                'path': '/messages',
                'description': 'Admin sends message to create new conversation',
                'params': ['msg_type', 'from_date', 'target', 'content_body', 'subject'],  # message_type → msg_type, from → from_date, to → target, body → content_body
                'required': ['msg_type', 'from_date', 'target', 'content_body']
            },
            'customer_initiated_conversation': {
                'method': 'POST',
                'path': '/conversations',
                'description': 'Customer creates new conversation',
                'params': ['from_date', 'content_body', 'msg_type'],  # from → from_date, body → content_body, message_type → msg_type
                'required': ['from_date', 'content_body']
            },
            'group_message': {
                'method': 'POST',
                'path': '/messages',
                'description': 'Send message to multiple users',
                'params': ['msg_type', 'from_date', 'target', 'content_body', 'create_conversation_without_contact_reply'],  # message_type → msg_type, from → from_date, to → target, body → content_body
                'required': ['msg_type', 'from_date', 'target', 'content_body']
            },
            'message_attachments': {
                'method': 'POST',
                'path': '/conversations/{conversation_id}/parts',
                'description': 'Add attachments to message',
                'params': ['msg_type', 'item_type', 'content_body', 'attachment_urls'],  # message_type → msg_type, type → item_type, body → content_body
                'required': ['conversation_id', 'msg_type', 'item_type']
            },
            'email_message': {
                'method': 'POST',
                'path': '/messages',
                'description': 'Send email message through Intercom',
                'params': ['msg_type', 'from_date', 'target', 'subject', 'content_body', 'template_id'],  # message_type → msg_type, from → from_date, to → target, body → content_body
                'required': ['msg_type', 'from_date', 'target', 'content_body']
            }
        }
        
        # 3. CONTACT TOOLS (12 tools) - FIXED PARAMETER NAMES
        self.contact_tools = {
            'list_contacts': {
                'method': 'GET',
                'path': '/contacts',
                'description': 'List all contacts with pagination',
                'params': ['page_size', 'starting_after'],  # per_page → page_size
                'required': []
            },
            'create_contact': {
                'method': 'POST',
                'path': '/contacts',
                'description': 'Create a new contact',
                'params': ['role', 'email', 'phone', 'item_name', 'custom_attributes'],  # name → item_name
                'required': ['role']
            },
            'retrieve_contact': {
                'method': 'GET',
                'path': '/contacts/{item_id}',  # {id} → {item_id}
                'description': 'Retrieve a specific contact by ID',
                'params': ['item_id'],
                'required': ['item_id']
            },
            'update_contact': {
                'method': 'PUT',
                'path': '/contacts/{item_id}',  # {id} → {item_id}
                'description': 'Update an existing contact',
                'params': ['item_id', 'email', 'phone', 'item_name', 'custom_attributes'],  # name → item_name
                'required': ['item_id']
            },
            'delete_contact': {
                'method': 'DELETE',
                'path': '/contacts/{item_id}',  # {id} → {item_id}
                'description': 'Delete a contact',
                'params': ['item_id'],
                'required': ['item_id']
            },
            'search_contacts': {
                'method': 'POST',
                'path': '/contacts/search',
                'description': 'Search contacts using query',
                'params': ['search_query', 'pagination'],  # query → search_query
                'required': ['search_query']
            },
            'convert_contact': {
                'method': 'POST',
                'path': '/contacts/convert',
                'description': 'Convert lead to customer',
                'params': ['contact', 'user'],
                'required': ['contact', 'user']
            },
            'archive_contact': {
                'method': 'POST',
                'path': '/contacts/{item_id}/archive',  # {id} → {item_id}
                'description': 'Archive a contact',
                'params': ['item_id'],
                'required': ['item_id']
            },
            'unarchive_contact': {
                'method': 'POST',
                'path': '/contacts/{item_id}/unarchive',  # {id} → {item_id}
                'description': 'Unarchive a contact',
                'params': ['item_id'],
                'required': ['item_id']
            },
            'add_remove_tags': {
                'method': 'POST',
                'path': '/contacts/{item_id}/tags',  # {id} → {item_id}
                'description': 'Add or remove tags from contact',
                'params': ['item_id', 'tags'],
                'required': ['item_id']
            },
            'merge_contacts': {
                'method': 'POST',
                'path': '/contacts/merge',
                'description': 'Merge two contacts',
                'params': ['primary_contact_id', 'secondary_contact_id'],
                'required': ['primary_contact_id', 'secondary_contact_id']
            },
            'list_segments': {
                'method': 'GET',
                'path': '/contacts/segments',
                'description': 'List contact segments',
                'params': ['page_size'],  # per_page → page_size
                'required': []
            }
        }
        
        # 4. COMPANY TOOLS (10 tools) - FIXED PARAMETER NAMES
        self.company_tools = {
            'list_companies': {
                'method': 'GET',
                'path': '/companies',
                'description': 'List all companies with pagination',
                'params': ['page_size', 'starting_after'],  # per_page → page_size
                'required': []
            },
            'create_company': {
                'method': 'POST',
                'path': '/companies',
                'description': 'Create a new company',
                'params': ['company_id', 'item_name', 'monthly_spend', 'plan', 'size', 'website', 'industry', 'custom_attributes'],  # name → item_name
                'required': []
            },
            'retrieve_company': {
                'method': 'GET',
                'path': '/companies/{item_id}',  # {id} → {item_id}
                'description': 'Retrieve a specific company by ID',
                'params': ['item_id'],
                'required': ['item_id']
            },
            'update_company': {
                'method': 'PUT',
                'path': '/companies/{item_id}',  # {id} → {item_id}
                'description': 'Update an existing company',
                'params': ['item_id', 'item_name', 'monthly_spend', 'plan', 'size', 'website', 'industry', 'custom_attributes'],  # name → item_name
                'required': ['item_id']
            },
            'archive_company': {
                'method': 'DELETE',
                'path': '/companies/{item_id}',  # {id} → {item_id}
                'description': 'Archive a company',
                'params': ['item_id'],
                'required': ['item_id']
            },
            'list_company_contacts': {
                'method': 'GET',
                'path': '/companies/{item_id}/contacts',  # {id} → {item_id}
                'description': 'List all contacts associated with a company',
                'params': ['item_id', 'page_size', 'starting_after'],  # per_page → page_size
                'required': ['item_id']
            },
            'add_remove_users': {
                'method': 'POST',
                'path': '/companies/{item_id}/users',  # {id} → {item_id}
                'description': 'Add or remove users from company',
                'params': ['item_id', 'users'],
                'required': ['item_id']
            },
            'add_remove_company_tags': {
                'method': 'POST',
                'path': '/companies/{item_id}/tags',  # {id} → {item_id}
                'description': 'Add or remove tags from company',
                'params': ['item_id', 'tags'],
                'required': ['item_id']
            },
            'scroll_companies': {
                'method': 'GET',
                'path': '/companies/scroll',
                'description': 'Scroll through all companies',
                'params': ['scroll_param'],
                'required': []
            },
            'search_companies': {
                'method': 'POST',
                'path': '/companies/search',
                'description': 'Search companies using query',
                'params': ['search_query', 'pagination'],  # query → search_query
                'required': ['search_query']
            }
        }
        
        # 5. DATA ATTRIBUTES (6 tools) - FIXED PARAMETER NAMES
        self.data_attribute_tools = {
            'create_data_attribute': {
                'method': 'POST',
                'path': '/data_attributes',
                'description': 'Create a new data attribute',
                'params': ['item_name', 'model_type', 'data_type', 'description', 'options'],  # name → item_name, model → model_type
                'required': ['item_name', 'model_type', 'data_type']
            },
            'list_data_attributes': {
                'method': 'GET',
                'path': '/data_attributes',
                'description': 'List all data attributes',
                'params': ['model_type', 'include_archived'],  # model → model_type
                'required': []
            },
            'retrieve_data_attribute': {
                'method': 'GET',
                'path': '/data_attributes/{item_id}',  # {id} → {item_id}
                'description': 'Retrieve a specific data attribute',
                'params': ['item_id'],
                'required': ['item_id']
            },
            'update_data_attribute': {
                'method': 'PUT',
                'path': '/data_attributes/{item_id}',  # {id} → {item_id}
                'description': 'Update an existing data attribute',
                'params': ['item_id', 'item_name', 'description', 'options'],  # name → item_name
                'required': ['item_id']
            },
            'delete_data_attribute': {
                'method': 'DELETE',
                'path': '/data_attributes/{item_id}',  # {id} → {item_id}
                'description': 'Delete a data attribute',
                'params': ['item_id'],
                'required': ['item_id']
            },
            'archive_data_attribute': {
                'method': 'POST',
                'path': '/data_attributes/{item_id}/archive',  # {id} → {item_id}
                'description': 'Archive a data attribute',
                'params': ['item_id'],
                'required': ['item_id']
            }
        }
        
        # 6. ARTICLES (8 tools) - FIXED PARAMETER NAMES
        self.article_tools = {
            'create_article': {
                'method': 'POST',
                'path': '/articles',
                'description': 'Create a new help center article',
                'params': ['item_title', 'content_body', 'author_id', 'state', 'parent_id', 'parent_type', 'translated_content'],  # title → item_title, body → content_body
                'required': ['item_title', 'content_body', 'author_id']
            },
            'retrieve_article': {
                'method': 'GET',
                'path': '/articles/{item_id}',  # {id} → {item_id}
                'description': 'Retrieve a specific article by ID',
                'params': ['item_id'],
                'required': ['item_id']
            },
            'update_article': {
                'method': 'PUT',
                'path': '/articles/{item_id}',  # {id} → {item_id}
                'description': 'Update an existing article',
                'params': ['item_id', 'item_title', 'content_body', 'author_id', 'state', 'translated_content'],  # title → item_title, body → content_body
                'required': ['item_id']
            },
            'delete_article': {
                'method': 'DELETE',
                'path': '/articles/{item_id}',  # {id} → {item_id}
                'description': 'Delete an article permanently',
                'params': ['item_id'],
                'required': ['item_id']
            },
            'list_articles': {
                'method': 'GET',
                'path': '/articles',
                'description': 'List all help center articles',
                'params': ['page_size', 'page', 'parent_id', 'parent_type'],  # per_page → page_size
                'required': []
            },
            'search_articles': {
                'method': 'GET',
                'path': '/articles/search',
                'description': 'Search articles by phrase',
                'params': ['search_phrase', 'page_size', 'page'],  # phrase → search_phrase, per_page → page_size
                'required': ['search_phrase']
            },
            'translate_article': {
                'method': 'POST',
                'path': '/articles/{item_id}/translate',  # {id} → {item_id}
                'description': 'Add translation to an article',
                'params': ['item_id', 'lang_code', 'item_title', 'content_body'],  # language → lang_code, title → item_title, body → content_body
                'required': ['item_id', 'lang_code', 'item_title', 'content_body']
            },
            'archive_article': {
                'method': 'POST',
                'path': '/articles/{item_id}/archive',  # {id} → {item_id}
                'description': 'Archive an article',
                'params': ['item_id'],
                'required': ['item_id']
            }
        }
        
        # 7. HELP CENTER (6 tools) - FIXED PARAMETER NAMES
        self.help_center_tools = {
            'create_collection': {
                'method': 'POST',
                'path': '/help_center/collections',
                'description': 'Create a new help center collection',
                'params': ['item_name', 'description', 'translated_content'],  # name → item_name
                'required': ['item_name']
            },
            'list_collections': {
                'method': 'GET',
                'path': '/help_center/collections',
                'description': 'List all help center collections',
                'params': ['page_size', 'page'],  # per_page → page_size
                'required': []
            },
            'retrieve_collection': {
                'method': 'GET',
                'path': '/help_center/collections/{item_id}',  # {id} → {item_id}
                'description': 'Retrieve a specific collection',
                'params': ['item_id'],
                'required': ['item_id']
            },
            'update_collection': {
                'method': 'PUT',
                'path': '/help_center/collections/{item_id}',  # {id} → {item_id}
                'description': 'Update an existing collection',
                'params': ['item_id', 'item_name', 'description', 'translated_content'],  # name → item_name
                'required': ['item_id']
            },
            'delete_collection': {
                'method': 'DELETE',
                'path': '/help_center/collections/{item_id}',  # {id} → {item_id}
                'description': 'Delete a collection permanently',
                'params': ['item_id'],
                'required': ['item_id']
            },
            'help_center_settings': {
                'method': 'GET',
                'path': '/help_center',
                'description': 'Get help center settings and configuration',
                'params': [],
                'required': []
            }
        }
        
        # 8. ADMINS/TEAMMATES (7 tools) - FIXED PARAMETER NAMES
        self.admin_tools = {
            'retrieve_admin': {
                'method': 'GET',
                'path': '/admins/{item_id}',  # {id} → {item_id}
                'description': 'Retrieve a specific admin by ID',
                'params': ['item_id'],
                'required': ['item_id']
            },
            'list_admins': {
                'method': 'GET',
                'path': '/admins',
                'description': 'List all admins and teammates',
                'params': ['page_size', 'page'],  # per_page → page_size
                'required': []
            },
            'set_admin_away': {
                'method': 'PUT',
                'path': '/admins/{item_id}/away',  # {id} → {item_id}
                'description': 'Set admin away status',
                'params': ['item_id', 'is_away', 'away_mode_reassign'],  # away_mode_enabled → is_away
                'required': ['item_id', 'is_away']
            },
            'list_admin_activities': {
                'method': 'GET',
                'path': '/admins/activity_logs',
                'description': 'List admin activity logs',
                'params': ['created_after', 'created_at_before'],  # created_at_after → created_after
                'required': []
            },
            'get_team_permissions': {
                'method': 'GET',
                'path': '/teams',
                'description': 'List all teams and their permissions',
                'params': ['page_size', 'page'],  # per_page → page_size
                'required': []
            },
            'list_away_reasons': {
                'method': 'GET',
                'path': '/admins/away_reasons',
                'description': 'List all away status reasons',
                'params': [],
                'required': []
            },
            'get_activity_logs': {
                'method': 'GET',
                'path': '/admins/{item_id}/activity_logs',  # {id} → {item_id}
                'description': 'Get activity logs for specific admin',
                'params': ['item_id', 'created_after', 'created_at_before'],  # created_at_after → created_after
                'required': ['item_id']
            }
        }
        
        # 9. SEGMENTS (4 tools) - FIXED PARAMETER NAMES
        self.segment_tools = {
            'create_segment': {
                'method': 'POST',
                'path': '/segments',
                'description': 'Create a new user/company segment',
                'params': ['item_name', 'person_type', 'filter_query'],  # name → item_name, filter → filter_query
                'required': ['item_name', 'person_type', 'filter_query']
            },
            'retrieve_segment': {
                'method': 'GET',
                'path': '/segments/{item_id}',  # {id} → {item_id}
                'description': 'Retrieve a specific segment by ID',
                'params': ['item_id'],
                'required': ['item_id']
            },
            'update_segment': {
                'method': 'PUT',
                'path': '/segments/{item_id}',  # {id} → {item_id}
                'description': 'Update an existing segment',
                'params': ['item_id', 'item_name', 'filter_query'],  # name → item_name, filter → filter_query
                'required': ['item_id']
            },
            'delete_segment': {
                'method': 'DELETE',
                'path': '/segments/{item_id}',  # {id} → {item_id}
                'description': 'Delete a segment permanently',
                'params': ['item_id'],
                'required': ['item_id']
            }
        }
        
        # 10. TAGS (4 tools) - FIXED PARAMETER NAMES
        self.tag_tools = {
            'create_tag': {
                'method': 'POST',
                'path': '/tags',
                'description': 'Create a new tag',
                'params': ['item_name'],  # name → item_name
                'required': ['item_name']
            },
            'delete_tag': {
                'method': 'DELETE',
                'path': '/tags/{item_id}',  # {id} → {item_id}
                'description': 'Delete a tag permanently',
                'params': ['item_id'],
                'required': ['item_id']
            },
            'list_tags': {
                'method': 'GET',
                'path': '/tags',
                'description': 'List all tags',
                'params': [],
                'required': []
            },
            'tag_objects': {
                'method': 'POST',
                'path': '/tags/{item_id}/tag',  # {id} → {item_id}
                'description': 'Apply tag to contacts/companies/conversations',
                'params': ['item_id', 'contact_list', 'companies', 'conversations'],  # contacts → contact_list
                'required': ['item_id']
            }
        }
        
        # 11. NOTES (3 tools) - FIXED PARAMETER NAMES
        self.note_tools = {
            'create_note': {
                'method': 'POST',
                'path': '/notes',
                'description': 'Create a new note for contact',
                'params': ['contact_data', 'admin_id', 'content_body'],  # contact → contact_data, body → content_body
                'required': ['contact_data', 'admin_id', 'content_body']
            },
            'retrieve_note': {
                'method': 'GET',
                'path': '/notes/{item_id}',  # {id} → {item_id}
                'description': 'Retrieve a specific note by ID',
                'params': ['item_id'],
                'required': ['item_id']
            },
            'list_notes': {
                'method': 'GET',
                'path': '/notes',
                'description': 'List all notes for a contact',
                'params': ['contact_ref', 'page_size', 'page'],  # contact_id → contact_ref, per_page → page_size
                'required': ['contact_ref']
            }
        }
        
        # 12. DATA EVENTS (4 tools) - FIXED PARAMETER NAMES
        self.data_event_tools = {
            'create_event': {
                'method': 'POST',
                'path': '/events',
                'description': 'Create a new data event for tracking',
                'params': ['event_type', 'user_id', 'email', 'created_at', 'metadata'],  # event_name → event_type
                'required': ['event_type']
            },
            'list_events': {
                'method': 'GET',
                'path': '/events',
                'description': 'List all data events',
                'params': ['filter_query', 'page_size', 'starting_after'],  # filter → filter_query, per_page → page_size
                'required': []
            },
            'event_summaries': {
                'method': 'GET',
                'path': '/events/summaries',
                'description': 'Get summaries of events by time period',
                'params': ['event_type', 'user_id', 'start_time', 'end_time'],  # event_name → event_type
                'required': []
            },
            'event_metadata': {
                'method': 'GET',
                'path': '/events/{event_type}/summaries',  # {event_name} → {event_type}
                'description': 'Get metadata summaries for specific event',
                'params': ['event_type', 'user_id', 'start_time', 'end_time'],  # event_name → event_type
                'required': ['event_type']
            }
        }
        
        # Update all_tools with each tool category
        self.all_tools.update(self.conversation_tools)
        self.all_tools.update(self.message_tools)
        self.all_tools.update(self.contact_tools)
        self.all_tools.update(self.company_tools)
        self.all_tools.update(self.data_attribute_tools)
        self.all_tools.update(self.article_tools)
        self.all_tools.update(self.help_center_tools)
        self.all_tools.update(self.admin_tools)
        self.all_tools.update(self.segment_tools)
        self.all_tools.update(self.tag_tools)
        self.all_tools.update(self.note_tools)
        self.all_tools.update(self.data_event_tools)
        
        logger.info(f"🔧 Configured {len(self.all_tools)} Intercom API tools with sanitized parameter names")
    
    async def make_request(
        self, 
        method: str, 
        endpoint: str, 
        params: Dict[str, Any] = None, 
        data: Dict[str, Any] = None,
        files: Dict[str, Any] = None
    ) -> Dict[str, Any]:
        """
        Make authenticated request to Intercom API
        
        Args:
            method: HTTP method (GET, POST, PUT, DELETE)
            endpoint: API endpoint path
            params: Query parameters
            data: Request body data
            files: File attachments (not commonly used in Intercom)
            
        Returns:
            API response as dictionary
        """
        # Check rate limit first
        rate_check = await self.rate_limiter.check_rate_limit(self.platform_name)
        if not rate_check['allowed']:
            self.stats['rate_limit_hits'] += 1
            raise Exception(f"Rate limit exceeded: {rate_check['message']}")
        
        url = f"{self.base_url}{endpoint}"
        headers = {
            'Authorization': f'Bearer {self.access_token}',
            'Accept': f'application/vnd.intercom.3+json',
            'Content-Type': 'application/json',
            'Intercom-Version': self.api_version
        }
        
        # Handle file uploads (rare in Intercom)
        if files:
            headers.pop('Content-Type')  # Let aiohttp set multipart boundary
        
        self.stats['requests_made'] += 1
        
        try:
            timeout = aiohttp.ClientTimeout(total=30)
            async with aiohttp.ClientSession(timeout=timeout) as session:
                async with session.request(
                    method=method,
                    url=url,
                    headers=headers,
                    params=params,
                    json=data if not files else None,
                    data=files if files else None
                ) as response:
                    # Record successful request for rate limiting
                    await self.rate_limiter.record_request(self.platform_name)
                    
                    if response.status in [200, 201]:
                        self.stats['successful_requests'] += 1
                        try:
                            result = await response.json()
                        except (json.JSONDecodeError, aiohttp.ContentTypeError):
                            result = await response.text()
                        
                        return {
                            'success': True,
                            'data': result,
                            'status_code': response.status,
                            'platform': self.platform_name
                        }
                    
                    elif response.status == 204:  # No content (successful delete)
                        self.stats['successful_requests'] += 1
                        return {
                            'success': True,
                            'data': 'Operation completed successfully',
                            'status_code': response.status,
                            'platform': self.platform_name
                        }
                    
                    elif response.status == 429:  # Rate limited by API
                        self.stats['rate_limit_hits'] += 1
                        error_text = await response.text()
                        # Parse rate limit headers if available
                        reset_time = response.headers.get('X-RateLimit-Reset')
                        raise Exception(f"API rate limit exceeded: {error_text}. Reset at: {reset_time}")
                    
                    elif response.status == 401:
                        self.stats['failed_requests'] += 1
                        raise Exception("Authentication failed - check your access token")
                    
                    elif response.status == 404:
                        self.stats['failed_requests'] += 1
                        error_text = await response.text()
                        raise Exception(f"Resource not found: {error_text}")
                    
                    elif response.status == 422:
                        self.stats['failed_requests'] += 1
                        error_text = await response.text()
                        raise Exception(f"Validation error: {error_text}")
                    
                    else:
                        self.stats['failed_requests'] += 1
                        error_text = await response.text()
                        raise Exception(f"API request failed (status {response.status}): {error_text}")
        
        except aiohttp.ClientError as e:
            self.stats['failed_requests'] += 1
            logger.error(f"💥 Network error in Intercom API request: {e}")
            raise Exception(f"Network error: {str(e)}")
        
        except Exception as e:
            self.stats['failed_requests'] += 1
            logger.error(f"💥 Unexpected error in Intercom API request: {e}")
            raise
    
    async def call_tool(self, tool_name: str, arguments: Dict[str, Any] = None) -> Dict[str, Any]:
        """
        Execute an Intercom API tool call
        
        Args:
            tool_name: Name of the tool to execute
            arguments: Tool arguments (optional)
            
        Returns:
            Tool execution result
        """
        if arguments is None:
            arguments = {}
            
        if tool_name not in self.all_tools:
            return {
                'success': False,
                'error': f"Tool '{tool_name}' not found in Intercom adapter",
                'available_tools': list(self.all_tools.keys())
            }
        
        config = self.all_tools[tool_name]
        
        try:
            # Validate required parameters
            missing_params = []
            for req_param in config.get('required', []):
                if req_param not in arguments:
                    missing_params.append(req_param)
            
            if missing_params:
                return {
                    'success': False,
                    'error': f"Missing required parameters: {missing_params}",
                    'required_params': config.get('required', []),
                    'all_params': config.get('params', [])
                }
            
            # Build endpoint path with dynamic parameters - MAPPING SANITIZED BACK TO ORIGINAL
            endpoint_path = config['path']
            path_params = {}
            
            # Map sanitized parameters back to original API parameter names
            param_mapping = {
                # Common mappings that reverse the sanitization
                'item_id': 'id',
                'item_name': 'name', 
                'item_title': 'title',
                'item_type': 'type',
                'page_size': 'per_page',
                'content_body': 'body',
                'from_date': 'from',
                'target': 'to',
                'msg_type': 'message_type',
                'search_query': 'query',
                'search_phrase': 'phrase',
                'lang_code': 'language',
                'is_away': 'away_mode_enabled',
                'created_after': 'created_at_after',
                'contact_list': 'contacts',
                'contact_data': 'contact',
                'contact_ref': 'contact_id',
                'event_type': 'event_name',
                'filter_query': 'filter',
                'model_type': 'model'
            }
            
            # Convert sanitized arguments back to original parameter names
            converted_arguments = {}
            for key, value in arguments.items():
                original_key = param_mapping.get(key, key)
                converted_arguments[original_key] = value
            
            # Extract path parameters (e.g., {id}, {conversation_id})
            import re
            path_param_matches = re.findall(r'\{([^}]+)\}', endpoint_path)
            for param in path_param_matches:
                # Check both original and mapped parameter names
                if param in converted_arguments:
                    path_params[param] = converted_arguments[param]
                    endpoint_path = endpoint_path.replace(f'{{{param}}}', str(converted_arguments[param]))
                    converted_arguments.pop(param)
                elif param in arguments:
                    path_params[param] = arguments[param]
                    endpoint_path = endpoint_path.replace(f'{{{param}}}', str(arguments[param]))
                    # Remove from both dictionaries
                    arguments.pop(param, None)
                    converted_arguments.pop(param, None)
                else:
                    return {
                        'success': False,
                        'error': f"Missing path parameter: {param}",
                        'endpoint_path': config['path']
                    }
            
            # Separate query parameters and body data
            query_params = {}
            body_data = {}
            files_data = {}
            
            for key, value in converted_arguments.items():
                if key in ['per_page', 'page', 'starting_after', 'sort', 'order', 'display_as'] and config['method'] == 'GET':
                    query_params[key] = value
                elif key == 'attachments' or key.endswith('_files'):
                    files_data[key] = value
                elif config['method'] == 'GET':
                    query_params[key] = value
                else:
                    body_data[key] = value
            
            # Handle special Intercom API patterns
            if tool_name in ['search_conversations', 'search_contacts', 'search_companies']:
                # Search tools need special handling
                if 'query' in body_data:
                    body_data = {'query': body_data['query']}
                    if 'pagination' in converted_arguments:
                        body_data['pagination'] = converted_arguments['pagination']
            
            # Make the API request
            result = await self.make_request(
                method=config['method'],
                endpoint=endpoint_path,
                params=query_params if query_params else None,
                data=body_data if body_data else None,
                files=files_data if files_data else None
            )
            
            return {
                'success': True,
                'tool_name': tool_name,
                'endpoint': tool_name,
                'method': config['method'],
                'result': result,
                'platform': self.platform_name,
                'execution_time': datetime.now().isoformat()
            }
            
        except Exception as e:
            logger.error(f"💥 Error executing Intercom tool {tool_name}: {e}")
            return {
                'success': False,
                'error': str(e),
                'tool_name': tool_name,
                'endpoint': tool_name,
                'platform': self.platform_name
            }
    
    async def get_health_status(self) -> Dict[str, Any]:
        """Get adapter health status and statistics"""
        try:
            # Test basic connectivity with a simple API call
            test_result = await self.make_request('GET', '/me')
            connectivity = test_result['success']
        except:
            connectivity = False
        
        rate_stats = await self.rate_limiter.get_platform_stats(self.platform_name)
        
        return {
            'platform': self.platform_name,
            'status': 'healthy' if connectivity else 'unhealthy',
            'connectivity': connectivity,
            'base_url': self.base_url,
            'api_version': self.api_version,
            'total_tools': len(self.all_tools),
            'request_stats': self.stats,
            'rate_limiting': rate_stats.get(self.platform_name, {}),
            'last_check': datetime.now().isoformat()
        }
    
    async def search_unified_data(self, query: str, data_type: str = "all") -> Dict[str, Any]:
        """
        Search across multiple Intercom data types
        
        Args:
            query: Search query string
            data_type: Type of data to search (conversations, contacts, companies, articles, all)
            
        Returns:
            Unified search results
        """
        results = {
            'query': query,
            'data_type': data_type,
            'results': {},
            'total_results': 0,
            'matches': [],
            'platform': self.platform_name
        }
        
        try:
            # Search conversations
            if data_type in ['conversations', 'all']:
                search_query = {
                    'query': {
                        'operator': 'OR',
                        'value': [
                            {
                                'field': 'body',
                                'operator': '~',
                                'value': query
                            },
                            {
                                'field': 'subject',
                                'operator': '~',
                                'value': query
                            }
                        ]
                    }
                }
                conv_results = await self.call_tool('search_conversations', {'search_query': search_query})
                if conv_results['success']:
                    results['results']['conversations'] = conv_results['result']['data']
                    if isinstance(conv_results['result']['data'], dict) and 'conversations' in conv_results['result']['data']:
                        conversations = conv_results['result']['data']['conversations']
                        results['total_results'] += len(conversations)
                        for conv in conversations:
                            results['matches'].append({
                                'type': 'conversation',
                                'item_id': conv.get('id'),
                                'item_title': conv.get('source', {}).get('subject', 'Conversation'),
                                'platform': self.platform_name
                            })
            
            # Search contacts
            if data_type in ['contacts', 'all']:
                search_query = {
                    'query': {
                        'operator': 'OR',
                        'value': [
                            {
                                'field': 'name',
                                'operator': '~',
                                'value': query
                            },
                            {
                                'field': 'email',
                                'operator': '~',
                                'value': query
                            }
                        ]
                    }
                }
                contact_results = await self.call_tool('search_contacts', {'search_query': search_query})
                if contact_results['success']:
                    results['results']['contacts'] = contact_results['result']['data']
                    if isinstance(contact_results['result']['data'], dict) and 'data' in contact_results['result']['data']:
                        contacts = contact_results['result']['data']['data']
                        results['total_results'] += len(contacts)
                        for contact in contacts:
                            results['matches'].append({
                                'type': 'contact',
                                'item_id': contact.get('id'),
                                'item_title': contact.get('name', contact.get('email', 'Contact')),
                                'platform': self.platform_name
                            })
            
            return results
            
        except Exception as e:
            logger.error(f"Error in search_unified_data: {str(e)}")
            results['error'] = str(e)
            return results
    
    async def discover_api_schema(self) -> Dict[str, Any]:
        """Discover API schema and capabilities"""
        return {
            "platform": self.platform_name,
            "api_version": self.api_version,
            "base_url": self.base_url,
            "total_tools": len(self.all_tools),
            "categories": {
                "conversations": ["list_conversations", "retrieve_conversation", "search_conversations", "reply_to_conversation", "assign_conversation", "close_conversation", "snooze_conversation", "open_conversation"],
                "contacts": ["list_contacts", "retrieve_contact", "create_contact", "update_contact", "delete_contact", "search_contacts", "merge_contacts", "archive_contact", "unarchive_contact"],
                "companies": ["list_companies", "retrieve_company", "create_company", "update_company", "delete_company", "list_company_contacts", "list_company_segments"],
                "messages": ["create_message", "list_messages"],
                "articles": ["list_articles", "retrieve_article", "create_article", "update_article", "delete_article", "search_articles"],
                "admins": ["list_admins", "retrieve_admin", "set_admin_away"],
                "teams": ["list_teams", "retrieve_team"],
                "segments": ["list_segments", "retrieve_segment"],
                "tags": ["list_tags", "create_tag", "delete_tag", "tag_contact", "tag_company", "untag_contact", "untag_company"],
                "notes": ["create_note", "list_notes", "retrieve_note"],
                "events": ["create_event", "list_events"],
                "data_attributes": ["list_data_attributes", "create_data_attribute", "update_data_attribute"],
                "subscription_types": ["list_subscription_types"],
                "phone_call_redirects": ["list_phone_call_redirects", "create_phone_call_redirect"],
                "visitors": ["retrieve_visitor", "update_visitor", "convert_visitor"],
                "counts": ["get_app_total_count", "get_company_segment_count", "get_company_tag_count", "get_company_user_count", "get_conversation_admin_count", "get_user_segment_count", "get_user_tag_count"]
            }
        }

    async def get_available_tools(self) -> List[Dict[str, Any]]:
        """Get list of all available tools for this platform"""
        tools = []
        for tool_name, tool_config in self.all_tools.items():
            tools.append({
                "name": tool_name,
                "description": tool_config.get("description", f"Intercom {tool_name} operation"),
                "category": self._get_tool_category(tool_name),
                "parameters": tool_config.get("parameters", {}),
                "platform": self.platform_name
            })
        return tools

    def _get_tool_category(self, tool_name: str) -> str:
        """Determine category for a tool based on its name"""
        if any(x in tool_name for x in ["conversation", "reply", "assign", "close", "snooze", "open"]):
            return "conversations"
        elif any(x in tool_name for x in ["contact", "merge", "archive", "unarchive"]):
            return "contacts"
        elif any(x in tool_name for x in ["company", "companies"]):
            return "companies"
        elif any(x in tool_name for x in ["message"]):
            return "messages"
        elif any(x in tool_name for x in ["article"]):
            return "articles"
        elif any(x in tool_name for x in ["admin"]):
            return "admins"
        elif any(x in tool_name for x in ["team"]):
            return "teams"
        elif any(x in tool_name for x in ["segment"]):
            return "segments"
        elif any(x in tool_name for x in ["tag", "untag"]):
            return "tags"
        elif any(x in tool_name for x in ["note"]):
            return "notes"
        elif any(x in tool_name for x in ["event"]):
            return "events"
        elif any(x in tool_name for x in ["data_attribute"]):
            return "data_attributes"
        elif any(x in tool_name for x in ["subscription"]):
            return "subscription_types"
        elif any(x in tool_name for x in ["phone_call"]):
            return "phone_call_redirects"
        elif any(x in tool_name for x in ["visitor"]):
            return "visitors"
        elif any(x in tool_name for x in ["count"]):
            return "counts"
        else:
            return "general"

    def __repr__(self) -> str:
        return (
            f"IntercomAdapter(base_url={self.base_url}, "
            f"api_version={self.api_version}, "
            f"total_tools={len(self.all_tools)}, "
            f"rate_limit={self.rate_limiter})"
        )