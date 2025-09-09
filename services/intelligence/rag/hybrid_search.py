#!/usr/bin/env python3
"""
Hybrid Search Engine for 42Gears RAG System
- Combines vector search (ChromaDB) with BM25 keyword search
- Implements query enhancement and re-ranking
- Designed for high relevance and fast response times
"""

import os
import sys
import json
import logging
import chromadb
from typing import List, Dict, Any, Optional, Tuple
from dataclasses import dataclass
from rank_bm25 import BM25Okapi
import numpy as np
from sentence_transformers import SentenceTransformer

# Add project root to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))))

@dataclass
class SearchResult:
    """Search result with relevance scoring"""
    id: str
    title: str
    content: str
    url: str
    source: str
    category: str
    vector_score: float
    bm25_score: float
    hybrid_score: float
    metadata: Dict[str, Any]

class QueryEnhancer:
    """Enhance queries for better search results"""
    
    def __init__(self):
        # 42Gears specific term mappings
        self.tech_synonyms = {
            'mdm': ['mobile device management', 'device management'],
            'android': ['android device', 'mobile device'],
            'windows': ['windows device', 'pc', 'desktop'],
            'suremdm': ['42gears mdm', 'device management platform'],
            'kiosk': ['kiosk mode', 'single app mode', 'locked mode'],
            'app': ['application', 'software', 'program'],
            'install': ['installation', 'deployment', 'setup'],
            'configuration': ['config', 'settings', 'setup'],
            'policy': ['policies', 'rules', 'restrictions'],
            'security': ['protection', 'safety', 'secure']
        }
        
        self.common_misspellings = {
            'andriod': 'android',
            'winodws': 'windows',
            'configuratin': 'configuration',
            'instalation': 'installation',
            'managment': 'management'
        }
    
    def enhance_query(self, query: str) -> str:
        """Enhance query with synonyms and corrections"""
        enhanced = query.lower().strip()
        
        # Fix common misspellings
        for wrong, correct in self.common_misspellings.items():
            enhanced = enhanced.replace(wrong, correct)
        
        # Add synonyms for key terms
        words = enhanced.split()
        enhanced_words = []
        
        for word in words:
            enhanced_words.append(word)
            # Add synonyms if available
            if word in self.tech_synonyms:
                enhanced_words.extend(self.tech_synonyms[word])
        
        return ' '.join(enhanced_words)
    
    def extract_keywords(self, query: str) -> List[str]:
        """Extract important keywords from query"""
        # Remove common stop words
        stop_words = {'the', 'a', 'an', 'and', 'or', 'but', 'in', 'on', 'at', 'to', 'for', 'of', 'with', 'by', 'how', 'what', 'where', 'when', 'why'}
        
        words = query.lower().split()
        keywords = [word for word in words if word not in stop_words and len(word) > 2]
        
        return keywords

