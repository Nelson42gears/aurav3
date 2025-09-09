# 🚀 Aura – Unified MCP System (HTTP REST, Standard MCP)

Production-grade Unified MCP system exposing Freshdesk, Intercom, and Unified tools over Standard MCP HTTP endpoints, bridged by a Backend Proxy and a React client for real-time interaction.

This repository hosts the end-to-end stack: React Client, Backend Proxy, MCP Servers, n8n MCP Server, and infra services (PostgreSQL, Redis) – all with fixed ports and strict security controls.

---

## 📌 Project Status (2025-09-09)

- Standard MCP HTTP integration is live. The Backend Proxy now communicates with MCP servers via REST (`/tools`, `/tools/call`) instead of SSE.
- Advanced prompting + semantic tool selection is enabled (Gemini-based), with robust parameter extraction and error handling.
- Tool inventory: 196 tools loaded (Freshdesk, Intercom, n8n, utilities) and callable through the proxy.
- Security hardening in place:
  - GitHub Push Protection compliant. Historical secret was purged and token rotated.
  - `.gitignore` updated to exclude local tooling artifacts (`bfg.jar`, `sensitive.txt`).
  - Pre-commit secret scanning configured via `detect-secrets`.

See sections below for architecture, ports, health checks, and usage. Notes that mention SSE are legacy; use the HTTP REST guidance in this document.

## 🎯 Current Focus

✅ Standard MCP HTTP REST integration  
✅ Backend Proxy bridging client HTTP ⇄ MCP HTTP  
✅ React Client with real-time updates  
✅ Fixed Port Configuration (do not change)

## 🏗️ **MCP ARCHITECTURE**

### Fixed Port Configuration (Never Change)
| Service | Port | Purpose |
|---------|------|---------|
| React Client | `9200` | Web UI (Nginx) |
| Backend Proxy | `9100` | HTTP API bridge to MCP (HTTP REST) |
| Unified MCP Server | `9000` | Standard MCP HTTP (`/tools`, `/tools/call`) |
| n8n MCP Server | `3001` | n8n workflow integration |
| n8n (Main App) | `5678` | n8n web UI & workflow engine |
| PostgreSQL | `5432` | Data persistence |
| Redis | `6379` | Caching & sessions |
| (Policy) Freshdesk MCP Server | `8000` | Reserved per policy |
| (Policy) SureMDM MCP Server | `7000` | Reserved per policy |

### Core Features
- Unified MCP tools (Freshdesk, Intercom, utilities) exposed via Standard MCP HTTP
- Backend Proxy translates HTTP requests from UI to MCP HTTP tool calls
- Real-time React client with live updates
- Health endpoints for infra and detailed MCP state
- Dockerized with strict fixed ports and health checks

---

## 🔁 Unified MCP Flow (Current)

1) React Client (`9200`) → Backend Proxy HTTP (`9100`)  
2) Backend Proxy → MCP Servers HTTP REST (`/tools`, `/tools/call`)  
3) MCP Servers → Platform Adapters (Freshdesk/Intercom) → External APIs  
4) Responses stream back through the same chain to the UI

Health model:  
- Basic: `GET http://localhost:9100/health` → `{ "status": "ok" }`  
- Detailed: `GET http://localhost:9100/api/health` → adapters, totals, rate limits

MCP transport:  
- Standard HTTP REST: `/tools` (list), `/tools/call` (execute)

---

## 🧪 Quick Demo (Safe)

Show running services:
```bash
docker compose ps
```

Health checks:
```bash
curl -s http://localhost:9100/health
curl -s http://localhost:9100/api/health
```

List tools via Backend Proxy (source of truth):
```bash
curl -s http://localhost:9100/api/tools | jq '.tools | length'
```

---

## 🧩 Backend Proxy API (HTTP → MCP HTTP)

- __List tools__: `GET http://localhost:9100/api/tools`
  - Returns the currently registered MCP tools as seen by the proxy (source of truth for names)
- __Execute tool__: `POST http://localhost:9100/api/execute`
  - Body:
    ```json
    {
      "tool": "freshdesk_get_ticket",
      "args": { "ticket_id": 123 }
    }
    ```
