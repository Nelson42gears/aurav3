#!/usr/bin/env python3
"""
Direct test script for 42Gears RAG Pipeline with Gemini integration
This script bypasses n8n and tests the components directly
"""

import sys
import os
import json
import logging
import requests
import chromadb
from pathlib import Path

# Add the project root to the path so we can import our modules
sys.path.append(str(Path(__file__).parent.parent))
from scripts.gemini_rag_integration import GeminiRAGClient

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(Path('/home/nelson/nebula/Aura/logs/rag_direct_test.log')),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# ChromaDB configuration
CHROMA_HOST = "localhost"
CHROMA_PORT = 8001
COLLECTION_NAME = "42gears-kb-complete-v2"  # From enhanced_extraction_status.json

def query_chromadb(query_text, n_results=5):
    """Query ChromaDB for relevant documents using the ChromaDB client"""
    try:
        # Initialize ChromaDB client
        client = chromadb.HttpClient(host=CHROMA_HOST, port=CHROMA_PORT)
        
        # Get the collection
        collection = client.get_collection(name=COLLECTION_NAME)
        
        # Query the collection
        results = collection.query(
            query_texts=[query_text],
            n_results=n_results
        )
        
        return results
    except Exception as e:
        logger.error(f"Error querying ChromaDB: {e}")
        return None

def process_chromadb_results(results, query):
    """Process ChromaDB results into a format suitable for RAG"""
    if not results or not results.get("ids") or len(results["ids"]) == 0:
        logger.warning("No relevant documents found")
        return None
    
    documents = results["documents"][0]
    metadatas = results["metadatas"][0]
    distances = results["distances"][0]
    
    context_docs = []
    for i in range(len(documents)):
        context_docs.append({
            "content": documents[i],
            "metadata": metadatas[i],
            "relevance": 1 - distances[i],  # Convert distance to relevance score
            "id": results["ids"][0][i]
        })
    
    # Format context for RAG
    formatted_context = []
    for i, doc in enumerate(context_docs):
        formatted_context.append(
            f"[Document {i+1}] {doc['content']}\n\n"
            f"Source: {doc['metadata'].get('source', 'Unknown')}\n"
            f"Category: {doc['metadata'].get('category', 'General')}"
        )
    
    return {
        "query": query,
        "context_documents": formatted_context,
        "raw_results": context_docs
    }

def test_rag_query(query_text):
    """Test the full RAG pipeline with a query"""
    logger.info(f"Testing query: {query_text}")
    
    # Step 1: Query ChromaDB
    logger.info("Querying ChromaDB for relevant documents...")
    chroma_results = query_chromadb(query_text)
    
    if not chroma_results:
        logger.error("Failed to retrieve documents from ChromaDB")
        return None
    
    # Step 2: Process results
    logger.info("Processing ChromaDB results...")
    context_docs = process_chromadb_results(chroma_results, query_text)
    
    if not context_docs:
        logger.error("No relevant documents found or failed to process results")
        return None
    
    # Step 3: Generate response with Gemini
    logger.info("Generating response with Gemini API...")
    client = GeminiRAGClient()
    
    # Extract just the formatted context documents for the RAG query
    formatted_context = context_docs.get("context_documents", [])
    response = client.rag_query(query_text, formatted_context)
    
    if response:
        logger.info(f"Answer: {response[:200]}...")
        
        # Format final result
        result = {
            "success": True,
            "query": query_text,
            "answer": response,
            "sources": [
                {
                    "title": doc["metadata"].get("title", "Untitled"),
                    "url": doc["metadata"].get("url", ""),
                    "category": doc["metadata"].get("category", "General"),
                    "relevance": doc["relevance"]
                }
                for doc in context_docs["raw_results"]
            ],
            "metadata": {
                "model": "gemini-2.0-flash",
                "timestamp": None  # Will be filled by the client
            }
        }
        
        # Log source details
        logger.info(f"Sources: {len(result['sources'])} documents")
        for i, source in enumerate(result["sources"][:3]):
            logger.info(f"Source {i+1}: {source['title']} (Relevance: {source['relevance']:.2f})")
            
        return result
    else:
        logger.error("Failed to generate response with Gemini API")
        return None

def run_test_queries():
    """Run a set of test queries against the RAG pipeline"""
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
        result = test_rag_query(query)
        results[query] = result
    
    return results

if __name__ == "__main__":
    logger.info("Starting direct RAG pipeline test")
    
    # Check if GEMINI_API_KEY is set
    if not os.environ.get("GEMINI_API_KEY"):
        logger.error("GEMINI_API_KEY environment variable not set")
        logger.info("Setting from docker-compose.yml value...")
        os.environ["GEMINI_API_KEY"] = "AIzaSyD2a5oIjwzfsmNIxN4gUxtuzfWB9L228LE"
    
    results = run_test_queries()
    logger.info("RAG pipeline test completed")
