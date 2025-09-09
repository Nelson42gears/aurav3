#!/usr/bin/env python3
"""
Tonight's Full Knowledge Base Extraction - Production Run
- Enhanced deduplication pipeline
- Complete 42gears.com + docs processing  
- Automated monitoring and reporting
"""

import sys
import os
import time
import json
import logging
import subprocess
from datetime import datetime
from pathlib import Path

# Add scripts directory to path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

# Configure detailed logging for tonight's run
log_file = f"/home/nelson/nebula/Aura/logs/tonight_extraction_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(log_file),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

def check_system_status():
    """Pre-flight system checks"""
    logger.info("🔍 Pre-flight system checks...")
    
    checks = {
        'chromadb': ('curl -s http://localhost:8001/api/v1/heartbeat', 'ChromaDB'),
        'embedding_service': ('curl -s http://localhost:8002/health', 'Embedding Service'),
        'disk_space': ('df -h /home/nelson/nebula/Aura', 'Disk Space')
    }
    
    all_passed = True
    
    for check_name, (command, description) in checks.items():
        try:
            result = subprocess.run(command, shell=True, capture_output=True, text=True, timeout=10)
            if result.returncode == 0:
                logger.info(f"   ✅ {description}: OK")
            else:
                logger.error(f"   ❌ {description}: Failed - {result.stderr}")
                all_passed = False
        except Exception as e:
            logger.error(f"   ❌ {description}: Check failed - {e}")
            all_passed = False
    
    return all_passed

def run_enhanced_extraction():
    """Run the enhanced extraction with deduplication"""
    logger.info("🚀 Starting enhanced knowledge base extraction...")
    
    try:
        # Run enhanced extraction script
        cmd = "cd /home/nelson/nebula/Aura && source .venv/bin/activate && python3 scripts/enhanced_extraction_with_dedup.py"
        result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
        
        if result.returncode == 0:
            logger.info("✅ Enhanced extraction completed successfully")
            logger.info("📋 Output summary:")
            for line in result.stdout.split('\n')[-10:]:  # Last 10 lines
                if line.strip():
                    logger.info(f"   {line}")
            return True
        else:
            logger.error(f"❌ Enhanced extraction failed: {result.stderr}")
            return False
            
    except Exception as e:
        logger.error(f"❌ Extraction execution failed: {e}")
        return False

def run_integrity_check():
    """Run data integrity validation"""
    logger.info("🔍 Running post-extraction integrity check...")
    
    try:
        cmd = "cd /home/nelson/nebula/Aura && source .venv/bin/activate && python3 scripts/data_integrity_monitor.py"
        result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
        
        if result.returncode == 0:
            logger.info("✅ Integrity check passed")
            # Extract key metrics from output
            for line in result.stdout.split('\n'):
                if 'Overall Status:' in line or 'Collections Monitored:' in line or 'Health:' in line:
                    logger.info(f"   {line}")
            return True
        else:
            logger.error(f"❌ Integrity check failed: {result.stderr}")
            return False
            
    except Exception as e:
        logger.error(f"❌ Integrity check execution failed: {e}")
        return False

def update_production_collection():
    """Switch production to use the enhanced collection"""
    logger.info("🔄 Updating production collection reference...")
    
    # This would update the n8n workflow to use the new collection
    # For now, just document the recommended collection
    production_config = {
        "recommended_collection": "42gears-kb-complete-v2",
        "reason": "Enhanced with deduplication and better content processing",
        "updated_at": datetime.now().isoformat(),
        "extraction_type": "enhanced_dedup"
    }
    
    config_file = "/home/nelson/nebula/Aura/logs/production_collection_config.json"
    with open(config_file, 'w') as f:
        json.dump(production_config, f, indent=2)
    
    logger.info(f"📋 Production config updated: {config_file}")
    return True

def generate_final_report():
    """Generate comprehensive final report"""
    logger.info("📊 Generating final extraction report...")
    
    report = {
        "extraction_date": datetime.now().isoformat(),
        "extraction_type": "tonight_full_enhanced",
        "log_file": log_file,
        "status": "completed",
        "next_steps": [
            "Review data quality in ChromaDB collections",
            "Update n8n workflows to use enhanced collection",
            "Schedule regular integrity monitoring"
        ]
    }
    
    # Try to get collection stats
    try:
        import chromadb
        client = chromadb.HttpClient(host='localhost', port=8001)
        
        for collection_name in ['42gears-kb-complete-v2']:
            try:
                collection = client.get_collection(collection_name)
                count = collection.count()
                
                if count > 0:
                    data = collection.get(include=['metadatas'])
                    categories = {}
                    total_words = 0
                    
                    for meta in data['metadatas']:
                        cat = meta.get('category', 'unknown')
                        word_count = meta.get('word_count', 0)
                        categories[cat] = categories.get(cat, 0) + 1
                        total_words += word_count
                    
                    report["collections"] = {
                        collection_name: {
                            "document_count": count,
                            "total_words": total_words,
                            "categories": categories
                        }
                    }
            except Exception as e:
                report["collection_error"] = str(e)
                
    except Exception as e:
        report["chromadb_error"] = str(e)
    
    report_file = f"/home/nelson/nebula/Aura/logs/tonight_final_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    with open(report_file, 'w') as f:
        json.dump(report, f, indent=2)
    
    logger.info(f"📋 Final report saved: {report_file}")
    return report_file

def main():
    """Execute tonight's full extraction pipeline"""
    logger.info("🌙 STARTING TONIGHT'S FULL KNOWLEDGE BASE EXTRACTION")
    logger.info("=" * 60)
    
    start_time = time.time()
    success = True
    
    # Step 1: System checks
    if not check_system_status():
        logger.error("❌ Pre-flight checks failed. Aborting extraction.")
        sys.exit(1)
    
    # Step 2: Run enhanced extraction
    if not run_enhanced_extraction():
        logger.error("❌ Enhanced extraction failed.")
        success = False
    
    # Step 3: Integrity validation
    if success and not run_integrity_check():
        logger.error("❌ Integrity check failed.")
        success = False
    
    # Step 4: Update production config
    if success:
        update_production_collection()
    
    # Step 5: Final report
    report_file = generate_final_report()
    
    # Summary
    duration = time.time() - start_time
    logger.info("=" * 60)
    
    if success:
        logger.info("✅ TONIGHT'S EXTRACTION COMPLETED SUCCESSFULLY!")
        logger.info(f"⏱️ Duration: {duration/60:.1f} minutes")
        logger.info(f"📋 Final report: {report_file}")
        logger.info("🚀 Ready for production use!")
    else:
        logger.error("❌ TONIGHT'S EXTRACTION FAILED")
        logger.error(f"⏱️ Duration: {duration/60:.1f} minutes")
        logger.error(f"📋 Error report: {report_file}")
        sys.exit(1)

if __name__ == "__main__":
    main()
