"""
Unified Customer API Endpoints
Provides REST API for unified customer data operations
"""

import asyncio
import json
import logging
from datetime import datetime, timezone
from typing import Dict, List, Optional, Any
from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel, Field
from unified_customer_models import UnifiedCustomerManager, UnifiedCustomer, CustomerJourneyEntry

logger = logging.getLogger(__name__)

# Pydantic models for API
class CustomerSearchRequest(BaseModel):
    query: str = Field(..., description="Search query (email, name, company)")
    platform: Optional[str] = Field(None, description="Filter by platform")

class CustomerSearchResponse(BaseModel):
    customers: List[Dict[str, Any]]
    total_count: int
    query: str

class UnifiedSearchRequest(BaseModel):
    query: str = Field(..., description="Customer identifier (email, phone, name)")
    include_journey: bool = Field(True, description="Include customer journey")

class UnifiedSearchResponse(BaseModel):
    customer: Optional[Dict[str, Any]]
    journey: List[Dict[str, Any]]
    platforms: List[str]
    total_interactions: int

class CustomerJourneyRequest(BaseModel):
    customer_identifier: str = Field(..., description="Customer email, phone, or ID")
    identifier_type: str = Field("email", description="Type of identifier")

class CustomerJourneyResponse(BaseModel):
    customer_profile: Dict[str, Any]
    timeline: List[Dict[str, Any]]
    summary: Dict[str, Any]

class CreateCustomerRequest(BaseModel):
    platform: str = Field(..., description="Platform (freshdesk/intercom)")
    platform_id: str = Field(..., description="Platform-specific customer ID")
    customer_data: Dict[str, Any] = Field(..., description="Customer data")

# Global unified customer manager
unified_manager = None

async def get_unified_manager() -> UnifiedCustomerManager:
    """Dependency to get unified customer manager"""
    global unified_manager
    if not unified_manager:
        db_config = {
            'host': 'postgres',
            'port': 5432,
            'user': 'postgres',
            'password': 'postgres',
            'database': 'aura'
        }
        unified_manager = UnifiedCustomerManager(db_config)
        await unified_manager.initialize()
    return unified_manager

# Create router
router = APIRouter(prefix="/api", tags=["unified-customer"])

@router.post("/unified_search", response_model=UnifiedSearchResponse)
async def unified_search(
    request: UnifiedSearchRequest,
    manager: UnifiedCustomerManager = Depends(get_unified_manager)
):
    """
    Search for unified customer across all platforms
    Returns complete customer profile and journey
    """
    try:
        # Try different identifier types
        customer = None
        for id_type in ["email", "phone", "id"]:
            customer = await manager.get_unified_customer(request.query, id_type)
            if customer:
                break
        
        if not customer:
            # Try fuzzy search
            customers = await manager.search_unified_customers(request.query)
            if customers:
                customer = customers[0]  # Take best match
        
        if not customer:
            return UnifiedSearchResponse(
                customer=None,
                journey=[],
                platforms=[],
                total_interactions=0
            )
        
        # Get customer journey if requested
        journey = []
        platforms = set()
        if request.include_journey:
            journey_entries = await manager.get_customer_journey(customer.id)
            for entry in journey_entries:
                platforms.add(entry.platform)
                journey.append({
                    "id": entry.id,
                    "platform": entry.platform,
                    "interaction_type": entry.interaction_type,
                    "subject": entry.subject,
                    "content": entry.content,
                    "status": entry.status,
                    "priority": entry.priority,
                    "timestamp": entry.timestamp.isoformat() if entry.timestamp else None,
                    "metadata": entry.metadata
                })
        
        # Convert customer to dict
        customer_dict = {
            "id": customer.id,
            "email": customer.email,
            "phone": customer.phone,
            "company_name": customer.company_name,
            "first_name": customer.first_name,
            "last_name": customer.last_name,
            "full_name": customer.full_name,
            "freshdesk_id": customer.freshdesk_id,
            "intercom_id": customer.intercom_id,
            "created_at": customer.created_at.isoformat() if customer.created_at else None,
            "updated_at": customer.updated_at.isoformat() if customer.updated_at else None,
            "last_activity_at": customer.last_activity_at.isoformat() if customer.last_activity_at else None,
            "data_quality_score": customer.data_quality_score,
            "is_verified": customer.is_verified
        }
        
        return UnifiedSearchResponse(
            customer=customer_dict,
            journey=journey,
            platforms=list(platforms),
            total_interactions=len(journey)
        )
        
    except Exception as e:
        logger.error(f"Error in unified search: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/get_customer_journey", response_model=CustomerJourneyResponse)
