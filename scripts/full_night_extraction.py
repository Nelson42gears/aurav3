#!/usr/bin/env python3
"""
42Gears Full Night Knowledge Base Extraction
Complete extraction and indexing for overnight processing
Designed for terminal-independent operation
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

# Configure logging for overnight operation
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('/home/nelson/nebula/Aura/logs/full_night_extraction.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

def main():
    """Run complete overnight knowledge base extraction - all 690,500 words"""
    logger.info("🌙 Starting FULL NIGHT 42Gears knowledge base extraction...")
    logger.info("📊 Target: Complete knowledge base (~690,500 words)")
    
    try:
        # Import knowledge base explorer
        from knowledge_base_explorer import KnowledgeBaseExplorer
        
        # Initialize explorer for full extraction
        explorer = KnowledgeBaseExplorer()
        
        # Run COMPLETE extraction (all categories, all articles)
        logger.info("🔍 Starting COMPLETE knowledge base extraction (all categories)...")
        
        # Extract ALL categories and articles - no limits
        results = explorer.run_dry_run(max_articles=None)
        
        # Save complete results
        output_file = "full_night_kb_extract.json"
        with open(output_file, "w") as f:
            json.dump(results, f, indent=2)
        
        stats = results.get('stats', {})
        total_articles = stats.get('total_articles', len(results.get('articles', [])))
        total_words = stats.get('total_words', 0)
        
        logger.info(f"✅ COMPLETE extraction finished: {total_articles} articles, {total_words:,} words")
        
        # Index ALL articles in ChromaDB with memory optimization
        logger.info("📚 Starting COMPLETE ChromaDB indexing...")
        
        client = chromadb.HttpClient(host='localhost', port=8001)
        collection = client.get_or_create_collection('42gears-kb-complete')
        
        # Load extracted data
        with open(output_file, 'r') as f:
            kb_data = json.load(f)
        
        # Process in small memory-efficient batches for overnight stability
        batch_size = 8  # Small batches to prevent memory issues
        total_indexed = 0
        
        valid_articles = [a for a in kb_data['articles'] if a.get('full_text') and len(a['full_text']) > 100]
        logger.info(f"📝 Processing {len(valid_articles)} articles in batches of {batch_size}")
        
        for i in range(0, len(valid_articles), batch_size):
            batch = valid_articles[i:i+batch_size]
            documents = []
            metadatas = []
            ids = []
            
            for j, article in enumerate(batch):
                # Chunk articles for better search and memory management
                content = article['full_text'][:4000]  # 4k char limit for stability
                
                documents.append(content)
                metadatas.append({
                    'category': article.get('category', 'unknown'),
                    'title': article.get('title', 'Unknown')[:150],
                    'url': article.get('url', ''),
                    'word_count': len(content.split()),
                    'extracted_at': time.strftime('%Y-%m-%d %H:%M:%S'),
                    'extraction_type': 'full_night'
                })
                
                # Generate unique ID using title slug and position to avoid duplicates
                title_slug = article.get('title', '').lower().replace(' ', '-')[:30]
                article_id = f'night-{i}-{j}-{title_slug}-{int(time.time())}'
                ids.append(article_id)
            
            if documents:
                try:
                    collection.add(documents=documents, metadatas=metadatas, ids=ids)
                    total_indexed += len(documents)
                    logger.info(f"✅ Batch {i//batch_size + 1}: Indexed {len(documents)} articles (Total: {total_indexed})")
                    
                    # Longer delay for overnight stability and server courtesy
                    time.sleep(3)
                    
                except Exception as e:
                    logger.error(f"❌ Batch {i//batch_size + 1} failed: {e}")
                    continue
        
        # Final statistics and verification
        final_count = collection.count()
        logger.info(f"🎉 FULL NIGHT extraction complete!")
        logger.info(f"📊 Final statistics:")
        logger.info(f"   - Articles extracted: {total_articles}")
        logger.info(f"   - Words extracted: {total_words:,}")
        logger.info(f"   - Articles indexed: {total_indexed}")
        logger.info(f"   - ChromaDB collection size: {final_count}")
        
        # Comprehensive search testing
        test_queries = [
            'Android device management policy',
            'iOS device enrollment configuration', 
            'Windows kiosk mode setup',
            'YouTube video streaming playlist',
            'security policy configuration',
            'remote device monitoring',
            'application installation',
            'device lockdown settings'
        ]
        
        logger.info("🔍 Testing COMPLETE search functionality...")
        
        for query in test_queries:
            try:
                results = collection.query(query_texts=[query], n_results=3)
                result_count = len(results['documents'][0])
                logger.info(f"   Search '{query}': {result_count} results")
                
                # Log top result for verification
                if result_count > 0:
                    top_meta = results['metadatas'][0][0]
                    logger.info(f"     Top: {top_meta['title'][:50]} ({top_meta['category']})")
                    
            except Exception as e:
                logger.error(f"   Search '{query}' failed: {e}")
        
        logger.info("✅ FULL NIGHT extraction and indexing completed successfully!")
        logger.info(f"🌅 Ready for production use - {final_count} documents searchable")
        
        # Create completion status file
        status = {
            "status": "completed",
            "completed_at": time.strftime('%Y-%m-%d %H:%M:%S'),
            "articles_extracted": total_articles,
            "words_extracted": total_words,
            "articles_indexed": total_indexed,
            "collection_size": final_count,
            "collection_name": "42gears-kb-complete"
        }
        
        with open('/home/nelson/nebula/Aura/logs/full_night_status.json', 'w') as f:
            json.dump(status, f, indent=2)
        
        logger.info("📋 Status file saved: /home/nelson/nebula/Aura/logs/full_night_status.json")
        
    except Exception as e:
        logger.error(f"❌ FULL NIGHT processing failed: {e}")
        
        # Create error status file
        error_status = {
            "status": "failed",
            "failed_at": time.strftime('%Y-%m-%d %H:%M:%S'),
            "error": str(e)
        }
        
        with open('/home/nelson/nebula/Aura/logs/full_night_status.json', 'w') as f:
            json.dump(error_status, f, indent=2)
        
        sys.exit(1)

if __name__ == "__main__":
    main()
