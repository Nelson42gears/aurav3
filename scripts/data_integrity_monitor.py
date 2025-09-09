#!/usr/bin/env python3
"""
Data Integrity Monitor for 42Gears Knowledge Base
- Continuous monitoring of ChromaDB collections
- Data validation and quality checks
- Automated integrity reports
"""

import sys
import os
import json
import time
import logging
import chromadb
from datetime import datetime
from pathlib import Path

# Add scripts directory to path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class DataIntegrityMonitor:
    """Monitor and validate ChromaDB data integrity"""
    
    def __init__(self, host='localhost', port=8001):
        self.client = chromadb.HttpClient(host=host, port=port)
        self.collections_to_monitor = [
            '42gears-kb-complete',
            '42gears-kb-complete-v2'
        ]
    
    def check_collection_health(self, collection_name):
        """Comprehensive health check for a collection"""
        try:
            collection = self.client.get_collection(collection_name)
            count = collection.count()
            
            if count == 0:
                return {
                    'status': 'empty',
                    'count': 0,
                    'issues': ['Collection is empty']
                }
            
            # Sample data for validation
            sample_size = min(10, count)
            sample = collection.get(limit=sample_size, include=['metadatas', 'documents'])
            
            issues = []
            valid_docs = 0
            
            # Validate sample documents
            for i, (doc, meta) in enumerate(zip(sample['documents'], sample['metadatas'])):
                if not doc or len(doc.strip()) < 50:
                    issues.append(f"Document {i+1}: Empty or too short content")
                else:
                    valid_docs += 1
                
                if not meta.get('title') or meta['title'] == 'Unknown':
                    issues.append(f"Document {i+1}: Invalid title")
                
                if not meta.get('category') or meta['category'] == 'unknown':
                    issues.append(f"Document {i+1}: Missing category")
                
                if not meta.get('url'):
                    issues.append(f"Document {i+1}: Missing URL")
            
            # Check for potential duplicates in sample
            titles = [meta.get('title', '') for meta in sample['metadatas']]
            unique_titles = set(titles)
            if len(titles) != len(unique_titles):
                issues.append(f"Potential duplicates found in sample")
            
            # Determine overall health status
            if len(issues) == 0:
                status = 'healthy'
            elif len(issues) <= 2:
                status = 'warning'
            else:
                status = 'critical'
            
            return {
                'status': status,
                'count': count,
                'sample_size': sample_size,
                'valid_documents': valid_docs,
                'issues': issues,
                'categories': list(set([meta.get('category', 'unknown') for meta in sample['metadatas']])),
                'avg_doc_length': sum([len(doc) for doc in sample['documents']]) // len(sample['documents'])
            }
            
        except Exception as e:
            return {
                'status': 'error',
                'count': 0,
                'error': str(e),
                'issues': [f"Collection access failed: {e}"]
            }
    
    def test_search_functionality(self, collection_name):
        """Test search functionality with predefined queries"""
        try:
            collection = self.client.get_collection(collection_name)
            
            test_queries = [
                'Android device management',
                'Windows configuration',
                'video streaming',
                'application installation',
                'device security'
            ]
            
            search_results = {}
            total_queries = len(test_queries)
            successful_queries = 0
            
            for query in test_queries:
                try:
                    results = collection.query(query_texts=[query], n_results=3)
                    result_count = len(results['documents'][0])
                    search_results[query] = {
                        'success': True,
                        'result_count': result_count,
                        'has_relevant_results': result_count > 0
                    }
                    if result_count > 0:
                        successful_queries += 1
                except Exception as e:
                    search_results[query] = {
                        'success': False,
                        'error': str(e)
                    }
            
            return {
                'overall_success': successful_queries == total_queries,
                'success_rate': successful_queries / total_queries,
                'queries_tested': total_queries,
                'successful_queries': successful_queries,
                'detailed_results': search_results
            }
            
        except Exception as e:
            return {
                'overall_success': False,
                'error': str(e),
                'queries_tested': 0,
                'successful_queries': 0
            }
    
    def generate_integrity_report(self):
        """Generate comprehensive integrity report"""
        report = {
            'timestamp': datetime.now().isoformat(),
            'monitoring_type': 'data_integrity',
            'collections': {},
            'overall_status': 'unknown',
            'recommendations': []
        }
        
        healthy_collections = 0
        total_collections = 0
        
        logger.info("🔍 Starting data integrity monitoring...")
        
        for collection_name in self.collections_to_monitor:
            logger.info(f"   Checking collection: {collection_name}")
            
            try:
                # Health check
                health = self.check_collection_health(collection_name)
                
                # Search functionality test
                search_test = self.test_search_functionality(collection_name)
                
                report['collections'][collection_name] = {
                    'health': health,
                    'search_functionality': search_test,
                    'last_checked': datetime.now().isoformat()
                }
                
                total_collections += 1
                
                if health['status'] == 'healthy' and search_test['overall_success']:
                    healthy_collections += 1
                    logger.info(f"   ✅ {collection_name}: Healthy ({health['count']} docs)")
                else:
                    logger.warning(f"   ⚠️ {collection_name}: Issues detected")
                    if health['issues']:
                        for issue in health['issues'][:3]:
                            logger.warning(f"      - {issue}")
                
            except Exception as e:
                logger.error(f"   ❌ {collection_name}: Failed to check - {e}")
                report['collections'][collection_name] = {
                    'health': {'status': 'error', 'error': str(e)},
                    'search_functionality': {'overall_success': False, 'error': str(e)},
                    'last_checked': datetime.now().isoformat()
                }
        
        # Overall status assessment
        if healthy_collections == total_collections:
            report['overall_status'] = 'healthy'
        elif healthy_collections > 0:
            report['overall_status'] = 'partial'
        else:
            report['overall_status'] = 'critical'
        
        # Generate recommendations
        if report['overall_status'] != 'healthy':
            report['recommendations'].append("Review collection health issues")
            report['recommendations'].append("Consider running data integrity repair")
        
        if total_collections > 1:
            report['recommendations'].append("Multiple collections detected - consider consolidation")
        
        return report
    
    def save_report(self, report, filename=None):
        """Save integrity report to file"""
        if filename is None:
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            filename = f"/home/nelson/nebula/Aura/logs/integrity_report_{timestamp}.json"
        
        with open(filename, 'w') as f:
            json.dump(report, f, indent=2)
        
        logger.info(f"📋 Integrity report saved: {filename}")
        return filename
    
    def quick_status(self):
        """Quick status check for all monitored collections"""
        status_summary = {}
        
        for collection_name in self.collections_to_monitor:
            try:
                collection = self.client.get_collection(collection_name)
                count = collection.count()
                status_summary[collection_name] = {
                    'status': 'online',
                    'document_count': count,
                    'last_checked': datetime.now().isoformat()
                }
            except Exception as e:
                status_summary[collection_name] = {
                    'status': 'offline',
                    'error': str(e),
                    'last_checked': datetime.now().isoformat()
                }
        
        return status_summary

