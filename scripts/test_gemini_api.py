#!/usr/bin/env python3
"""
Test script for Gemini API integration
"""

import os
import sys
from pathlib import Path
import logging

# Add the project root to the path so we can import our modules
sys.path.append(str(Path(__file__).parent.parent))
from scripts.gemini_rag_integration import GeminiRAGClient

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(Path('/home/nelson/nebula/Aura/logs/gemini_test.log')),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

def test_gemini_api():
    """Test the Gemini API integration with sample queries"""
    # Set API key from environment or use default for testing
    api_key = os.environ.get("GEMINI_API_KEY", "AIzaSyD2a5oIjwzfsmNIxN4gUxtuzfWB9L228LE")
    
    # Initialize client
    client = GeminiRAGClient(api_key=api_key)
    
    # Test queries
    test_queries = [
        "Explain how SureMDM helps with device management",
        "What are the key features of 42Gears products?",
        "How does kiosk mode work in SureLock?",
        "What is the difference between SureMDM and SureLock?"
    ]
    
    # Sample context for RAG simulation
    sample_context = [
        "SureMDM is 42Gears' flagship product for unified endpoint management. It allows IT administrators to manage, monitor, and secure company-owned devices across multiple platforms including Android, iOS, Windows, and macOS.",
        "SureLock is a kiosk lockdown solution that restricts device usage to authorized applications only, preventing users from accessing system settings or installing unauthorized apps.",
        "42Gears offers a comprehensive suite of enterprise mobility management solutions including SureMDM, SureLock, SureFox, and SureVideo for device management, kiosk mode, secure browsing, and digital signage respectively.",
        "The 42Gears UEM solution supports remote troubleshooting, software distribution, location tracking, and security policy enforcement across diverse device types and operating systems."
    ]
    
    results = {}
    
    # Test simple generation
    logger.info("Testing simple content generation...")
    for query in test_queries:
        logger.info(f"\n{'='*50}\nTesting query: {query}\n{'='*50}")
        
        # Generate content without context
        response = client.generate_content(query)
        result = client.extract_text_from_response(response)
        
        logger.info(f"Response without context: {result[:200]}...")
        results[query] = {"simple": result}
        
        # Generate content with RAG context
        rag_result = client.rag_query(query, sample_context)
        
        logger.info(f"Response with RAG context: {rag_result[:200]}...")
        results[query]["rag"] = rag_result
    
    return results

if __name__ == "__main__":
    logger.info("Starting Gemini API test")
    
    # Ensure API key is set
    if not os.environ.get("GEMINI_API_KEY"):
        logger.info("Setting API key from docker-compose.yml value...")
        os.environ["GEMINI_API_KEY"] = "AIzaSyD2a5oIjwzfsmNIxN4gUxtuzfWB9L228LE"
    
    results = test_gemini_api()
    logger.info("Gemini API test completed")