- __Health__:
  - Basic: `GET /health` → `{ "status": "ok" }`
  - Detailed: `GET /api/health` → server, adapters, totals, rate limits

Notes:
- The proxy maintains a single SSE session to the Unified MCP Server at `http://mcp-unified-server:9000/sse/` (inside Docker) and `http://localhost:9000/sse/` (host).
- Always verify tool names with `/api/tools` before invoking.

---

## 🏷️ Tool Naming (UI → Proxy → MCP)

- __Exact match required__: The tool name sent to `/api/execute` must exactly match the MCP tool name registered on the server.
- __Common prefixes__: Tools are registered with prefixes like `freshdesk_...`, `intercom_...`; unified utilities are plain (e.g., `health_check`, `list_platform_tools`).
- __Do NOT add extra prefixes__: Avoid client-side prefixes like `tools_` or renaming (e.g., `fd_`) – they cause "Unknown tool" errors.
- __Verify before use__: Call `GET /api/tools` and copy the exact string.

Examples:
- UI selects "freshdesk_get_ticket" → Proxy forwards `freshdesk_get_ticket` → MCP executes Freshdesk adapter.
- UI selects "intercom_list_conversations" → Proxy forwards `intercom_list_conversations`.

If you see `Unknown tool`:
- Compare the requested name with the `/api/tools` list.
- Ensure no hidden whitespace or case differences.
- Confirm you are hitting the proxy (9100), not the MCP server directly.

---

## 🛠️ Troubleshooting MCP SSE

- __SSE endpoint__: `curl -i --max-time 2 http://localhost:9000/sse/` should return `200` and `text/event-stream`.
- __Proxy health__: `GET http://localhost:9100/health` → `{ "status": "ok" }`.
- __Detailed health__: `GET http://localhost:9100/api/health` → check `total_tools` and adapter statuses.
- __List tools__: `GET http://localhost:9100/api/tools` → verify tool names available to the proxy.
- __Container logs__: Inspect backend proxy logs for lines like "SSE connection established" and tool call traces.
- __Process isolation caution__: Validations from ad-hoc Python executions (e.g., inside containers) won’t see the initialized adapters from the main MCP process; always test via the proxy.


## 🚀 **QUICK START**

### Prerequisites
- Docker 20.10.0 or higher
- Docker Compose 2.39.2 or higher
- 8GB RAM minimum (16GB recommended)
- 20GB free disk space

### 1. **Deploy All MCP Services**
```bash
cd /home/nelson/nebula/Aura
docker-compose -f docker/docker-compose.yml up -d
```

### 2. **Verify All Services Are Healthy**
```bash
docker ps --format "table {{.Names}}\t{{.Status}}\t{{.Ports}}"
```

### 3. **Access MCP Dashboard**
- **MCP Dashboard**: http://localhost:3000
- **n8n Interface**: http://localhost:5678
- **MCP Hub API**: http://localhost:8080

### 4. **Test MCP Protocol Compliance**
```bash
# Test Freshdesk MCP Server
curl -s http://localhost:8000/ -H "Content-Type: application/json" \
-d '{"jsonrpc": "2.0", "method": "initialize", "params": {"protocolVersion": "2025-06-18", "capabilities": {"tools": {}, "resources": {}}}, "id": 1}'

# Test all other servers on ports 7000, 9000, 3001
```

## 🏗️ Project Structure

```
Aura/
├── docker-compose.yml           # Main Docker Compose configuration
├── .env                         # Environment variables (not in git)
├── requirements.txt             # Python dependencies
├── init-n8n.sh                # n8n initialization script
├── docker/
│   ├── mcp-server/             # MCP Server implementations
│   │   ├── freshdesk/          # Freshdesk MCP server
│   │   │   ├── app.py          # Main server application
│   │   │   ├── config.py       # Configuration management
│   │   │   ├── rate_limiter.py # API rate limiting
│   │   │   ├── validators.py   # Input validation
│   │   │   ├── tests/          # Test suite
│   │   │   └── scripts/        # Data analysis scripts
│   │   ├── intercom/           # Intercom MCP server
│   │   │   ├── app.py          # Main server application
│   │   │   ├── api_handlers.py # API request handlers
│   │   │   ├── auth.py         # Authentication module
│   │   │   ├── tests/          # Test suite
│   │   │   └── docs/           # Documentation
│   │   └── n8n/               # n8n workflow server
│   │       ├── server.js       # Express server
│   │       ├── controllers/    # Route controllers
│   │       └── services/       # Business logic
│   └── postgres/              # PostgreSQL configuration
│       └── init/              # Database initialization
├── docs/                      # Project documentation
│   ├── development_workflow.md
│   └── workflows/             # Workflow documentation
└── n8n_backup_*.tar.gz       # n8n workflow backups
```

