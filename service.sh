#!/bin/bash
# BlockyMarketMaker Service Management Script
# For ZorinOS/Ubuntu/Debian systems using systemd

SERVICE_NAME="blocky-market-maker"
SERVICE_FILE="blocky-market-maker.service"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# Colors
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

print_help() {
    echo "BlockyMarketMaker Service Manager"
    echo ""
    echo "Usage: $0 [command]"
    echo ""
    echo "Commands:"
    echo "  install     Install and enable the systemd service"
    echo "  uninstall   Remove the systemd service"
    echo "  start       Start the bot"
    echo "  stop        Stop the bot"
    echo "  restart     Restart the bot"
    echo "  status      Check bot status"
    echo "  logs        View live logs"
    echo "  logs-full   View full logs since boot"
    echo ""
}

install_service() {
    echo -e "${YELLOW}Installing BlockyMarketMaker service...${NC}"
    
    # Check if service file exists
    if [ ! -f "$SCRIPT_DIR/$SERVICE_FILE" ]; then
        echo -e "${RED}Error: $SERVICE_FILE not found in $SCRIPT_DIR${NC}"
        exit 1
    fi
    
    # Copy service file to systemd
    sudo cp "$SCRIPT_DIR/$SERVICE_FILE" /etc/systemd/system/
    
    # Reload systemd
    sudo systemctl daemon-reload
    
    # Enable service
    sudo systemctl enable $SERVICE_NAME
    
    echo -e "${GREEN}✓ Service installed and enabled${NC}"
    echo ""
    echo "The bot will now start automatically when you boot your system."
    echo ""
    echo "Commands:"
    echo "  Start now:    $0 start"
    echo "  View status:  $0 status"
    echo "  View logs:    $0 logs"
}

uninstall_service() {
    echo -e "${YELLOW}Removing BlockyMarketMaker service...${NC}"
    
    # Stop service if running
    sudo systemctl stop $SERVICE_NAME 2>/dev/null
    
    # Disable service
    sudo systemctl disable $SERVICE_NAME 2>/dev/null
    
    # Remove service file
    sudo rm -f /etc/systemd/system/$SERVICE_FILE
    
    # Reload systemd
    sudo systemctl daemon-reload
    
    echo -e "${GREEN}✓ Service removed${NC}"
}

start_service() {
    echo -e "${YELLOW}Starting BlockyMarketMaker...${NC}"
    sudo systemctl start $SERVICE_NAME
    sleep 2
    
    if systemctl is-active --quiet $SERVICE_NAME; then
        echo -e "${GREEN}✓ Bot started successfully${NC}"
        echo ""
        echo "Dashboard: http://localhost:8081/dashboard"
        echo "Health:    http://localhost:8080/health"
    else
        echo -e "${RED}✗ Failed to start${NC}"
        echo "Check logs with: $0 logs"
    fi
}

stop_service() {
    echo -e "${YELLOW}Stopping BlockyMarketMaker...${NC}"
    sudo systemctl stop $SERVICE_NAME
    echo -e "${GREEN}✓ Bot stopped${NC}"
}

restart_service() {
    echo -e "${YELLOW}Restarting BlockyMarketMaker...${NC}"
    sudo systemctl restart $SERVICE_NAME
    sleep 2
    
    if systemctl is-active --quiet $SERVICE_NAME; then
        echo -e "${GREEN}✓ Bot restarted successfully${NC}"
    else
        echo -e "${RED}✗ Failed to restart${NC}"
        echo "Check logs with: $0 logs"
    fi
}

show_status() {
    echo -e "${YELLOW}BlockyMarketMaker Status:${NC}"
    echo ""
    systemctl status $SERVICE_NAME --no-pager
}

show_logs() {
    echo -e "${YELLOW}BlockyMarketMaker Logs (Ctrl+C to exit):${NC}"
    echo ""
    journalctl -u $SERVICE_NAME -f
}

show_logs_full() {
    echo -e "${YELLOW}BlockyMarketMaker Full Logs:${NC}"
    echo ""
    journalctl -u $SERVICE_NAME -b --no-pager
}

# Main
case "$1" in
    install)
        install_service
        ;;
    uninstall)
        uninstall_service
        ;;
    start)
        start_service
        ;;
    stop)
        stop_service
        ;;
    restart)
        restart_service
        ;;
    status)
        show_status
        ;;
    logs)
        show_logs
        ;;
    logs-full)
        show_logs_full
        ;;
    *)
        print_help
        ;;
esac
