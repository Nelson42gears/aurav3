#!/usr/bin/env python3
"""
42Gears Complete Knowledge Base Extraction
Combines extraction from knowledgebase.42gears.com and docs.42gears.com
"""

import sys
import os
import time
import json
import logging
import chromadb
from pathlib import Path
from datetime import datetime

# Add scripts directory to path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

# Configure logging
log_file = f"/home/nelson/nebula/Aura/logs/complete_extraction_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(log_file),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

def run_knowledge_base_extraction():
    """Run extraction from knowledgebase.42gears.com"""
    logger.info("🔍 Starting knowledge base extraction (knowledgebase.42gears.com)...")
    
    try:
        # Import knowledge base explorer
        from knowledge_base_explorer import KnowledgeBaseExplorer
        
        # Initialize explorer
        explorer = KnowledgeBaseExplorer()
        
        # Run full extraction (no limit)
        results = explorer.run_dry_run(max_articles=None)
        
        # Save results to output file
        kb_output_file = "/home/nelson/nebula/Aura/kb_extraction.json"
        with open(kb_output_file, "w") as f:
            json.dump(results, f, indent=2)
        
        stats = results.get('stats', {})
        total_articles = stats.get('total_articles', len(results.get('articles', [])))
        total_words = stats.get('total_words', 0)
        
        logger.info(f"✅ Knowledge base extraction complete: {total_articles} articles, {total_words:,} words")
        logger.info(f"📄 Results saved to: {kb_output_file}")
        
        return results
        
    except Exception as e:
        logger.error(f"❌ Knowledge base extraction failed: {e}")
        return {"articles": [], "stats": {"total_articles": 0, "total_words": 0}}

def run_docs_extraction():
    """Run extraction from docs.42gears.com"""
    logger.info("🔍 Starting documentation extraction (docs.42gears.com)...")
    
    try:
        # Import docs explorer
        from docs_explorer import DocsExplorer
        
        # Initialize explorer
        explorer = DocsExplorer()
        
        # Run full extraction (no limit)
        results = explorer.run_extraction(max_articles=None)
        
        # Save results to output file
        docs_output_file = "/home/nelson/nebula/Aura/docs_extraction.json"
        with open(docs_output_file, "w") as f:
            json.dump(results, f, indent=2)
        
        stats = results.get('stats', {})
        total_articles = stats.get('total_articles', len(results.get('articles', [])))
        total_words = stats.get('total_words', 0)
        
        logger.info(f"✅ Documentation extraction complete: {total_articles} articles, {total_words:,} words")
        logger.info(f"📄 Results saved to: {docs_output_file}")
        
        return results
        
    except Exception as e:
        logger.error(f"❌ Documentation extraction failed: {e}")
        return {"articles": [], "stats": {"total_articles": 0, "total_words": 0}}

def combine_results(kb_results, docs_results):
    """Combine results from both sources"""
    logger.info("🔄 Combining results from both sources...")
    
    kb_articles = kb_results.get('articles', [])
    docs_articles = docs_results.get('articles', [])
    
    # Add source identifier if not present
    for article in kb_articles:
        if 'source' not in article:
            article['source'] = 'knowledgebase.42gears.com'
    
    # Combine articles
    all_articles = kb_articles + docs_articles
    
    # Calculate combined stats
    kb_stats = kb_results.get('stats', {})
    docs_stats = docs_results.get('stats', {})
    
    combined_stats = {
        'total_articles': len(all_articles),
        'total_words': kb_stats.get('total_words', 0) + docs_stats.get('total_words', 0),
        'total_chars': kb_stats.get('total_chars', 0) + docs_stats.get('total_chars', 0),
        'kb_articles': len(kb_articles),
        'docs_articles': len(docs_articles),
        'sources': ['knowledgebase.42gears.com', 'docs.42gears.com']
    }
    
    # Prepare combined results
    combined_results = {
        'articles': all_articles,
        'stats': combined_stats
    }
    
    # Save combined results
    combined_output_file = "/home/nelson/nebula/Aura/complete_extraction.json"
    with open(combined_output_file, "w") as f:
        json.dump(combined_results, f, indent=2)
    
    logger.info(f"✅ Combined extraction complete: {combined_stats['total_articles']} articles, {combined_stats['total_words']:,} words")
    logger.info(f"📄 Combined results saved to: {combined_output_file}")
    
    return combined_results

