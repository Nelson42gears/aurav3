#!/usr/bin/env python3
"""
Freshdesk Webhook Setup Script
Automatically configures Freshdesk to send webhooks to n8n
"""

import requests
import json

# Freshdesk Configuration
FRESHDESK_DOMAIN = "https://42gears.freshdesk.com"
FRESHDESK_API_KEY = "fn0AhlgurAXdgn4b"  # From your docker-compose.yml

# n8n Webhook Configuration
N8N_WEBHOOK_URL = "http://localhost:5678/webhook/freshdesk-webhook"
# For production, you'd use your public URL: "https://your-domain.com:5678/webhook/freshdesk-webhook"

def create_freshdesk_webhook():
    """Create webhook in Freshdesk to send ticket events to n8n"""
    
    webhook_config = {
        "webhook": {
            "webhook_url": N8N_WEBHOOK_URL,
            "events": ["ticket_create"],  # Trigger on new tickets
            "encoding": "json",
            "custom_headers": {
                "Content-Type": "application/json",
                "User-Agent": "n8n-freshdesk-integration"
            }
        }
    }
    
    headers = {
        "Content-Type": "application/json"
    }
    
    try:
        print(f"Creating webhook in Freshdesk...")
        print(f"Webhook URL: {N8N_WEBHOOK_URL}")
        print(f"Freshdesk Domain: {FRESHDESK_DOMAIN}")
        
        response = requests.post(
            f"{FRESHDESK_DOMAIN}/api/v2/webhooks",
            json=webhook_config,
            auth=(FRESHDESK_API_KEY, "x"),
            headers=headers,
            timeout=30
        )
        
        if response.status_code == 201:
            webhook_data = response.json()
            print("✅ Webhook created successfully!")
            print(f"Webhook ID: {webhook_data.get('id')}")
            print(f"Webhook URL: {webhook_data.get('webhook_url')}")
            return webhook_data
        else:
            print(f"❌ Failed to create webhook: {response.status_code}")
            print(f"Response: {response.text}")
            return None
            
    except Exception as e:
        print(f"❌ Error creating webhook: {str(e)}")
        return None

def list_existing_webhooks():
    """List existing webhooks in Freshdesk"""
    try:
        response = requests.get(
            f"{FRESHDESK_DOMAIN}/api/v2/webhooks",
            auth=(FRESHDESK_API_KEY, "x"),
            timeout=30
        )
        
        if response.status_code == 200:
            webhooks = response.json()
            print(f"📋 Found {len(webhooks)} existing webhooks:")
            for webhook in webhooks:
                print(f"  - ID: {webhook.get('id')}, URL: {webhook.get('webhook_url')}")
            return webhooks
        else:
            print(f"❌ Failed to list webhooks: {response.status_code}")
            return []
            
    except Exception as e:
        print(f"❌ Error listing webhooks: {str(e)}")
        return []

def main():
    print("🚀 Freshdesk Webhook Setup for n8n Integration")
    print("=" * 50)
    
    # First, list existing webhooks
    existing_webhooks = list_existing_webhooks()
    
    # Check if webhook already exists
    n8n_webhook_exists = any(
        webhook.get('webhook_url') == N8N_WEBHOOK_URL 
        for webhook in existing_webhooks
    )
    
    if n8n_webhook_exists:
        print("✅ n8n webhook already exists!")
    else:
        print("📝 Creating new webhook...")
        create_freshdesk_webhook()
    
    print("\n🎯 Next Steps:")
    print("1. Ensure n8n workflow is active")
    print("2. Test by creating a new ticket in Freshdesk")
    print("3. Check n8n executions for webhook events")
    print(f"4. Webhook endpoint: {N8N_WEBHOOK_URL}")

if __name__ == "__main__":
    main()
