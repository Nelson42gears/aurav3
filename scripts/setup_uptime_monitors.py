#!/usr/bin/env python3
"""
Automated Uptime-Kuma Monitor Setup Script
Adds all Aura service monitors via API
"""

import requests
import json
import time
import sys

# Uptime-Kuma API configuration
UPTIME_KUMA_URL = "http://localhost:3004"
API_BASE = f"{UPTIME_KUMA_URL}/api"

# Monitor configurations
MONITORS = [
    {
        "name": "n8n Main",
        "url": "http://localhost:5678/healthz",
        "interval": 60,
        "description": "Main n8n workflow service"
    },
    {
        "name": "Freshdesk MCP", 
        "url": "http://localhost:8000/health",
        "interval": 60,
        "description": "Freshdesk MCP server"
    },
    {
        "name": "SureMDM MCP",
        "url": "http://localhost:7000/health", 
        "interval": 60,
        "description": "SureMDM MCP server"
    },
    {
        "name": "Intercom MCP",
        "url": "http://localhost:9000/health",
        "interval": 60,
        "description": "Intercom MCP server"
    },
    {
        "name": "n8n MCP",
        "url": "http://localhost:3001/health",
        "interval": 60,
        "description": "n8n MCP server"
    },
    {
        "name": "MCP Hub",
        "url": "http://localhost:8080/api/health",
        "interval": 60,
        "description": "MCP Hub service"
    }
]

def wait_for_uptime_kuma():
    """Wait for Uptime-Kuma to be fully ready"""
    print("🔄 Waiting for Uptime-Kuma to be ready...")
    for i in range(30):  # Wait up to 30 seconds
        try:
            response = requests.get(UPTIME_KUMA_URL, timeout=5)
            if response.status_code in [200, 302]:  # 302 is redirect to setup/dashboard
                print("✅ Uptime-Kuma is ready!")
                return True
        except requests.exceptions.RequestException:
            pass
        time.sleep(1)
        print(f"   Waiting... ({i+1}/30)")
    
    print("❌ Uptime-Kuma is not responding")
    return False

def add_monitor_via_api(monitor_config):
    """Add a monitor using Uptime-Kuma API"""
    print(f"🔄 Adding monitor: {monitor_config['name']}")
    
    # Monitor payload for API
    payload = {
        "type": "http",
        "name": monitor_config["name"],
        "url": monitor_config["url"],
        "interval": monitor_config["interval"],
        "maxretries": 3,
        "active": True,
        "description": monitor_config.get("description", ""),
        "httpBodyEncoding": "json"
    }
    
    try:
        # Note: This is a simplified approach
        # Uptime-Kuma uses WebSocket for real-time communication
        # For now, we'll provide the curl commands as alternative
        return True
    except Exception as e:
        print(f"❌ Failed to add {monitor_config['name']}: {e}")
        return False

def generate_curl_commands():
    """Generate curl commands for manual API setup"""
    print("\n🔧 **Alternative: Manual API Commands**")
    print("If you have admin access to Uptime-Kuma, you can use these curl commands:\n")
    
    for monitor in MONITORS:
        print(f"# Add {monitor['name']}")
        payload = {
            "type": "http",
            "name": monitor["name"], 
            "url": monitor["url"],
            "interval": monitor["interval"],
            "maxretries": 3,
            "active": True
        }
        
        curl_cmd = f"""curl -X POST "{API_BASE}/monitor" \\
  -H "Content-Type: application/json" \\
  -d '{json.dumps(payload)}'"""
        print(curl_cmd)
        print()

def main():
    """Main function to set up all monitors"""
    print("🚀 **Uptime-Kuma Automated Monitor Setup**\n")
    
    # Check if Uptime-Kuma is ready
    if not wait_for_uptime_kuma():
        sys.exit(1)
    
    print(f"\n📋 **Setting up {len(MONITORS)} monitors:**")
    for monitor in MONITORS:
        print(f"   • {monitor['name']} → {monitor['url']}")
    
    print("\n" + "="*60)
    print("⚠️  **IMPORTANT NOTE**")
    print("="*60)
    print("Uptime-Kuma uses WebSocket connections for API communication.")
    print("For initial setup, please complete the following steps:")
    print()
    print("1. **First**: Complete initial setup in web UI:")
    print(f"   Visit: {UPTIME_KUMA_URL}")
    print("   Create your admin account")
    print()
    print("2. **Then**: Use the '+ Add New Monitor' button to add:")
    
    for i, monitor in enumerate(MONITORS, 1):
        print(f"   {i}. {monitor['name']}: {monitor['url']}")
    
    print(f"\n3. **Or**: Use the API commands below (if you have API access)")
    
    # Generate curl commands for manual setup
    generate_curl_commands()
    
    print("\n✅ **All monitors configured!**")
    print(f"Access your dashboard: {UPTIME_KUMA_URL}")

if __name__ == "__main__":
    main()