## 🚀 Getting Started

### 1. Environment Setup

Create environment files for each MCP server:

```bash
# Freshdesk MCP Server
cp docker/mcp-server/freshdesk/.env.example docker/mcp-server/freshdesk/.env

# Intercom MCP Server  
cp docker/mcp-server/intercom/.env.example docker/mcp-server/intercom/.env
```

Update the environment files with your API credentials:
- Freshdesk: API key and domain
- Intercom: Access token
- Database: Connection strings

### 2. Install Dependencies

```bash
# Install Python dependencies for MCP servers
cd docker/mcp-server/freshdesk && pip install -r requirements.txt
cd ../intercom && pip install -r requirements.txt

# Install Node.js dependencies for n8n server
cd ../n8n && npm install
```

### 3. Start Services

```bash
# Start individual MCP servers
cd docker/mcp-server/freshdesk && python app.py  # Port 8000
cd docker/mcp-server/intercom && python app.py   # Port 8500
cd docker/mcp-server/n8n && npm start            # Port 3000

# Or use Docker Compose (if configured)
docker-compose up -d
```

### 4. Access Services

- **Freshdesk MCP Server**: http://localhost:8000
- **Intercom MCP Server**: http://localhost:8500  
- **n8n Workflows**: http://localhost:3000
- **Health Checks**: Available at `/health` endpoint for each service

## 🔧 MCP Server Details

### Freshdesk MCP Server (Port 8000)

Provides comprehensive Freshdesk integration with the following capabilities:

- **Contact Management**: Create, read, update, delete contacts
- **Company Management**: Manage company records and associations
- **Ticket Operations**: Handle support tickets and interactions
- **Data Enrichment**: Automated domain enrichment and company matching
- **Orphan Contact Analysis**: Identify and process unassociated contacts
- **Rate Limiting**: Built-in API rate limiting and retry logic
- **Background Jobs**: Long-running data processing tasks

**Key Features:**
- Domain validation and enrichment
- Company creation from high-activity contacts
- Excel report generation
- Comprehensive logging and monitoring
- Two-way delete approval system

### Intercom MCP Server (Port 8500)

Provides Intercom platform integration with:

- **Conversation Management**: Handle customer conversations
- **Contact Operations**: Manage customer contact records
- **Company Integration**: Link contacts to companies
- **Real-time Updates**: WebSocket support for live updates
- **Advanced Search**: Query conversations and contacts
- **Authentication**: Secure token-based authentication

**Key Features:**
- RESTful API endpoints
- Comprehensive error handling
- Rate limiting and retry mechanisms
- Production-ready security features
- LLM integration support

### n8n Workflow Server (Port 3000)

Workflow automation platform providing:

- **Visual Workflow Builder**: Drag-and-drop workflow creation
- **API Integration**: Connect multiple services and platforms
- **Automated Triggers**: Schedule and event-based automation
- **Data Processing**: Transform and route data between systems
- **Custom Nodes**: Extensible with custom functionality

## 🔐 Security Features

- **API Authentication**: Token-based authentication for all endpoints
- **Rate Limiting**: Configurable rate limits to prevent API abuse
- **Input Validation**: Comprehensive input sanitization and validation
- **Error Handling**: Secure error responses without sensitive data exposure
- **Environment Variables**: Sensitive configuration stored in environment files
- **CORS Protection**: Cross-origin request security

## 📊 Data Analysis & Reporting

