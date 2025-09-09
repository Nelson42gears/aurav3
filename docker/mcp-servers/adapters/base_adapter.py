"""
Base API Adapter - Common functionality for all platform integrations
Provides rate limiting, error handling, and HTTP client management
"""

import asyncio
import logging
from abc import ABC, abstractmethod
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Tuple, Union
import json
import base64
from urllib.parse import urljoin, urlparse

import httpx
from pydantic import BaseModel

from .rate_limiter import RateLimiter

logger = logging.getLogger(__name__)


class APIResponse(BaseModel):
    """Standardized API response model"""
    success: bool
    data: Optional[Dict[str, Any]] = None
    error: Optional[str] = None
    status_code: Optional[int] = None
    headers: Optional[Dict[str, str]] = None
    rate_limit_info: Optional[Dict[str, Any]] = None


class BaseAdapter(ABC):
    """
    Abstract base class for all API adapters
    Provides common functionality for HTTP operations, rate limiting, and error handling
    """
    
    def __init__(
        self,
        base_url: str,
        api_key: Optional[str] = None,
        access_token: Optional[str] = None,
        rate_limit_per_minute: int = 1000,
        timeout: int = 30
    ):
        self.base_url = base_url.rstrip('/')
        self.api_key = api_key
        self.access_token = access_token
        self.timeout = timeout
        
        # Rate limiting
        self.rate_limiter = RateLimiter(
            max_requests=rate_limit_per_minute,
            window_minutes=1
        )
        
        # HTTP client configuration
        self._setup_http_client()
        
        # Platform-specific configuration
        self.platform_name = self.__class__.__name__.replace('Adapter', '').lower()
        
        logger.info(f"🔌 Initialized {self.platform_name} adapter: {self.base_url}")
    
    def _setup_http_client(self):
        """Setup HTTP client with proper authentication and headers"""
        headers = {
            "Content-Type": "application/json",
            "User-Agent": "Aura-MCP-Unified-Server/1.0.0"
        }
        
        # Authentication setup (platform-specific)
        if self.api_key:
            if self.platform_name == 'freshdesk':
                # Freshdesk uses Basic Auth with API key
                auth_string = f"{self.api_key}:X"
                encoded_auth = base64.b64encode(auth_string.encode()).decode()
                headers["Authorization"] = f"Basic {encoded_auth}"
            else:
                headers["Authorization"] = f"Bearer {self.api_key}"
        
        if self.access_token:
            headers["Authorization"] = f"Bearer {self.access_token}"
        
        self.client = httpx.AsyncClient(
            base_url=self.base_url,
            headers=headers,
            timeout=httpx.Timeout(self.timeout),
            follow_redirects=True
        )
    
    async def __aenter__(self):
        """Async context manager entry"""
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit"""
        await self.close()
    
    async def close(self):
        """Close HTTP client"""
        if hasattr(self, 'client'):
            await self.client.aclose()
    
    async def _make_request(
        self,
        method: str,
        endpoint: str,
        params: Optional[Dict[str, Any]] = None,
        data: Optional[Dict[str, Any]] = None,
        headers: Optional[Dict[str, str]] = None
    ) -> APIResponse:
        """
        Make HTTP request with rate limiting and error handling
        
        Args:
            method: HTTP method (GET, POST, PUT, DELETE)
            endpoint: API endpoint path
            params: Query parameters
            data: Request body data
            headers: Additional headers
            
        Returns:
            APIResponse: Standardized response object
        """
        
        # Check rate limits
        rate_limit_status = await self.rate_limiter.check_rate_limit(self.platform_name)
        if not rate_limit_status["allowed"]:
            return APIResponse(
                success=False,
                error=f"⚡ Rate limit exceeded for {self.platform_name}. Try again in {rate_limit_status['retry_after']} seconds.",
                rate_limit_info=rate_limit_status
            )
        
        # Construct full URL
        url = endpoint if endpoint.startswith('http') else f"/api/v2/{endpoint.lstrip('/')}"
        
        try:
            # Add platform-specific headers
            request_headers = {}
            if headers:
                request_headers.update(headers)
            
            # Add platform-specific parameters
            if self.platform_name == 'intercom':
                if not request_headers.get('Intercom-Version'):
                    request_headers['Intercom-Version'] = '2.11'
            
            logger.debug(f"🌐 {method} {url} - {self.platform_name}")
            
            # Make the request
            response = await self.client.request(
                method=method.upper(),
                url=url,
                params=params,
                json=data if method.upper() in ['POST', 'PUT', 'PATCH'] else None,
                headers=request_headers
            )
            
            # Update rate limit tracking
            await self.rate_limiter.record_request(self.platform_name)
            
            # Extract rate limit info from response headers
            rate_limit_info = self._extract_rate_limit_info(response.headers)
            
            # Parse response
            try:
                response_data = response.json() if response.text else {}
            except json.JSONDecodeError:
                response_data = {"raw_response": response.text}
            
            if response.is_success:
                return APIResponse(
                    success=True,
                    data=response_data,
                    status_code=response.status_code,
                    headers=dict(response.headers),
                    rate_limit_info=rate_limit_info
                )
            else:
                error_message = self._extract_error_message(response, response_data)
                logger.warning(f"❌ API Error [{response.status_code}]: {error_message}")
                
                return APIResponse(
                    success=False,
                    error=error_message,
                    status_code=response.status_code,
                    headers=dict(response.headers),
                    rate_limit_info=rate_limit_info
                )
                
        except httpx.TimeoutException:
            error_msg = f"⏰ Request timeout after {self.timeout}s for {self.platform_name}"
            logger.error(error_msg)
            return APIResponse(success=False, error=error_msg)
            
        except httpx.RequestError as e:
            error_msg = f"🔌 Network error for {self.platform_name}: {str(e)}"
            logger.error(error_msg)
            return APIResponse(success=False, error=error_msg)
            
        except Exception as e:
            error_msg = f"💥 Unexpected error for {self.platform_name}: {str(e)}"
            logger.error(error_msg, exc_info=True)
            return APIResponse(success=False, error=error_msg)
    
    def _extract_rate_limit_info(self, headers: httpx.Headers) -> Dict[str, Any]:
        """Extract rate limit information from response headers"""
        rate_info = {}
        
        # Platform-specific rate limit headers
        if self.platform_name == 'freshdesk':
            rate_info.update({
                'total': headers.get('X-Ratelimit-Total'),
                'remaining': headers.get('X-Ratelimit-Remaining'),
                'used_current': headers.get('X-Ratelimit-Used-CurrentRequest'),
                'retry_after': headers.get('Retry-After')
            })
        elif self.platform_name == 'intercom':
            rate_info.update({
                'limit': headers.get('X-RateLimit-Limit'),
                'remaining': headers.get('X-RateLimit-Remaining'),
                'reset': headers.get('X-RateLimit-Reset')
            })
        
        return {k: v for k, v in rate_info.items() if v is not None}
    
    def _extract_error_message(self, response: httpx.Response, data: Dict[str, Any]) -> str:
        """Extract meaningful error message from API response"""
        
        # Try to get platform-specific error format
        if isinstance(data, dict):
            # Freshdesk error format
            if 'errors' in data and isinstance(data['errors'], list):
                errors = []
                for error in data['errors']:
                    if isinstance(error, dict):
                        msg = error.get('message', error.get('code', str(error)))
                        field = error.get('field', '')
                        errors.append(f"{field}: {msg}" if field else msg)
                return "; ".join(errors)
            
            # Intercom error format  
            if 'errors' in data and isinstance(data['errors'], list):
                return "; ".join([err.get('message', str(err)) for err in data['errors']])
            
            # Generic error formats
            if 'error' in data:
                error = data['error']
                if isinstance(error, dict):
                    return error.get('message', str(error))
                return str(error)
            
            if 'message' in data:
                return data['message']
            
            if 'description' in data:
                return data['description']
        
        # Fallback to HTTP status
        return f"HTTP {response.status_code}: {response.reason_phrase}"
    
    # Abstract methods that subclasses must implement
    @abstractmethod
    async def test_connection(self) -> APIResponse:
        """Test API connection and authentication"""
        pass
    
    @abstractmethod
    async def get_available_tools(self) -> List[Dict[str, Any]]:
        """Get list of all available tools for this platform"""
        pass
    
    @abstractmethod
    async def discover_api_schema(self) -> Dict[str, Any]:
        """Discover API schema and capabilities"""
        pass
    
    # Common utility methods
    async def get(self, endpoint: str, params: Optional[Dict[str, Any]] = None) -> APIResponse:
        """GET request wrapper"""
        return await self._make_request('GET', endpoint, params=params)
    
    async def post(self, endpoint: str, data: Optional[Dict[str, Any]] = None, 
                  params: Optional[Dict[str, Any]] = None) -> APIResponse:
        """POST request wrapper"""
        return await self._make_request('POST', endpoint, params=params, data=data)
    
    async def put(self, endpoint: str, data: Optional[Dict[str, Any]] = None,
                 params: Optional[Dict[str, Any]] = None) -> APIResponse:
        """PUT request wrapper"""
        return await self._make_request('PUT', endpoint, params=params, data=data)
    
    async def patch(self, endpoint: str, data: Optional[Dict[str, Any]] = None,
                   params: Optional[Dict[str, Any]] = None) -> APIResponse:
        """PATCH request wrapper"""
        return await self._make_request('PATCH', endpoint, params=params, data=data)
    
    async def delete(self, endpoint: str, params: Optional[Dict[str, Any]] = None) -> APIResponse:
        """DELETE request wrapper"""
        return await self._make_request('DELETE', endpoint, params=params)
    
    def get_platform_info(self) -> Dict[str, Any]:
        """Get adapter platform information"""
        return {
            'platform': self.platform_name,
            'base_url': self.base_url,
            'authenticated': bool(self.api_key or self.access_token),
            'rate_limit_per_minute': self.rate_limiter.max_requests
        }