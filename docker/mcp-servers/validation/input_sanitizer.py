"""
Input Sanitization Layer for MCP Server
Provides comprehensive content/value sanitization beyond parameter names
Prevents injection attacks, XSS, and other security vulnerabilities
"""

import re
import html
import urllib.parse
from typing import Any, Dict, List, Union, Optional
import logging

logger = logging.getLogger(__name__)

class InputSanitizer:
    """
    Comprehensive input sanitization for MCP server tools
    Sanitizes actual parameter VALUES (not just names)
    """
    
    # Dangerous patterns that should be blocked/escaped
    DANGEROUS_PATTERNS = [
        r'<script[^>]*>.*?</script>',  # XSS scripts
        r'javascript:',               # JavaScript URLs
        r'data:text/html',           # Data URLs with HTML
        r'vbscript:',                # VBScript URLs
        r'onload\s*=',               # Event handlers
        r'onerror\s*=',              # Error handlers
        r'onclick\s*=',              # Click handlers
        r'\{\{.*?\}\}',              # Template injection
        r'\$\{.*?\}',                # Variable substitution
        r'<%.*?%>',                  # Server-side includes
        r'<\?.*?\?>',                # PHP/XML processing
        r'<!--.*?-->',               # HTML comments (potential hiding)
        r'union\s+select',           # SQL injection
        r'drop\s+table',             # SQL injection
        r'delete\s+from',            # SQL injection
        r'insert\s+into',            # SQL injection
        r'update\s+.*\s+set',        # SQL injection
        r'\.\./\.\.',                # Path traversal
        r'\.\.\\\.\.\\',             # Windows path traversal
        r'\r\n|\n\r|\r|\n',          # CRLF injection (for headers)
    ]
    
    # Compile patterns for performance
    COMPILED_PATTERNS = [re.compile(pattern, re.IGNORECASE | re.DOTALL) 
                        for pattern in DANGEROUS_PATTERNS]
    
    @classmethod
    def sanitize_value(cls, value: Any, field_name: str = "unknown") -> Any:
        """
        Sanitize a single parameter value
        
        Args:
            value: The value to sanitize
            field_name: Name of the field (for logging)
            
        Returns:
            Sanitized value
        """
        if value is None:
            return None
            
        # Handle different data types
        if isinstance(value, bool):
            return value
        elif isinstance(value, (int, float)):
            return value
        elif isinstance(value, str):
            return cls._sanitize_string(value, field_name)
        elif isinstance(value, list):
            return [cls.sanitize_value(item, f"{field_name}[{i}]") 
                   for i, item in enumerate(value)]
        elif isinstance(value, dict):
            return {k: cls.sanitize_value(v, f"{field_name}.{k}") 
                   for k, v in value.items()}
        else:
            # Convert unknown types to string and sanitize
            return cls._sanitize_string(str(value), field_name)
    
    @classmethod
    def _sanitize_string(cls, text: str, field_name: str) -> str:
        """
        Sanitize a string value for security
        
        Args:
            text: String to sanitize
            field_name: Field name for logging
            
        Returns:
            Sanitized string
        """
        if not isinstance(text, str) or not text.strip():
            return text
            
        original_text = text
        
        # 1. Detect and log dangerous patterns
        for pattern in cls.COMPILED_PATTERNS:
            if pattern.search(text):
                logger.warning(
                    f"🚨 SECURITY: Dangerous pattern detected in field '{field_name}': "
                    f"{pattern.pattern[:50]}..."
                )
        
        # 2. HTML escape to prevent XSS
        text = html.escape(text, quote=True)
        
        # 3. URL encode special characters that could cause injection
        # But preserve normal characters for usability
        text = cls._selective_url_encode(text)
        
        # 4. Remove/escape dangerous patterns
        for pattern in cls.COMPILED_PATTERNS:
            text = pattern.sub('', text)  # Remove dangerous content
        
        # 5. Normalize whitespace and control characters
        text = cls._normalize_whitespace(text)
        
        # 6. Length limiting (prevent DoS)
        text = cls._limit_length(text, field_name)
        
        if text != original_text:
            logger.debug(f"🧹 Sanitized field '{field_name}': {len(original_text)} → {len(text)} chars")
        
        return text
    
    @classmethod
    def _selective_url_encode(cls, text: str) -> str:
        """URL encode only dangerous characters, preserve readability"""
        # Characters that could be used for injection
        dangerous_chars = {
            '\r': '%0D',
            '\n': '%0A', 
            '\t': '%09',
            '<': '%3C',
            '>': '%3E',
            '"': '%22',
            "'": '%27',
            '`': '%60',
            '\\': '%5C',
        }
        
        for char, encoded in dangerous_chars.items():
            text = text.replace(char, encoded)
        
        return text
    
    @classmethod
    def _normalize_whitespace(cls, text: str) -> str:
        """Normalize whitespace and remove control characters"""
        # Remove control characters except normal whitespace
        text = re.sub(r'[\x00-\x08\x0B\x0C\x0E-\x1F\x7F]', '', text)
        
        # Normalize multiple whitespace to single space
        text = re.sub(r'\s+', ' ', text)
        
        return text.strip()
    
    @classmethod
    def _limit_length(cls, text: str, field_name: str, max_length: int = 10000) -> str:
        """Limit string length to prevent DoS attacks"""
        if len(text) > max_length:
            logger.warning(
                f"⚠️  Field '{field_name}' truncated: {len(text)} → {max_length} chars"
            )
            return text[:max_length] + "..."
        return text
    
    @classmethod
    def sanitize_parameters(cls, params: Dict[str, Any]) -> Dict[str, Any]:
        """
        Sanitize all parameters in a dictionary
        
        Args:
            params: Dictionary of parameters to sanitize
            
        Returns:
            Dictionary with sanitized values
        """
        if not isinstance(params, dict):
            return params
            
        sanitized = {}
        
        for key, value in params.items():
            # Sanitize the key name too (basic safety)
            clean_key = re.sub(r'[^\w\-_.]', '_', str(key))
            
            # Sanitize the value
            clean_value = cls.sanitize_value(value, key)
            
            sanitized[clean_key] = clean_value
        
        return sanitized
    
    @classmethod
    def validate_safe_patterns(cls, text: str, field_name: str) -> bool:
        """
        Check if text contains only safe patterns
        
        Returns:
            True if safe, False if dangerous content detected
        """
        if not isinstance(text, str):
            return True
            
        for pattern in cls.COMPILED_PATTERNS:
            if pattern.search(text):
                logger.error(
                    f"🚫 BLOCKED: Dangerous content in field '{field_name}': "
                    f"Pattern '{pattern.pattern[:30]}...' detected"
                )
                return False
        
        return True


# Convenience functions for easy integration
def sanitize_input(value: Any, field_name: str = "input") -> Any:
    """Quick sanitization function"""
    return InputSanitizer.sanitize_value(value, field_name)

def sanitize_params(params: Dict[str, Any]) -> Dict[str, Any]:
    """Quick parameter sanitization function"""
    return InputSanitizer.sanitize_parameters(params)

def is_safe_input(text: str, field_name: str = "input") -> bool:
    """Quick safety validation function"""
    return InputSanitizer.validate_safe_patterns(text, field_name)
