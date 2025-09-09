"""
Rate Limiter for API Adapters
Implements sliding window rate limiting with platform-specific limits
"""

import asyncio
import time
import logging
from collections import defaultdict, deque
from datetime import datetime, timedelta
from typing import Dict, Any, Optional
import json

logger = logging.getLogger(__name__)


class RateLimiter:
    """
    Sliding window rate limiter for API requests
    Supports different limits per platform and provides user-friendly messages
    """
    
    def __init__(self, max_requests: int = 1000, window_minutes: int = 1):
        self.max_requests = max_requests
        self.window_seconds = window_minutes * 60
        
        # Track requests per platform using sliding window
        self._request_history: Dict[str, deque] = defaultdict(deque)
        self._lock = asyncio.Lock()
        
        # Platform-specific rate limits (requests per minute)
        self._platform_limits = {
            'freshdesk': 600,   # Based on Enterprise plan
            'intercom': 9000,   # Based on API documentation
            'jira': 1000,       # Default for Jira Cloud
            'odoo': 1000,       # Default conservative limit
            'default': max_requests
        }
        
        # Track rate limit violations for reporting
        self._violations: Dict[str, int] = defaultdict(int)
        self._last_violation: Dict[str, float] = {}
        
        logger.info(f"⚡ Rate limiter initialized: {max_requests} req/{window_minutes}min")
    
    async def check_rate_limit(self, platform: str) -> Dict[str, Any]:
        """
        Check if a request is allowed under rate limits
        
        Args:
            platform: Platform name (freshdesk, intercom, etc.)
            
        Returns:
            Dict containing:
                - allowed: bool - whether request is allowed
                - current_usage: int - current request count in window
                - limit: int - maximum allowed requests
                - remaining: int - requests remaining in window
                - retry_after: int - seconds to wait if rate limited
                - message: str - user-friendly message
        """
        async with self._lock:
            now = time.time()
            platform_limit = self._platform_limits.get(platform, self._platform_limits['default'])
            
            # Get request history for this platform
            request_times = self._request_history[platform]
            
            # Remove old requests outside the window
            cutoff_time = now - self.window_seconds
            while request_times and request_times[0] <= cutoff_time:
                request_times.popleft()
            
            current_usage = len(request_times)
            remaining = max(0, platform_limit - current_usage)
            
            if current_usage >= platform_limit:
                # Rate limit exceeded
                self._violations[platform] += 1
                self._last_violation[platform] = now
                
                # Calculate retry after time
                if request_times:
                    oldest_request = request_times[0]
                    retry_after = int(oldest_request + self.window_seconds - now + 1)
                else:
                    retry_after = self.window_seconds
                
                message = self._get_rate_limit_message(platform, retry_after, current_usage, platform_limit)
                
                logger.warning(
                    f"🚫 Rate limit exceeded for {platform}: "
                    f"{current_usage}/{platform_limit} requests used. "
                    f"Retry in {retry_after}s"
                )
                
                return {
                    'allowed': False,
                    'current_usage': current_usage,
                    'limit': platform_limit,
                    'remaining': 0,
                    'retry_after': retry_after,
                    'message': message,
                    'platform': platform,
                    'violations_count': self._violations[platform]
                }
            else:
                # Request allowed
                return {
                    'allowed': True,
                    'current_usage': current_usage,
                    'limit': platform_limit,
                    'remaining': remaining,
                    'retry_after': 0,
                    'message': f"✅ Request allowed for {platform} ({remaining} remaining)",
                    'platform': platform
                }
    
    async def record_request(self, platform: str) -> None:
        """
        Record a successful API request
        
        Args:
            platform: Platform name
        """
        async with self._lock:
            now = time.time()
            self._request_history[platform].append(now)
            
            # Log periodic usage stats
            if len(self._request_history[platform]) % 10 == 0:  # Every 10 requests
                current_usage = len(self._request_history[platform])
                limit = self._platform_limits.get(platform, self._platform_limits['default'])
                remaining = max(0, limit - current_usage)
                
                logger.debug(f"📊 {platform} usage: {current_usage}/{limit} ({remaining} remaining)")
    
    def _get_rate_limit_message(self, platform: str, retry_after: int, usage: int, limit: int) -> str:
        """Generate user-friendly rate limit message"""
        
        platform_friendly = platform.title()
        
        if retry_after <= 60:
            time_msg = f"{retry_after} seconds"
        elif retry_after <= 3600:
            time_msg = f"{retry_after // 60} minutes"
        else:
            time_msg = f"{retry_after // 3600} hours"
        
        violations = self._violations.get(platform, 0)
        
        message = (
            f"⚡ {platform_friendly} API rate limit reached!\n"
            f"📈 Current usage: {usage}/{limit} requests per minute\n"
            f"⏳ Please wait {time_msg} before trying again\n"
            f"💡 Tip: Consider spacing out your requests to avoid limits"
        )
        
        if violations > 5:
            message += f"\n⚠️  High rate limit violations ({violations} times) - consider reviewing API usage patterns"
        
        return message
    
    async def get_platform_stats(self, platform: Optional[str] = None) -> Dict[str, Any]:
        """
        Get rate limiting statistics
        
        Args:
            platform: Specific platform, or None for all platforms
            
        Returns:
            Dictionary of rate limiting statistics
        """
        async with self._lock:
            now = time.time()
            stats = {}
            
            platforms = [platform] if platform else self._request_history.keys()
            
            for p in platforms:
                if p not in self._request_history:
                    continue
                
                # Clean old requests
                request_times = self._request_history[p]
                cutoff_time = now - self.window_seconds
                while request_times and request_times[0] <= cutoff_time:
                    request_times.popleft()
                
                current_usage = len(request_times)
                limit = self._platform_limits.get(p, self._platform_limits['default'])
                remaining = max(0, limit - current_usage)
                
                # Calculate requests per second
                if request_times:
                    time_span = now - request_times[0] if len(request_times) > 1 else self.window_seconds
                    rps = len(request_times) / max(time_span, 1)
                else:
                    rps = 0
                
                stats[p] = {
                    'current_usage': current_usage,
                    'limit_per_minute': limit,
                    'remaining': remaining,
                    'usage_percentage': round((current_usage / limit) * 100, 2),
                    'requests_per_second': round(rps, 2),
                    'violations': self._violations.get(p, 0),
                    'last_violation': self._last_violation.get(p),
                    'window_seconds': self.window_seconds
                }
            
            return stats
    
    async def reset_platform_stats(self, platform: str) -> None:
        """Reset statistics for a specific platform"""
        async with self._lock:
            if platform in self._request_history:
                self._request_history[platform].clear()
            self._violations[platform] = 0
            if platform in self._last_violation:
                del self._last_violation[platform]
            
            logger.info(f"🔄 Reset rate limit stats for {platform}")
    
    async def update_platform_limit(self, platform: str, new_limit: int) -> None:
        """
        Update rate limit for a specific platform
        
        Args:
            platform: Platform name
            new_limit: New rate limit (requests per minute)
        """
        async with self._lock:
            old_limit = self._platform_limits.get(platform, self._platform_limits['default'])
            self._platform_limits[platform] = new_limit
            
            logger.info(f"📝 Updated {platform} rate limit: {old_limit} → {new_limit} req/min")
    
    def get_platform_limits(self) -> Dict[str, int]:
        """Get all platform rate limits"""
        return self._platform_limits.copy()
    
    async def is_healthy(self) -> bool:
        """Check if rate limiter is functioning properly"""
        try:
            # Simple health check - ensure data structures are accessible
            stats = await self.get_platform_stats()
            return True
        except Exception as e:
            logger.error(f"💥 Rate limiter health check failed: {e}")
            return False
    
    async def cleanup_old_data(self) -> None:
        """Periodic cleanup of old request data"""
        async with self._lock:
            now = time.time()
            cutoff_time = now - self.window_seconds
            cleaned_platforms = 0
            
            for platform, request_times in self._request_history.items():
                original_size = len(request_times)
                
                # Remove old requests
                while request_times and request_times[0] <= cutoff_time:
                    request_times.popleft()
                
                if len(request_times) < original_size:
                    cleaned_platforms += 1
            
            if cleaned_platforms > 0:
                logger.debug(f"🧹 Cleaned old request data for {cleaned_platforms} platforms")
    
    def __str__(self) -> str:
        return f"RateLimiter(max_requests={self.max_requests}, window={self.window_seconds}s)"
    
    def __repr__(self) -> str:
        return (
            f"RateLimiter(max_requests={self.max_requests}, "
            f"window_seconds={self.window_seconds}, "
            f"platforms={list(self._platform_limits.keys())})"
        )