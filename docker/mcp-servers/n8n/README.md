# n8n MCP Server

This MCP server provides a modular interface for managing n8n workflows programmatically in the Aura project. It supports workflow management through CLI commands and webhook-based automation.

## Table of Contents
- [Setup](#setup)
- [Configuration](#configuration)
- [Workflow Management](#workflow-management)
  - [CLI Commands](#cli-commands)
  - [Webhook Configuration](#webhook-configuration)
- [Environment Variables](#environment-variables)
- [Best Practices](#best-practices)
- [Troubleshooting](#troubleshooting)

## Setup

The n8n MCP server is configured in the main `docker-compose.yml` file. It runs alongside the n8n instance and requires specific environment variables for authentication.

### Prerequisites
- Docker and Docker Compose
- n8n Community Edition
- Node.js environment for local development

### Installation
1. The server is automatically set up when running `docker compose up`
2. No additional installation steps are required as dependencies are managed through Docker

## Configuration

### Environment Variables
Required environment variables in `docker-compose.yml`:
```yaml
environment:
  - N8N_API_KEY=${N8N_API_KEY}  # Must match n8n service's API key
  - N8N_RUNNERS_ENABLED=true     # Recommended to avoid deprecation warnings
```

## Workflow Management

### CLI Commands

#### List Workflows
```bash
docker compose exec n8n n8n list:workflow
```

#### Import Workflow
```bash
# Create workflow JSON file
cat > workflow.json << EOL
[{
  "name": "my_workflow",
  "nodes": [...],
  "connections": {...}
}]
EOL

# Import workflow
docker compose exec n8n n8n import:workflow --input=/path/to/workflow.json
```

#### Update Workflow
```bash
# Activate workflow
docker compose exec n8n n8n update:workflow --id=WORKFLOW_ID --active=true

# Important: Restart n8n after activation
docker compose restart n8n
```

### Webhook Configuration

#### Creating Webhook Workflows
1. Define webhook path in workflow configuration:
```json
{
  "parameters": {
    "path": "test",           # Do not include leading slash
    "httpMethod": "POST",     # Specify HTTP method explicitly
    "responseMode": "responseNode"
  },
  "name": "Webhook",
  "type": "n8n-nodes-base.webhook"
}
```

2. Import and activate the workflow using CLI commands
3. Restart n8n to register webhook endpoints

#### Webhook URL Format
Production webhook URLs follow this format:
```
http://localhost:5678/webhook/:workflow_id/webhook/:path
```

Example:
```bash
# For a workflow with:
# - ID: YNbaZiafOOaFR5Nn
# - Path: test
curl -X POST http://localhost:5678/webhook/YNbaZiafOOaFR5Nn/webhook/test
```

#### Important Notes
- Webhook paths are case-sensitive
- HTTP method must match workflow configuration
- Workflow must be active for webhooks to work
- Container restart required after workflow activation
- Imported workflows are deactivated by default

## Best Practices

1. **Naming Conventions**
   - Use snake_case for all file names and variables
   - Follow consistent naming patterns for workflows

2. **Workflow Management**
   - Keep workflow IDs consistent across environments
   - Document webhook endpoints and their purposes
   - Test webhook endpoints after configuration changes

3. **Security**
   - Never expose API keys in code or version control
   - Use environment variables for sensitive configuration
   - Validate webhook payloads in workflows

## Troubleshooting

### Common Issues

1. **Webhook 404 Errors**
   - Verify workflow is active
   - Check exact path format including workflow ID
   - Ensure n8n container was restarted after activation
   - Confirm HTTP method matches workflow configuration

2. **Authentication Issues**
   - Verify N8N_API_KEY is set correctly in both services
   - Check environment variable propagation

3. **Workflow Activation Issues**
   - Use CLI to check workflow status
   - Verify workflow ID is correct
   - Restart n8n after activation changes

### Logs
To check n8n logs for troubleshooting:
```bash
docker compose logs n8n --tail 50
```

Look for webhook registration and execution messages in the logs to verify proper setup.

### Support
For additional support:
1. Check n8n documentation: https://docs.n8n.io/
2. Review MCP server source code in this directory
3. Consult the development team for project-specific questions
