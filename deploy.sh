#!/bin/bash
# Vibe2Crazy Deployment Script - Start/Stop frontend and backend with one command

set -e

# Get script directory absolute path
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"

# Config
FRONTEND_PORT=5173
BACKEND_PORT=8863
FRONTEND_DIR="$SCRIPT_DIR/frontend"
BACKEND_DIR="$SCRIPT_DIR/backend"

# Color output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Install backend dependencies
install_backend() {
    echo ""
    echo "=== Installing Backend Dependencies ==="
    echo ""

    cd "$BACKEND_DIR"

    # Check if venv exists
    if [ -d "venv" ]; then
        echo -e "${YELLOW}Virtual environment already exists, skipping creation${NC}"
    else
        echo "Creating Python virtual environment..."
        python3 -m venv venv
        echo -e "${GREEN}✓ Virtual environment created successfully${NC}"
    fi

    # Activate virtual environment
    source venv/bin/activate

    # Install dependencies
    echo "Installing Python dependencies..."
    pip install -r requirements.txt

    echo ""
    echo -e "${GREEN}=== Backend Dependencies Installation Complete ===${NC}"
    cd "$SCRIPT_DIR"
}

# Install frontend dependencies
install_frontend() {
    echo ""
    echo "=== Installing Frontend Dependencies ==="
    echo ""

    cd "$FRONTEND_DIR"

    if [ -d "node_modules" ]; then
        echo -e "${YELLOW}node_modules already exists, skipping installation${NC}"
    else
        echo "Installing npm dependencies..."
        npm install
        echo -e "${GREEN}✓ Frontend dependencies installed${NC}"
    fi

    cd "$SCRIPT_DIR"
}

# Print help information
print_help() {
    echo "Usage: ./deploy.sh [command]"
    echo ""
    echo "Commands:"
    echo "  start       Start frontend and backend"
    echo "  stop        Stop frontend and backend"
    echo "  restart     Restart frontend and backend"
    echo "  status      Check service status"
    echo "  install     Install frontend and backend dependencies"
    echo "  init_db     Initialize database"
    echo "  help        Show help information"
    echo ""
    echo "Port Configuration:"
    echo "  Frontend: $FRONTEND_PORT, Backend: $BACKEND_PORT"
}

# Kill process by port
kill_process_on_port() {
    local port=$1
    local name=$2

    # Find PID using the port
    local pid=$(lsof -ti:$port 2>/dev/null || true)

    if [ -n "$pid" ]; then
        echo -e "${YELLOW}Stopping ${name} (port ${port}, PID: ${pid})...${NC}"
        kill $pid 2>/dev/null || true

        # Wait for process to end
        local count=0
        while lsof -ti:$port >/dev/null 2>&1; do
            if [ $count -ge 10 ]; then
                echo -e "${YELLOW}Force killing ${name}...${NC}"
                kill -9 $pid 2>/dev/null || true
                break
            fi
            sleep 1
            count=$((count + 1))
        done

        echo -e "${GREEN}✓ ${name} stopped${NC}"
    else
        echo -e "${YELLOW}${name} (port ${port}) not running${NC}"
    fi
}

# Initialize database
init_db() {
    echo ""
    echo "=== Initializing Database ==="
    cd "$BACKEND_DIR"

    # Activate virtual environment
    if [ -d "venv" ]; then
        source venv/bin/activate
    fi

    # Run initialization script
    echo "Running database initialization..."
    python init_db.py

    if [ $? -eq 0 ]; then
        echo -e "${GREEN}✓ Database initialized successfully${NC}"
        return 0
    else
        echo -e "${RED}✗ Database initialization failed${NC}"
        return 1
    fi
}

# Stop all services
stop_all() {
    echo ""
    echo "=== Stopping Vibe2Crazy Services ==="

    kill_process_on_port $FRONTEND_PORT "Frontend"
    kill_process_on_port $BACKEND_PORT "Backend"

    echo ""
    echo -e "${GREEN}=== All Services Stopped ===${NC}"
}

