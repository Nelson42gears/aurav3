# 🤖 AI Customer Data Chat Interface

## Quick Setup

1. **Add Gemini API Key to .env**:
```bash
echo "GEMINI_API_KEY=your_gemini_api_key_here" >> /home/nelson/nebula/Aura/.env
```

2. **Restart n8n to load API key**:
```bash
docker-compose up -d n8n
```

## Chat Endpoint
- **URL**: `http://localhost:5678/webhook/customer-chat`
- **Method**: POST
- **Content-Type**: application/json

## Example Queries

### 1. Get Customer Data
```bash
curl -X POST http://localhost:5678/webhook/customer-chat \
  -H "Content-Type: application/json" \
  -d '{"query": "Get data for customer john.doe@company.com"}'
```

### 2. Sentiment Analysis
```bash
curl -X POST http://localhost:5678/webhook/customer-chat \
  -H "Content-Type: application/json" \
  -d '{"query": "What is the sentiment of customer sarah@startup.io?"}'
```

### 3. Customer Report
```bash
curl -X POST http://localhost:5678/webhook/customer-chat \
  -H "Content-Type: application/json" \
  -d '{"query": "Generate a 6-month report for customer mike@enterprise.com"}'
```

### 4. Recent Issues
```bash
curl -X POST http://localhost:5678/webhook/customer-chat \
  -H "Content-Type: application/json" \
  -d '{"query": "Show me recent issues from GlobalTech customer"}'
```

## Response Format
```json
{
  "query": "original user query",
  "timestamp": "2025-08-18T07:17:00Z",
  "data_source": "Freshdesk|Intercom",
  "customer_data": {...},
  "ai_insights": "AI-generated analysis and recommendations",
  "response_type": "customer_analysis",
  "status": "success"
}
```

## Supported Query Types
- **Customer Data Lookup**: Email, name, or company identifier
- **Sentiment Analysis**: Emotional tone analysis of customer interactions
- **Historical Reports**: Time-based customer interaction summaries
- **Issue Tracking**: Recent problems and resolution status
- **Pattern Analysis**: Trends in customer behavior/satisfaction

## Data Sources
- **Freshdesk MCP** (Port 8000): Support tickets, customer profiles
- **Intercom MCP** (Port 9000): Chat conversations, user interactions
- **Gemini AI**: Natural language processing and insights generation

## Architecture Flow
1. **User Query** → Chat Webhook
2. **Gemini Analysis** → Intent extraction
3. **Route Decision** → Freshdesk vs Intercom MCP
4. **Data Retrieval** → Customer information
5. **AI Insights** → Gemini analysis of data
6. **Response** → Formatted JSON output

## n8n Workflow
- **ID**: 97YWHLshna3ad0aQ
- **URL**: http://localhost:5678/workflow/97YWHLshna3ad0aQ
- **Status**: Active (webhook-triggered)
