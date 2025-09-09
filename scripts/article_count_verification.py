#!/usr/bin/env python3
"""
Article Count Verification
Query knowledgebase.42gears.com and docs.42gears.com to count total articles
Compare against extracted and embedded counts
"""

import sys
import os
import time
import json
import logging
import requests
import chromadb
from typing import Dict, List, Set
from bs4 import BeautifulSoup
from urllib.parse import urljoin, urlparse

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('/home/nelson/nebula/Aura/logs/article_count_verification.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

class ArticleCounter:
    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        })
        
    def count_knowledgebase_articles(self) -> Dict:
        """Count total articles available on knowledgebase.42gears.com"""
        logger.info("🔍 Counting articles on knowledgebase.42gears.com...")
        
        base_url = "https://knowledgebase.42gears.com"
        article_urls = set()
        
        try:
            # Get main page to find categories
            response = self.session.get(base_url)
            response.raise_for_status()
            soup = BeautifulSoup(response.content, 'html.parser')
            
            # Find category links
            categories = []
            for link in soup.find_all('a', href=True):
                href = link['href']
                if 'article-categories' in href:
                    full_url = urljoin(base_url, href)
                    categories.append(full_url)
            
            categories = list(set(categories))
            logger.info(f"Found {len(categories)} categories")
            
            # Count articles in each category
            for category_url in categories:
                try:
                    logger.info(f"Checking category: {category_url}")
                    response = self.session.get(category_url)
                    response.raise_for_status()
                    soup = BeautifulSoup(response.content, 'html.parser')
                    
                    # Find article links in category
                    for link in soup.find_all('a', href=True):
                        href = link['href']
                        if '/article/' in href and href != '/article/':
                            full_url = urljoin(base_url, href)
                            article_urls.add(full_url)
                    
                    time.sleep(1)  # Be respectful
                    
                except Exception as e:
                    logger.error(f"Error processing category {category_url}: {e}")
            
            return {
                'source': 'knowledgebase.42gears.com',
                'categories_found': len(categories),
                'total_articles': len(article_urls),
                'article_urls': list(article_urls)
            }
            
        except Exception as e:
            logger.error(f"Error counting knowledgebase articles: {e}")
            return {'source': 'knowledgebase.42gears.com', 'total_articles': 0, 'error': str(e)}
    
    def count_docs_articles(self) -> Dict:
        """Count total articles available on docs.42gears.com"""
        logger.info("🔍 Counting articles on docs.42gears.com...")
        
        base_url = "https://docs.42gears.com"
        article_urls = set()
        visited_urls = set()
        
        def crawl_page(url, depth=0, max_depth=3):
            if depth > max_depth or url in visited_urls:
                return
                
            visited_urls.add(url)
            
            try:
                response = self.session.get(url)
                response.raise_for_status()
                soup = BeautifulSoup(response.content, 'html.parser')
                
                # Find all internal links
                for link in soup.find_all('a', href=True):
                    href = link['href']
                    if href.startswith('/') and not href.startswith('/search'):
                        full_url = urljoin(base_url, href)
                        
                        # Check if this looks like a documentation page
                        parsed = urlparse(full_url)
                        path = parsed.path.strip('/')
                        
                        if path and path != '' and '.' not in path.split('/')[-1]:
                            article_urls.add(full_url)
                            
                            # Recursively crawl if not too deep
                            if depth < max_depth:
                                crawl_page(full_url, depth + 1, max_depth)
                
                time.sleep(1)  # Be respectful
                
            except Exception as e:
                logger.error(f"Error crawling {url}: {e}")
        
        try:
            # Start crawling from main page
            crawl_page(base_url)
            
            return {
                'source': 'docs.42gears.com',
                'total_articles': len(article_urls),
                'article_urls': list(article_urls)
            }
            
        except Exception as e:
            logger.error(f"Error counting docs articles: {e}")
            return {'source': 'docs.42gears.com', 'total_articles': 0, 'error': str(e)}
    
    def check_chromadb_count(self) -> Dict:
        """Check ChromaDB collection count"""
        logger.info("🔍 Checking ChromaDB collection count...")
        
        try:
            client = chromadb.HttpClient(host='localhost', port=8001)
            
            # Check all collections
            collections = client.list_collections()
            collection_stats = {}
            
            for collection in collections:
                try:
                    coll = client.get_collection(collection.name)
                    count = coll.count()
                    collection_stats[collection.name] = count
                    logger.info(f"Collection '{collection.name}': {count} documents")
                except Exception as e:
                    logger.error(f"Error getting count for collection {collection.name}: {e}")
                    collection_stats[collection.name] = f"Error: {e}"
            
            return {
                'chromadb_host': 'localhost:8001',
                'collections': collection_stats,
                'total_collections': len(collections)
            }
            
        except Exception as e:
            logger.error(f"Error checking ChromaDB: {e}")
            return {'error': str(e)}
    
    def check_extraction_files(self) -> Dict:
        """Check our extraction file counts"""
        logger.info("🔍 Checking extraction file counts...")
        
        extraction_files = [
            '/home/nelson/nebula/Aura/full_night_kb_extract.json',
            '/home/nelson/nebula/Aura/kb_extraction.json',
            '/home/nelson/nebula/Aura/docs_extraction.json',
            '/home/nelson/nebula/Aura/complete_extraction.json'
        ]
        
        file_stats = {}
        
        for file_path in extraction_files:
            try:
                if os.path.exists(file_path):
                    with open(file_path, 'r') as f:
                        data = json.load(f)
                    
                    articles = data.get('articles', [])
                    stats = data.get('stats', {})
                    
                    file_stats[os.path.basename(file_path)] = {
                        'exists': True,
                        'article_count': len(articles),
                        'stats': stats
                    }
                else:
                    file_stats[os.path.basename(file_path)] = {'exists': False}
                    
            except Exception as e:
                file_stats[os.path.basename(file_path)] = {'error': str(e)}
        
        return file_stats

