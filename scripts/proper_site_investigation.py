#!/usr/bin/env python3
"""
Proper Site Investigation
Check the actual structure of knowledgebase.42gears.com and www.42gears.com/documentation/
to understand why extraction is incomplete
"""

import sys
import os
import time
import json
import logging
import requests
from typing import Dict, List, Set
from bs4 import BeautifulSoup
from urllib.parse import urljoin, urlparse

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('/home/nelson/nebula/Aura/logs/site_investigation.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

class SiteInvestigator:
    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        })
        
    def investigate_knowledgebase(self) -> Dict:
        """Deep investigation of knowledgebase.42gears.com structure"""
        logger.info("🔍 Deep investigation of https://knowledgebase.42gears.com/")
        
        base_url = "https://knowledgebase.42gears.com"
        
        try:
            # Get main page
            response = self.session.get(base_url)
            response.raise_for_status()
            
            with open('/tmp/knowledgebase_main.html', 'w') as f:
                f.write(response.text)
            
            soup = BeautifulSoup(response.content, 'html.parser')
            
            logger.info("🔍 Analyzing page structure...")
            
            # Find all unique link patterns
            all_links = set()
            article_links = set()
            category_links = set()
            
            for link in soup.find_all('a', href=True):
                href = link['href']
                full_url = urljoin(base_url, href)
                all_links.add(full_url)
                
                if '/article/' in href and len(href) > 10:
                    article_links.add(full_url)
                elif '/article-categories/' in href:
                    category_links.add(full_url)
            
            logger.info(f"Found {len(all_links)} total links")
            logger.info(f"Found {len(article_links)} article links")
            logger.info(f"Found {len(category_links)} category links")
            
            # Check for pagination or AJAX loading
            pagination_elements = soup.find_all(['div', 'span', 'a'], class_=lambda x: x and any(term in str(x).lower() for term in ['page', 'next', 'more', 'load', 'ajax']))
            logger.info(f"Found {len(pagination_elements)} potential pagination elements")
            
            # Look for JavaScript that might load content
            scripts = soup.find_all('script')
            ajax_indicators = []
            for script in scripts:
                if script.string:
                    script_content = script.string.lower()
                    if any(term in script_content for term in ['ajax', 'fetch', 'xmlhttprequest', 'api', 'json']):
                        ajax_indicators.append(script_content[:200])
            
            logger.info(f"Found {len(ajax_indicators)} scripts with AJAX indicators")
            
            # Check specific selectors that might contain articles
            potential_article_containers = []
            for selector in ['.article', '.content', '.post', '.item', '[data-article]', '.knowledge-item']:
                elements = soup.select(selector)
                if elements:
                    potential_article_containers.append({'selector': selector, 'count': len(elements)})
            
            return {
                'url': base_url,
                'total_links': len(all_links),
                'article_links': len(article_links),
                'category_links': len(category_links),
                'article_urls': list(article_links),
                'category_urls': list(category_links),
                'pagination_elements': len(pagination_elements),
                'ajax_scripts': len(ajax_indicators),
                'potential_containers': potential_article_containers,
                'page_saved': '/tmp/knowledgebase_main.html'
            }
            
        except Exception as e:
            logger.error(f"Error investigating knowledgebase: {e}")
            return {'error': str(e)}
    
    def investigate_documentation(self) -> Dict:
        """Deep investigation of www.42gears.com/documentation/ structure"""
        logger.info("🔍 Deep investigation of https://www.42gears.com/documentation/")
        
        base_url = "https://www.42gears.com/documentation/"
        
        try:
            # Get main page
            response = self.session.get(base_url)
            response.raise_for_status()
            
            with open('/tmp/documentation_main.html', 'w') as f:
                f.write(response.text)
            
            soup = BeautifulSoup(response.content, 'html.parser')
            
            logger.info("🔍 Analyzing documentation structure...")
            
            # Find all unique link patterns
            all_links = set()
            doc_links = set()
            section_links = set()
            
            for link in soup.find_all('a', href=True):
                href = link['href']
                full_url = urljoin(base_url, href)
                all_links.add(full_url)
                
                # Documentation specific patterns
                if '/documentation/' in href or 'docs' in href:
                    doc_links.add(full_url)
                    
                # Look for section patterns
                if any(term in href.lower() for term in ['suremdm', 'surelock', 'surefox', 'surevideo', 'api']):
                    section_links.add(full_url)
            
            logger.info(f"Found {len(all_links)} total links")
            logger.info(f"Found {len(doc_links)} documentation links")
            logger.info(f"Found {len(section_links)} section links")
            
            # Look for specific documentation patterns
            nav_elements = soup.find_all(['nav', 'ul', 'ol'], class_=lambda x: x and any(term in str(x).lower() for term in ['nav', 'menu', 'toc', 'sidebar']))
            logger.info(f"Found {len(nav_elements)} navigation elements")
            
            # Check for documentation sections
            section_containers = []
            for selector in ['.doc-section', '.docs-section', '.documentation-item', '[data-section]', '.guide']:
                elements = soup.select(selector)
                if elements:
                    section_containers.append({'selector': selector, 'count': len(elements)})
            
            # Look for iframe or embedded content
            iframes = soup.find_all('iframe')
            embeds = soup.find_all(['embed', 'object'])
            
            return {
                'url': base_url,
                'total_links': len(all_links),
                'doc_links': len(doc_links),
                'section_links': len(section_links),
                'doc_urls': list(doc_links)[:50],  # Limit for readability
                'section_urls': list(section_links),
                'nav_elements': len(nav_elements),
                'section_containers': section_containers,
                'iframes': len(iframes),
                'embeds': len(embeds),
                'page_saved': '/tmp/documentation_main.html'
            }
            
        except Exception as e:
            logger.error(f"Error investigating documentation: {e}")
            return {'error': str(e)}
    
    def check_search_apis(self) -> Dict:
        """Check if sites have search APIs that might reveal more content"""
        logger.info("🔍 Checking for search APIs...")
        
        search_endpoints = [
            "https://knowledgebase.42gears.com/search",
            "https://knowledgebase.42gears.com/api/search",
            "https://www.42gears.com/documentation/search",
            "https://www.42gears.com/api/documentation",
        ]
        
        results = {}
        
        for endpoint in search_endpoints:
            try:
                response = self.session.get(endpoint, timeout=10)
                results[endpoint] = {
                    'status_code': response.status_code,
                    'content_type': response.headers.get('content-type', ''),
                    'accessible': response.status_code == 200
                }
            except Exception as e:
                results[endpoint] = {'error': str(e)}
        
        return results

