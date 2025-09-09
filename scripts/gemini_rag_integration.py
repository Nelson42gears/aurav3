#!/usr/bin/env python3
"""
Gemini API Integration for 42Gears RAG System
Provides a secure interface to the Gemini API for RAG operations
"""

import os
import json
import requests
import logging
from pathlib import Path
from typing import Dict, List, Any, Optional
from urllib.parse import urljoin

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('/home/nelson/nebula/Aura/logs/gemini_rag.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

class GeminiRAGClient:
    """Client for Gemini API with RAG capabilities"""
    
    def __init__(self, api_key: str = None):
        """Initialize the Gemini client with API key"""
        # Use provided API key or get from environment
        self.api_key = api_key or os.environ.get("GEMINI_API_KEY")
        if not self.api_key:
            raise ValueError("Gemini API key is required. Provide as parameter or set GEMINI_API_KEY environment variable.")
        
        # API endpoints
        self.base_url = "https://generativelanguage.googleapis.com/v1beta/models/"
        self.model = "gemini-2.0-flash"  # Default model
        
        logger.info(f"Initialized Gemini RAG client with model: {self.model}")
    
    def generate_content(self, prompt: str, context: Optional[List[str]] = None, 
                         temperature: float = 0.7, max_tokens: int = 1024) -> Dict[str, Any]:
        """Generate content using Gemini API with optional RAG context"""
        endpoint = f"{self.base_url}{self.model}:generateContent"
        
        # Build request payload
        parts = [{"text": prompt}]
        
        # Add context if provided (RAG)
        if context:
            context_text = "\n\nRelevant context:\n" + "\n\n".join(context)
            parts = [{"text": context_text + "\n\nUser query: " + prompt}]
        
        payload = {
            "contents": [{"parts": parts}],
            "generationConfig": {
                "temperature": temperature,
                "maxOutputTokens": max_tokens,
                "topP": 0.95,
                "topK": 40
            }
        }
        
        # Add API key to headers
        headers = {
            "Content-Type": "application/json",
            "X-goog-api-key": self.api_key
        }
        
        try:
            logger.info(f"Sending request to Gemini API: {endpoint}")
            response = requests.post(endpoint, json=payload, headers=headers)
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            logger.error(f"Error calling Gemini API: {e}")
            if hasattr(e, 'response') and e.response:
                logger.error(f"Response: {e.response.text}")
            return {"error": str(e)}
    
    def extract_text_from_response(self, response: Dict[str, Any]) -> str:
        """Extract text content from Gemini API response"""
        try:
            if "error" in response:
                return f"Error: {response['error']}"
            
            if "candidates" in response and response["candidates"]:
                candidate = response["candidates"][0]
                if "content" in candidate and "parts" in candidate["content"]:
                    parts = candidate["content"]["parts"]
                    return "".join(part.get("text", "") for part in parts)
            
            return "No text content found in response"
        except Exception as e:
            logger.error(f"Error extracting text from response: {e}")
            return f"Error processing response: {str(e)}"

    def rag_query(self, query: str, context_docs: List[str], temperature: float = 0.7) -> str:
        """Perform a RAG query with retrieved context documents"""
        logger.info(f"Performing RAG query: {query}")
        logger.info(f"Using {len(context_docs)} context documents")
        
        response = self.generate_content(query, context=context_docs, temperature=temperature)
        return self.extract_text_from_response(response)


def test_gemini_api():
    """Test the Gemini API integration"""
    # Get API key from environment or use default for testing
    api_key = os.environ.get("GEMINI_API_KEY", "AIzaSyD2a5oIjwzfsmNIxN4gUxtuzfWB9L228LE")
    
    try:
        # Initialize client
        client = GeminiRAGClient(api_key=api_key)
        
        # Test simple query
        test_query = "Explain how AI works in a few words"
        logger.info(f"Testing simple query: {test_query}")
        
        response = client.generate_content(test_query)
        result = client.extract_text_from_response(response)
        
        logger.info(f"Response: {result[:100]}...")
        return True
    except Exception as e:
        logger.error(f"Test failed: {e}")
        return False


if __name__ == "__main__":
    # Set API key in environment for testing
    os.environ["GEMINI_API_KEY"] = "AIzaSyD2a5oIjwzfsmNIxN4gUxtuzfWB9L228LE"
    
    if test_gemini_api():
        logger.info("✅ Gemini API test successful!")
    else:
        logger.error("❌ Gemini API test failed!")
