#!/usr/bin/env python3
"""
Modern Enterprise Content Extraction Approaches (2025)
Evaluate current best practices for large-scale content extraction
"""

import sys
import os
import time
import json
import logging
import requests
from typing import Dict, List, Set
from bs4 import BeautifulSoup
from urllib.parse import urljoin, urlparse, parse_qs
from urllib.robotparser import RobotFileParser

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('/home/nelson/nebula/Aura/logs/modern_extraction_analysis.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

class ModernExtractionAnalyzer:
    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        })
        
    def check_api_endpoints(self, base_url: str) -> Dict:
        """Check for modern API endpoints that might serve content"""
        logger.info(f"🔍 Checking API endpoints for {base_url}")
        
        api_patterns = [
            '/api/v1/', '/api/v2/', '/api/v3/', '/api/',
            '/rest/', '/graphql', '/search/api/',
            '/wp-json/', '/drupal/api/', '/headless/',
            '/_next/static/', '/_nuxt/', '/api/content/',
            '/cms/api/', '/strapi/', '/contentful/',
            '/.netlify/functions/', '/api/search',
            '/elasticsearch/', '/solr/', '/algolia/'
        ]
        
        found_apis = {}
        
        for pattern in api_patterns:
            try:
                test_url = f"{base_url.rstrip('/')}{pattern}"
                response = self.session.head(test_url, timeout=5)
                if response.status_code in [200, 401, 403]:  # API exists but may require auth
                    found_apis[pattern] = {
                        'url': test_url,
                        'status': response.status_code,
                        'content_type': response.headers.get('content-type', ''),
                        'accessible': response.status_code == 200
                    }
            except:
                continue
        
        return found_apis
    
    def check_sitemaps(self, base_url: str) -> Dict:
        """Check for XML sitemaps - modern standard for content discovery"""
        logger.info(f"🗺️ Checking sitemaps for {base_url}")
        
        sitemap_urls = [
            f"{base_url}/sitemap.xml",
            f"{base_url}/sitemap_index.xml",
            f"{base_url}/sitemaps.xml",
            f"{base_url}/sitemap/sitemap.xml",
            f"{base_url}/wp-sitemap.xml"
        ]
        
        found_sitemaps = {}
        
        for sitemap_url in sitemap_urls:
            try:
                response = self.session.get(sitemap_url, timeout=10)
                if response.status_code == 200:
                    # Parse sitemap
                    if 'xml' in response.headers.get('content-type', '').lower():
                        soup = BeautifulSoup(response.content, 'xml')
                        urls = soup.find_all('url')
                        sitemaps = soup.find_all('sitemap')
                        
                        found_sitemaps[sitemap_url] = {
                            'status': 'found',
                            'url_count': len(urls),
                            'nested_sitemaps': len(sitemaps),
                            'content_length': len(response.content)
                        }
            except:
                continue
        
        return found_sitemaps
    
    def check_rss_feeds(self, base_url: str) -> Dict:
        """Check for RSS/Atom feeds for content updates"""
        logger.info(f"📡 Checking RSS feeds for {base_url}")
        
        feed_urls = [
            f"{base_url}/rss.xml", f"{base_url}/feed.xml",
            f"{base_url}/atom.xml", f"{base_url}/feeds/",
            f"{base_url}/rss/", f"{base_url}/feed/",
            f"{base_url}/blog/rss.xml", f"{base_url}/news/rss.xml"
        ]
        
        found_feeds = {}
        
        for feed_url in feed_urls:
            try:
                response = self.session.get(feed_url, timeout=10)
                if response.status_code == 200:
                    soup = BeautifulSoup(response.content, 'xml')
                    items = soup.find_all(['item', 'entry'])
                    
                    found_feeds[feed_url] = {
                        'status': 'found',
                        'item_count': len(items),
                        'feed_type': 'rss' if soup.find('rss') else 'atom'
                    }
            except:
                continue
        
        return found_feeds
    
    def check_search_functionality(self, base_url: str) -> Dict:
        """Check for search functionality that might be exploitable"""
        logger.info(f"🔍 Checking search functionality for {base_url}")
        
        # Get main page to find search forms/endpoints
        try:
            response = self.session.get(base_url)
            soup = BeautifulSoup(response.content, 'html.parser')
            
            # Find search forms
            search_forms = soup.find_all('form', {'action': lambda x: x and 'search' in x.lower()})
            search_inputs = soup.find_all('input', {'type': 'search'})
            search_endpoints = []
            
            for form in search_forms:
                action = form.get('action', '')
                if action:
                    search_endpoints.append(urljoin(base_url, action))
            
            # Look for search in JavaScript
            scripts = soup.find_all('script')
            js_search_patterns = []
            for script in scripts:
                if script.string:
                    content = script.string.lower()
                    if any(term in content for term in ['search', 'query', 'elasticsearch', 'solr']):
                        js_search_patterns.append(True)
            
            return {
                'search_forms': len(search_forms),
                'search_inputs': len(search_inputs),
                'search_endpoints': search_endpoints,
                'js_search_indicators': len(js_search_patterns)
            }
            
        except Exception as e:
            return {'error': str(e)}
    
    def check_robots_txt(self, base_url: str) -> Dict:
        """Check robots.txt for crawling guidelines and sitemap references"""
        logger.info(f"🤖 Checking robots.txt for {base_url}")
        
        try:
            robots_url = f"{base_url}/robots.txt"
            rp = RobotFileParser()
            rp.set_url(robots_url)
            rp.read()
            
            response = self.session.get(robots_url)
            robots_content = response.text if response.status_code == 200 else ""
            
            # Extract sitemap URLs from robots.txt
            sitemap_refs = []
            for line in robots_content.split('\n'):
                if line.lower().startswith('sitemap:'):
                    sitemap_refs.append(line.split(':', 1)[1].strip())
            
            return {
                'exists': response.status_code == 200,
                'sitemap_references': sitemap_refs,
                'crawl_allowed': rp.can_fetch('*', base_url),
                'content_length': len(robots_content)
            }
            
        except Exception as e:
            return {'error': str(e)}
    
    def analyze_modern_approaches(self, base_urls: List[str]) -> Dict:
        """Analyze both URLs using modern extraction approaches"""
        results = {}
        
        for base_url in base_urls:
            logger.info(f"\n🚀 Analyzing {base_url} with modern approaches...")
            
            site_analysis = {
                'url': base_url,
                'api_endpoints': self.check_api_endpoints(base_url),
                'sitemaps': self.check_sitemaps(base_url),
                'rss_feeds': self.check_rss_feeds(base_url),
                'search_functionality': self.check_search_functionality(base_url),
                'robots_txt': self.check_robots_txt(base_url)
            }
            
            # Determine best extraction approach
            recommendations = []
            
            if site_analysis['api_endpoints']:
                recommendations.append({
                    'method': 'API-first extraction',
                    'priority': 'HIGH',
                    'rationale': f"Found {len(site_analysis['api_endpoints'])} API endpoints"
                })
            
            if site_analysis['sitemaps']:
                total_urls = sum(data['url_count'] for data in site_analysis['sitemaps'].values())
                recommendations.append({
                    'method': 'Sitemap-based crawling',
                    'priority': 'HIGH',
                    'rationale': f"Sitemap contains {total_urls} URLs"
                })
            
            if site_analysis['search_functionality']['search_endpoints']:
                recommendations.append({
                    'method': 'Search API exploitation',
                    'priority': 'MEDIUM',
                    'rationale': f"Found {len(site_analysis['search_functionality']['search_endpoints'])} search endpoints"
                })
            
            if site_analysis['rss_feeds']:
                recommendations.append({
                    'method': 'RSS feed parsing',
                    'priority': 'LOW',
                    'rationale': f"Found {len(site_analysis['rss_feeds'])} RSS feeds"
                })
            
            if not recommendations:
                recommendations.append({
                    'method': 'Enhanced crawling with modern tools (Scrapy/Crawlee)',
                    'priority': 'FALLBACK',
                    'rationale': 'No structured data sources found'
                })
            
            site_analysis['recommended_approaches'] = recommendations
            results[base_url] = site_analysis
        
        return results

