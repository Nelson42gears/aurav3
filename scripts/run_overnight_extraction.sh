#!/bin/bash
# 42Gears Overnight Knowledge Base Extraction Runner
# Runs extraction and indexing as background Docker process

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

echo "🌙 Starting 42Gears overnight knowledge base extraction..."
echo "📂 Project root: $PROJECT_ROOT"

# Ensure logs directory exists
mkdir -p "$PROJECT_ROOT/logs"

# Check if services are running
if ! docker ps | grep -q "aura-chromadb-1"; then
    echo "⚠️  ChromaDB not running, starting services..."
    cd "$PROJECT_ROOT"
    docker-compose up -d chromadb embedding_service
    sleep 10
fi

# Run extraction in Docker container to ensure isolation
echo "🚀 Launching overnight extraction in Docker container..."

docker run --rm \
    --name aura-overnight-extraction \
    --network aura_aura-network \
    -v "$PROJECT_ROOT/scripts:/app/scripts" \
    -v "$PROJECT_ROOT/logs:/app/logs" \
    -v "$PROJECT_ROOT:/app/project" \
    -w /app/scripts \
    -e CHROMADB_HOST=chromadb \
    -e CHROMADB_PORT=8000 \
    --memory=2g \
    --cpus=1.0 \
    python:3.12-slim \
    bash -c "
        pip install chromadb requests beautifulsoup4 lxml && \
        python3 overnight_extraction.py
    " &

EXTRACTION_PID=$!
echo "✅ Overnight extraction launched with PID: $EXTRACTION_PID"
echo "📋 Monitor progress: tail -f $PROJECT_ROOT/logs/overnight_extraction.log"
echo "🛑 Stop extraction: docker stop aura-overnight-extraction"

# Create status file
cat > "$PROJECT_ROOT/logs/extraction_status.json" << EOF
{
    "status": "running",
    "started_at": "$(date -Iseconds)",
    "pid": $EXTRACTION_PID,
    "container": "aura-overnight-extraction",
    "log_file": "$PROJECT_ROOT/logs/overnight_extraction.log"
}
EOF

echo "🎯 Background extraction started successfully!"
echo "   Status file: $PROJECT_ROOT/logs/extraction_status.json"
echo "   Log file: $PROJECT_ROOT/logs/overnight_extraction.log"
