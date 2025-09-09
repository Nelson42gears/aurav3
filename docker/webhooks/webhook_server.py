#!/usr/bin/env python3
"""
Aura Webhook Service
Handles webhooks from Freshdesk and Intercom for real-time data synchronization
"""

import json
import logging
import os
import sys
from datetime import datetime
from typing import Dict, Any

from fastapi import FastAPI, Request, HTTPException, BackgroundTasks
from fastapi.responses import JSONResponse
import uvicorn

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler('/app/logs/webhook_server.log')
    ]
)
logger = logging.getLogger(__name__)

# Initialize FastAPI app
app = FastAPI(
    title="Aura Webhook Service",
    description="Handles webhooks from Freshdesk and Intercom",
    version="1.0.0"
)

# Configuration
class WebhookConfig:
    PORT = int(os.getenv("PORT", 8000))
    FRESHDESK_WEBHOOK_SECRET = os.getenv("FRESHDESK_WEBHOOK_SECRET")
    INTERCOM_WEBHOOK_SECRET = os.getenv("INTERCOM_WEBHOOK_SECRET")
    MCP_SERVER_URL = os.getenv("MCP_SERVER_URL", "http://mcp-server:9000")

# Webhook event storage (in production, use Redis or database)
webhook_events = []

@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {
        "status": "healthy",
        "service": "Aura Webhook Service",
        "version": "1.0.0",
        "timestamp": datetime.now().isoformat(),
        "events_processed": len(webhook_events)
    }

@app.post("/webhook/freshdesk")
async def freshdesk_webhook(request: Request, background_tasks: BackgroundTasks):
    """Handle Freshdesk webhooks"""
    try:
        # Get request body and headers
        body = await request.body()
        headers = request.headers
        
        # Verify webhook signature (if configured)
        if WebhookConfig.FRESHDESK_WEBHOOK_SECRET:
            # TODO: Implement Freshdesk signature verification
            pass
        
        # Parse webhook payload
        try:
            payload = json.loads(body)
        except json.JSONDecodeError:
            raise HTTPException(status_code=400, detail="Invalid JSON payload")
        
        # Extract event information
        event_data = {
            "platform": "freshdesk",
            "timestamp": datetime.now().isoformat(),
            "event_type": headers.get("x-freshdesk-event-type", "unknown"),
            "webhook_id": headers.get("x-freshdesk-webhook-id"),
            "payload": payload
        }
        
        # Process webhook in background
        background_tasks.add_task(process_webhook_event, event_data)
        
        # Log the event
        logger.info(f"📨 Freshdesk webhook received: {event_data['event_type']}")
        
        return JSONResponse(
            status_code=200,
            content={"status": "received", "event_type": event_data["event_type"]}
        )
        
    except Exception as e:
        logger.error(f"❌ Freshdesk webhook error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/webhook/intercom")
async def intercom_webhook(request: Request, background_tasks: BackgroundTasks):
    """Handle Intercom webhooks"""
    try:
        # Get request body and headers
        body = await request.body()
        headers = request.headers
        
        # Verify webhook signature (if configured)
        if WebhookConfig.INTERCOM_WEBHOOK_SECRET:
            # TODO: Implement Intercom signature verification
            pass
        
        # Parse webhook payload
        try:
            payload = json.loads(body)
        except json.JSONDecodeError:
            raise HTTPException(status_code=400, detail="Invalid JSON payload")
        
        # Extract event information
        event_data = {
            "platform": "intercom",
            "timestamp": datetime.now().isoformat(),
            "event_type": payload.get("type", "unknown"),
            "topic": payload.get("topic"),
            "payload": payload
        }
        
        # Process webhook in background
        background_tasks.add_task(process_webhook_event, event_data)
        
        # Log the event
        logger.info(f"📨 Intercom webhook received: {event_data['event_type']}")
        
        return JSONResponse(
            status_code=200,
            content={"status": "received", "event_type": event_data["event_type"]}
        )
        
    except Exception as e:
        logger.error(f"❌ Intercom webhook error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/webhook/events")
