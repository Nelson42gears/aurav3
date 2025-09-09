#!/usr/bin/env python3
"""
Unified Knowledge Base Extractor
- Single extraction point for knowledgebase.42gears.com and docs.42gears.com
- Built-in deduplication and data quality validation
- Designed for one-time bulk extraction + incremental updates via n8n
"""

import sys
import os
import time
import json
import logging
import hashlib
import requests
import chromadb
from typing import Dict, List, Optional, Set, Tuple
from datetime import datetime
from pathlib import Path
from bs4 import BeautifulSoup
from urllib.parse import urljoin, urlparse, urlunparse
from dataclasses import dataclass, asdict
import PyPDF2
import pytesseract
from PIL import Image
import io
import fitz  # PyMuPDF for better PDF handling

# Add project root to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))))

@dataclass
class UnifiedArticle:
    """Unified article schema for all sources"""
    id: str                    # SHA-256 hash of normalized_url
    url: str                   # Original URL
    normalized_url: str        # Normalized URL (primary dedup key)
    title: str                 # Article title
    content: str              # Full text content
    content_hash: str         # SHA-256 of content (secondary dedup key)
    source: str               # knowledgebase.42gears.com | docs.42gears.com
    category: str             # Normalized category/section
    word_count: int           # Content statistics
    char_count: int
    extracted_at: str         # ISO timestamp
    last_updated: str         # ISO timestamp
    metadata: dict            # Additional source-specific metadata
    has_images: bool = False  # Contains processed images
    has_pdfs: bool = False    # Contains PDF content

