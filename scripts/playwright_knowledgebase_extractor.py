#!/usr/bin/env python3
"""
Playwright-based Knowledge Base Extractor
Uses browser automation to handle JavaScript content loading and pagination
"""

import sys
import os
import time
import json
import logging
import asyncio
from typing import Dict, List, Set
from playwright.async_api import async_playwright

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('/home/nelson/nebula/Aura/logs/playwright_extraction.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

class PlaywrightKnowledgeBaseExtractor:
    def __init__(self):
        self.articles = []
        self.visited_urls = set()
        
    async def extract_knowledgebase_articles(self) -> Dict:
        """Extract all articles from knowledgebase.42gears.com using browser automation"""
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            page = await browser.new_page()
            
            try:
                logger.info("🚀 Starting JavaScript-enabled extraction of knowledgebase.42gears.com")
                
                # Navigate to main page
                await page.goto("https://knowledgebase.42gears.com/", wait_until='networkidle')
                await page.wait_for_timeout(3000)  # Wait for AJAX content
                
                # Get all category links
                category_links = await page.evaluate("""
                    () => {
                        const links = Array.from(document.querySelectorAll('a[href*="article-categories"]'));
                        return links.map(link => link.href).filter(href => href.includes('/article-categories/'));
                    }
                """)
                
                logger.info(f"Found {len(category_links)} categories")
                
                all_articles = []
                
                # Extract articles from each category
                for category_url in category_links:
                    logger.info(f"Processing category: {category_url}")
                    articles = await self.extract_category_articles(page, category_url)
                    all_articles.extend(articles)
                    await page.wait_for_timeout(2000)  # Be respectful
                
                await browser.close()
                
                return {
                    'source': 'knowledgebase.42gears.com',
                    'extraction_method': 'playwright_browser_automation',
                    'categories_processed': len(category_links),
                    'total_articles': len(all_articles),
                    'articles': all_articles
                }
                
            except Exception as e:
                await browser.close()
                logger.error(f"Error in extraction: {e}")
                return {'error': str(e), 'articles': []}
    
    async def extract_category_articles(self, page, category_url: str) -> List[Dict]:
        """Extract all articles from a category, handling pagination"""
        try:
            await page.goto(category_url, wait_until='networkidle')
            await page.wait_for_timeout(3000)
            
            articles = []
            page_num = 1
            
            while True:
                logger.info(f"  Processing page {page_num}")
                
                # Get article links on current page
                article_links = await page.evaluate("""
                    () => {
                        const links = Array.from(document.querySelectorAll('a[href*="/article/"]'));
                        return links
                            .map(link => ({
                                url: link.href,
                                title: link.textContent.trim(),
                                description: link.getAttribute('title') || ''
                            }))
                            .filter(item => item.url.length > 30 && item.title.length > 0);
                    }
                """)
                
                logger.info(f"    Found {len(article_links)} articles on page {page_num}")
                
                # Extract content from each article
                for article_data in article_links:
                    if article_data['url'] not in self.visited_urls:
                        self.visited_urls.add(article_data['url'])
                        article = await self.extract_article_content(page, article_data)
                        if article:
                            articles.append(article)
                
                # Check for next page
                next_button = await page.query_selector('a[href*="page"]:has-text("Next"), .pagination a:has-text("Next"), [class*="next"]')
                
                if not next_button:
                    # Try to find pagination by looking for page numbers
                    pagination = await page.evaluate("""
                        () => {
                            const pageLinks = Array.from(document.querySelectorAll('a[href*="page="], a[href*="/page/"]'));
                            return pageLinks.length > 0;
                        }
                    """)
                    
                    if not pagination:
                        break
                
                # Try to click next page
                try:
                    if next_button:
                        await next_button.click()
                        await page.wait_for_load_state('networkidle')
                        await page.wait_for_timeout(3000)
                        page_num += 1
                    else:
                        break
                except Exception as e:
                    logger.warning(f"Pagination failed: {e}")
                    break
            
            return articles
            
        except Exception as e:
            logger.error(f"Error extracting category {category_url}: {e}")
            return []
    
    async def extract_article_content(self, page, article_data: Dict) -> Dict:
        """Extract content from individual article"""
        try:
            await page.goto(article_data['url'], wait_until='networkidle')
            await page.wait_for_timeout(2000)
            
            # Extract article content
            content_data = await page.evaluate("""
                () => {
                    // Remove unwanted elements
                    const unwanted = document.querySelectorAll('nav, header, footer, .sidebar, script, style');
                    unwanted.forEach(el => el.remove());
                    
                    // Find main content
                    const contentSelectors = [
                        'article', '.article-content', '.content', '.post-content', 
                        '.kb-article', '.knowledge-article', 'main', '.main-content'
                    ];
                    
                    let mainContent = null;
                    for (const selector of contentSelectors) {
                        mainContent = document.querySelector(selector);
                        if (mainContent) break;
                    }
                    
                    if (!mainContent) {
                        mainContent = document.body;
                    }
                    
                    const fullText = mainContent.innerText || mainContent.textContent || '';
                    const title = document.querySelector('h1, .title, .article-title')?.innerText || 
                                 document.title || '';
                    
                    return {
                        title: title.trim(),
                        full_text: fullText.trim(),
                        word_count: fullText.trim().split(/\s+/).length,
                        char_count: fullText.length
                    };
                }
            """)
            
            # Combine with original data
            article = {
                'id': article_data['url'].split('/')[-2] if '/' in article_data['url'] else str(hash(article_data['url'])),
                'url': article_data['url'],
                'title': content_data['title'] or article_data['title'],
                'description': article_data['description'],
                'full_text': content_data['full_text'],
                'word_count': content_data['word_count'],
                'char_count': content_data['char_count'],
                'source': 'knowledgebase.42gears.com',
                'extraction_method': 'playwright'
            }
            
            return article if article['full_text'] and len(article['full_text']) > 100 else None
            
        except Exception as e:
            logger.error(f"Error extracting article {article_data['url']}: {e}")
            return None

async def main():
    """Run playwright-based extraction"""
    logger.info("🚀 Starting Playwright Knowledge Base Extraction...")
    
    extractor = PlaywrightKnowledgeBaseExtractor()
    results = await extractor.extract_knowledgebase_articles()
    
    # Save results
    output_file = "/home/nelson/nebula/Aura/playwright_knowledgebase_extraction.json"
    with open(output_file, 'w') as f:
        json.dump(results, f, indent=2)
    
    if results.get('articles'):
        total_articles = len(results['articles'])
        total_words = sum(article.get('word_count', 0) for article in results['articles'])
        
        logger.info(f"✅ Playwright extraction complete:")
        logger.info(f"   Articles extracted: {total_articles}")
        logger.info(f"   Total words: {total_words:,}")
        logger.info(f"📄 Results saved to: {output_file}")
    else:
        logger.error("❌ Extraction failed or no articles found")

if __name__ == "__main__":
    asyncio.run(main())