async def get_customer_journey(
    request: CustomerJourneyRequest,
    manager: UnifiedCustomerManager = Depends(get_unified_manager)
):
    """
    Get complete customer journey timeline across all platforms
    """
    try:
        # Find customer
        customer = await manager.get_unified_customer(
            request.customer_identifier, 
            request.identifier_type
        )
        
        if not customer:
            raise HTTPException(status_code=404, detail="Customer not found")
        
        # Get journey
        journey_entries = await manager.get_customer_journey(customer.id)
        
        # Build timeline
        timeline = []
        platforms = set()
        interaction_types = {}
        
        for entry in journey_entries:
            platforms.add(entry.platform)
            interaction_types[entry.interaction_type] = interaction_types.get(entry.interaction_type, 0) + 1
            
            timeline.append({
                "id": entry.id,
                "platform": entry.platform,
                "interaction_type": entry.interaction_type,
                "subject": entry.subject,
                "content": entry.content,
                "status": entry.status,
                "priority": entry.priority,
                "timestamp": entry.timestamp.isoformat() if entry.timestamp else None,
                "platform_record_id": entry.platform_record_id,
                "metadata": entry.metadata
            })
        
        # Customer profile
        customer_profile = {
            "id": customer.id,
            "email": customer.email,
            "phone": customer.phone,
            "company_name": customer.company_name,
            "full_name": customer.full_name,
            "freshdesk_id": customer.freshdesk_id,
            "intercom_id": customer.intercom_id,
            "platforms": list(platforms),
            "total_interactions": len(timeline),
            "last_activity": customer.last_activity_at.isoformat() if customer.last_activity_at else None
        }
        
        # Summary
        summary = {
            "total_interactions": len(timeline),
            "platforms": list(platforms),
            "interaction_types": interaction_types,
            "first_interaction": timeline[-1]["timestamp"] if timeline else None,
            "last_interaction": timeline[0]["timestamp"] if timeline else None
        }
        
        return CustomerJourneyResponse(
            customer_profile=customer_profile,
            timeline=timeline,
            summary=summary
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting customer journey: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/create_unified_customer")
async def create_unified_customer(
    request: CreateCustomerRequest,
    manager: UnifiedCustomerManager = Depends(get_unified_manager)
):
    """
    Create or update unified customer from platform data
    """
    try:
        unified_customer_id = await manager.create_or_update_unified_customer(
            request.customer_data,
            request.platform,
            request.platform_id
        )
        
        return {
            "unified_customer_id": unified_customer_id,
            "platform": request.platform,
            "platform_id": request.platform_id,
            "status": "success"
        }
        
    except Exception as e:
        logger.error(f"Error creating unified customer: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/search_customers")
async def search_customers(
    query: str,
    manager: UnifiedCustomerManager = Depends(get_unified_manager)
):
    """
    Search unified customers by query
    """
    try:
        customers = await manager.search_unified_customers(query)
        
        results = []
        for customer in customers:
            results.append({
                "id": customer.id,
                "email": customer.email,
                "full_name": customer.full_name,
                "company_name": customer.company_name,
                "platforms": [
                    p for p in ["freshdesk", "intercom"] 
                    if getattr(customer, f"{p}_id")
                ],
                "last_activity": customer.last_activity_at.isoformat() if customer.last_activity_at else None
            })
        
        return {
            "customers": results,
            "total_count": len(results),
            "query": query
        }
        
    except Exception as e:
        logger.error(f"Error searching customers: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/add_journey_entry")
async def add_journey_entry(
    unified_customer_id: str,
    platform: str,
    platform_record_id: str,
    interaction_type: str,
    subject: Optional[str] = None,
    content: Optional[str] = None,
    status: Optional[str] = None,
    priority: Optional[str] = None,
    timestamp: Optional[str] = None,
    metadata: Optional[Dict] = None,
    manager: UnifiedCustomerManager = Depends(get_unified_manager)
):
    """
    Add entry to customer journey timeline
    """
    try:
        # Parse timestamp
        if timestamp:
            parsed_timestamp = datetime.fromisoformat(timestamp.replace('Z', '+00:00'))
        else:
            parsed_timestamp = datetime.now(timezone.utc)
        
        entry = CustomerJourneyEntry(
            unified_customer_id=unified_customer_id,
            platform=platform,
            platform_record_id=platform_record_id,
            interaction_type=interaction_type,
            subject=subject,
            content=content,
            status=status,
            priority=priority,
            timestamp=parsed_timestamp,
            metadata=metadata
        )
        
        entry_id = await manager.add_journey_entry(entry)
        
        return {
            "entry_id": entry_id,
            "unified_customer_id": unified_customer_id,
            "status": "success"
        }
        
    except Exception as e:
        logger.error(f"Error adding journey entry: {e}")
        raise HTTPException(status_code=500, detail=str(e))