def main():
    """Run site investigation"""
    logger.info("🚀 Starting Proper Site Investigation...")
    
    investigator = SiteInvestigator()
    
    # Investigate knowledgebase
    kb_results = investigator.investigate_knowledgebase()
    
    # Investigate documentation
    doc_results = investigator.investigate_documentation()
    
    # Check search APIs
    search_results = investigator.check_search_apis()
    
    # Compile results
    results = {
        'investigation_date': time.strftime('%Y-%m-%d %H:%M:%S'),
        'knowledgebase_investigation': kb_results,
        'documentation_investigation': doc_results,
        'search_api_check': search_results,
        'analysis': {
            'knowledgebase_issues': [],
            'documentation_issues': [],
            'extraction_challenges': []
        }
    }
    
    # Analysis
    if kb_results.get('article_links', 0) < 100:
        results['analysis']['knowledgebase_issues'].append("Low article count suggests missing content detection")
    
    if kb_results.get('ajax_scripts', 0) > 0:
        results['analysis']['knowledgebase_issues'].append("AJAX content loading detected - may need JavaScript rendering")
    
    if doc_results.get('doc_links', 0) < 100:
        results['analysis']['documentation_issues'].append("Low documentation link count - may need deeper crawling")
    
    if doc_results.get('iframes', 0) > 0:
        results['analysis']['documentation_issues'].append("Embedded content detected - may need iframe extraction")
    
    # Save results
    output_file = "/home/nelson/nebula/Aura/logs/site_investigation.json"
    with open(output_file, 'w') as f:
        json.dump(results, f, indent=2)
    
    # Print summary
    logger.info("📊 INVESTIGATION RESULTS:")
    logger.info(f"   knowledgebase.42gears.com: {kb_results.get('article_links', 0)} article links found")
    logger.info(f"   www.42gears.com/documentation/: {doc_results.get('doc_links', 0)} doc links found")
    logger.info(f"   Knowledgebase AJAX scripts: {kb_results.get('ajax_scripts', 0)}")
    logger.info(f"   Documentation iframes: {doc_results.get('iframes', 0)}")
    logger.info(f"📄 Full results saved to: {output_file}")
    logger.info(f"📄 Pages saved to: /tmp/knowledgebase_main.html and /tmp/documentation_main.html")

if __name__ == "__main__":
    main()
