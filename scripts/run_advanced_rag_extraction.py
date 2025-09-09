#!/usr/bin/env python3
"""
Advanced RAG Extraction Runner
- One-time bulk extraction with deduplication
- Automatic ChromaDB backup before processing
- Complete pipeline execution with monitoring
"""

import sys
import os
import time
import json
import logging
from pathlib import Path
from datetime import datetime

# Add services directory to path
sys.path.append(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'services'))

def main():
    """Run the complete advanced RAG extraction pipeline"""
    
    print("🚀 ADVANCED RAG EXTRACTION PIPELINE")
    print("="*60)
    print("This will:")
    print("  1. Backup existing ChromaDB collections")
    print("  2. Extract from knowledgebase.42gears.com")
    print("  3. Extract from docs.42gears.com") 
    print("  4. Deduplicate all content")
    print("  5. Create unified collection in ChromaDB")
    print("  6. Generate comprehensive report")
    print("="*60)
    
    # Confirm execution
    confirm = input("\n📋 Proceed with extraction? (y/N): ").strip().lower()
    if confirm != 'y':
        print("❌ Extraction cancelled.")
        return
    
    print("\n🔄 Starting extraction pipeline...")
    start_time = time.time()
    
    try:
        # Import and run unified extractor
        from intelligence.rag.unified_extractor import UnifiedExtractor
        
        print("📦 Initializing unified extractor...")
        extractor = UnifiedExtractor()
        
        print("🚀 Running unified extraction...")
        results = extractor.run_unified_extraction()
        
        # Calculate total time
        end_time = time.time()
        total_duration = end_time - start_time
        
        # Display results
        print("\n" + "="*60)
        print("🎉 EXTRACTION PIPELINE COMPLETE!")
        print("="*60)
        print(f"Status: {results['status'].upper()}")
        print(f"Duration: {total_duration:.1f} seconds ({total_duration/60:.1f} minutes)")
        print()
        print("📊 EXTRACTION STATISTICS:")
        extraction = results['extraction']
        print(f"  Knowledgebase Articles: {extraction['knowledgebase_articles']:,}")
        print(f"  Documentation Articles: {extraction['docs_articles']:,}")
        print(f"  Total Extracted: {extraction['total_extracted']:,}")
        print(f"  Duplicates Removed: {extraction['duplicates_removed']:,}")
        print(f"  Unique Articles: {extraction['unique_articles']:,}")
        print(f"  Articles Indexed: {extraction['articles_indexed']:,}")
        print()
        print("📁 OUTPUT FILES:")
        print(f"  Backup Location: {results['backup_location']}")
        print(f"  Collection Name: {results['collection']}")
        print(f"  Log File: {results['log_file']}")
        print(f"  Results File: /home/nelson/nebula/Aura/logs/unified_extraction_results.json")
        print(f"  Articles Data: /home/nelson/nebula/Aura/unified_articles.json")
        print()
        print("🔍 NEXT STEPS:")
        print("  1. Test hybrid search: python services/intelligence/rag/hybrid_search.py")
        print("  2. Deploy n8n automation workflows")
        print("  3. Integrate with your applications")
        print("="*60)
        
        # Test hybrid search if requested
        test_search = input("\n🔍 Test hybrid search now? (y/N): ").strip().lower()
        if test_search == 'y':
            print("\n🔍 Testing hybrid search...")
            try:
                from intelligence.rag.hybrid_search import HybridSearchEngine
                
                search_engine = HybridSearchEngine()
                test_query = "Android device management setup"
                
                print(f"Query: '{test_query}'")
                results = search_engine.search(test_query, n_results=3)
                
                for i, result in enumerate(results, 1):
                    print(f"\n{i}. {result.title}")
                    print(f"   Score: {result.hybrid_score:.3f}")
                    print(f"   Source: {result.source}")
                    print(f"   Content: {result.content[:200]}...")
                
                print("\n✅ Hybrid search test complete!")
                
            except Exception as e:
                print(f"❌ Search test failed: {e}")
        
    except Exception as e:
        print(f"\n❌ EXTRACTION FAILED: {e}")
        print("\nCheck the log files for detailed error information.")
        sys.exit(1)

if __name__ == "__main__":
    main()