class UnifiedExtractor:
    """Production-grade unified extractor for 42Gears knowledge sources"""
    
    def __init__(self, 
                 chromadb_host='localhost', 
                 chromadb_port=8001,
                 requests_per_minute=20,  # Configurable rate limiting
                 enable_ocr=True,
                 enable_pdf=True):
        self.chromadb_host = chromadb_host
        self.chromadb_port = chromadb_port
        self.requests_per_minute = requests_per_minute
        self.enable_ocr = enable_ocr
        self.enable_pdf = enable_pdf
        
        # Setup session with better headers
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (compatible; 42GearsBot/1.0; +https://42gears.com/contact)'
        })
        
        # Rate limiting
        self.request_times = []
        self.base_delay = 60.0 / requests_per_minute  # Convert to delay between requests
        self.current_delay = self.base_delay
        
        # Logging setup
        self.setup_logging()
        
        # Deduplication tracking
        self.url_fingerprints: Set[str] = set()
        self.content_fingerprints: Set[str] = set()
        self.duplicate_count = 0
        
        # Statistics
        self.pdf_count = 0
        self.image_count = 0
        self.failed_urls = set()
        
    def setup_logging(self):
        """Configure logging with timestamp"""
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        log_file = f"/home/nelson/nebula/Aura/logs/unified_extraction_{timestamp}.log"
        
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(levelname)s - %(message)s',
            handlers=[
                logging.FileHandler(log_file),
                logging.StreamHandler()
            ]
        )
        self.logger = logging.getLogger(__name__)
        self.log_file = log_file
    
    def normalize_url(self, url: str) -> str:
        """Normalize URL for deduplication"""
        parsed = urlparse(url)
        # Remove query parameters and fragments
        normalized = urlunparse((
            parsed.scheme,
            parsed.netloc.lower(),
            parsed.path.rstrip('/'),
            '',  # params
            '',  # query
            ''   # fragment
        ))
        return normalized
    
    def create_article_fingerprint(self, url: str, content: str) -> Tuple[str, str]:
        """Create fingerprints for deduplication"""
        normalized_url = self.normalize_url(url)
        url_fingerprint = hashlib.sha256(normalized_url.encode()).hexdigest()
        
        # Content fingerprint (first 1000 chars for efficiency)
        content_sample = content[:1000] if content else ""
        content_fingerprint = hashlib.sha256(content_sample.encode()).hexdigest()
        
        return url_fingerprint, content_fingerprint
    
    def rate_limit_wait(self):
        """Intelligent rate limiting for 42gears sites"""
        now = time.time()
        
        # Remove requests older than 1 minute
        self.request_times = [t for t in self.request_times if now - t < 60]
        
        # Check if we need to wait
        if len(self.request_times) >= self.requests_per_minute:
            wait_time = 60 - (now - self.request_times[0])
            if wait_time > 0:
                self.logger.info(f"⏱️ Rate limiting: waiting {wait_time:.1f}s")
                time.sleep(wait_time)
        
        # Apply current delay (starts small, increases on errors)
        time.sleep(self.current_delay)
        self.request_times.append(now)
    
    def is_pdf_url(self, url: str) -> bool:
        """Check if URL points to a PDF"""
        return url.lower().endswith('.pdf') or 'pdf' in url.lower()
    
    def is_image_url(self, url: str) -> bool:
        """Check if URL points to an image"""
        image_extensions = ('.jpg', '.jpeg', '.png', '.gif', '.bmp', '.webp', '.svg')
        return any(url.lower().endswith(ext) for ext in image_extensions)
    
    def extract_pdf_content(self, pdf_url: str) -> Optional[str]:
        """Extract text from PDF using PyMuPDF with OCR fallback"""
        if not self.enable_pdf:
            return None
            
        try:
            self.rate_limit_wait()
            response = self.session.get(pdf_url, timeout=30)
            response.raise_for_status()
            
            # Use PyMuPDF for better text extraction
            doc = fitz.open(stream=response.content, filetype="pdf")
            text_content = []
            
            # Limit pages (max 50 for performance)
            max_pages = min(len(doc), 50)
            
            for page_num in range(max_pages):
                page = doc[page_num]
                text = page.get_text()
                
                if text.strip():
                    text_content.append(text)
                
                # OCR on images if text is sparse and OCR enabled
                if self.enable_ocr and len(text.strip()) < 100:
                    try:
                        pix = page.get_pixmap()
                        img_data = pix.tobytes("png")
                        img = Image.open(io.BytesIO(img_data))
                        ocr_text = pytesseract.image_to_string(img, lang='eng')
                        
                        if ocr_text.strip():
                            text_content.append(f"[OCR] {ocr_text}")
                    except Exception as e:
                        self.logger.debug(f"OCR failed for PDF page {page_num}: {e}")
            
            doc.close()
            self.pdf_count += 1
            return '\n\n'.join(text_content)
            
        except Exception as e:
            self.logger.error(f"PDF extraction failed for {pdf_url}: {e}")
            self.failed_urls.add(pdf_url)
            return None
    
    def extract_image_content(self, img_url: str, alt_text: str = "") -> str:
        """Extract content from images using OCR"""
        if not self.enable_ocr:
            return alt_text
        
        try:
            response = self.session.get(img_url, timeout=30)
            response.raise_for_status()
            
            img = Image.open(io.BytesIO(response.content))
            ocr_text = pytesseract.image_to_string(img, lang='eng')
            
            content_parts = []
            if alt_text.strip():
                content_parts.append(f"Alt: {alt_text}")
            if ocr_text.strip():
                content_parts.append(f"OCR: {ocr_text}")
            
            if content_parts:
                self.image_count += 1
            
            return ' | '.join(content_parts)
            
        except Exception as e:
            self.logger.debug(f"Image OCR failed for {img_url}: {e}")
            return alt_text
    
    def fetch_with_retry(self, url: str, max_retries: int = 3) -> Optional[requests.Response]:
        """Fetch URL with retry logic - NO robots.txt restrictions for 42gears sites"""
        for attempt in range(max_retries + 1):
            try:
                self.rate_limit_wait()
                response = self.session.get(url, timeout=30)
                response.raise_for_status()
                
                # Success: gradually reduce delay
                self.current_delay = max(self.current_delay * 0.9, self.base_delay)
                return response
                
            except Exception as e:
                self.logger.warning(f"Attempt {attempt + 1} failed for {url}: {e}")
                
                if attempt < max_retries:
                    # Error: increase delay (exponential backoff)
                    self.current_delay = min(self.current_delay * 2, 30.0)
                    time.sleep(5 * (attempt + 1))
                else:
                    self.failed_urls.add(url)
                    return None
    
    def is_duplicate(self, url: str, content: str) -> bool:
        """Check if article is duplicate"""
        url_fp, content_fp = self.create_article_fingerprint(url, content)
        
        if url_fp in self.url_fingerprints:
            self.duplicate_count += 1
            self.logger.debug(f"Duplicate URL detected: {url}")
            return True
            
        if content_fp in self.content_fingerprints:
            self.duplicate_count += 1
            self.logger.debug(f"Duplicate content detected: {url}")
            return True
            
        # Add to tracking sets
        self.url_fingerprints.add(url_fp)
        self.content_fingerprints.add(content_fp)
        return False
    
    def extract_knowledgebase_articles(self) -> List[UnifiedArticle]:
        """Extract articles from knowledgebase.42gears.com"""
        self.logger.info("🔍 Extracting from knowledgebase.42gears.com...")
        
        base_url = "https://knowledgebase.42gears.com"
        articles = []
        
        try:
            # Get main page to find categories
            response = self.session.get(base_url)
            response.raise_for_status()
            soup = BeautifulSoup(response.content, 'html.parser')
            
            # Find category links
            categories = set()
            for link in soup.find_all('a', href=True):
                href = link['href']
                if 'article-categories' in href:
                    full_url = urljoin(base_url, href)
                    categories.add(full_url)
            
            self.logger.info(f"   Found {len(categories)} categories")
            
            # Extract articles from each category
            for category_url in categories:
                category_articles = self._extract_knowledgebase_category(category_url)
                articles.extend(category_articles)
                time.sleep(1)  # Be respectful
                
        except Exception as e:
            self.logger.error(f"Error extracting knowledgebase articles: {e}")
        
        self.logger.info(f"✅ Knowledgebase extraction: {len(articles)} articles")
        return articles
    
    def _extract_knowledgebase_category(self, category_url: str) -> List[UnifiedArticle]:
        """Extract articles from a knowledgebase category"""
        articles = []
        
        try:
            response = self.session.get(category_url)
            response.raise_for_status()
            soup = BeautifulSoup(response.content, 'html.parser')
            
            # Find article links
            for link in soup.find_all('a', href=True):
                href = link['href']
                if '/article/' in href and href != '/article/':
                    article_url = urljoin(category_url, href)
                    
                    # Extract article content
                    article = self._extract_knowledgebase_article(article_url)
                    if article and not self.is_duplicate(article.url, article.content):
                        articles.append(article)
                    
                    time.sleep(0.5)  # Be respectful
                    
        except Exception as e:
            self.logger.error(f"Error extracting category {category_url}: {e}")
        
        return articles
    
    def _extract_knowledgebase_article(self, url: str) -> Optional[UnifiedArticle]:
        """Extract content from a knowledgebase article with PDF and image support"""
        try:
            # Handle PDFs directly
            if self.is_pdf_url(url):
                return self._extract_pdf_article(url)
            
            response = self.fetch_with_retry(url)
            if not response:
                return None
            soup = BeautifulSoup(response.content, 'html.parser')
            
            # Remove unwanted elements
            for element in soup.select('nav, header, footer, script, style, .sidebar'):
                element.decompose()
            
            # Extract title
            title_elem = soup.select_one('h1, .article-title, .title')
            title = title_elem.get_text().strip() if title_elem else "Unknown"
            
            # Extract main content
            content_elem = soup.select_one('article, .article-content, .content, main')
            if not content_elem:
                content_elem = soup.body
            
            if content_elem:
                full_text = content_elem.get_text(separator='\n', strip=True)
            else:
                full_text = soup.get_text(separator='\n', strip=True)
            
            # Clean text
            lines = [line.strip() for line in full_text.split('\n') if line.strip()]
            clean_text = '\n'.join(lines)
            
            # Skip if content too short
            if len(clean_text) < 100:
                return None
            
            # Create unified article
            normalized_url = self.normalize_url(url)
            article_id = hashlib.sha256(normalized_url.encode()).hexdigest()
            content_hash = hashlib.sha256(clean_text.encode()).hexdigest()
            now = datetime.now().isoformat()
            
            return UnifiedArticle(
                id=article_id,
                url=url,
                normalized_url=normalized_url,
                title=title,
                content=clean_text,
                content_hash=content_hash,
                source='knowledgebase.42gears.com',
                category='knowledgebase',
                word_count=len(clean_text.split()),
                char_count=len(clean_text),
                extracted_at=now,
                last_updated=now,
                metadata={'original_url': url}
            )
            
        except Exception as e:
            self.logger.error(f"Error extracting article {url}: {e}")
            return None
    
    def extract_docs_articles(self) -> List[UnifiedArticle]:
        """Extract articles from docs.42gears.com"""
        self.logger.info("🔍 Extracting from docs.42gears.com...")
        
        base_url = "https://docs.42gears.com"
        articles = []
        visited_urls = set()
        
        def crawl_page(url: str, depth: int = 0, max_depth: int = 3):
            if depth > max_depth or url in visited_urls:
                return
                
            visited_urls.add(url)
            
            try:
                response = self.session.get(url)
                response.raise_for_status()
                soup = BeautifulSoup(response.content, 'html.parser')
                
                # Extract content from current page
                article = self._extract_docs_article(url, soup)
                if article and not self.is_duplicate(article.url, article.content):
                    articles.append(article)
                
                # Find internal links for further crawling
                for link in soup.find_all('a', href=True):
                    href = link['href']
                    if href.startswith('/') and not href.startswith('/search'):
                        full_url = urljoin(base_url, href)
                        parsed = urlparse(full_url)
                        path = parsed.path.strip('/')
                        
                        # Only crawl documentation pages (no file extensions)
                        if path and '.' not in path.split('/')[-1]:
                            crawl_page(full_url, depth + 1, max_depth)
                
                time.sleep(1)  # Be respectful
                
            except Exception as e:
                self.logger.error(f"Error crawling {url}: {e}")
        
        try:
            crawl_page(base_url)
        except Exception as e:
            self.logger.error(f"Error extracting docs articles: {e}")
        
        self.logger.info(f"✅ Docs extraction: {len(articles)} articles")
        return articles
    
    def _extract_docs_article(self, url: str, soup: BeautifulSoup = None) -> Optional[UnifiedArticle]:
        """Extract content from a docs article with comprehensive processing"""
        try:
            # Handle PDFs directly
            if self.is_pdf_url(url):
                return self._extract_pdf_article(url)
            
            # Get soup if not provided
            if not soup:
                response = self.fetch_with_retry(url)
                if not response:
                    return None
                soup = BeautifulSoup(response.content, 'html.parser')
            
            # Remove unwanted elements
            for element in soup.select('nav, header, footer, script, style'):
                element.decompose()
            
            # Extract title
            title_elem = soup.select_one('h1, title')
            title = title_elem.get_text().strip() if title_elem else "Unknown"
            
            # Extract main content
            content_elem = soup.select_one('main, article, .content, .documentation')
            if not content_elem:
                content_elem = soup.body
            
            if content_elem:
                full_text = content_elem.get_text(separator='\n', strip=True)
            else:
                full_text = soup.get_text(separator='\n', strip=True)
            
            # Clean text
            lines = [line.strip() for line in full_text.split('\n') if line.strip()]
            clean_text = '\n'.join(lines)
            
            # Skip if content too short
            if len(clean_text) < 100:
                return None
            
            # Create unified article
            normalized_url = self.normalize_url(url)
            article_id = hashlib.sha256(normalized_url.encode()).hexdigest()
            content_hash = hashlib.sha256(clean_text.encode()).hexdigest()
            now = datetime.now().isoformat()
            
            return UnifiedArticle(
                id=article_id,
                url=url,
                normalized_url=normalized_url,
                title=title,
                content=clean_text,
                content_hash=content_hash,
                source='docs.42gears.com',
                category='documentation',
                word_count=len(clean_text.split()),
                char_count=len(clean_text),
                extracted_at=now,
                last_updated=now,
                metadata={'original_url': url}
            )
            
        except Exception as e:
            self.logger.error(f"Error extracting docs article {url}: {e}")
            return None
    
    def _extract_pdf_article(self, pdf_url: str) -> Optional[UnifiedArticle]:
        """Extract content from PDF and create UnifiedArticle"""
        try:
            pdf_content = self.extract_pdf_content(pdf_url)
            if not pdf_content or len(pdf_content) < 100:
                return None
            
            # Create unified article for PDF
            normalized_url = self.normalize_url(pdf_url)
            article_id = hashlib.sha256(normalized_url.encode()).hexdigest()
            content_hash = hashlib.sha256(pdf_content.encode()).hexdigest()
            now = datetime.now().isoformat()
            
            return UnifiedArticle(
                id=article_id,
                url=pdf_url,
                normalized_url=normalized_url,
                title=f"PDF Document - {os.path.basename(pdf_url)}",
                content=pdf_content,
                content_hash=content_hash,
                source=urlparse(pdf_url).netloc,
                category='pdf_document',
                word_count=len(pdf_content.split()),
                char_count=len(pdf_content),
                extracted_at=now,
                last_updated=now,
                metadata={
                    'original_url': pdf_url,
                    'document_type': 'pdf',
                    'extraction_method': 'unified_production'
                },
                has_images=False,
                has_pdfs=True
            )
            
        except Exception as e:
            self.logger.error(f"PDF article creation failed for {pdf_url}: {e}")
            return None
    
    def backup_chromadb(self) -> str:
        """Create backup of existing ChromaDB collections"""
        self.logger.info("💾 Creating ChromaDB backup...")
        
        try:
            client = chromadb.HttpClient(host=self.chromadb_host, port=self.chromadb_port)
            collections = client.list_collections()
            
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            backup_dir = f"/home/nelson/nebula/Aura/backups/chromadb_backup_{timestamp}"
            os.makedirs(backup_dir, exist_ok=True)
            
            backup_info = {
                'timestamp': timestamp,
                'collections': [],
                'total_documents': 0
            }
            
            for collection in collections:
                try:
                    coll = client.get_collection(collection.name)
                    count = coll.count()
                    
                    if count > 0:
                        # Export collection data
                        data = coll.get(include=['documents', 'metadatas'])
                        collection_backup = {
                            'name': collection.name,
                            'count': count,
                            'data': data
                        }
                        
                        backup_file = f"{backup_dir}/{collection.name}_backup.json"
                        with open(backup_file, 'w') as f:
                            json.dump(collection_backup, f, indent=2)
                        
                        backup_info['collections'].append({
                            'name': collection.name,
                            'count': count,
                            'backup_file': backup_file
                        })
                        backup_info['total_documents'] += count
                        
                        self.logger.info(f"   ✅ Backed up '{collection.name}': {count} documents")
                    
                except Exception as e:
                    self.logger.error(f"   ❌ Failed to backup '{collection.name}': {e}")
            
            # Save backup info
            info_file = f"{backup_dir}/backup_info.json"
            with open(info_file, 'w') as f:
                json.dump(backup_info, f, indent=2)
            
            self.logger.info(f"✅ Backup complete: {backup_info['total_documents']} documents backed up to {backup_dir}")
            return backup_dir
            
        except Exception as e:
            self.logger.error(f"❌ Backup failed: {e}")
            raise
    
    def index_articles(self, articles: List[UnifiedArticle], collection_name: str = '42gears-unified-v1') -> int:
        """Index articles in ChromaDB with deduplication"""
        self.logger.info(f"📚 Indexing {len(articles)} articles in ChromaDB...")
        
        try:
            client = chromadb.HttpClient(host=self.chromadb_host, port=self.chromadb_port)
            
            # Delete existing collection if it exists
            try:
                client.delete_collection(collection_name)
                self.logger.info(f"   Deleted existing collection: {collection_name}")
            except:
                pass
            
            # Create new collection
            collection = client.create_collection(collection_name)
            
            # Index in batches
            batch_size = 10
            total_indexed = 0
            
            for i in range(0, len(articles), batch_size):
                batch = articles[i:i+batch_size]
                documents = []
                metadatas = []
                ids = []
                
                for article in batch:
                    documents.append(article.content)
                    metadatas.append({
                        'title': article.title,
                        'url': article.url,
                        'source': article.source,
                        'category': article.category,
                        'word_count': article.word_count,
                        'char_count': article.char_count,
                        'extracted_at': article.extracted_at
                    })
                    ids.append(article.id)
                
                # Add batch to collection
                collection.add(
                    documents=documents,
                    metadatas=metadatas,
                    ids=ids
                )
                
                total_indexed += len(batch)
                self.logger.info(f"   ✅ Batch {i//batch_size + 1}: Indexed {len(batch)} articles (Total: {total_indexed})")
                time.sleep(1)  # Prevent overloading
            
            self.logger.info(f"✅ Indexing complete: {total_indexed} articles in '{collection_name}'")
            return total_indexed
            
        except Exception as e:
            self.logger.error(f"❌ Indexing failed: {e}")
            raise
    
    def run_unified_extraction(self, incremental: bool = False) -> dict:
        """
        Run extraction with automatic monitoring and validation
        """
        # Add --incremental CLI support
        if '--incremental' in sys.argv:
            incremental = True
        """Run complete unified extraction process"""
        self.logger.info("🚀 Starting UNIFIED 42Gears Knowledge Extraction...")
        
        start_time = time.time()
        
        # Step 1: Backup existing ChromaDB
        backup_dir = self.backup_chromadb()
        
        # Step 2: Extract from both sources
        kb_articles = self.extract_knowledgebase_articles()
        docs_articles = self.extract_docs_articles()
        
        # Step 3: Combine and deduplicate
        all_articles = kb_articles + docs_articles
        unique_articles = []
        
        # Reset fingerprints for final dedup check
        self.url_fingerprints.clear()
        self.content_fingerprints.clear()
        final_duplicates = 0
        
        for article in all_articles:
            if not self.is_duplicate(article.url, article.content):
                unique_articles.append(article)
            else:
                final_duplicates += 1
        
        # Step 4: Index in ChromaDB
        indexed_count = self.index_articles(unique_articles)
        
        # Step 5: Generate results
        end_time = time.time()
        duration = end_time - start_time
        
        results = {
            'status': 'completed',
            'duration_seconds': round(duration, 2),
            'extraction': {
                'knowledgebase_articles': len(kb_articles),
                'docs_articles': len(docs_articles),
                'total_extracted': len(all_articles),
                'duplicates_removed': final_duplicates,
                'unique_articles': len(unique_articles),
                'articles_indexed': indexed_count
            },
            'sources': ['knowledgebase.42gears.com', 'docs.42gears.com'],
            'collection': '42gears-unified-v1',
            'backup_location': backup_dir,
            'log_file': self.log_file,
            'completed_at': datetime.now().isoformat()
        }
        
        # Save results
        results_file = f"/home/nelson/nebula/Aura/logs/unified_extraction_results.json"
        with open(results_file, 'w') as f:
            json.dump(results, f, indent=2)
        
        # Save article data
        articles_data = [asdict(article) for article in unique_articles]
        articles_file = f"/home/nelson/nebula/Aura/unified_articles.json"
        with open(articles_file, 'w') as f:
            json.dump({
                'articles': articles_data,
                'stats': results['extraction']
            }, f, indent=2)
        
        self.logger.info("🎉 UNIFIED EXTRACTION COMPLETE!")
        self.logger.info(f"   📊 Total articles: {results['extraction']['unique_articles']}")
        self.logger.info(f"   📚 Indexed: {results['extraction']['articles_indexed']}")
        self.logger.info(f"   🗑️ Duplicates removed: {results['extraction']['duplicates_removed']}")
        self.logger.info(f"   ⏱️ Duration: {results['duration_seconds']} seconds")
        self.logger.info(f"   💾 Backup: {backup_dir}")
        self.logger.info(f"   📄 Results: {results_file}")
        
        return results

def main():
    """Run unified extraction"""
    extractor = UnifiedExtractor()
    results = extractor.run_unified_extraction()
    
    print("\n" + "="*60)
    print("🎉 UNIFIED EXTRACTION SUMMARY")
    print("="*60)
    print(f"Status: {results['status'].upper()}")
    print(f"Unique Articles: {results['extraction']['unique_articles']:,}")
    print(f"Articles Indexed: {results['extraction']['articles_indexed']:,}")
    print(f"Duplicates Removed: {results['extraction']['duplicates_removed']:,}")
    print(f"Duration: {results['duration_seconds']} seconds")
    print(f"Collection: {results['collection']}")
    print("="*60)

if __name__ == "__main__":
    main()
