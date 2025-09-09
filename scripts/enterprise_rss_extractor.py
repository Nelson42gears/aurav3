#!/usr/bin/env python3
"""
Enterprise RSS-Based Content Extractor (2025 Standard)
Uses structured feeds and search APIs - no browser automation needed
"""

import sys
import os
import time
import json
import logging
import requests
from typing import Dict, List, Optional
from urllib.parse import urljoin, quote
from bs4 import BeautifulSoup
import xml.etree.ElementTree as ET

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('/home/nelson/nebula/Aura/logs/enterprise_extraction.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

class EnterpriseRSSExtractor:
    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36'
        })
        
    def extract_via_rss(self, base_url: str) -> List[Dict]:
        """Extract articles via RSS feed - enterprise standard approach"""
        logger.info(f"🔍 RSS extraction from {base_url}")
        
        feed_url = f"{base_url}/feed/"
        articles = []
        
        try:
            response = self.session.get(feed_url)
            if response.status_code != 200:
                logger.warning(f"RSS feed returned {response.status_code}")
                return []
                
            # Parse RSS XML
            root = ET.fromstring(response.content)
            
            # Handle different RSS formats
            items = root.findall('.//item') or root.findall('.//{http://www.w3.org/2005/Atom}entry')
            
            logger.info(f"Found {len(items)} articles in RSS feed")
            
            for item in items:
                title = (item.find('title') or item.find('{http://www.w3.org/2005/Atom}title'))
                title = title.text if title is not None else ''
                
                link = (item.find('link') or item.find('{http://www.w3.org/2005/Atom}link'))
                if link is not None:
                    url = link.text if hasattr(link, 'text') and link.text else link.get('href', '')
                else:
                    url = ''
                
                description = (item.find('description') or item.find('{http://www.w3.org/2005/Atom}summary'))
                description = description.text if description is not None else ''
                
                if title and url:
                    article = {
                        'id': str(hash(url)),
                        'title': title.strip(),
                        'url': url.strip(),
                        'description': self.clean_html(description),
                        'source': 'rss_feed',
                        'extraction_method': 'enterprise_rss'
                    }
                    
                    # Get full content
                    content = self.extract_content(url)
                    if content:
                        article.update(content)
                        articles.append(article)
            
        except Exception as e:
            logger.error(f"RSS extraction failed: {e}")
            
        return articles
    
    def extract_via_search(self, base_url: str) -> List[Dict]:
        """Search-based discovery for comprehensive coverage"""
        logger.info(f"🔍 Search-based discovery from {base_url}")
        
        search_terms = [
            'suremdm', 'surelock', 'surefox', 'surevideo', 'astrofarm', 'astrocontacts',
            'android', 'ios', 'windows', 'device', 'installation', 'configuration',
            'troubleshooting', 'management', 'enrollment', 'deployment'
        ]
        
        articles = []
        seen_urls = set()
        
        for term in search_terms:
            try:
                search_url = f"{base_url}/?s={quote(term)}"
                response = self.session.get(search_url)
                
                if response.status_code == 200:
                    soup = BeautifulSoup(response.content, 'html.parser')
                    
                    # Find article links
                    for link in soup.find_all('a', href=True):
                        href = link['href']
                        if '/article/' in href and href not in seen_urls:
                            seen_urls.add(href)
                            
                            title = link.get_text().strip()
                            if title and len(title) > 5:
                                article = {
                                    'id': str(hash(href)),
                                    'title': title,
                                    'url': href,
                                    'search_term': term,
                                    'source': 'search_discovery',
                                    'extraction_method': 'search_api'
                                }
                                
                                content = self.extract_content(href)
                                if content and content.get('word_count', 0) > 100:
                                    article.update(content)
                                    articles.append(article)
                
                time.sleep(1)  # Rate limiting
                
            except Exception as e:
                logger.warning(f"Search failed for {term}: {e}")
        
        return articles
    
    def extract_content(self, url: str) -> Optional[Dict]:
        """Extract full content from article URL"""
        try:
            response = self.session.get(url, timeout=10)
            if response.status_code != 200:
                return None
                
            soup = BeautifulSoup(response.content, 'html.parser')
            
            # Remove unwanted elements
            for element in soup.select('nav, header, footer, .sidebar, script, style'):
                element.decompose()
            
            # Find main content
            content_selectors = [
                'article', '.article-content', '.content', '.post-content',
                '.entry-content', 'main', '.main-content', '.kb-article'
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
            logger.warning(f"Content extraction failed for {url}: {e}")
        
        return None
    
    def clean_html(self, html_content: str) -> str:
        """Clean HTML tags from content"""
        if not html_content:
            return ''
        soup = BeautifulSoup(html_content, 'html.parser')
        return soup.get_text(strip=True)
    
    def deduplicate_articles(self, articles: List[Dict]) -> List[Dict]:
        """Remove duplicates using URL and title"""
        seen_urls = set()
        seen_titles = set()
        unique_articles = []
        
        for article in articles:
            url = article.get('url', '')
            title = article.get('title', '').lower().strip()
            
            if url not in seen_urls and title not in seen_titles:
                seen_urls.add(url)
                seen_titles.add(title)
                unique_articles.append(article)
        
        logger.info(f"Deduplication: {len(articles)} → {len(unique_articles)} articles")
        return unique_articles
    
    def extract_knowledgebase(self) -> Dict:
        """Complete enterprise extraction from knowledgebase"""
        base_url = "https://knowledgebase.42gears.com"
        logger.info(f"🚀 Enterprise extraction from {base_url}")
        
        # Method 1: RSS feed (structured data)
        rss_articles = self.extract_via_rss(base_url)
        
        # Method 2: Search discovery (comprehensive coverage)
        search_articles = self.extract_via_search(base_url)
        
        # Combine and deduplicate
        all_articles = rss_articles + search_articles
        unique_articles = self.deduplicate_articles(all_articles)
        
        # Calculate stats
        total_words = sum(article.get('word_count', 0) for article in unique_articles)
        total_chars = sum(article.get('char_count', 0) for article in unique_articles)
        
        return {
            'source': base_url,
            'extraction_method': 'enterprise_api_first',
            'total_articles': len(unique_articles),
            'total_words': total_words,
            'total_chars': total_chars,
            'rss_articles': len(rss_articles),
            'search_articles': len(search_articles),
            'duplicates_removed': len(all_articles) - len(unique_articles),
            'articles': unique_articles
        }

def main():
    """Run enterprise extraction"""
    logger.info("🚀 Enterprise Content Extraction (2025 Standard)")
    
    extractor = EnterpriseRSSExtractor()
    results = extractor.extract_knowledgebase()
    
    # Save results
    output_file = "/home/nelson/nebula/Aura/enterprise_extraction.json"
    with open(output_file, 'w') as f:
        json.dump(results, f, indent=2)
    
    logger.info("📊 ENTERPRISE EXTRACTION RESULTS:")
    logger.info(f"   Total articles: {results['total_articles']}")
    logger.info(f"   Total words: {results['total_words']:,}")
    logger.info(f"   RSS articles: {results['rss_articles']}")
    logger.info(f"   Search articles: {results['search_articles']}")
    logger.info(f"   Duplicates removed: {results['duplicates_removed']}")
    logger.info(f"📄 Results saved to: {output_file}")

if __name__ == "__main__":
    main()
