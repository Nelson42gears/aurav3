#!/usr/bin/env python3
"""
Modern API-First Content Extractor (2025)
Uses WordPress REST API, RSS feeds, and search APIs instead of browser automation
"""

import sys
import os
import time
import json
import logging
import requests
import feedparser
from typing import Dict, List, Optional
from urllib.parse import urljoin, quote

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('/home/nelson/nebula/Aura/logs/modern_api_extraction.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

class ModernAPIExtractor:
    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36',
            'Accept': 'application/json, text/html, */*'
        })
        self.articles = []
        
    def extract_via_rss(self, base_url: str) -> List[Dict]:
        """Extract articles via RSS feed - modern, efficient approach"""
        logger.info(f"🔍 Extracting via RSS feed from {base_url}")
        
        rss_urls = [
            f"{base_url}/feed/",
            f"{base_url}/rss.xml",
            f"{base_url}/atom.xml"
        ]
        
        articles = []
        
        for rss_url in rss_urls:
            try:
                logger.info(f"  Trying RSS: {rss_url}")
                feed = feedparser.parse(rss_url)
                
                if feed.entries:
                    logger.info(f"  ✅ Found {len(feed.entries)} articles in RSS feed")
                    
                    for entry in feed.entries:
                        article = {
                            'id': entry.get('id', entry.get('link', '')),
                            'title': entry.get('title', ''),
                            'url': entry.get('link', ''),
                            'description': entry.get('summary', ''),
                            'published': entry.get('published', ''),
                            'categories': [tag.term for tag in entry.get('tags', [])],
                            'source': 'rss_feed',
                            'extraction_method': 'rss_api'
                        }
                        
                        # Get full content
                        full_content = self.get_article_content(article['url'])
                        if full_content:
                            article.update(full_content)
                        
                        articles.append(article)
                    
                    break  # Use first working RSS feed
                    
            except Exception as e:
                logger.warning(f"  RSS failed for {rss_url}: {e}")
                continue
        
        return articles
    
    def extract_via_wordpress_api(self, base_url: str) -> List[Dict]:
        """Extract via WordPress REST API"""
        logger.info(f"🔍 Extracting via WordPress REST API from {base_url}")
        
        wp_api_base = f"{base_url}/wp-json/wp/v2"
        articles = []
        
        try:
            # Try to get posts
            posts_url = f"{wp_api_base}/posts?per_page=100"
            response = self.session.get(posts_url)
            
            if response.status_code == 200:
                posts = response.json()
                logger.info(f"  ✅ Found {len(posts)} posts via WordPress API")
                
                for post in posts:
                    article = {
                        'id': str(post.get('id')),
                        'title': post.get('title', {}).get('rendered', ''),
                        'url': post.get('link', ''),
                        'description': post.get('excerpt', {}).get('rendered', ''),
                        'full_text': post.get('content', {}).get('rendered', ''),
                        'published': post.get('date', ''),
                        'categories': post.get('categories', []),
                        'source': 'wordpress_api',
                        'extraction_method': 'rest_api'
                    }
                    
                    # Clean HTML from content
                    if article['full_text']:
                        from bs4 import BeautifulSoup
                        soup = BeautifulSoup(article['full_text'], 'html.parser')
                        article['full_text'] = soup.get_text(separator='\n', strip=True)
                        article['word_count'] = len(article['full_text'].split())
                        article['char_count'] = len(article['full_text'])
                    
                    articles.append(article)
            else:
                logger.warning(f"  WordPress API returned status {response.status_code}")
                
        except Exception as e:
            logger.warning(f"  WordPress API failed: {e}")
        
        return articles
    
    def extract_via_search_api(self, base_url: str) -> List[Dict]:
        """Extract articles via search functionality"""
        logger.info(f"🔍 Extracting via search API from {base_url}")
        
        # Common search terms to discover articles
        search_terms = [
            'suremdm', 'surelock', 'surefox', 'surevideo', 'astrofarm',
            'android', 'ios', 'windows', 'device', 'management', 
            'configuration', 'installation', 'troubleshooting'
        ]
        
        articles = []
        seen_urls = set()
        
        for term in search_terms:
            try:
                search_url = f"{base_url}/?s={quote(term)}"
                logger.info(f"  Searching for: {term}")
                
                response = self.session.get(search_url)
                if response.status_code == 200:
                    from bs4 import BeautifulSoup
                    soup = BeautifulSoup(response.content, 'html.parser')
                    
                    # Find article links in search results
                    for link in soup.find_all('a', href=True):
                        href = link['href']
                        if '/article/' in href and href not in seen_urls:
                            seen_urls.add(href)
                            
                            article = {
                                'id': href.split('/')[-2] if '/' in href else str(hash(href)),
                                'title': link.get_text().strip(),
                                'url': href,
                                'source': 'search_discovery',
                                'search_term': term,
                                'extraction_method': 'search_api'
                            }
                            
                            # Get full content
                            full_content = self.get_article_content(href)
                            if full_content:
                                article.update(full_content)
                                articles.append(article)
                
                time.sleep(1)  # Rate limiting
                
            except Exception as e:
                logger.warning(f"  Search failed for {term}: {e}")
        
        return articles
    
    def get_article_content(self, url: str) -> Optional[Dict]:
        """Extract full content from article URL"""
        try:
            response = self.session.get(url)
            if response.status_code == 200:
                from bs4 import BeautifulSoup
                soup = BeautifulSoup(response.content, 'html.parser')
                
                # Remove unwanted elements
                for element in soup.select('nav, header, footer, .sidebar, script, style'):
                    element.decompose()
                
                # Find main content
                content_selectors = [
                    'article', '.article-content', '.content', '.post-content',
                    '.kb-article', '.entry-content', 'main', '.main-content'
                ]
                
                main_content = None
                for selector in content_selectors:
                    main_content = soup.select_one(selector)
                    if main_content:
                        break
                
                if not main_content:
                    main_content = soup.find('body')
                
                if main_content:
                    full_text = main_content.get_text(separator='\n', strip=True)
                    
                    return {
                        'full_text': full_text,
                        'word_count': len(full_text.split()),
                        'char_count': len(full_text)
                    }
                    
        except Exception as e:
            logger.warning(f"Failed to extract content from {url}: {e}")
        
        return None
    
    def extract_knowledgebase(self) -> Dict:
        """Extract from knowledgebase using modern API-first approaches"""
        base_url = "https://knowledgebase.42gears.com"
        logger.info(f"🚀 Starting modern API-first extraction from {base_url}")
        
        all_articles = []
        
        # Method 1: RSS Feed (fastest, most reliable)
        rss_articles = self.extract_via_rss(base_url)
        all_articles.extend(rss_articles)
        
        # Method 2: WordPress REST API (structured data)
        if not rss_articles:  # Only if RSS failed
            wp_articles = self.extract_via_wordpress_api(base_url)
            all_articles.extend(wp_articles)
        
        # Method 3: Search API (comprehensive discovery)
        search_articles = self.extract_via_search_api(base_url)
        
        # Deduplicate by URL
        seen_urls = {article['url'] for article in all_articles}
        for article in search_articles:
            if article['url'] not in seen_urls:
                all_articles.append(article)
                seen_urls.add(article['url'])
        
        # Calculate stats
        total_words = sum(article.get('word_count', 0) for article in all_articles)
        total_chars = sum(article.get('char_count', 0) for article in all_articles)
        
        return {
            'source': base_url,
            'extraction_method': 'modern_api_first',
            'total_articles': len(all_articles),
            'total_words': total_words,
            'total_chars': total_chars,
            'extraction_methods_used': ['rss_feed', 'search_api'],
            'articles': all_articles
        }

def main():
    """Run modern API-first extraction"""
    logger.info("🚀 Starting Modern API-First Content Extraction (2025)...")
    
    extractor = ModernAPIExtractor()
    results = extractor.extract_knowledgebase()
    
    # Save results
    output_file = "/home/nelson/nebula/Aura/modern_api_extraction.json"
    with open(output_file, 'w') as f:
        json.dump(results, f, indent=2)
    
    logger.info("📊 MODERN EXTRACTION RESULTS:")
    logger.info(f"   Articles extracted: {results['total_articles']}")
    logger.info(f"   Total words: {results['total_words']:,}")
    logger.info(f"   Total characters: {results['total_chars']:,}")
    logger.info(f"   Methods used: {', '.join(results['extraction_methods_used'])}")
    logger.info(f"📄 Results saved to: {output_file}")

if __name__ == "__main__":
    main()
