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

# Get the correct local IP address
SERVER_IP=$(hostname -I | tr ' ' '\n' | grep -E '^192\.168\.' | head -1)
if [ -z "$SERVER_IP" ]; then
    # Fallback: get primary network interface IP
    SERVER_IP=$(ip route get 1 | awk '{print $7; exit}')
fi
if [ -z "$SERVER_IP" ]; then
    SERVER_IP="localhost"
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
cd /home/makodev58/DataEngg/canary-stt

# Check if we have the conda environment available
if [ -f "/home/makodev58/anaconda3/bin/python" ]; then
    PYTHON_CMD="/home/makodev58/anaconda3/bin/python"
    echo "Using conda Python: $PYTHON_CMD"
elif [ -d "canary-stt" ]; then
    # Use the existing venv
    source canary-stt/bin/activate
    PYTHON_CMD="python"
    echo "Using virtual environment Python"
else
    # Try system Python
    PYTHON_CMD="python3"
    echo "Using system Python: $PYTHON_CMD"
fi

cd backend

# Start backend with error handling
$PYTHON_CMD main.py &
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
cd /home/makodev58/DataEngg/canary-stt/frontend

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
echo "📡 Backend API: http://$SERVER_IP:8000"
echo "🌐 Frontend UI: http://$SERVER_IP:3000"
echo ""
echo "🌍 Network Access:"
echo "   - Backend: http://$SERVER_IP:8000"
echo "   - Frontend: http://$SERVER_IP:3000"
echo "   - API Docs: http://$SERVER_IP:8000/docs"
echo ""
echo "Press Ctrl+C to stop both services"

# Trap Ctrl+C and cleanup
trap 'echo ""; echo "Stopping services..."; kill $BACKEND_PID $FRONTEND_PID 2>/dev/null || true; exit 0' INT

# Wait for processes
wait