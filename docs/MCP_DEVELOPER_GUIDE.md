# 🧑‍💻 MCP Developer Guide - Protocol 2025-06-18

## 📋 **MCP Protocol Overview**

The Model Context Protocol (MCP) is a standardized way for AI systems to connect with data sources and tools. Our implementation follows the **2025-06-18 specification** using **JSON-RPC 2.0 over HTTP**.

### **Key Protocol Features**
- **Transport**: HTTP with JSON-RPC 2.0 
- **Version**: 2025-06-18
- **No Basic HTTP**: All communication uses MCP protocol
- **Session Lifecycle**: Initialize → Discover → Operate → Shutdown
- **Dynamic Discovery**: Tools and resources discovered at runtime

## 🔌 **MCP Server Integration**

### **1. Initialize Connection**
```bash
curl -X POST http://localhost:8000/ \
  -H "Content-Type: application/json" \
  -d '{
    "jsonrpc": "2.0",
    "method": "initialize", 
    "params": {
      "protocolVersion": "2025-06-18",
      "capabilities": {"tools": {}, "resources": {}}
    },
    "id": 1
  }'
```

### **2. List Available Tools**
```bash
curl -X POST http://localhost:8000/ \
  -H "Content-Type: application/json" \
  -d '{
    "jsonrpc": "2.0",
    "method": "tools/list",
    "params": {},
    "id": 2
  }'
```

### **3. List Available Resources**
```bash
curl -X POST http://localhost:8000/ \
  -H "Content-Type: application/json" \
  -d '{
    "jsonrpc": "2.0",
    "method": "resources/list", 
    "params": {},
    "id": 3
  }'
```

### **4. Call a Tool**
```bash
curl -X POST http://localhost:8000/ \
  -H "Content-Type: application/json" \
  -d '{
    "jsonrpc": "2.0",
    "method": "tools/call",
    "params": {
      "name": "search_tickets",
      "arguments": {"query": "billing", "limit": 10}
    },
    "id": 4
  }'
```

### **5. Read a Resource**
```bash
curl -X POST http://localhost:8000/ \
  -H "Content-Type: application/json" \
  -d '{
    "jsonrpc": "2.0", 
    "method": "resources/read",
    "params": {"uri": "freshdesk://tickets/overview"},
    "id": 5
  }'
```

## 🏗️ **MCP Server Details**

### **Freshdesk MCP Server (Port 8000)**
- **5 Tools**: `search_tickets`, `create_ticket`, `get_ticket`, `update_ticket`, `list_recent_tickets`
- **2 Resources**: Available via resources/list endpoint
- **Health**: http://localhost:8000/health

### **Intercom MCP Server (Port 9000)**  
- **6 Tools**: `search_conversations`, `get_conversation`, `reply_to_conversation`, `list_users`, `get_user`, `create_or_update_user`
- **3 Resources**: Available via resources/list endpoint
- **Health**: http://localhost:9000/health

### **SureMDM MCP Server (Port 7000)**
- **6 Tools**: `list_devices`, `get_device`, `send_device_command`, `list_groups`, `get_device_location`, `install_app`
- **3 Resources**: Available via resources/list endpoint
- **Health**: http://localhost:7000/health

### **n8n MCP Server (Port 3001)**
- **7 Tools**: `list_workflows`, `get_workflow`, `execute_workflow`, `list_executions`, `get_execution`, `toggle_workflow`, `create_workflow`
- **3 Resources**: Available via resources/list endpoint
- **Health**: http://localhost:3001/health

### **Summary**
- **Total Tools**: 24 across all MCP servers
- **Total Resources**: 11 across all MCP servers

## 🔧 **Development Workflow**

### **1. Adding New MCP Servers**
```bash
# Create new server directory
mkdir -p docker/mcp-servers/new-service

# Copy MCP base classes
cp -r docker/shared/mcp-base/* docker/mcp-servers/new-service/

# Implement server.py with MCPServerBase
# Add to docker-compose.yml with fixed port
# Deploy: docker-compose -f docker/docker-compose.yml up -d new-service
```

### **2. Testing MCP Protocol Compliance**
```bash
# Test initialization
curl -s http://localhost:PORT/ -H "Content-Type: application/json" \
-d '{"jsonrpc": "2.0", "method": "initialize", "params": {"protocolVersion": "2025-06-18", "capabilities": {"tools": {}, "resources": {}}}, "id": 1}'

# Verify JSON-RPC 2.0 response structure
# Check protocolVersion: "2025-06-18"
# Validate capabilities object
```

### **3. Debugging MCP Services**
```bash
# Check service logs
docker logs aura_SERVICE_NAME_production

# Check health status  
curl http://localhost:PORT/health

# Inspect container
docker exec -it aura_SERVICE_NAME_production /bin/bash
```

## 🚨 **Critical Rules**

### **NEVER CHANGE PORTS**
The following ports are **FIXED** and must **NEVER** be changed:
- Freshdesk MCP: `8000`
- SureMDM MCP: `7000` 
- Intercom MCP: `9000`
- n8n MCP: `3001`
- MCP Hub: `8080`
- MCP Dashboard: `3000`
- n8n Main: `5678`
- PostgreSQL: `5433`

### **Docker Container Naming**
All containers use prefix: `aura_` + `service_name` + `_production`

### **MCP Protocol Requirements**
- ✅ **MUST**: Use JSON-RPC 2.0 over HTTP
- ✅ **MUST**: Implement protocol version "2025-06-18"
- ✅ **MUST**: Support initialize, tools/list, resources/list, tools/call, resources/read
- ❌ **NEVER**: Use basic HTTP requests without JSON-RPC wrapper
- ❌ **NEVER**: Skip protocol version negotiation

## 📊 **Monitoring & Maintenance**

### **Health Checks**
```bash
# Check all services
docker ps --format "table {{.Names}}\t{{.Status}}\t{{.Ports}}"

# Individual health endpoints
curl http://localhost:8000/health  # Freshdesk
curl http://localhost:9000/health  # Intercom  
curl http://localhost:7000/health  # SureMDM
curl http://localhost:3001/health  # n8n MCP
```

### **Log Analysis**
```bash
# View all logs
docker-compose -f docker/docker-compose.yml logs

# Follow specific service
docker logs -f aura_freshdesk_mcp_production
```

### **Performance Monitoring**
```bash
# Resource usage
docker stats

# Database connections
docker exec aura_postgres_production psql -U aura_user -d aura_mcp -c "SELECT * FROM pg_stat_activity;"
```

---

**📚 For additional information, see the main README.md and /docs/ directory.**