async def get_recent_events(limit: int = 50):
    """Get recent webhook events"""
    return {
        "total_events": len(webhook_events),
        "recent_events": webhook_events[-limit:] if webhook_events else [],
        "timestamp": datetime.now().isoformat()
    }

async def process_webhook_event(event_data: Dict[str, Any]):
    """Process webhook event in background"""
    try:
        # Store event
        webhook_events.append(event_data)
        
        # Keep only last 1000 events in memory
        if len(webhook_events) > 1000:
            webhook_events.pop(0)
        
        # Process based on event type
        platform = event_data["platform"]
        event_type = event_data["event_type"]
        
        if platform == "freshdesk":
            await process_freshdesk_event(event_data)
        elif platform == "intercom":
            await process_intercom_event(event_data)
        
        logger.info(f"✅ Processed {platform} webhook: {event_type}")
        
    except Exception as e:
        logger.error(f"❌ Webhook processing error: {e}")

async def process_freshdesk_event(event_data: Dict[str, Any]):
    """Process Freshdesk-specific webhook events"""
    event_type = event_data["event_type"]
    payload = event_data["payload"]
    
    # Handle different Freshdesk events
    if event_type in ["ticket_created", "ticket_updated"]:
        # Extract ticket information
        ticket_data = payload.get("freshdesk_webhook", {})
        logger.info(f"🎫 Freshdesk ticket event: {ticket_data.get('ticket_id')}")
        
        # TODO: Update MCP server with ticket changes
        # await notify_mcp_server("freshdesk_ticket_updated", ticket_data)
        
    elif event_type in ["contact_created", "contact_updated"]:
        # Extract contact information
        contact_data = payload.get("freshdesk_webhook", {})
        logger.info(f"👤 Freshdesk contact event: {contact_data.get('contact_id')}")
        
        # TODO: Update MCP server with contact changes
        # await notify_mcp_server("freshdesk_contact_updated", contact_data)

async def process_intercom_event(event_data: Dict[str, Any]):
    """Process Intercom-specific webhook events"""
    event_type = event_data["event_type"]
    topic = event_data.get("topic")
    payload = event_data["payload"]
    
    # Handle different Intercom events
    if topic == "conversation.admin.assigned":
        # Extract conversation information
        conversation = payload.get("data", {}).get("item", {})
        logger.info(f"💬 Intercom conversation assigned: {conversation.get('id')}")
        
        # TODO: Update MCP server with conversation changes
        # await notify_mcp_server("intercom_conversation_assigned", conversation)
        
    elif topic in ["contact.created", "contact.changed"]:
        # Extract contact information
        contact = payload.get("data", {}).get("item", {})
        logger.info(f"👤 Intercom contact event: {contact.get('id')}")
        
        # TODO: Update MCP server with contact changes
        # await notify_mcp_server("intercom_contact_updated", contact)

async def notify_mcp_server(event_type: str, data: Dict[str, Any]):
    """Notify MCP server of webhook events (for future implementation)"""
    # TODO: Implement MCP server notification
    # This would send real-time updates to the MCP server
    # for cache invalidation and data synchronization
    pass

if __name__ == "__main__":
    # Ensure logs directory exists
    os.makedirs("/app/logs", exist_ok=True)
    
    logger.info("🚀 Starting Aura Webhook Service...")
    logger.info(f"📡 Port: {WebhookConfig.PORT}")
    logger.info(f"🔒 Freshdesk webhook secret: {'configured' if WebhookConfig.FRESHDESK_WEBHOOK_SECRET else 'not configured'}")
    logger.info(f"🔒 Intercom webhook secret: {'configured' if WebhookConfig.INTERCOM_WEBHOOK_SECRET else 'not configured'}")
    
    uvicorn.run(
        "webhook_server:app",
        host="0.0.0.0",
        port=WebhookConfig.PORT,
        log_level="info",
        access_log=True
    )