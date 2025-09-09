"""
Aura MCP Unified Server - API Adapters Package
Contains adapters for Freshdesk, Intercom, Jira, and Odoo integrations
"""

from .base_adapter import BaseAdapter
from .rate_limiter import RateLimiter
from .freshdesk_adapter import FreshdeskAdapter
from .intercom_adapter import IntercomAdapter

__all__ = [
    'BaseAdapter',
    'RateLimiter', 
    'FreshdeskAdapter',
    'IntercomAdapter'
]

__version__ = '1.0.0'