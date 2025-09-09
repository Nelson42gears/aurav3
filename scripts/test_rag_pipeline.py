#!/usr/bin/env python3
"""
Test script for 42Gears RAG Pipeline with Gemini integration
"""

import requests
import json
import logging
from pathlib import Path

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(Path('/home/nelson/nebula/Aura/logs/rag_test.log')),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

def test_rag_endpoint(query, n_results=5, temperature=0.2):
    """Test the RAG endpoint with a query"""
    url = "http://localhost:5678/webhook/GaIAqfW9eg1pvYDy"
    
    payload = {
        "query": query,
        "n_results": n_results,
        "temperature": temperature
    }
    
    headers = {
        "Content-Type": "application/json"
    }
    
    logger.info(f"Sending query: {query}")
    
    try:
        response = requests.post(url, json=payload, headers=headers)
        response.raise_for_status()
        
        result = response.json()
        logger.info(f"Response status: {response.status_code}")
        
        if result.get("success"):
            logger.info("Query successful!")
            logger.info(f"Answer: {result.get('answer')[:200]}...")
            logger.info(f"Sources: {len(result.get('sources', []))} documents")
            
            # Print source details
            for i, source in enumerate(result.get('sources', [])[:3]):
                logger.info(f"Source {i+1}: {source.get('title')} (Relevance: {source.get('relevance'):.2f})")
            
            return result
        else:
            logger.error(f"Query failed: {result.get('error')}")
            return None
            
    except requests.exceptions.RequestException as e:
        logger.error(f"Error calling RAG endpoint: {e}")
        return None

def run_test_queries():
    """Run a set of test queries against the RAG endpoint"""
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
        result = test_rag_endpoint(query)
        results[query] = result
    
    return results

if __name__ == "__main__":
    logger.info("Starting RAG pipeline test")
    results = run_test_queries()
    logger.info("RAG pipeline test completed")
