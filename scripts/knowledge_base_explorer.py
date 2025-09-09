#!/usr/bin/env python3
"""
42Gears Knowledge Base Explorer - Dry Run Script
Extracts article structure, IDs, and content for RAG system analysis
"""

import requests
from bs4 import BeautifulSoup
import json
import time
import re
from urllib.parse import urljoin, urlparse
from typing import List, Dict, Set

class KnowledgeBaseExplorer:
    def __init__(self):
        self.base_url = "https://knowledgebase.42gears.com"
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        })
        self.articles = []
        self.categories = set()
        
    def get_categories(self) -> List[str]:
        """Extract all knowledge base categories"""
        try:
            response = self.session.get(self.base_url)
            response.raise_for_status()
            
            soup = BeautifulSoup(response.content, 'html.parser')
            
            # Find category links
            category_links = []
            for link in soup.find_all('a', href=True):
                href = link['href']
                if '/article-categories/' in href:
                    category_links.append(urljoin(self.base_url, href))
                    
            return list(set(category_links))
            
        except Exception as e:
            print(f"Error getting categories: {e}")
            return []
    
    def extract_articles_from_category(self, category_url: str) -> List[Dict]:
        """Extract all article URLs from a category page"""
        try:
            response = self.session.get(category_url)
            response.raise_for_status()
            
            soup = BeautifulSoup(response.content, 'html.parser')
            articles = []
            
            # Find article links
            for link in soup.find_all('a', href=True):
                href = link['href']
                if '/article/' in href and href not in [a.get('url') for a in articles]:
                    # Extract article ID from URL
                    article_id = href.split('/article/')[-1].rstrip('/')
                    
                    # Get article title
                    title = link.get_text().strip()
                    if not title:
                        title = f"Article {article_id}"
                    
                    articles.append({
                        'id': article_id,
                        'url': urljoin(self.base_url, href),
                        'title': title,
                        'category': category_url.split('/article-categories/')[-1].rstrip('/')
                    })
                    
            return articles
            
        except Exception as e:
            print(f"Error extracting articles from {category_url}: {e}")
            return []
    
    def extract_article_content(self, article: Dict) -> Dict:
        """Extract full content from an article"""
        try:
            response = self.session.get(article['url'])
            response.raise_for_status()
            
            soup = BeautifulSoup(response.content, 'html.parser')
            
            # Extract main content
            content_sections = []
            
            # Find main content area
            main_content = soup.find('div', class_='single-article-content') or \
                          soup.find('article') or \
                          soup.find('main')
            
            if main_content:
                # Extract text content while preserving structure
                for element in main_content.find_all(['h1', 'h2', 'h3', 'h4', 'p', 'li', 'div']):
                    text = element.get_text().strip()
                    if text and len(text) > 10:  # Filter out very short text
                        content_sections.append({
                            'type': element.name,
                            'text': text
                        })
            
            # Extract metadata
            meta_description = soup.find('meta', {'name': 'description'})
            og_description = soup.find('meta', {'property': 'og:description'})
            
            description = ""
            if meta_description:
                description = meta_description.get('content', '')
            elif og_description:
                description = og_description.get('content', '')
            
            # Combine all text for full content
            full_text = ' '.join([section['text'] for section in content_sections])
            
            # Extract structured data
            structured_content = {
                'purpose': '',
                'prerequisites': '',
                'steps': [],
                'other_content': []
            }
            
            current_section = 'other_content'
            for section in content_sections:
                text = section['text'].lower()
                if 'purpose' in text and len(section['text']) < 200:
                    current_section = 'purpose'
                elif 'prerequisite' in text and len(section['text']) < 200:
                    current_section = 'prerequisites'  
                elif 'step' in text and len(section['text']) < 200:
                    current_section = 'steps'
                elif section['type'] in ['h1', 'h2', 'h3']:
                    if current_section == 'steps':
                        if isinstance(structured_content['steps'], list):
                            structured_content['steps'].append(section['text'])
                    else:
                        structured_content[current_section] = section['text']
                else:
                    if current_section == 'steps':
                        if isinstance(structured_content['steps'], list):
                            structured_content['steps'].append(section['text'])
                    elif current_section in ['purpose', 'prerequisites']:
                        if isinstance(structured_content[current_section], str):
                            structured_content[current_section] += ' ' + section['text']
                    else:
                        if isinstance(structured_content['other_content'], list):
                            structured_content['other_content'].append(section['text'])
            
            article.update({
                'description': description,
                'content_sections': content_sections,
                'full_text': full_text,
                'structured_content': structured_content,
                'word_count': len(full_text.split()),
                'char_count': len(full_text)
            })
            
            return article
            
        except Exception as e:
            print(f"Error extracting content from {article['url']}: {e}")
            return article
    
    def run_dry_run(self, max_articles: int = None) -> Dict:
        """Run dry run to analyze knowledge base structure"""
        print("🔍 Starting 42Gears Knowledge Base Dry Run Analysis...")
        
        # Get categories
        print("\n📂 Discovering categories...")
        categories = self.get_categories()
        print(f"Found {len(categories)} categories:")
        for cat in categories[:10]:  # Show first 10
            print(f"  - {cat}")
        
        # Extract articles from each category (limited for dry run)
        print("\n📄 Extracting articles...")
        all_articles = []
        articles_processed = 0
        
        # Process all categories - no limit
        categories_to_process = categories
        for category_url in categories_to_process:
            print(f"\nProcessing category: {category_url}")
            articles = self.extract_articles_from_category(category_url)
            print(f"  Found {len(articles)} articles")
            
            # Process all articles in the category
            limit = len(articles)
            for article in articles[:limit]:
                print(f"    Processing: {article['title'][:50]}...")
                article_with_content = self.extract_article_content(article)
                all_articles.append(article_with_content)
                articles_processed += 1
                
                if max_articles is not None and articles_processed >= max_articles:
                    break
                    
                time.sleep(1)  # Be respectful to the server
                
            if max_articles is not None and articles_processed >= max_articles:
                break
        
        # Analyze results
        print("\n📊 Analysis Results:")
        print(f"  Total articles processed: {len(all_articles)}")
        
        total_words = sum(article.get('word_count', 0) for article in all_articles)
        total_chars = sum(article.get('char_count', 0) for article in all_articles)
        
        print(f"  Total words: {total_words:,}")
        print(f"  Total characters: {total_chars:,}")
        print(f"  Average words per article: {total_words // len(all_articles) if all_articles else 0}")
        
        # Show sample articles
        print("\n📋 Sample Articles:")
        for i, article in enumerate(all_articles[:3]):
            print(f"\n  Article {i+1}:")
            print(f"    ID: {article['id']}")
            print(f"    Title: {article['title']}")
            print(f"    Category: {article['category']}")
            print(f"    Words: {article.get('word_count', 0)}")
            print(f"    URL: {article['url']}")
            if article.get('description'):
                print(f"    Description: {article['description'][:100]}...")
        
        return {
            'categories': categories,
            'articles': all_articles,
            'stats': {
                'total_categories': len(categories),
                'articles_processed': len(all_articles),
                'total_words': total_words,
                'total_chars': total_chars,
                'avg_words_per_article': total_words // len(all_articles) if all_articles else 0
            }
        }

if __name__ == "__main__":
    explorer = KnowledgeBaseExplorer()
    results = explorer.run_dry_run(max_articles=15)
    
    # Save results
    with open('/home/nelson/nebula/Aura/knowledge_base_dry_run.json', 'w') as f:
        json.dump(results, f, indent=2)
    
    print(f"\n✅ Dry run complete! Results saved to knowledge_base_dry_run.json")
    print(f"   Estimated full knowledge base size: {results['stats']['total_words'] * 50:,} words")
