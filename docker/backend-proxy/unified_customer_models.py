"""
Unified Customer Data Models
Handles cross-platform customer unification, deduplication, and journey reconstruction
"""

import asyncio
import asyncpg
import json
import logging
import httpx
from datetime import datetime, timezone
from typing import Dict, List, Optional, Tuple, Any
from dataclasses import dataclass
from difflib import SequenceMatcher
import re

logger = logging.getLogger(__name__)

@dataclass
class UnifiedCustomer:
    """Unified customer view combining real-time data from multiple platforms"""
    id: Optional[str] = None
    email: Optional[str] = None
    phone: Optional[str] = None
    company_name: Optional[str] = None
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    full_name: Optional[str] = None
    freshdesk_data: Optional[Dict] = None
    intercom_data: Optional[Dict] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    last_activity_at: Optional[datetime] = None
    data_quality_score: float = 1.0
    is_verified: bool = False

@dataclass
class CustomerMapping:
    """Maps unified customers to platform-specific records"""
    id: Optional[str] = None
    unified_customer_id: str = ""
    platform: str = ""
    platform_customer_id: str = ""
    matching_confidence: float = 1.0
    matching_method: str = ""
    created_at: Optional[datetime] = None

@dataclass
class CustomerJourneyEntry:
    """Individual entry in customer journey timeline"""
    id: Optional[str] = None
    unified_customer_id: str = ""
    platform: str = ""
    platform_record_id: str = ""
    interaction_type: str = ""
    subject: Optional[str] = None
    content: Optional[str] = None
    status: Optional[str] = None
    priority: Optional[str] = None
    timestamp: datetime = None
    created_at: Optional[datetime] = None
    metadata: Optional[Dict] = None