class HybridSearchEngine:
    """Hybrid search combining vector and BM25 search"""
    
    def __init__(self, 
                 chromadb_host='localhost', 
                 chromadb_port=8001,
                 collection_name='42gears-unified-v1',
                 vector_weight=0.7,
                 bm25_weight=0.3):
        
        self.chromadb_host = chromadb_host
        self.chromadb_port = chromadb_port
        self.collection_name = collection_name
        self.vector_weight = vector_weight
        self.bm25_weight = bm25_weight
        
        # Initialize components
        self.query_enhancer = QueryEnhancer()
        self.logger = self._setup_logging()
        
        # Initialize ChromaDB
        self._initialize_chromadb()
        
        # Initialize BM25 (will be populated on first search)
        self.bm25_index = None
        self.documents_corpus = []
        self.documents_metadata = []
        self._bm25_initialized = False
    
    def _setup_logging(self):
        """Setup logging"""
        logging.basicConfig(level=logging.INFO)
        return logging.getLogger(__name__)
    
    def _initialize_chromadb(self):
        """Initialize ChromaDB connection"""
        try:
            self.chromadb_client = chromadb.HttpClient(
                host=self.chromadb_host, 
                port=self.chromadb_port
            )
            self.collection = self.chromadb_client.get_collection(self.collection_name)
            self.logger.info(f"✅ Connected to ChromaDB collection: {self.collection_name}")
        except Exception as e:
            self.logger.error(f"❌ Failed to connect to ChromaDB: {e}")
            raise
    
    def _initialize_bm25(self):
        """Initialize BM25 index with all documents"""
        if self._bm25_initialized:
            return
        
        try:
            self.logger.info("🔍 Initializing BM25 index...")
            
            # Get all documents from ChromaDB
            results = self.collection.get(include=['documents', 'metadatas'])
            
            if not results['documents']:
                self.logger.warning("No documents found in collection")
                return
            
            # Prepare corpus for BM25
            self.documents_corpus = []
            self.documents_metadata = []
            
            for i, (doc, metadata) in enumerate(zip(results['documents'], results['metadatas'])):
                # Tokenize document for BM25
                tokens = doc.lower().split()
                self.documents_corpus.append(tokens)
                
                # Store metadata with document index
                metadata['doc_index'] = i
                self.documents_metadata.append(metadata)
            
            # Create BM25 index
            self.bm25_index = BM25Okapi(self.documents_corpus)
            self._bm25_initialized = True
            
            self.logger.info(f"✅ BM25 index initialized with {len(self.documents_corpus)} documents")
            
        except Exception as e:
            self.logger.error(f"❌ Failed to initialize BM25: {e}")
            raise
    
    def vector_search(self, query: str, n_results: int = 10) -> List[Dict]:
        """Perform vector search using ChromaDB"""
        try:
            results = self.collection.query(
                query_texts=[query],
                n_results=n_results,
                include=['documents', 'metadatas', 'distances']
            )
            
            search_results = []
            for i, (doc, metadata, distance) in enumerate(zip(
                results['documents'][0],
                results['metadatas'][0], 
                results['distances'][0]
            )):
                # Convert distance to similarity score (lower distance = higher similarity)
                similarity = 1.0 / (1.0 + distance)
                
                search_results.append({
                    'content': doc,
                    'metadata': metadata,
                    'vector_score': similarity,
                    'rank': i + 1
                })
            
            return search_results
            
        except Exception as e:
            self.logger.error(f"Vector search failed: {e}")
            return []
    
    def bm25_search(self, query: str, n_results: int = 10) -> List[Dict]:
        """Perform BM25 keyword search"""
        if not self._bm25_initialized:
            self._initialize_bm25()
        
        if not self.bm25_index:
            return []
        
        try:
            # Tokenize query
            query_tokens = query.lower().split()
            
            # Get BM25 scores
            scores = self.bm25_index.get_scores(query_tokens)
            
            # Get top results with scores
            scored_docs = [(i, score) for i, score in enumerate(scores)]
            scored_docs.sort(key=lambda x: x[1], reverse=True)
            
            search_results = []
            for rank, (doc_index, score) in enumerate(scored_docs[:n_results]):
                if score > 0:  # Only include results with positive scores
                    # Reconstruct document from tokens
                    doc_content = ' '.join(self.documents_corpus[doc_index])
                    metadata = self.documents_metadata[doc_index].copy()
                    
                    search_results.append({
                        'content': doc_content,
                        'metadata': metadata,
                        'bm25_score': float(score),
                        'rank': rank + 1
                    })
            
            return search_results
            
        except Exception as e:
            self.logger.error(f"BM25 search failed: {e}")
            return []
    
    def hybrid_search(self, query: str, n_results: int = 10) -> List[SearchResult]:
        """Perform hybrid search combining vector and BM25"""
        # Enhance query
        enhanced_query = self.query_enhancer.enhance_query(query)
        
        # Perform both searches
        vector_results = self.vector_search(enhanced_query, n_results * 2)
        bm25_results = self.bm25_search(enhanced_query, n_results * 2)
        
        # Combine results using document ID/URL as key
        combined_results = {}
        
        # Process vector results
        for result in vector_results:
            doc_id = result['metadata'].get('url', result['metadata'].get('id', ''))
            if doc_id:
                combined_results[doc_id] = {
                    'content': result['content'],
                    'metadata': result['metadata'],
                    'vector_score': result['vector_score'],
                    'bm25_score': 0.0,
                    'vector_rank': result['rank']
                }
        
        # Process BM25 results
        for result in bm25_results:
            doc_id = result['metadata'].get('url', result['metadata'].get('id', ''))
            if doc_id:
                if doc_id in combined_results:
                    combined_results[doc_id]['bm25_score'] = result['bm25_score']
                    combined_results[doc_id]['bm25_rank'] = result['rank']
                else:
                    combined_results[doc_id] = {
                        'content': result['content'],
                        'metadata': result['metadata'],
                        'vector_score': 0.0,
                        'bm25_score': result['bm25_score'],
                        'bm25_rank': result['rank']
                    }
        
        # Calculate hybrid scores and create SearchResult objects
        final_results = []
        for doc_id, result in combined_results.items():
            # Normalize scores
            vector_score = result['vector_score']
            bm25_score = result['bm25_score']
            
            # Calculate hybrid score
            hybrid_score = (
                self.vector_weight * vector_score + 
                self.bm25_weight * bm25_score
            )
            
            search_result = SearchResult(
                id=result['metadata'].get('id', doc_id),
                title=result['metadata'].get('title', 'Unknown'),
                content=result['content'][:500] + '...' if len(result['content']) > 500 else result['content'],
                url=result['metadata'].get('url', ''),
                source=result['metadata'].get('source', 'unknown'),
                category=result['metadata'].get('category', 'unknown'),
                vector_score=vector_score,
                bm25_score=bm25_score,
                hybrid_score=hybrid_score,
                metadata=result['metadata']
            )
            
            final_results.append(search_result)
        
        # Sort by hybrid score
        final_results.sort(key=lambda x: x.hybrid_score, reverse=True)
        
        return final_results[:n_results]
    
    def search(self, query: str, n_results: int = 5, search_type: str = 'hybrid') -> List[SearchResult]:
        """Main search interface"""
        self.logger.info(f"🔍 Searching: '{query}' (type: {search_type})")
        
        if search_type == 'vector':
            vector_results = self.vector_search(query, n_results)
            return [
                SearchResult(
                    id=r['metadata'].get('id', ''),
                    title=r['metadata'].get('title', 'Unknown'),
                    content=r['content'][:500] + '...' if len(r['content']) > 500 else r['content'],
                    url=r['metadata'].get('url', ''),
                    source=r['metadata'].get('source', 'unknown'),
                    category=r['metadata'].get('category', 'unknown'),
                    vector_score=r['vector_score'],
                    bm25_score=0.0,
                    hybrid_score=r['vector_score'],
                    metadata=r['metadata']
                ) for r in vector_results
            ]
        
        elif search_type == 'bm25':
            bm25_results = self.bm25_search(query, n_results)
            return [
                SearchResult(
                    id=r['metadata'].get('id', ''),
                    title=r['metadata'].get('title', 'Unknown'),
                    content=r['content'][:500] + '...' if len(r['content']) > 500 else r['content'],
                    url=r['metadata'].get('url', ''),
                    source=r['metadata'].get('source', 'unknown'),
                    category=r['metadata'].get('category', 'unknown'),
                    vector_score=0.0,
                    bm25_score=r['bm25_score'],
                    hybrid_score=r['bm25_score'],
                    metadata=r['metadata']
                ) for r in bm25_results
            ]
        
        else:  # hybrid (default)
            return self.hybrid_search(query, n_results)
    
    def get_search_stats(self) -> Dict[str, Any]:
        """Get search engine statistics"""
        try:
            collection_count = self.collection.count()
            return {
                'collection_name': self.collection_name,
                'total_documents': collection_count,
                'bm25_initialized': self._bm25_initialized,
                'vector_weight': self.vector_weight,
                'bm25_weight': self.bm25_weight,
                'chromadb_host': f"{self.chromadb_host}:{self.chromadb_port}"
            }
        except Exception as e:
            return {'error': str(e)}

def main():
    """Test the hybrid search engine"""
    print("🔍 Testing Hybrid Search Engine...")
    
    try:
        # Initialize search engine
        search_engine = HybridSearchEngine()
        
        # Get stats
        stats = search_engine.get_search_stats()
        print(f"📊 Collection: {stats.get('collection_name')}")
        print(f"📚 Documents: {stats.get('total_documents', 0):,}")
        
        # Test queries
        test_queries = [
            "Android device configuration",
            "SureMDM kiosk mode setup",
            "Windows application installation",
            "Device security policies",
            "Mobile device management"
        ]
        
        for query in test_queries:
            print(f"\n🔍 Query: '{query}'")
            results = search_engine.search(query, n_results=3)
            
            for i, result in enumerate(results, 1):
                print(f"  {i}. {result.title[:50]}...")
                print(f"     Score: {result.hybrid_score:.3f} (V:{result.vector_score:.3f}, BM25:{result.bm25_score:.3f})")
                print(f"     Source: {result.source}")
                print(f"     URL: {result.url}")
                print()
    
    except Exception as e:
        print(f"❌ Error: {e}")

if __name__ == "__main__":
    main()
