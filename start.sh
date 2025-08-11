#!/bin/bash

# Canary STT Application Startup Script
echo "🎤 Starting Canary STT Application..."

# Function to check if port is in use
check_port() {
    if lsof -Pi :$1 -sTCP:LISTEN -t >/dev/null 2>&1; then
        echo "Port $1 is already in use"
        return 1
    fi
    return 0
}

# Kill any existing processes
echo "Stopping any existing processes..."
pkill -f "uvicorn.*main:app" 2>/dev/null || true
pkill -f "npm.*start" 2>/dev/null || true
pkill -f "react-scripts start" 2>/dev/null || true

# Force kill processes on specific ports
echo "Freeing up ports 3000 and 8000..."
lsof -ti:3000 | xargs kill -9 2>/dev/null || true
lsof -ti:8000 | xargs kill -9 2>/dev/null || true

# Wait for ports to be free
sleep 3

# Get the correct local IP address (not gateway/docker IPs)
JETSON_IP=$(hostname -I | tr ' ' '\n' | grep -E '^192\.168\.(80|1)\.' | grep -v '^192\.168\.1\.1$' | head -1)
if [ -z "$JETSON_IP" ]; then
    # Fallback: get primary network interface IP
    JETSON_IP=$(ip route get 1 | awk '{print $7; exit}')
fi

# Check if required ports are available
if ! check_port 8000; then
    echo "Backend port 8000 is busy. Please stop the process using it."
    exit 1
fi

if ! check_port 3000; then
    echo "Frontend port 3000 is busy. Please stop the process using it."
    exit 1
fi

# Start backend
echo "Starting FastAPI backend on 0.0.0.0:8000..."
cd /home/makojetson/dataengg/canary-stt

# Check if virtual environment exists
if [ ! -d "canary-dev" ]; then
    echo "❌ Virtual environment 'canary-dev' not found. Please run: uv venv canary-dev"
    exit 1
fi

source canary-dev/bin/activate
cd backend

# Start backend with error handling
python main.py &
BACKEND_PID=$!

# Wait for backend to start
echo "Waiting for backend to start..."
sleep 5

# Check if backend process is still running
if ! kill -0 $BACKEND_PID 2>/dev/null; then
    echo "❌ Backend process died immediately"
    exit 1
fi

# Check if backend is responding
if ! curl -s http://localhost:8000/ > /dev/null; then
    echo "❌ Backend failed to start or is not responding"
    kill $BACKEND_PID 2>/dev/null || true
    exit 1
fi
echo "✅ Backend started successfully"

# Start frontend
echo "Starting React frontend on 0.0.0.0:3000..."
cd /home/makojetson/dataengg/canary-stt/frontend

# Check if package.json exists
if [ ! -f "package.json" ]; then
    echo "❌ package.json not found in frontend directory"
    kill $BACKEND_PID 2>/dev/null || true
    exit 1
fi

# Start frontend with error handling
HOST=0.0.0.0 npm start &
FRONTEND_PID=$!

# Wait a bit for frontend to start
echo "Waiting for frontend to start..."
sleep 10

# Check if frontend process is still running
if ! kill -0 $FRONTEND_PID 2>/dev/null; then
    echo "❌ Frontend process died immediately"
    kill $BACKEND_PID 2>/dev/null || true
    exit 1
fi

echo ""
echo "🚀 Application starting up..."
echo "📡 Backend API: http://$JETSON_IP:8000"
echo "🌐 Frontend UI: http://$JETSON_IP:3000"
echo ""
echo "🌍 Network Access:"
echo "   - Backend: http://$JETSON_IP:8000"
echo "   - Frontend: http://$JETSON_IP:3000"
echo "   - API Docs: http://$JETSON_IP:8000/docs"
echo ""
echo "Press Ctrl+C to stop both services"

# Trap Ctrl+C and cleanup
trap 'echo ""; echo "Stopping services..."; kill $BACKEND_PID $FRONTEND_PID 2>/dev/null || true; exit 0' INT

# Wait for processes
wait