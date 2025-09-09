#!/usr/bin/env python3
"""
42Gears Documentation Explorer
Extracts content from docs.42gears.com to complement knowledge base extraction
"""

import sys
import os
import time
import json
import logging
import hashlib
import requests
from typing import Dict, List, Optional, Any
from bs4 import BeautifulSoup
from urllib.parse import urljoin, urlparse

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('/home/nelson/nebula/Aura/logs/docs_extraction.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

class DocsExplorer:
    def __init__(self):
        self.base_url = "https://docs.42gears.com"
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        })
        self.articles = []
        self.sections = set()
        self.visited_urls = set()
        
    def get_sections(self) -> List[str]:
        """Extract all documentation sections"""
        try:
            response = self.session.get(self.base_url)
            response.raise_for_status()
            
            soup = BeautifulSoup(response.content, 'html.parser')
            
            # Find section links (main documentation categories)
            section_links = []
            for link in soup.find_all('a', href=True):
                href = link['href']
                # Filter for main documentation sections
                if href.startswith('/') and not href.startswith('/search') and not href == '/':
                    full_url = urljoin(self.base_url, href)
                    section_links.append(full_url)
                    
            return list(set(section_links))
            
        except Exception as e:
            logger.error(f"Error getting documentation sections: {e}")
            return []
    
    def extract_articles_from_section(self, section_url: str) -> List[Dict]:
        """Extract all article URLs from a documentation section"""
        try:
            if section_url in self.visited_urls:
                return []
                
            self.visited_urls.add(section_url)
            response = self.session.get(section_url)
            response.raise_for_status()
            
            soup = BeautifulSoup(response.content, 'html.parser')
            articles = []
            
            # Find article links
            for link in soup.find_all('a', href=True):
                href = link['href']
                if href.startswith('/') and not href.startswith('/search') and not href == '/':
                    full_url = urljoin(self.base_url, href)
                    
                    # Skip already visited URLs
                    if full_url in self.visited_urls:
                        continue
                    
                    # Extract article ID from URL
                    article_id = hashlib.md5(full_url.encode()).hexdigest()
                    
                    # Get article title
                    title = link.get_text().strip()
                    if not title:
                        title = f"Doc {article_id[:8]}"
                    
                    section_name = section_url.replace(self.base_url, '').strip('/')
                    if not section_name:
                        section_name = "main"
                    
                    articles.append({
                        'id': article_id,
                        'url': full_url,
                        'title': title,
                        'section': section_name
                    })
                    
                    # Also add this URL to be explored for nested content
                    if full_url != section_url and full_url not in self.visited_urls:
                        nested_articles = self.extract_articles_from_section(full_url)
                        articles.extend(nested_articles)
                    
            return articles
            
        except Exception as e:
            logger.error(f"Error extracting articles from section {section_url}: {e}")
            return []
    
    def extract_article_content(self, article: Dict) -> Dict:
        """Extract content from a documentation article"""
        try:
            url = article['url']
            response = self.session.get(url)
            response.raise_for_status()
            
            soup = BeautifulSoup(response.content, 'html.parser')
            
            # Remove navigation, headers, footers, etc.
            for element in soup.select('nav, header, footer, script, style'):
                element.decompose()
            
            # Find the main content area - adjust selectors based on the actual site structure
            main_content = soup.select_one('main, article, .content, .documentation, .doc-content')
            
            if not main_content:
                main_content = soup.body
            
            # Extract text content
            if main_content:
                full_text = main_content.get_text(separator='\n', strip=True)
            else:
                full_text = soup.get_text(separator='\n', strip=True)
            
            # Clean up the text
            lines = [line.strip() for line in full_text.split('\n') if line.strip()]
            clean_text = '\n'.join(lines)
            
            # Update article with content
            article['full_text'] = clean_text
            article['word_count'] = len(clean_text.split())
            article['char_count'] = len(clean_text)
            article['source'] = 'docs.42gears.com'
            
            return article
            
        except Exception as e:
            logger.error(f"Error extracting content from {article['url']}: {e}")
            article['full_text'] = ''
            article['word_count'] = 0
            article['char_count'] = 0
            article['source'] = 'docs.42gears.com'
            return article
    
    def run_extraction(self, max_articles: Optional[int] = None) -> Dict:
        """Run full extraction of 42Gears documentation"""
        logger.info("🔍 Starting 42Gears Documentation Extraction...")
        
        # Get sections
        logger.info("\n📂 Discovering documentation sections...")
        sections = self.get_sections()
        logger.info(f"Found {len(sections)} sections:")
        for section in sections[:10]:  # Show first 10
            logger.info(f"  - {section}")
        
        # Extract articles from each section
        logger.info("\n📄 Extracting articles...")
        all_articles = []
        articles_processed = 0
        
        # Process all sections
        for section_url in sections:
            logger.info(f"\nProcessing section: {section_url}")
            articles = self.extract_articles_from_section(section_url)
            logger.info(f"  Found {len(articles)} articles")
            
            # Process all articles in the section
            for article in articles:
                logger.info(f"    Processing: {article['title'][:50]}...")
                article_with_content = self.extract_article_content(article)
                all_articles.append(article_with_content)
                articles_processed += 1
                
                if max_articles is not None and articles_processed >= max_articles:
                    break
                    
                time.sleep(1)  # Be respectful to the server
                
            if max_articles is not None and articles_processed >= max_articles:
                break
        
        # Analyze results
        logger.info("\n📊 Analysis Results:")
        logger.info(f"  Total articles processed: {len(all_articles)}")
        
        total_words = sum(article.get('word_count', 0) for article in all_articles)
        total_chars = sum(article.get('char_count', 0) for article in all_articles)
        
        logger.info(f"  Total words: {total_words:,}")
        logger.info(f"  Total characters: {total_chars:,}")
        logger.info(f"  Average words per article: {total_words // len(all_articles) if all_articles else 0}")
        
        # Prepare results
        results = {
            'articles': all_articles,
            'stats': {
                'total_articles': len(all_articles),
                'total_words': total_words,
                'total_chars': total_chars,
                'sections_found': len(sections),
                'source': 'docs.42gears.com'
            }
        }
        
        return results

def main():
    """Run documentation extraction"""
    explorer = DocsExplorer()
    results = explorer.run_extraction(max_articles=None)  # No limit - extract everything
    
    # Save results to output file
    output_file = "/home/nelson/nebula/Aura/docs_extraction.json"
    with open(output_file, "w") as f:
        json.dump(results, f, indent=2)
    
    logger.info(f"✅ Documentation extraction complete: {results['stats']['total_articles']} articles, {results['stats']['total_words']:,} words")
    logger.info(f"📄 Results saved to: {output_file}")

if __name__ == "__main__":
    main()