# Start backend
start_backend() {
    echo ""
    echo "Starting backend..."

    # Check if port is already in use
    if lsof -ti:$BACKEND_PORT >/dev/null 2>&1; then
        echo -e "${YELLOW}Backend already running (port $BACKEND_PORT)${NC}"
        return
    fi

    # Activate virtual environment and start
    cd "$BACKEND_DIR"
    if [ -d "venv" ]; then
        source venv/bin/activate
    fi

    # Check dependencies
    if ! python -c "import fastapi" 2>/dev/null; then
        echo -e "${YELLOW}Installing backend dependencies...${NC}"
        pip install -r requirements.txt -q
    fi

    # Start in background
    nohup python -m uvicorn app:app --host 0.0.0.0 --port $BACKEND_PORT > "$SCRIPT_DIR/logs/backend.log" 2>&1 &
    echo $! > "$SCRIPT_DIR/logs/backend.pid"

    # Wait for startup
    sleep 5

    if lsof -ti:$BACKEND_PORT >/dev/null 2>&1; then
        echo -e "${GREEN}✓ Backend started successfully (port $BACKEND_PORT)${NC}"
    else
        echo -e "${RED}✗ Backend startup failed, check logs: logs/backend.log${NC}"
        exit 1
    fi

    # Return to original directory
    cd "$SCRIPT_DIR"
}

# Start frontend
start_frontend() {
    echo ""
    echo "Starting frontend..."

    # Check if port is already in use
    if lsof -ti:$FRONTEND_PORT >/dev/null 2>&1; then
        echo -e "${YELLOW}Frontend already running (port $FRONTEND_PORT)${NC}"
        return
    fi

    cd "$FRONTEND_DIR"

    # Check node_modules
    if [ ! -d "node_modules" ]; then
        echo -e "${YELLOW}Installing frontend dependencies...${NC}"
        npm install
    fi

    # Create log directory
    mkdir -p "$SCRIPT_DIR/logs"

    # Start in background
    nohup npm run dev > "$SCRIPT_DIR/logs/frontend.log" 2>&1 &
    echo $! > "$SCRIPT_DIR/logs/frontend.pid"

    # Wait for startup
    sleep 3

    if lsof -ti:$FRONTEND_PORT >/dev/null 2>&1; then
        echo -e "${GREEN}✓ Frontend started successfully (port $FRONTEND_PORT)${NC}"
    else
        echo -e "${RED}✗ Frontend startup failed, check logs: logs/frontend.log${NC}"
        exit 1
    fi

    # Return to original directory
    cd "$SCRIPT_DIR"
}

# Start all services
start_all() {
    echo ""
    echo "=== Starting Vibe2Crazy Services ==="

    # Create log directory
    mkdir -p logs

    start_backend
    start_frontend

    echo ""
    echo -e "${GREEN}=== All Services Started ===${NC}"
    echo ""
    echo "Access URLs:"
    echo "  Frontend: http://localhost:$FRONTEND_PORT"
    echo "  Backend: http://localhost:$BACKEND_PORT"
    echo ""
    echo "Log Files:"
    echo "  Frontend: logs/frontend.log"
    echo "  Backend: logs/backend.log"
}

# Show status
show_status() {
    echo ""
    echo "=== Vibe2Crazy Services Status ==="
    echo ""

    # Frontend status
    frontend_pid=$(lsof -ti:$FRONTEND_PORT 2>/dev/null || true)
    if [ -n "$frontend_pid" ]; then
        echo -e "${GREEN}✓ Frontend Running${NC} (port $FRONTEND_PORT, PID: $frontend_pid)"
    else
        echo -e "${RED}✗ Frontend Not Running${NC} (port $FRONTEND_PORT)"
    fi

    # Backend status
    backend_pid=$(lsof -ti:$BACKEND_PORT 2>/dev/null || true)
    if [ -n "$backend_pid" ]; then
        echo -e "${GREEN}✓ Backend Running${NC} (port $BACKEND_PORT, PID: $backend_pid)"
    else
        echo -e "${RED}✗ Backend Not Running${NC} (port $BACKEND_PORT)"
    fi

    echo ""
}

main() {
    case "${1:-help}" in
        start)
            start_all
            ;;
        stop)
            stop_all
            ;;
        restart)
            stop_all
            sleep 1
            start_all
            ;;
        status)
            show_status
            ;;
        init_db)
            init_db
            ;;
        install)
            install_backend
            install_frontend
            ;;
        help|--help|-h)
            print_help
            ;;
        *)
            echo -e "${RED}Unknown command: $1${NC}"
            echo ""
            print_help
            exit 1
            ;;
    esac
}

main "$@"
