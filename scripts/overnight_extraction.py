#!/usr/bin/env python3
"""
42Gears Knowledge Base Overnight Extraction
Runs full knowledge base extraction and indexing in background
"""

import sys
import os
import time
import json
import logging
import chromadb
from pathlib import Path

# Add scripts directory to path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('/home/nelson/nebula/Aura/logs/overnight_extraction.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

def main():
    """Run overnight knowledge base extraction and indexing"""
    logger.info("🌙 Starting overnight 42Gears knowledge base extraction...")
    
    try:
        # Import knowledge base explorer
        from knowledge_base_explorer import KnowledgeBaseExplorer
        
        # Initialize explorer with memory-optimized settings
        explorer = KnowledgeBaseExplorer()
        
        # Run full extraction (no limit for overnight run)
        logger.info("🔍 Starting full knowledge base extraction...")
        
        # Extract all categories and articles using the correct method
        results = explorer.run_dry_run(max_articles=None)  # No limit - extract everything
        
        # Save results to output file
        with open("overnight_kb_extract.json", "w") as f:
            json.dump(results, f, indent=2)
        
        stats = results.get('stats', {})
        total_articles = stats.get('total_articles', len(results.get('articles', [])))
        total_words = stats.get('total_words', 0)
        logger.info(f"✅ Extraction complete: {total_articles} articles, {total_words} words")
        
        # Index articles in ChromaDB
        logger.info("📚 Starting ChromaDB indexing...")
        
        client = chromadb.HttpClient(host='localhost', port=8001)
        collection = client.get_or_create_collection('42gears-kb-full')
        
        # Load extracted data
        with open('overnight_kb_extract.json', 'r') as f:
            kb_data = json.load(f)
        
        # Process in memory-efficient batches
        batch_size = 10  # Small batches for memory efficiency
        total_indexed = 0
        
        valid_articles = [a for a in kb_data['articles'] if a.get('full_text') and len(a['full_text']) > 100]
        logger.info(f"📝 Processing {len(valid_articles)} valid articles in batches of {batch_size}")
        
        for i in range(0, len(valid_articles), batch_size):
            batch = valid_articles[i:i+batch_size]
            documents = []
            metadatas = []
            ids = []
            
            for j, article in enumerate(batch):
                # Chunk long articles for better search
                content = article['full_text'][:3000]  # 3k char limit
                
                documents.append(content)
                metadatas.append({
                    'category': article.get('category', 'unknown'),
                    'title': article.get('title', 'Unknown')[:150],
                    'url': article.get('url', ''),
                    'word_count': len(content.split()),
                    'extracted_at': time.strftime('%Y-%m-%d %H:%M:%S')
                })
                
                article_id = article.get('id') or f'overnight-{i}-{j}'
                ids.append(article_id)
            
            if documents:
                collection.add(documents=documents, metadatas=metadatas, ids=ids)
                total_indexed += len(documents)
                logger.info(f"✅ Batch {i//batch_size + 1}: Indexed {len(documents)} articles (Total: {total_indexed})")
                
                # Small delay to prevent overwhelming the system
                time.sleep(2)
        
        logger.info(f"🎉 Overnight processing complete!")
        logger.info(f"📊 Final stats:")
        logger.info(f"   - Articles extracted: {len(valid_articles)}")
        logger.info(f"   - Articles indexed: {total_indexed}")
        logger.info(f"   - ChromaDB collection size: {collection.count()}")
        
        # Test search functionality
        test_queries = ['device management', 'kiosk mode', 'YouTube streaming', 'security policy']
        logger.info("🔍 Testing search functionality...")
        
        for query in test_queries:
            results = collection.query(query_texts=[query], n_results=3)
            logger.info(f"   Search '{query}': {len(results['documents'][0])} results")
        
        logger.info("✅ Overnight extraction and indexing completed successfully!")
        
    except Exception as e:
        logger.error(f"❌ Overnight processing failed: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
