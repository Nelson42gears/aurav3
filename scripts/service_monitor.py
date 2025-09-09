#!/usr/bin/env python3
"""
Service Monitor for Aura Stack
Monitors Docker containers and ensures they are running properly
"""

import subprocess
import json
import time
import logging
import os
from datetime import datetime

# Configure logging
log_dir = "/home/nelson/nebula/Aura/logs"
os.makedirs(log_dir, exist_ok=True)
log_file = os.path.join(log_dir, "service_monitor.log")

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(log_file),
        logging.StreamHandler()
    ]
)

# Critical services to monitor
CRITICAL_SERVICES = [
    {"name": "aura-n8n-1", "description": "n8n Workflow Engine", "port": 5678},
    {"name": "aura-n8n_mcp_server-1", "description": "n8n MCP Server", "port": 3001},
    {"name": "aura-freshdesk_mcp_server-1", "description": "Freshdesk MCP Server", "port": 8000},
    {"name": "aura-suremdm_mcp_server-1", "description": "SureMDM MCP Server", "port": 7000},
    {"name": "aura-intercom_mcp_server-1", "description": "Intercom MCP Server", "port": 9000},
    {"name": "aura-chromadb-1", "description": "ChromaDB Vector Database", "port": 8001},
    {"name": "aura-embedding-service-1", "description": "Embedding Service", "port": 8002}
]

def get_container_status(container_name):
    """Get the status of a Docker container"""
    try:
        result = subprocess.run(
            ["docker", "inspect", "--format", "{{.State.Status}}", container_name],
            capture_output=True, text=True, check=True
        )
        return result.stdout.strip()
    except subprocess.CalledProcessError:
        return "not found"

def restart_container(container_name):
    """Restart a Docker container"""
    try:
        logging.info(f"Attempting to restart {container_name}")
        subprocess.run(["docker", "restart", container_name], check=True)
        logging.info(f"Successfully restarted {container_name}")
        return True
    except subprocess.CalledProcessError as e:
        logging.error(f"Failed to restart {container_name}: {str(e)}")
        return False

def check_port_availability(port):
    """Check if a port is responding"""
    try:
        result = subprocess.run(
            ["curl", "-s", "-o", "/dev/null", "-w", "%{http_code}", f"http://localhost:{port}/health"],
            capture_output=True, text=True, timeout=5
        )
        status_code = result.stdout.strip()
        return status_code.startswith("2") or status_code.startswith("3")
    except (subprocess.CalledProcessError, subprocess.TimeoutExpired):
        return False

def monitor_services():
    """Monitor all critical services and restart if needed"""
    logging.info("Starting service monitoring check")
    
    for service in CRITICAL_SERVICES:
        container_name = service["name"]
        status = get_container_status(container_name)
        
        if status != "running":
            logging.warning(f"{container_name} ({service['description']}) is not running (status: {status})")
            restart_container(container_name)
        else:
            # Check port availability for running containers
            port_available = check_port_availability(service["port"])
            if not port_available:
                logging.warning(f"{container_name} is running but port {service['port']} is not responding")
                restart_container(container_name)
            else:
                logging.info(f"{container_name} ({service['description']}) is running properly")
    
    logging.info("Service monitoring check completed")

def main():
    """Main function to run the service monitor"""
    logging.info("Service Monitor started")
    
    while True:
        try:
            monitor_services()
        except Exception as e:
            logging.error(f"Error in monitoring cycle: {str(e)}")
        
        # Wait for the next check (5 minutes)
        time.sleep(300)

if __name__ == "__main__":
    main()
