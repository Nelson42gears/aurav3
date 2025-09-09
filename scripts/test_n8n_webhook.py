#!/usr/bin/env python3
"""
Test script for 42Gears RAG Pipeline with n8n webhook
This script tests the n8n webhook endpoint for the RAG workflow
"""

import sys
import os
import json
import logging
import requests
from pathlib import Path

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(Path('/home/nelson/nebula/Aura/logs/n8n_webhook_test.log')),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# n8n webhook configuration
N8N_HOST = "localhost"
N8N_PORT = 5678
# Standard n8n webhook URL format
WEBHOOK_PATH = "rag-gemini"
WEBHOOK_URL = f"http://{N8N_HOST}:{N8N_PORT}/webhook/{WEBHOOK_PATH}"

def test_webhook_query(query_text, n_results=5, temperature=0.2, max_tokens=1024):
    """Test the n8n webhook endpoint with a query"""
    logger.info(f"Testing webhook query: {query_text}")
    
    # Prepare payload
    payload = {
        "query": query_text,
        "n_results": n_results,
        "temperature": temperature,
        "max_tokens": max_tokens
    }
    
    headers = {
        "Content-Type": "application/json"
    }
    
    try:
        # Send request to webhook
        logger.info(f"Sending request to webhook: {WEBHOOK_URL}")
        response = requests.post(WEBHOOK_URL, json=payload, headers=headers, timeout=30)
        response.raise_for_status()
        
        # Process response
        result = response.json()
        
        # Log results
        if result.get("success"):
            answer = result.get("answer", "")
            logger.info(f"Answer: {answer[:200]}...")
            
            sources = result.get("sources", [])
            logger.info(f"Sources: {len(sources)} documents")
            
            # Print source details
            for i, source in enumerate(sources[:3]):
                logger.info(f"Source {i+1}: {source.get('title', 'Untitled')} (Relevance: {source.get('relevance', 0):.2f})")
        else:
            logger.error(f"Error: {result.get('error', 'Unknown error')}")
        
        return result
    except Exception as e:
        logger.error(f"Error testing webhook: {e}")
        return None

def run_test_queries():
    """Run a set of test queries against the n8n webhook"""
    test_queries = [
        "How do I configure SureMDM for Android devices?",
        "What is AstroContacts and how does it work?",
        "How to set up kiosk mode in SureLock?",
        "What are the system requirements for 42Gears products?",
        "How to troubleshoot device connectivity issues?"
    ]
    
    results = {}
    
    for query in test_queries:
        logger.info(f"\n{'='*50}\nTesting query: {query}\n{'='*50}")
        result = test_webhook_query(query)
        results[query] = result
    
    return results

if __name__ == "__main__":
    logger.info("Starting n8n webhook test")
    
    # Check if workflow is active
    logger.info("Note: Make sure the n8n workflow '42Gears-RAG-Gemini-API' is active before running this test")
    logger.info("You can activate it with: n8n workflow:activate --id GaIAqfW9eg1pvYDy")
    
    # Run tests
    results = run_test_queries()
    logger.info("n8n webhook test completed")