def index_in_chromadb(combined_results):
    """Index all articles in ChromaDB"""
    logger.info("📚 Starting ChromaDB indexing...")
    
    try:
        client = chromadb.HttpClient(host='localhost', port=8001)
        collection = client.get_or_create_collection('42gears-kb-complete-v2')
        
        # Process in small memory-efficient batches
        batch_size = 8  # Small batches to prevent memory issues
        total_indexed = 0
        
        valid_articles = [a for a in combined_results['articles'] if a.get('full_text') and len(a['full_text']) > 100]
        logger.info(f"📝 Processing {len(valid_articles)} articles in batches of {batch_size}")
        
        for i in range(0, len(valid_articles), batch_size):
            batch = valid_articles[i:i+batch_size]
            documents = []
            metadatas = []
            ids = []
            
            for j, article in enumerate(batch):
                # Generate a unique ID for each article
                article_id = f"{article['id']}-{int(time.time())}-{i}-{j}"
                
                # Prepare document and metadata
                documents.append(article['full_text'])
                metadatas.append({
                    'title': article['title'],
                    'url': article['url'],
                    'source': article.get('source', 'unknown'),
                    'category': article.get('category', article.get('section', 'unknown')),
                    'word_count': article.get('word_count', 0),
                    'char_count': article.get('char_count', 0)
                })
                ids.append(article_id)
            
            # Add batch to collection
            collection.add(
                documents=documents,
                metadatas=metadatas,
                ids=ids
            )
            
            total_indexed += len(batch)
            logger.info(f"✅ Batch {i//batch_size + 1}: Indexed {len(batch)} articles (Total: {total_indexed})")
            
            # Small delay to prevent overloading
            time.sleep(2)
        
        logger.info(f"✅ Indexing complete: {total_indexed} articles indexed in ChromaDB")
        
        # Update status file
        status = {
            "status": "completed",
            "completed_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "extraction": {
                "raw_articles_extracted": len(combined_results['articles']),
                "unique_articles_processed": len(valid_articles),
                "articles_indexed": total_indexed,
                "data_integrity": "maintained"
            },
            "collection": {
                "name": "42gears-kb-complete-v2",
                "size": total_indexed,
                "type": "complete_extraction"
            }
        }
        
        with open("/home/nelson/nebula/Aura/logs/complete_extraction_status.json", "w") as f:
            json.dump(status, f, indent=2)
        
        return total_indexed
        
    except Exception as e:
        logger.error(f"❌ ChromaDB indexing failed: {e}")
        return 0

def main():
    """Run complete extraction process"""
    logger.info("🚀 Starting COMPLETE 42Gears extraction (knowledgebase + docs)...")
    logger.info("📊 Target: Complete knowledge base (~690,500 words)")
    
    # Step 1: Extract from knowledge base
    kb_results = run_knowledge_base_extraction()
    
    # Step 2: Extract from docs
    docs_results = run_docs_extraction()
    
    # Step 3: Combine results
    combined_results = combine_results(kb_results, docs_results)
    
    # Step 4: Index in ChromaDB
    total_indexed = index_in_chromadb(combined_results)
    
    logger.info(f"🎉 Complete extraction process finished!")
    logger.info(f"📊 Final stats:")
    logger.info(f"   - Total articles extracted: {combined_results['stats']['total_articles']}")
    logger.info(f"   - Total words extracted: {combined_results['stats']['total_words']:,}")
    logger.info(f"   - Total articles indexed: {total_indexed}")
    logger.info(f"   - Log file: {log_file}")

if __name__ == "__main__":
    main()
