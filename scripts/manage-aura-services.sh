#!/bin/bash

# Aura Services Management Script
# This script provides easy management of the Aura MCP stack via systemd

SERVICE_NAME="aura-stack.service"

case "$1" in
    start)
        echo "🚀 Starting Aura MCP Services Stack..."
        sudo systemctl start $SERVICE_NAME
        sudo systemctl status $SERVICE_NAME --no-pager
        ;;
    stop)
        echo "🛑 Stopping Aura MCP Services Stack..."
        sudo systemctl stop $SERVICE_NAME
        sudo systemctl status $SERVICE_NAME --no-pager
        ;;
    restart)
        echo "🔄 Restarting Aura MCP Services Stack..."
        sudo systemctl restart $SERVICE_NAME
        sudo systemctl status $SERVICE_NAME --no-pager
        ;;
    status)
        echo "📊 Aura MCP Services Stack Status:"
        sudo systemctl status $SERVICE_NAME --no-pager
        echo ""
        echo "🐳 Docker Container Status:"
        docker ps --format "table {{.Names}}\t{{.Status}}\t{{.Ports}}"
        ;;
    enable)
        echo "⚡ Enabling Aura stack to start on boot..."
        sudo systemctl enable $SERVICE_NAME
        ;;
    disable)
        echo "💤 Disabling Aura stack auto-start..."
        sudo systemctl disable $SERVICE_NAME
        ;;
    logs)
        echo "📋 Viewing systemd service logs..."
        sudo journalctl -u $SERVICE_NAME -f
        ;;
    health)
        echo "🏥 Health Check for all MCP services..."
        echo "Freshdesk MCP (port 8000):"
        curl -s http://localhost:8000/health || echo "❌ Failed"
        echo ""
        echo "SureMDM MCP (port 7000):"
        curl -s http://localhost:7000/health || echo "❌ Failed"
        echo ""
        echo "Intercom MCP (port 9000):"
        curl -s http://localhost:9000/health || echo "❌ Failed"
        echo ""
        echo "n8n MCP Server (port 3001):"
        curl -s http://localhost:3001/health || echo "❌ Failed"
        echo ""
        echo "n8n Main (port 5678):"
        curl -s http://localhost:5678/healthz || echo "❌ Failed"
        echo ""
        echo "Uptime Kuma (port 3004):"
        curl -s -o /dev/null -w "%{http_code}" http://localhost:3004 || echo "❌ Failed"
        ;;
    *)
        echo "Usage: $0 {start|stop|restart|status|enable|disable|logs|health}"
        echo ""
        echo "Commands:"
        echo "  start    - Start the Aura stack via systemd"
        echo "  stop     - Stop the Aura stack via systemd"
        echo "  restart  - Restart the Aura stack"
        echo "  status   - Show service and container status"
        echo "  enable   - Enable auto-start on boot"
        echo "  disable  - Disable auto-start on boot"
        echo "  logs     - View systemd service logs"
        echo "  health   - Check health of all MCP services"
        exit 1
        ;;
esac

exit 0
