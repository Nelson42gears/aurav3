# n8n CLI Workflow Creation Reference Guide

## Overview
Comprehensive guide for creating, importing, and managing n8n workflows via CLI, based on resolved database issues and production testing.

## Table of Contents
- [Critical Requirements](#critical-requirements)
- [Database Schema Compliance](#database-schema-compliance)
- [JSON Structure Template](#json-structure-template)
- [CLI Commands](#cli-commands)
- [Common Issues & Solutions](#common-issues--solutions)
- [LLM Integration Examples](#llm-integration-examples)
- [Testing & Validation](#testing--validation)

## Critical Requirements

### 🚨 **Must-Follow Rules**
1. **Array Format**: Always wrap workflow(s) in array brackets `[{workflow}]`
2. **Required Fields**: Include all non-null database fields
3. **No String Tags**: Omit tags unless using valid database tag IDs
4. **Complete Node Config**: All nodes must have complete parameter structures
5. **Restart After Activation**: Always restart n8n after activating workflows with webhooks

### 📋 **Database Schema Compliance**
n8n's PostgreSQL database has strict constraints. These fields are **REQUIRED**:

```json
{
  "name": "string (required)",
  "active": false,  // Boolean, defaults to false for import
  "nodes": [],      // Complete node array with all parameters
  "connections": {}, // Complete connection mapping
  "pinData": {},
  "settings": {"executionOrder": "v1"},
  "staticData": null,
  "meta": {"templateCredsSetupCompleted": true} // Optional but recommended
}
```

### ❌ **Avoid These (Cause Database Errors)**
- Single object format: `{workflow}` 
- Missing `active` field
- String tags: `"tags": ["llm", "api"]`
- Incomplete node parameters
- Null values in required fields

## JSON Structure Template

### Basic Workflow Template
```json
[
  {
    "name": "My-Workflow-Name",
    "active": false,
    "nodes": [
      {
        "parameters": {},
        "id": "unique-node-id",
        "name": "Node Name",
        "type": "n8n-nodes-base.nodeType",
        "typeVersion": 1,
        "position": [300, 300]
      }
    ],
    "connections": {
      "Node Name": {
        "main": [
          [
            {
              "node": "Next Node",
              "type": "main", 
              "index": 0
            }
          ]
        ]
      }
    },
    "pinData": {},
    "settings": {"executionOrder": "v1"},
    "staticData": null,
    "meta": {"templateCredsSetupCompleted": true}
  }
]
```

### Webhook Workflow Template
```json
[
  {
    "name": "Webhook-API-Service",
    "active": false,
    "nodes": [
      {
        "parameters": {
          "httpMethod": "POST",
          "path": "api-endpoint",
          "responseMode": "responseNode"
        },
        "id": "webhook-001",
        "name": "Webhook",
        "type": "n8n-nodes-base.webhook",
        "typeVersion": 1,
        "position": [300, 300]
      },
      {
        "parameters": {
          "respondWith": "json",
          "responseBody": "={{ $json }}"
        },
        "id": "respond-001",
        "name": "Respond to Webhook",
        "type": "n8n-nodes-base.respondToWebhook",
        "typeVersion": 1,
        "position": [500, 300]
      }
    ],
    "connections": {
      "Webhook": {
        "main": [
          [
            {
              "node": "Respond to Webhook",
              "type": "main",
              "index": 0
            }
          ]
        ]
      }
    },
    "pinData": {},
    "settings": {"executionOrder": "v1"},
    "staticData": null,
    "meta": {"templateCredsSetupCompleted": true}
  }
]
```

## CLI Commands

### 1. Import Workflow
```bash
# Copy workflow file to container
docker cp "/path/to/workflow.json" aura-n8n-1:/tmp/workflow.json

# Import via n8n CLI
docker exec aura-n8n-1 n8n import:workflow --input=/tmp/workflow.json
```

### 2. List Workflows
```bash
docker exec aura-n8n-1 n8n list:workflow
```

### 3. Activate Workflow
```bash
# Get workflow ID from list command, then activate
docker exec aura-n8n-1 n8n update:workflow --id=WORKFLOW_ID --active=true

# CRITICAL: Restart n8n after activation (especially for webhooks)
docker restart aura-n8n-1
```

### 4. Verify Workflow Status
```bash
# Check if workflow is active and webhook registered
curl -I http://localhost:5678/webhook/your-webhook-path
```

## Common Issues & Solutions

### Issue 1: Database Constraint Violations
**Error**: `null value in column "active" of relation "workflow_entity" violates not-null constraint`

**Solution**:
- Ensure `"active": false` is present in workflow JSON
- Use array format: `[{workflow}]`
- Include all required fields

### Issue 2: Tag ID Constraint Violations  
**Error**: `null value in column "tagId" of relation "workflows_tags" violates not-null constraint`

**Solution**:
- Remove tags from initial JSON: `"tags": []` or omit entirely
- Add tags later via n8n UI or API with proper tag IDs

### Issue 3: Webhook Not Registered
**Error**: `The requested webhook "POST path" is not registered`

**Solutions**:
1. Verify workflow is **active**
2. **Restart n8n container** after activation
3. Check webhook path matches workflow configuration
4. Ensure HTTP method matches (POST/GET)

### Issue 4: Node Parameter Validation Errors
**Error**: Various validation errors during import

**Solution**:
- Include complete parameter structures for all nodes
- Reference existing working workflows for parameter examples
- Use proper typeVersion for each node type

## LLM Integration Examples

### HTTP Request to External LLM API
```json
{
  "parameters": {
    "method": "POST",
    "url": "https://your-llm-endpoint/v1/chat/completions",
    "sendHeaders": true,
    "headerParameters": {
      "parameters": [
        {"name": "Content-Type", "value": "application/json"}
      ]
    },
    "sendBody": true,
    "bodyParameters": {
      "parameters": [
        {"name": "model", "value": "your-model-name"},
        {"name": "messages", "value": "=[{\"role\": \"user\", \"content\": \"{{ $json.prompt }}\"}]"},
        {"name": "max_tokens", "value": "={{ $json.max_tokens || 400 }}"},
        {"name": "temperature", "value": "={{ $json.temperature || 0.3 }}"}
      ]
    },
    "options": {"timeout": 30000}
  },
  "id": "llm-call-001",
  "name": "LLM API Call",
  "type": "n8n-nodes-base.httpRequest",
  "typeVersion": 4,
  "position": [500, 300]
}
```

### Response Processing Code Node
```json
{
  "parameters": {
    "jsCode": "// Process LLM response\nconst response = $input.first().json;\nconst content = response.choices[0].message.content;\n\n// Clean response (remove reasoning patterns)\nfunction cleanResponse(text) {\n  let cleaned = text.replace(/^(Okay|Hmm|Let me think).*?(?=\\n|\\.|!|\\?)/gim, '');\n  return cleaned.trim() || text;\n}\n\nreturn [{\n  json: {\n    response: cleanResponse(content),\n    raw: content,\n    tokens: response.usage.total_tokens\n  }\n}];"
  },
  "id": "process-001",
  "name": "Process Response",
  "type": "n8n-nodes-base.code",
  "typeVersion": 2,
  "position": [700, 300]
}
```

## Testing & Validation

### 1. Validate JSON Structure
```bash
# Test JSON validity
cat workflow.json | jq '.[0].name'  # Should return workflow name
```

### 2. Test Import Process
```bash
# Copy and import
docker cp "workflow.json" aura-n8n-1:/tmp/test.json
docker exec aura-n8n-1 n8n import:workflow --input=/tmp/test.json

# Check for success message: "Successfully imported X workflows"
```

### 3. Test Webhook Endpoints
```bash
# After activation and restart
curl -X POST "http://localhost:5678/webhook/your-path" \
  -H "Content-Type: application/json" \
  -d '{"test": "data"}'
```

### 4. Monitor n8n Logs
```bash
# Watch for errors during import/activation
docker logs aura-n8n-1 --tail 20 -f
```

## Environment Configuration

### Required Environment Variables
```yaml
# In docker-compose.yml
environment:
  - N8N_API_KEY=your_api_key_here
  - N8N_RUNNERS_ENABLED=true  # Recommended to avoid deprecation warnings
  - DB_TYPE=postgresdb
  - DB_POSTGRESDB_HOST=postgres
  - DB_POSTGRESDB_DATABASE=n8n
```

## Best Practices

1. **Test Locally First**: Validate JSON structure before importing
2. **Incremental Development**: Start with simple workflows, add complexity gradually
3. **Version Control**: Store workflow JSON files in version control
4. **Documentation**: Comment complex JavaScript code in Code nodes
5. **Error Handling**: Include error handling nodes in production workflows
6. **Monitoring**: Set up execution logging and monitoring

## Quick Reference Commands

```bash
# Complete workflow deployment sequence
docker cp "workflow.json" aura-n8n-1:/tmp/workflow.json
docker exec aura-n8n-1 n8n import:workflow --input=/tmp/workflow.json
docker exec aura-n8n-1 n8n list:workflow  # Get workflow ID
docker exec aura-n8n-1 n8n update:workflow --id=WORKFLOW_ID --active=true
docker restart aura-n8n-1
sleep 10  # Wait for restart
curl -X POST "http://localhost:5678/webhook/path" -d '{"test":"data"}'
```

## Troubleshooting Checklist

- [ ] JSON is valid and in array format
- [ ] All required fields present (`name`, `active`, `nodes`, `connections`)
- [ ] No string tags in workflow JSON
- [ ] Complete node parameter structures
- [ ] Workflow imported successfully (check logs)
- [ ] Workflow activated via CLI
- [ ] n8n container restarted after activation
- [ ] Webhook endpoint responds (if applicable)

## File Locations

- **Working Examples**: `/home/nelson/nebula/Aura/workflows/qwen3_fixed_workflow.json`
- **n8n Logs**: `docker logs aura-n8n-1`
- **Container**: `aura-n8n-1`
- **Internal Import Path**: `/tmp/` inside container

---

**Last Updated**: 2025-08-13  
**Status**: Production-tested and validated  
**Version**: 1.0