def main():
    """Run article count verification"""
    logger.info("🚀 Starting Article Count Verification...")
    
    counter = ArticleCounter()
    
    # Count articles on both sources
    kb_count = counter.count_knowledgebase_articles()
    docs_count = counter.count_docs_articles()
    
    # Check ChromaDB
    chromadb_count = counter.check_chromadb_count()
    
    # Check extraction files
    extraction_stats = counter.check_extraction_files()
    
    # Compile results
    results = {
        'verification_date': time.strftime('%Y-%m-%d %H:%M:%S'),
        'sources': {
            'knowledgebase_42gears': kb_count,
            'docs_42gears': docs_count
        },
        'chromadb': chromadb_count,
        'extraction_files': extraction_stats,
        'summary': {
            'knowledgebase_available': kb_count.get('total_articles', 0),
            'docs_available': docs_count.get('total_articles', 0),
            'total_available': kb_count.get('total_articles', 0) + docs_count.get('total_articles', 0),
            'chromadb_total': sum([v for v in chromadb_count.get('collections', {}).values() if isinstance(v, int)])
        }
    }
    
    # Save results
    output_file = "/home/nelson/nebula/Aura/logs/article_count_verification.json"
    with open(output_file, 'w') as f:
        json.dump(results, f, indent=2)
    
    # Print summary
    logger.info("📊 VERIFICATION RESULTS:")
    logger.info(f"   knowledgebase.42gears.com: {results['summary']['knowledgebase_available']} articles")
    logger.info(f"   docs.42gears.com: {results['summary']['docs_available']} articles")
    logger.info(f"   Total available: {results['summary']['total_available']} articles")
    logger.info(f"   ChromaDB total: {results['summary']['chromadb_total']} documents")
    logger.info(f"📄 Results saved to: {output_file}")

if __name__ == "__main__":
    main()