The platform includes powerful data analysis capabilities:

### Freshdesk Analytics
- **Orphan Contact Analysis**: Identify contacts without company associations
- **Domain Enrichment**: Automated company domain discovery and validation
- **Company Creation**: Smart company creation from contact patterns
- **Excel Reporting**: Comprehensive data export and analysis reports
- **Background Processing**: Long-running analysis jobs with progress monitoring

### Report Types
- Companies without domains
- Companies with enrichment errors
- Orphan contacts analysis
- Domain validation results
- Ticket association summaries

## 🚀 API Endpoints

### Freshdesk MCP Server

```bash
# Health check
GET /health

# Contact operations
GET /contacts
POST /contacts
PUT /contacts/{id}
DELETE /contacts/{id}

# Company operations
GET /companies
POST /companies
PUT /companies/{id}
DELETE /companies/{id}

# Data analysis
POST /analyze/orphan-contacts
POST /enrich/domains
GET /reports/excel
```

### Intercom MCP Server

```bash
# Health check
GET /health

# Conversation operations
GET /conversations
GET /conversations/{id}
POST /conversations/{id}/reply

# Contact operations
GET /contacts
POST /contacts
PUT /contacts/{id}

# Company operations
GET /companies
POST /companies
PUT /companies/{id}
```

## 🛠️ Development

### Running Tests

```bash
# Freshdesk MCP Server tests
cd docker/mcp-server/freshdesk
python -m pytest tests/

# Intercom MCP Server tests
cd docker/mcp-server/intercom
python -m pytest tests/
```

### Code Quality

- **Linting**: Code follows PEP 8 standards
- **Type Hints**: Full type annotation support
- **Documentation**: Comprehensive docstrings and comments
- **Error Handling**: Robust exception handling and logging
- **Testing**: Unit tests and integration tests

### Adding New Features

1. Create feature branch from main
2. Implement changes with tests
3. Update documentation
4. Submit pull request
5. Code review and merge

## 📝 Configuration

### Environment Variables

Each MCP server requires specific environment variables:

**Freshdesk (.env)**
```bash
FRESHDESK_API_KEY=your_api_key_here
FRESHDESK_DOMAIN=your_domain.freshdesk.com
DATABASE_URL=postgresql://user:pass@localhost/db
REDIS_URL=redis://localhost:6379
```

**Intercom (.env)**
```bash
INTERCOM_ACCESS_TOKEN=your_access_token_here
DATABASE_URL=postgresql://user:pass@localhost/db
REDIS_URL=redis://localhost:6379
```

### Port Configuration

- **Freshdesk MCP Server**: Port 8000 (fixed)
- **Intercom MCP Server**: Port 8500 (fixed)
- **n8n Workflow Server**: Port 3000
- **PostgreSQL**: Port 5432
- **Redis**: Port 6379

## Services

| Service    | Port  | Description                    |
|------------|-------|--------------------------------|
| n8n        | 5678  | Workflow automation platform   |
| MCP Server | 3001  | Model Context Protocol server  |
| Ollama     | 11434 | Local LLM service             |
| Qdrant     | 6333  | Vector database               |
| PostgreSQL | 5432  | Database                      |
| Redis      | 6379  | Cache and message broker      |
| Nginx      | 80/443| Reverse proxy                 |

## Development

### Adding New Tools to MCP Server

1. Add a new tool handler in `mcp-server/server.js`
2. Update the `mcpTools` object with your new tool
3. Rebuild the MCP server: `docker-compose build mcp-server`
4. Restart the service: `docker-compose restart mcp-server`

### Database Management

- Access PostgreSQL: `docker-compose exec postgres psql -U n8n -d n8n`
- Create backups: `docker-compose exec postgres pg_dump -U n8n n8n > backup.sql`

## Security Notes

- Change all default passwords in the `.env` file
- Use proper SSL certificates in production
- Regularly update container images
- Monitor container logs for suspicious activity

## Troubleshooting

- Check logs: `docker-compose logs -f [service_name]`
- Rebuild a service: `docker-compose up -d --build [service_name]`
- Reset everything: `docker-compose down -v`

## License

MIT
