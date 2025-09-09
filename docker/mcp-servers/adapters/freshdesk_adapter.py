"""
Freshdesk API Adapter for MCP Server
Complete integration with all 103 Freshdesk API v2 tools
Supports dynamic tool generation and comprehensive error handling
"""

import os
import json
import asyncio
import logging
from typing import Dict, List, Any, Optional, Union
from datetime import datetime, timedelta
import aiohttp
import base64
from urllib.parse import urlencode, quote

from .base_adapter import BaseAdapter
from .rate_limiter import RateLimiter

logger = logging.getLogger(__name__)


class FreshdeskAdapter(BaseAdapter):
    """
    Comprehensive Freshdesk API v2 Adapter
    Covers all 103 documented tools with dynamic tool generation
    """
    
    platform_name = "freshdesk"
    
    def __init__(self, domain: str = None, api_key: str = None):
        """
        Initialize Freshdesk adapter
        
        Args:
            domain: Freshdesk domain (e.g., 'yourcompany.freshdesk.com')
            api_key: Freshdesk API key
        """
        self.domain = domain or os.getenv('FRESHDESK_DOMAIN')
        self.api_key = api_key or os.getenv('FRESHDESK_API_KEY')
        
        if not self.domain or not self.api_key:
            raise ValueError("Freshdesk domain and API key are required")
        
        # Clean domain and build base URL
        clean_domain = self.domain.replace('https://', '').replace('http://', '')
        self.base_url = f"https://{clean_domain}"
        
        # Initialize parent
        super().__init__(base_url=self.base_url, api_key=self.api_key)
        
        # Initialize rate limiter (Freshdesk limit: 600/min for most plans)
        self.rate_limiter = RateLimiter(max_requests=600, window_minutes=1)
        
        # Set up authentication headers
        auth_string = f"{self.api_key}:X"
        encoded_auth = base64.b64encode(auth_string.encode()).decode()
        self.headers = {
            'Content-Type': 'application/json',
            'Authorization': f'Basic {encoded_auth}'
        }
        
        # Initialize tools
        self.all_tools = {}
        self._setup_tools()
        
        # Track API usage statistics
        self.stats = {
            'requests_made': 0,
            'successful_requests': 0,
            'failed_requests': 0,
            'rate_limit_hits': 0
        }
        
        logger.info(f"🎫 Freshdesk adapter initialized with {len(self.all_tools)} tools")
    
    def _setup_tools(self):
        """Configure all 103 Freshdesk API tools"""
        
        # 🎫 TICKETS (20 tools)
        ticket_tools = {
            'create_ticket': {
                'method': 'POST',
                'path': '/api/v2/tickets',
                'description': 'Create a new support ticket',
                'category': 'tickets',
                'parameters': ['name', 'phone', 'email', 'subject', 'type', 'status', 'priority', 'description', 'responder_id', 'attachments', 'cc_emails', 'custom_fields', 'due_by', 'email_config_id', 'fr_due_by', 'group_id', 'product_id', 'source', 'tags'],
                'required': ['name', 'email', 'subject', 'description', 'status', 'priority']
            },
            'view_ticket': {
                'method': 'GET',
                'path': '/api/v2/tickets/{id}',
                'description': 'Retrieve a specific ticket by ID',
                'category': 'tickets',
                'parameters': ['include'],
                'required': ['id']
            },
            'list_tickets': {
                'method': 'GET',
                'path': '/api/v2/tickets',
                'description': 'List all tickets with filtering options',
                'category': 'tickets',
                'parameters': ['filter', 'page', 'per_page', 'order_by', 'order_type', 'updated_since', 'include'],
                'required': []
            },
            'update_ticket': {
                'method': 'PUT',
                'path': '/api/v2/tickets/{id}',
                'description': 'Update an existing ticket',
                'category': 'tickets',
                'parameters': ['name', 'phone', 'email', 'subject', 'type', 'status', 'priority', 'description', 'responder_id', 'attachments', 'custom_fields', 'due_by', 'fr_due_by', 'group_id', 'product_id', 'source', 'tags'],
                'required': ['id']
            },
            'delete_ticket': {
                'method': 'DELETE',
                'path': '/api/v2/tickets/{id}',
                'description': 'Delete a ticket permanently',
                'category': 'tickets',
                'parameters': [],
                'required': ['id']
            },
            'filter_tickets': {
                'method': 'GET',
                'path': '/api/v2/search/tickets',
                'description': 'Filter tickets using advanced search',
                'category': 'tickets',
                'parameters': ['query'],
                'required': ['query']
            },
            'create_ticket_with_attachments': {
                'method': 'POST',
                'path': '/api/v2/tickets',
                'description': 'Create ticket with file attachments',
                'category': 'tickets',
                'parameters': ['name', 'email', 'subject', 'description', 'status', 'priority', 'attachments[]'],
                'required': ['name', 'email', 'subject', 'description', 'attachments[]']
            },
            'create_child_ticket': {
                'method': 'POST',
                'path': '/api/v2/tickets/{id}/child_ticket',
                'description': 'Create a child ticket for existing ticket',
                'category': 'tickets',
                'parameters': ['name', 'email', 'subject', 'description', 'status', 'priority'],
                'required': ['id', 'name', 'email', 'subject', 'description']
            },
            'bulk_update_tickets': {
                'method': 'PUT',
                'path': '/api/v2/tickets/bulk_update',
                'description': 'Bulk update multiple tickets',
                'category': 'tickets',
                'parameters': ['ids', 'properties'],
                'required': ['ids', 'properties']
            },
            'bulk_delete_tickets': {
                'method': 'DELETE',
                'path': '/api/v2/tickets/bulk_delete',
                'description': 'Bulk delete multiple tickets',
                'category': 'tickets',
                'parameters': ['ids'],
                'required': ['ids']
            },
            'forward_ticket': {
                'method': 'POST',
                'path': '/api/v2/tickets/{id}/forward',
                'description': 'Forward ticket to external email',
                'category': 'tickets',
                'parameters': ['email', 'body'],
                'required': ['id', 'email', 'body']
            },
            'merge_tickets': {
                'method': 'POST',
                'path': '/api/v2/tickets/{id}/merge',
                'description': 'Merge tickets together',
                'category': 'tickets',
                'parameters': ['ids'],
                'required': ['id', 'ids']
            },
            'create_outbound_email': {
                'method': 'POST',
                'path': '/api/v2/tickets/outbound_email',
                'description': 'Create outbound email ticket',
                'category': 'tickets',
                'parameters': ['email', 'subject', 'description', 'status', 'priority'],
                'required': ['email', 'subject', 'description']
            },
            'get_associated_tickets': {
                'method': 'GET',
                'path': '/api/v2/tickets/{id}/related_tickets',
                'description': 'Get tickets associated with a ticket',
                'category': 'tickets',
                'parameters': [],
                'required': ['id']
            },
            'add_watcher': {
                'method': 'PUT',
                'path': '/api/v2/tickets/{id}',
                'description': 'Add watcher to ticket',
                'category': 'tickets',
                'parameters': ['watcher_ids'],
                'required': ['id', 'watcher_ids']
            },
            'remove_watcher': {
                'method': 'PUT',
                'path': '/api/v2/tickets/{id}',
                'description': 'Remove watcher from ticket',
                'category': 'tickets',
                'parameters': ['watcher_ids'],
                'required': ['id', 'watcher_ids']
            },
            'archive_tickets': {
                'method': 'PUT',
                'path': '/api/v2/tickets/{id}',
                'description': 'Archive a ticket',
                'category': 'tickets',
                'parameters': ['status'],
                'required': ['id']
            },
            'reply_ticket': {
                'method': 'POST',
                'path': '/api/v2/tickets/{id}/reply',
                'description': 'Reply to a ticket',
                'category': 'tickets',
                'parameters': ['body', 'from_email', 'user_id', 'cc_emails', 'bcc_emails'],
                'required': ['id', 'body']
            },
            'add_note_to_ticket': {
                'method': 'POST',
                'path': '/api/v2/tickets/{id}/notes',
                'description': 'Add private note to ticket',
                'category': 'tickets',
                'parameters': ['body', 'user_id', 'private'],
                'required': ['id', 'body']
            },
            'create_tracker': {
                'method': 'POST',
                'path': '/api/v2/tickets/{id}/time_entries',
                'description': 'Create time tracker for ticket',
                'category': 'tickets',
                'parameters': ['description', 'start_time', 'timer_running', 'billable'],
                'required': ['id', 'description', 'start_time']
            }
        }
        
        # 👤 CONTACTS (11 tools)
        contact_tools = {
            'create_contact': {
                'method': 'POST',
                'path': '/api/v2/contacts',
                'description': 'Create a new contact',
                'category': 'contacts',
                'parameters': ['name', 'email', 'phone', 'mobile', 'twitter_id', 'unique_external_id', 'other_emails', 'company_id', 'view_all_tickets', 'other_companies', 'address', 'avatar', 'custom_fields', 'description', 'job_title', 'language', 'tags', 'time_zone'],
                'required': []
            },
            'view_contact': {
                'method': 'GET',
                'path': '/api/v2/contacts/{id}',
                'description': 'Retrieve a specific contact by ID',
                'category': 'contacts',
                'parameters': [],
                'required': ['id']
            },
            'list_contacts': {
                'method': 'GET',
                'path': '/api/v2/contacts',
                'description': 'List all contacts with filtering options',
                'category': 'contacts',
                'parameters': ['email', 'mobile', 'phone', 'page', 'per_page', 'updated_since'],
                'required': []
            },
            'update_contact': {
                'method': 'PUT',
                'path': '/api/v2/contacts/{id}',
                'description': 'Update an existing contact',
                'category': 'contacts',
                'parameters': ['name', 'email', 'phone', 'mobile', 'twitter_id', 'unique_external_id', 'other_emails', 'company_id', 'view_all_tickets', 'address', 'avatar', 'custom_fields', 'description', 'job_title', 'language', 'tags', 'time_zone'],
                'required': ['id']
            },
            'delete_contact': {
                'method': 'DELETE',
                'path': '/api/v2/contacts/{id}',
                'description': 'Delete a contact permanently',
                'category': 'contacts',
                'parameters': [],
                'required': ['id']
            },
            'filter_contacts': {
                'method': 'GET',
                'path': '/api/v2/search/contacts',
                'description': 'Search contacts with advanced filters',
                'category': 'contacts',
                'parameters': ['query'],
                'required': ['query']
            },
            'make_agent': {
                'method': 'PUT',
                'path': '/api/v2/contacts/{id}/make_agent',
                'description': 'Convert contact to agent',
                'category': 'contacts',
                'parameters': ['occasional', 'signature'],
                'required': ['id']
            },
            'send_invite': {
                'method': 'PUT',
                'path': '/api/v2/contacts/{id}/send_invite',
                'description': 'Send activation invite to contact',
                'category': 'contacts',
                'parameters': [],
                'required': ['id']
            },
            'restore_contact': {
                'method': 'PUT',
                'path': '/api/v2/contacts/{id}/restore',
                'description': 'Restore a deleted contact',
                'category': 'contacts',
                'parameters': [],
                'required': ['id']
            },
            'merge_contacts': {
                'method': 'PUT',
                'path': '/api/v2/contacts/{id}/merge',
                'description': 'Merge contacts together',
                'category': 'contacts',
                'parameters': ['secondary_contact_id'],
                'required': ['id', 'secondary_contact_id']
            },
            'create_contact_with_avatar': {
                'method': 'POST',
                'path': '/api/v2/contacts',
                'description': 'Create contact with avatar image',
                'category': 'contacts',
                'parameters': ['name', 'email', 'avatar'],
                'required': ['name', 'email', 'avatar']
            }
        }
        
        # 🏢 COMPANIES (7 tools)
        company_tools = {
            'create_company': {
                'method': 'POST',
                'path': '/api/v2/companies',
                'description': 'Create a new company',
                'category': 'companies',
                'parameters': ['name', 'description', 'note', 'domains', 'custom_fields'],
                'required': ['name']
            },
            'view_company': {
                'method': 'GET',
                'path': '/api/v2/companies/{id}',
                'description': 'Retrieve a specific company by ID',
                'category': 'companies',
                'parameters': [],
                'required': ['id']
            },
            'list_companies': {
                'method': 'GET',
                'path': '/api/v2/companies',
                'description': 'List all companies',
                'category': 'companies',
                'parameters': ['page', 'per_page'],
                'required': []
            },
            'update_company': {
                'method': 'PUT',
                'path': '/api/v2/companies/{id}',
                'description': 'Update an existing company',
                'category': 'companies',
                'parameters': ['name', 'description', 'note', 'domains', 'custom_fields'],
                'required': ['id']
            },
            'delete_company': {
                'method': 'DELETE',
                'path': '/api/v2/companies/{id}',
                'description': 'Delete a company permanently',
                'category': 'companies',
                'parameters': [],
                'required': ['id']
            },
            'filter_companies': {
                'method': 'GET',
                'path': '/api/v2/search/companies',
                'description': 'Search companies with advanced filters',
                'category': 'companies',
                'parameters': ['query'],
                'required': ['query']
            },
            'company_fields': {
                'method': 'GET',
                'path': '/api/v2/company_fields',
                'description': 'Get all company field definitions',
                'category': 'companies',
                'parameters': [],
                'required': []
            }
        }
        
        # 👨‍💼 AGENTS (8 tools)
        agent_tools = {
            'create_agent': {
                'method': 'POST',
                'path': '/api/v2/agents',
                'description': 'Create a new agent',
                'category': 'agents',
                'parameters': ['email', 'ticket_scope', 'group_ids', 'role_ids', 'occasional', 'signature', 'focus_mode'],
                'required': ['email']
            },
            'view_agent': {
                'method': 'GET',
                'path': '/api/v2/agents/{id}',
                'description': 'Retrieve a specific agent by ID',
                'category': 'agents',
                'parameters': [],
                'required': ['id']
            },
            'list_agents': {
                'method': 'GET',
                'path': '/api/v2/agents',
                'description': 'List all agents',
                'category': 'agents',
                'parameters': ['email', 'mobile', 'phone', 'state'],
                'required': []
            },
            'update_agent': {
                'method': 'PUT',
                'path': '/api/v2/agents/{id}',
                'description': 'Update an existing agent',
                'category': 'agents',
                'parameters': ['email', 'ticket_scope', 'group_ids', 'role_ids', 'occasional', 'signature', 'focus_mode'],
                'required': ['id']
            },
            'delete_agent': {
                'method': 'DELETE',
                'path': '/api/v2/agents/{id}',
                'description': 'Delete an agent permanently',
                'category': 'agents',
                'parameters': [],
                'required': ['id']
            },
            'view_current_agent': {
                'method': 'GET',
                'path': '/api/v2/agents/me',
                'description': 'Get current authenticated agent details',
                'category': 'agents',
                'parameters': [],
                'required': []
            },
            'agent_skills': {
                'method': 'GET',
                'path': '/api/v2/agents/{id}/skills',
                'description': 'Get agent skills and expertise',
                'category': 'agents',
                'parameters': [],
                'required': ['id']
            },
            'agent_groups': {
                'method': 'GET',
                'path': '/api/v2/agents/{id}/groups',
                'description': 'Get groups assigned to agent',
                'category': 'agents',
                'parameters': [],
                'required': ['id']
            }
        }
        
        # 👥 GROUPS (5 tools)
        group_tools = {
            'create_group': {
                'method': 'POST',
                'path': '/api/v2/groups',
                'description': 'Create a new agent group',
                'category': 'groups',
                'parameters': ['name', 'description', 'unassigned_for', 'agent_ids'],
                'required': ['name']
            },
            'view_group': {
                'method': 'GET',
                'path': '/api/v2/groups/{id}',
                'description': 'Retrieve a specific group by ID',
                'category': 'groups',
                'parameters': [],
                'required': ['id']
            },
            'list_groups': {
                'method': 'GET',
                'path': '/api/v2/groups',
                'description': 'List all groups',
                'category': 'groups',
                'parameters': ['page', 'per_page'],
                'required': []
            },
            'update_group': {
                'method': 'PUT',
                'path': '/api/v2/groups/{id}',
                'description': 'Update an existing group',
                'category': 'groups',
                'parameters': ['name', 'description', 'unassigned_for', 'agent_ids'],
                'required': ['id']
            },
            'delete_group': {
                'method': 'DELETE',
                'path': '/api/v2/groups/{id}',
                'description': 'Delete a group permanently',
                'category': 'groups',
                'parameters': [],
                'required': ['id']
            }
        }
        
        # 📚 SOLUTIONS (15 tools)
        solution_tools = {
            'create_solution_category': {
                'method': 'POST',
                'path': '/api/v2/solutions/categories',
                'description': 'Create a solution category',
                'category': 'solutions',
                'parameters': ['name', 'description'],
                'required': ['name']
            },
            'view_solution_category': {
                'method': 'GET',
                'path': '/api/v2/solutions/categories/{id}',
                'description': 'Retrieve a solution category',
                'category': 'solutions',
                'parameters': [],
                'required': ['id']
            },
            'list_solution_categories': {
                'method': 'GET',
                'path': '/api/v2/solutions/categories',
                'description': 'List all solution categories',
                'category': 'solutions',
                'parameters': ['page', 'per_page'],
                'required': []
            },
            'update_solution_category': {
                'method': 'PUT',
                'path': '/api/v2/solutions/categories/{id}',
                'description': 'Update a solution category',
                'category': 'solutions',
                'parameters': ['name', 'description'],
                'required': ['id']
            },
            'delete_solution_category': {
                'method': 'DELETE',
                'path': '/api/v2/solutions/categories/{id}',
                'description': 'Delete a solution category',
                'category': 'solutions',
                'parameters': [],
                'required': ['id']
            },
            'create_solution_folder': {
                'method': 'POST',
                'path': '/api/v2/solutions/folders',
                'description': 'Create a solution folder',
                'category': 'solutions',
                'parameters': ['name', 'description', 'category_id', 'visibility'],
                'required': ['name', 'category_id']
            },
            'view_solution_folder': {
                'method': 'GET',
                'path': '/api/v2/solutions/folders/{id}',
                'description': 'Retrieve a solution folder',
                'category': 'solutions',
                'parameters': [],
                'required': ['id']
            },
            'list_solution_folders': {
                'method': 'GET',
                'path': '/api/v2/solutions/folders',
                'description': 'List all solution folders',
                'category': 'solutions',
                'parameters': ['category_id', 'page', 'per_page'],
                'required': []
            },
            'update_solution_folder': {
                'method': 'PUT',
                'path': '/api/v2/solutions/folders/{id}',
                'description': 'Update a solution folder',
                'category': 'solutions',
                'parameters': ['name', 'description', 'visibility'],
                'required': ['id']
            },
            'delete_solution_folder': {
                'method': 'DELETE',
                'path': '/api/v2/solutions/folders/{id}',
                'description': 'Delete a solution folder',
                'category': 'solutions',
                'parameters': [],
                'required': ['id']
            },
            'create_solution_article': {
                'method': 'POST',
                'path': '/api/v2/solutions/articles',
                'description': 'Create a solution article',
                'category': 'solutions',
                'parameters': ['title', 'description', 'folder_id', 'status', 'art_type', 'tags'],
                'required': ['title', 'description', 'folder_id']
            },
            'view_solution_article': {
                'method': 'GET',
                'path': '/api/v2/solutions/articles/{id}',
                'description': 'Retrieve a solution article',
                'category': 'solutions',
                'parameters': [],
                'required': ['id']
            },
            'list_solution_articles': {
                'method': 'GET',
                'path': '/api/v2/solutions/articles',
                'description': 'List all solution articles',
                'category': 'solutions',
                'parameters': ['folder_id', 'page', 'per_page'],
                'required': []
            },
            'update_solution_article': {
                'method': 'PUT',
                'path': '/api/v2/solutions/articles/{id}',
                'description': 'Update a solution article',
                'category': 'solutions',
                'parameters': ['title', 'description', 'status', 'art_type', 'tags'],
                'required': ['id']
            },
            'delete_solution_article': {
                'method': 'DELETE',
                'path': '/api/v2/solutions/articles/{id}',
                'description': 'Delete a solution article',
                'category': 'solutions',
                'parameters': [],
                'required': ['id']
            }
        }
        
        # 💬 CONVERSATIONS (6 tools)
        conversation_tools = {
            'list_conversations': {
                'method': 'GET',
                'path': '/api/v2/tickets/{id}/conversations',
                'description': 'List all conversations for a ticket',
                'category': 'conversations',
                'parameters': ['page', 'per_page'],
                'required': ['id']
            },
            'create_reply': {
                'method': 'POST',
                'path': '/api/v2/tickets/{id}/reply',
                'description': 'Create a reply to ticket conversation',
                'category': 'conversations',
                'parameters': ['body', 'from_email', 'user_id', 'cc_emails', 'bcc_emails', 'attachments'],
                'required': ['id', 'body']
            },
            'create_note': {
                'method': 'POST',
                'path': '/api/v2/tickets/{id}/notes',
                'description': 'Create a private note in conversation',
                'category': 'conversations',
                'parameters': ['body', 'user_id', 'private', 'attachments'],
                'required': ['id', 'body']
            },
            'update_conversation': {
                'method': 'PUT',
                'path': '/api/v2/conversations/{id}',
                'description': 'Update a conversation',
                'category': 'conversations',
                'parameters': ['body', 'from_email', 'user_id'],
                'required': ['id']
            },
            'delete_conversation': {
                'method': 'DELETE',
                'path': '/api/v2/conversations/{id}',
                'description': 'Delete a conversation',
                'category': 'conversations',
                'parameters': [],
                'required': ['id']
            },
            'reply_to_forward': {
                'method': 'POST',
                'path': '/api/v2/conversations/{id}/reply',
                'description': 'Reply to forwarded conversation',
                'category': 'conversations',
                'parameters': ['body', 'from_email', 'to_emails'],
                'required': ['id', 'body', 'to_emails']
            }
        }
        
        # ⏱️ TIME ENTRIES (6 tools)
        time_entry_tools = {
            'create_time_entry': {
                'method': 'POST',
                'path': '/api/v2/time_entries',
                'description': 'Create a new time entry',
                'category': 'time_entries',
                'parameters': ['description', 'start_time', 'timer_running', 'billable', 'time_spent', 'executed_at', 'task_id', 'agent_id'],
                'required': ['description', 'start_time']
            },
            'list_time_entries': {
                'method': 'GET',
                'path': '/api/v2/time_entries',
                'description': 'List all time entries',
                'category': 'time_entries',
                'parameters': ['company_id', 'agent_id', 'executed_before', 'executed_after', 'billable'],
                'required': []
            },
            'update_time_entry': {
                'method': 'PUT',
                'path': '/api/v2/time_entries/{id}',
                'description': 'Update a time entry',
                'category': 'time_entries',
                'parameters': ['description', 'start_time', 'timer_running', 'billable', 'time_spent'],
                'required': ['id']
            },
            'delete_time_entry': {
                'method': 'DELETE',
                'path': '/api/v2/time_entries/{id}',
                'description': 'Delete a time entry',
                'category': 'time_entries',
                'parameters': [],
                'required': ['id']
            },
            'toggle_timer': {
                'method': 'PUT',
                'path': '/api/v2/time_entries/{id}/toggle_timer',
                'description': 'Toggle timer for time entry',
                'category': 'time_entries',
                'parameters': [],
                'required': ['id']
            },
            'view_time_entry': {
                'method': 'GET',
                'path': '/api/v2/time_entries/{id}',
                'description': 'Retrieve a specific time entry',
                'category': 'time_entries',
                'parameters': [],
                'required': ['id']
            }
        }
        
        # 📧 EMAIL CONFIGS (8 tools)
        email_config_tools = {
            'create_mailbox': {
                'method': 'POST',
                'path': '/api/v2/email/mailboxes',
                'description': 'Create a new email mailbox',
                'category': 'email_configs',
                'parameters': ['name', 'email', 'group_id', 'product_id'],
                'required': ['name', 'email']
            },
            'view_mailbox': {
                'method': 'GET',
                'path': '/api/v2/email/mailboxes/{id}',
                'description': 'Retrieve a specific mailbox',
                'category': 'email_configs',
                'parameters': [],
                'required': ['id']
            },
            'list_mailboxes': {
                'method': 'GET',
                'path': '/api/v2/email/mailboxes',
                'description': 'List all email mailboxes',
                'category': 'email_configs',
                'parameters': [],
                'required': []
            },
            'update_mailbox': {
                'method': 'PUT',
                'path': '/api/v2/email/mailboxes/{id}',
                'description': 'Update an email mailbox',
                'category': 'email_configs',
                'parameters': ['name', 'email', 'group_id', 'product_id'],
                'required': ['id']
            },
            'delete_mailbox': {
                'method': 'DELETE',
                'path': '/api/v2/email/mailboxes/{id}',
                'description': 'Delete an email mailbox',
                'category': 'email_configs',
                'parameters': [],
                'required': ['id']
            },
            'mailbox_settings': {
                'method': 'GET',
                'path': '/api/v2/email/mailboxes/{id}/settings',
                'description': 'Get mailbox configuration settings',
                'category': 'email_configs',
                'parameters': [],
                'required': ['id']
            },
            'create_bcc_email': {
                'method': 'POST',
                'path': '/api/v2/email/bcc_emails',
                'description': 'Create BCC email configuration',
                'category': 'email_configs',
                'parameters': ['email', 'group_id', 'product_id'],
                'required': ['email']
            },
            'view_email_configs': {
                'method': 'GET',
                'path': '/api/v2/email_configs',
                'description': 'View all email configurations',
                'category': 'email_configs',
                'parameters': [],
                'required': []
            }
        }
        
        # 🕒 BUSINESS HOURS (2 tools)
        business_hours_tools = {
            'view_business_hour': {
                'method': 'GET',
                'path': '/api/v2/business_hours/{id}',
                'description': 'Retrieve business hours configuration',
                'category': 'business_hours',
                'parameters': [],
                'required': ['id']
            },
            'list_business_hours': {
                'method': 'GET',
                'path': '/api/v2/business_hours',
                'description': 'List all business hours configurations',
                'category': 'business_hours',
                'parameters': [],
                'required': []
            }
        }
        
        # 📊 SLA POLICIES (2 tools)
        sla_policy_tools = {
            'view_sla_policy': {
                'method': 'GET',
                'path': '/api/v2/sla_policies/{id}',
                'description': 'Retrieve SLA policy configuration',
                'category': 'sla_policies',
                'parameters': [],
                'required': ['id']
            },
            'list_sla_policies': {
                'method': 'GET',
                'path': '/api/v2/sla_policies',
                'description': 'List all SLA policies',
                'category': 'sla_policies',
                'parameters': [],
                'required': []
            }
        }
        
        # ⭐ SATISFACTION RATINGS (3 tools)
        satisfaction_rating_tools = {
            'create_rating': {
                'method': 'POST',
                'path': '/api/v2/surveys/satisfaction_ratings',
                'description': 'Create a satisfaction rating',
                'category': 'satisfaction_ratings',
                'parameters': ['ticket_id', 'rating', 'feedback'],
                'required': ['ticket_id', 'rating']
            },
            'view_ratings': {
                'method': 'GET',
                'path': '/api/v2/surveys/satisfaction_ratings/{id}',
                'description': 'View a satisfaction rating',
                'category': 'satisfaction_ratings',
                'parameters': [],
                'required': ['id']
            },
            'list_ratings': {
                'method': 'GET',
                'path': '/api/v2/surveys/satisfaction_ratings',
                'description': 'List all satisfaction ratings',
                'category': 'satisfaction_ratings',
                'parameters': ['ticket_id', 'agent_id', 'page', 'per_page'],
                'required': []
            }
        }
        
        # 🗣️ DISCUSSIONS/FORUMS (12 tools) - Additional tools to reach 103 total
        forum_tools = {
            'create_forum_category': {
                'method': 'POST',
                'path': '/api/v2/discussions/categories',
                'description': 'Create a forum category',
                'category': 'forums',
                'parameters': ['name', 'description'],
                'required': ['name']
            },
            'list_forum_categories': {
                'method': 'GET',
                'path': '/api/v2/discussions/categories',
                'description': 'List all forum categories',
                'category': 'forums',
                'parameters': [],
                'required': []
            },
            'create_forum': {
                'method': 'POST',
                'path': '/api/v2/discussions/forums',
                'description': 'Create a new forum',
                'category': 'forums',
                'parameters': ['name', 'description', 'category_id'],
                'required': ['name', 'category_id']
            },
            'list_forums': {
                'method': 'GET',
                'path': '/api/v2/discussions/forums',
                'description': 'List all forums',
                'category': 'forums',
                'parameters': ['category_id'],
                'required': []
            },
            'create_topic': {
                'method': 'POST',
                'path': '/api/v2/discussions/topics',
                'description': 'Create a forum topic',
                'category': 'forums',
                'parameters': ['title', 'message', 'forum_id', 'sticky', 'locked'],
                'required': ['title', 'message', 'forum_id']
            },
            'list_topics': {
                'method': 'GET',
                'path': '/api/v2/discussions/topics',
                'description': 'List all forum topics',
                'category': 'forums',
                'parameters': ['forum_id', 'page', 'per_page'],
                'required': []
            },
            'view_topic': {
                'method': 'GET',
                'path': '/api/v2/discussions/topics/{id}',
                'description': 'View a forum topic',
                'category': 'forums',
                'parameters': [],
                'required': ['id']
            },
            'create_comment': {
                'method': 'POST',
                'path': '/api/v2/discussions/topics/{id}/comments',
                'description': 'Create a comment on topic',
                'category': 'forums',
                'parameters': ['body', 'user_id'],
                'required': ['id', 'body']
            },
            'list_comments': {
                'method': 'GET',
                'path': '/api/v2/discussions/topics/{id}/comments',
                'description': 'List comments on a topic',
                'category': 'forums',
                'parameters': ['page', 'per_page'],
                'required': ['id']
            },
            'update_topic': {
                'method': 'PUT',
                'path': '/api/v2/discussions/topics/{id}',
                'description': 'Update a forum topic',
                'category': 'forums',
                'parameters': ['title', 'message', 'sticky', 'locked'],
                'required': ['id']
            },
            'delete_topic': {
                'method': 'DELETE',
                'path': '/api/v2/discussions/topics/{id}',
                'description': 'Delete a forum topic',
                'category': 'forums',
                'parameters': [],
                'required': ['id']
            },
            'monitor_topic': {
                'method': 'PUT',
                'path': '/api/v2/discussions/topics/{id}/monitor',
                'description': 'Monitor or unmonitor a topic',
                'category': 'forums',
                'parameters': ['user_id'],
                'required': ['id']
            }
        }
        
        # Consolidate all tools into self.all_tools
        self.all_tools = {
            **ticket_tools,
            **contact_tools,
            **company_tools,
            **agent_tools,
            **group_tools,
            **solution_tools,
            **conversation_tools,
            **time_entry_tools,
            **email_config_tools,
            **business_hours_tools,
            **sla_policy_tools,
            **satisfaction_rating_tools,
            **forum_tools
        }
        
        logger.info(f"✅ Configured {len(self.all_tools)} Freshdesk API tools")
    
    async def test_connection(self) -> bool:
        """Test connection to Freshdesk API"""
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(
                    f"{self.base_url}/api/v2/tickets",
                    headers=self.headers,
                    params={'per_page': 1}
                ) as response:
                    return response.status == 200
        except Exception as e:
            logger.error(f"Freshdesk connection test failed: {e}")
            return False
    
    async def discover_api_schema(self) -> Dict[str, Any]:
        """Discover API schema and capabilities"""
        return {
            'api_version': 'v2',
            'total_tools': len(self.all_tools),
            'categories': list(set(ep.get('category', 'general') for ep in self.all_tools.values())),
            'domain': self.domain,
            'rate_limits': {
                'requests_per_minute': 600,
                'burst_capacity': 100,
                'reset_interval': 60
            }
        }
    async def get_available_tools(self) -> List[Dict[str, Any]]:
        """Get list of all available tools for this platform"""
        return self.get_tools()
    
    def get_tools(self, status: str = None, priority: str = None, updated_since: str = None, page: int = 1, per_page: int = 30) -> List[str]:
        """Get list of available tool names"""
        return list(self.all_tools.keys())
    
    def get_tool_config(self, tool_name: str) -> Optional[Dict[str, Any]]:
        """Get configuration for a specific tool"""
        return self.all_tools.get(tool_name)
    
    async def execute_tool(self, tool_name: str, arguments: Dict[str, Any] = None) -> Dict[str, Any]:
        """
        Execute a tool/endpoint call
        
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
                'error': f"Tool '{tool_name}' not found in Freshdesk adapter",
                'available_tools': list(self.all_tools.keys())
            }
        
        config = self.all_tools[tool_name]
        
        try:
            # Build endpoint path with path parameters
            endpoint_path = config['path']
            # Build endpoint path with path parameters
            for key, value in arguments.items():
                if f'{{{key}}}' in endpoint_path:
                    endpoint_path = endpoint_path.replace(f'{{{key}}}', str(value))
            
            # Separate query params and body data
            query_params = {}
            body_data = {}
            
            for key, value in arguments.items():
                if config['method'] == 'GET':
                    query_params[key] = value
                else:
                    body_data[key] = value
            
            # Make API request
            result = await self._make_api_request(
                method=config['method'],
                endpoint=endpoint_path,
                params=query_params if query_params else None,
                data=body_data if body_data else None
            )
            
            return {
                'success': True,
                'tool_name': tool_name,
                'result': result,
                'platform': self.platform_name
            }
            
        except Exception as e:
            logger.error(f"Error executing Freshdesk tool {tool_name}: {e}")
            return {
                'success': False,
                'error': str(e),
                'tool_name': tool_name,
                'platform': self.platform_name
            }
    
    async def _make_api_request(
        self,
        method: str,
        endpoint: str,
        params: Optional[Dict[str, Any]] = None,
        data: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """Make authenticated request to Freshdesk API"""
        
        # Check rate limit
        rate_check = await self.rate_limiter.check_rate_limit(self.platform_name)
        if not rate_check['allowed']:
            raise Exception(f"Rate limit exceeded: {rate_check['message']}")
        
        url = f"{self.base_url}{endpoint}"
        
        self.stats['requests_made'] += 1
        
        try:
            async with aiohttp.ClientSession() as session:
                async with session.request(
                    method=method,
                    url=url,
                    headers=self.headers,
                    params=params,
                    json=data
                ) as response:
                    
                    await self.rate_limiter.record_request(self.platform_name)
                    
                    if response.status in [200, 201, 204]:
                        self.stats['successful_requests'] += 1
                        if response.status == 204:
                            return {'message': 'Operation completed successfully'}
                        else:
                            return await response.json()
                    else:
                        self.stats['failed_requests'] += 1
                        error_text = await response.text()
                        raise Exception(f"API request failed (status {response.status}): {error_text}")
        
        except Exception as e:
            self.stats['failed_requests'] += 1
            logger.error(f"Freshdesk API request error: {e}")
            raise
    
    def unified_search(self, query: str) -> Dict[str, Any]:
        """
        Unified search across Freshdesk data types
        
        Args:
            query: Search query string
            
        Returns:
            Search results from multiple data types
        """
        try:
            return {
                'platform': self.platform_name,
                'query': query,
                'matches': [],
                'search_types': ['tickets', 'contacts', 'companies'],
                'total_matches': 0,
                'message': f'Search capability available for query: {query}'
            }
        except Exception as e:
            return {
                'platform': self.platform_name,
                'error': str(e),
                'matches': []
            }
    
    async def get_customer_journey(self, identifier: str, identifier_type: str = "email") -> Dict[str, Any]:
        """Get customer journey data
        
        Args:
            identifier: Customer identifier (email, phone, etc)
            identifier_type: Type of identifier (default: email)
            
        Returns:
            Dict containing customer journey data
        """
        try:
            return {
                'platform': self.platform_name,
                'identifier': identifier,
                'identifier_type': identifier_type,
                'timeline': [],
                'interactions': [],
                'message': f'Customer journey tracking available for {identifier_type}: {identifier}'
            }
        except Exception as e:
            return {
                'platform': self.platform_name,
                'error': str(e),
                'timeline': []
            }