def main():
    """Run data integrity monitoring"""
    monitor = DataIntegrityMonitor()
    
    if len(sys.argv) > 1 and sys.argv[1] == '--quick':
        # Quick status check
        status = monitor.quick_status()
        print("📊 QUICK STATUS:")
        for collection, info in status.items():
            if info['status'] == 'online':
                print(f"   ✅ {collection}: {info['document_count']} documents")
            else:
                print(f"   ❌ {collection}: {info['error']}")
    else:
        # Full integrity report
        report = monitor.generate_integrity_report()
        filename = monitor.save_report(report)
        
        print("\n📊 DATA INTEGRITY REPORT:")
        print(f"   Overall Status: {report['overall_status'].upper()}")
        print(f"   Collections Monitored: {len(report['collections'])}")
        
        for collection_name, details in report['collections'].items():
            health = details['health']
            search = details['search_functionality']
            
            print(f"\n   {collection_name}:")
            print(f"     Health: {health['status']} ({health.get('count', 0)} docs)")
            print(f"     Search: {'✅' if search['overall_success'] else '❌'}")
            
            if health.get('issues'):
                print(f"     Issues: {len(health['issues'])} found")
        
        if report['recommendations']:
            print(f"\n   Recommendations:")
            for rec in report['recommendations']:
                print(f"     - {rec}")
        
        print(f"\n   Full report: {filename}")

if __name__ == "__main__":
    main()
