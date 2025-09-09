FROM python:3.12-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Copy Python requirements first for better caching
COPY mcp-servers/n8n/requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Create shared directory for MCP base classes
RUN mkdir -p /app/shared/mcp-base

# Copy MCP base module
COPY shared/mcp-base/ /app/shared/mcp-base/

# Copy application code
COPY mcp-servers/n8n/mcp_server.py .

# Set environment variables
ENV PYTHONPATH=/app:/app/shared
ENV PYTHONUNBUFFERED=1

# Create logs directory
RUN mkdir -p logs

# Expose the server port
EXPOSE 3001

# Start the Python MCP server
CMD ["python", "mcp_server.py"]