class UnifiedCustomerManager:
    """Manages unified customer data operations using MCP calls for real-time data"""
    
    def __init__(self, db_config: Dict[str, str], mcp_server_url: str = "http://localhost:9000"):
        self.db_config = db_config
        self.pool = None
        self.mcp_server_url = mcp_server_url
        self.http_client = None
    
    async def initialize(self):
        """Initialize database connection pool and HTTP client for MCP calls"""
        try:
            self.pool = await asyncpg.create_pool(
                host=self.db_config['host'],
                port=self.db_config['port'],
                user=self.db_config['user'],
                password=self.db_config['password'],
                database=self.db_config['database'],
                min_size=2,
                max_size=10
            )
            self.http_client = httpx.AsyncClient(timeout=30.0)
            logger.info("Unified customer manager initialized with MCP integration")
        except Exception as e:
            logger.error(f"Failed to initialize unified customer manager: {e}")
            raise
    
    async def close(self):
        """Close database connection pool and HTTP client"""
        if self.pool:
            await self.pool.close()
        if self.http_client:
            await self.http_client.aclose()
    
    def _calculate_matching_confidence(self, customer1: Dict, customer2: Dict, method: str) -> float:
        """Calculate confidence score for customer matching"""
        if method == "email":
            return 1.0 if customer1.get("email", "").lower() == customer2.get("email", "").lower() else 0.0
        
        elif method == "phone":
            phone1 = re.sub(r'[^\d]', '', customer1.get("phone", ""))
            phone2 = re.sub(r'[^\d]', '', customer2.get("phone", ""))
            return 1.0 if phone1 and phone2 and phone1 == phone2 else 0.0
        
        elif method == "fuzzy":
            # Fuzzy matching based on name and company similarity
            name1 = f"{customer1.get('first_name', '')} {customer1.get('last_name', '')}".strip()
            name2 = f"{customer2.get('first_name', '')} {customer2.get('last_name', '')}".strip()
            company1 = customer1.get("company_name", "").lower().strip()
            company2 = customer2.get("company_name", "").lower().strip()
            
            name_similarity = SequenceMatcher(None, name1.lower(), name2.lower()).ratio()
            company_similarity = SequenceMatcher(None, company1, company2).ratio() if company1 and company2 else 0
            
            # Weighted average: name 60%, company 40%
            return (name_similarity * 0.6 + company_similarity * 0.4)
        
        return 0.0
    
    async def _call_mcp_tool(self, tool_name: str, arguments: Dict) -> Optional[Dict]:
        """Make MCP tool call to get real-time platform data"""
        try:
            payload = {
                "jsonrpc": "2.0",
                "id": 1,
                "method": "tools/call",
                "params": {
                    "name": tool_name,
                    "arguments": arguments
                }
            }
            
            response = await self.http_client.post(
                f"{self.mcp_server_url}/mcp",
                json=payload,
                headers={"Content-Type": "application/json"}
            )
            
            if response.status_code == 200:
                result = response.json()
                if "result" in result and "content" in result["result"]:
                    content = result["result"]["content"][0]["text"]
                    return json.loads(content) if isinstance(content, str) else content
            
            logger.warning(f"MCP call failed for {tool_name}: {response.status_code}")
            return None
            
        except Exception as e:
            logger.error(f"Error calling MCP tool {tool_name}: {e}")
            return None
    
    async def get_freshdesk_customer(self, email: str) -> Optional[Dict]:
        """Get customer data from Freshdesk via MCP"""
        return await self._call_mcp_tool("search_contacts", {"email": email})
    
    async def get_intercom_customer(self, email: str) -> Optional[Dict]:
        """Get customer data from Intercom via MCP"""
        return await self._call_mcp_tool("search_contacts", {"email": email})
    
    async def get_unified_customer_by_email(self, email: str) -> Optional[UnifiedCustomer]:
        """Get unified customer view with real-time platform data via MCP"""
        try:
            # Get real-time data from both platforms via MCP
            freshdesk_data = await self.get_freshdesk_customer(email)
            intercom_data = await self.get_intercom_customer(email)
            
            # Check if we have existing mapping
            unified_id = None
            async with self.pool.acquire() as conn:
                mapping = await conn.fetchrow(
                    "SELECT unified_customer_id FROM customer_mappings WHERE platform_customer_id = $1",
                    email.lower()
                )
                if mapping:
                    unified_id = mapping['unified_customer_id']
            
            # Create unified view from real-time data
            if freshdesk_data or intercom_data:
                return UnifiedCustomer(
                    id=unified_id,
                    email=email,
                    freshdesk_data=freshdesk_data,
                    intercom_data=intercom_data,
                    phone=freshdesk_data.get('phone') if freshdesk_data else intercom_data.get('phone') if intercom_data else None,
                    company_name=freshdesk_data.get('company_name') if freshdesk_data else intercom_data.get('company_name') if intercom_data else None,
                    first_name=freshdesk_data.get('name', '').split()[0] if freshdesk_data and freshdesk_data.get('name') else intercom_data.get('name', '').split()[0] if intercom_data and intercom_data.get('name') else None,
                    updated_at=datetime.now(timezone.utc)
                )
            
            return None
            
        except Exception as e:
            logger.error(f"Error getting unified customer for {email}: {e}")
            return None

    async def find_potential_matches(self, customer_data: Dict) -> List[Tuple[UnifiedCustomer, str, float]]:
        """Find potential matching customers using real-time MCP data"""
        matches = []
        
        # Check email match via real-time data
        if customer_data.get("email"):
            unified_customer = await self.get_unified_customer_by_email(customer_data["email"])
            if unified_customer:
                confidence = 1.0  # Exact email match
                matches.append((unified_customer, "email", confidence))
        
        # Sort by confidence descending
        return sorted(matches, key=lambda x: x[2], reverse=True)
    
    async def create_or_update_unified_customer(self, customer_data: Dict, platform: str, platform_id: str) -> str:
        """Create new unified customer or update existing one"""
        
        # Find potential matches
        matches = await self.find_potential_matches(customer_data)
        
        async with self.pool.acquire() as conn:
            async with conn.transaction():
                if matches and matches[0][2] > 0.8:  # High confidence match
                    # Update existing customer
                    unified_customer, method, confidence = matches[0]
                    
                    # Merge data (prefer non-null values)
                    update_data = {}
                    for field in ['email', 'phone', 'company_name', 'first_name', 'last_name']:
                        if customer_data.get(field) and not getattr(unified_customer, field):
                            update_data[field] = customer_data[field]
                    
                    # Update platform-specific ID
                    if platform == "freshdesk":
                        update_data['freshdesk_id'] = platform_id
                    elif platform == "intercom":
                        update_data['intercom_id'] = platform_id
                    
                    update_data['last_activity_at'] = datetime.now(timezone.utc)
                    
                    if update_data:
                        set_clause = ", ".join([f"{k} = ${i+2}" for i, k in enumerate(update_data.keys())])
                        query = f"UPDATE unified_customers SET {set_clause} WHERE id = $1"
                        await conn.execute(query, unified_customer.id, *update_data.values())
                    
                    unified_customer_id = unified_customer.id
                    
                    # Create or update mapping
                    await conn.execute("""
                        INSERT INTO customer_mappings (unified_customer_id, platform, platform_customer_id, matching_confidence, matching_method)
                        VALUES ($1, $2, $3, $4, $5)
                        ON CONFLICT (platform, platform_customer_id) 
                        DO UPDATE SET matching_confidence = $4, matching_method = $5
                    """, unified_customer_id, platform, platform_id, confidence, method)
                    
                else:
                    # Create new unified customer
                    full_name = f"{customer_data.get('first_name', '')} {customer_data.get('last_name', '')}".strip()
                    
                    platform_fields = {}
                    if platform == "freshdesk":
                        platform_fields['freshdesk_id'] = platform_id
                    elif platform == "intercom":
                        platform_fields['intercom_id'] = platform_id
                    
                    unified_customer_id = await conn.fetchval("""
                        INSERT INTO unified_customers (
                            email, phone, company_name, first_name, last_name, full_name,
                            freshdesk_id, intercom_id, last_activity_at
                        ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9)
                        RETURNING id
                    """, 
                        customer_data.get('email'),
                        customer_data.get('phone'),
                        customer_data.get('company_name'),
                        customer_data.get('first_name'),
                        customer_data.get('last_name'),
                        full_name,
                        platform_fields.get('freshdesk_id'),
                        platform_fields.get('intercom_id'),
                        datetime.now(timezone.utc)
                    )
                    
                    # Create mapping
                    await conn.execute("""
                        INSERT INTO customer_mappings (unified_customer_id, platform, platform_customer_id, matching_confidence, matching_method)
                        VALUES ($1, $2, $3, $4, $5)
                    """, unified_customer_id, platform, platform_id, 1.0, "exact")
                
                logger.info(f"Unified customer {unified_customer_id} created/updated for {platform}:{platform_id}")
                return unified_customer_id
    
    async def get_unified_customer(self, identifier: str, identifier_type: str = "email") -> Optional[UnifiedCustomer]:
        """Get unified customer by various identifiers"""
        async with self.pool.acquire() as conn:
            if identifier_type == "email":
                result = await conn.fetchrow(
                    "SELECT * FROM unified_customers WHERE email = $1",
                    identifier.lower()
                )
            elif identifier_type == "phone":
                phone_clean = re.sub(r'[^\d]', '', identifier)
                result = await conn.fetchrow(
                    "SELECT * FROM unified_customers WHERE phone LIKE $1",
                    f"%{phone_clean}%"
                )
            elif identifier_type == "id":
                result = await conn.fetchrow(
                    "SELECT * FROM unified_customers WHERE id = $1",
                    identifier
                )
            else:
                return None
            
            if result:
                return UnifiedCustomer(**dict(result))
            return None
    
    async def get_customer_journey(self, unified_customer_id: str) -> List[CustomerJourneyEntry]:
        """Get complete customer journey timeline"""
        async with self.pool.acquire() as conn:
            results = await conn.fetch("""
                SELECT * FROM unified_journey 
                WHERE unified_customer_id = $1 
                ORDER BY timestamp DESC
            """, unified_customer_id)
            
            journey = []
            for result in results:
                entry = CustomerJourneyEntry(**dict(result))
                journey.append(entry)
            
            return journey
    
    async def add_journey_entry(self, entry: CustomerJourneyEntry) -> str:
        """Add entry to customer journey"""
        async with self.pool.acquire() as conn:
            entry_id = await conn.fetchval("""
                INSERT INTO unified_journey (
                    unified_customer_id, platform, platform_record_id, interaction_type,
                    subject, content, status, priority, timestamp, metadata
                ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10)
                RETURNING id
            """, 
                entry.unified_customer_id, entry.platform, entry.platform_record_id,
                entry.interaction_type, entry.subject, entry.content, entry.status,
                entry.priority, entry.timestamp, json.dumps(entry.metadata) if entry.metadata else None
            )
            
            logger.info(f"Journey entry {entry_id} added for customer {entry.unified_customer_id}")
            return entry_id
    
    async def search_unified_customers(self, query: str) -> List[UnifiedCustomer]:
        """Search unified customers by various criteria"""
        async with self.pool.acquire() as conn:
            # Search by email, name, company
            results = await conn.fetch("""
                SELECT * FROM unified_customers 
                WHERE email ILIKE $1 
                   OR full_name ILIKE $1 
                   OR company_name ILIKE $1
                   OR first_name ILIKE $1
                   OR last_name ILIKE $1
                ORDER BY updated_at DESC
                LIMIT 50
            """, f"%{query}%")
            
            customers = []
            for result in results:
                customers.append(UnifiedCustomer(**dict(result)))
            
            return customers