def main():
    """Run modern extraction analysis"""
    logger.info("🚀 Analyzing Modern Enterprise Content Extraction Approaches...")
    
    analyzer = ModernExtractionAnalyzer()
    
    urls_to_analyze = [
        "https://knowledgebase.42gears.com",
        "https://www.42gears.com/documentation"
    ]
    
    results = analyzer.analyze_modern_approaches(urls_to_analyze)
    
    # Add modern tools comparison
    results['modern_tools_comparison'] = {
        'enterprise_solutions': [
            {'name': 'Apify', 'type': 'cloud', 'use_case': 'large-scale crawling'},
            {'name': 'Scrapy', 'type': 'open_source', 'use_case': 'structured crawling'},
            {'name': 'Crawlee', 'type': 'open_source', 'use_case': 'modern JS handling'},
            {'name': 'Firecrawl', 'type': 'api', 'use_case': 'AI-powered extraction'}
        ],
        'api_first_approaches': [
            'GraphQL introspection',
            'REST API discovery',
            'Headless CMS detection',
            'Search API exploitation'
        ],
        'ai_powered_extraction': [
            'LLM-based content parsing',
            'Computer vision for layout detection',
            'Natural language content extraction'
        ]
    }
    
    # Save results
    output_file = "/home/nelson/nebula/Aura/logs/modern_extraction_analysis.json"
    with open(output_file, 'w') as f:
        json.dump(results, f, indent=2)
    
    # Print summary
    logger.info("📊 MODERN EXTRACTION ANALYSIS RESULTS:")
    for url, analysis in results.items():
        if url.startswith('http'):
            logger.info(f"\n{url}:")
            for rec in analysis.get('recommended_approaches', []):
                logger.info(f"  {rec['priority']}: {rec['method']} - {rec['rationale']}")
    
    logger.info(f"\n📄 Full analysis saved to: {output_file}")

if __name__ == "__main__":
    main()
