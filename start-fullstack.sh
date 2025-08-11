#!/bin/bash

# Canary STT Full-Stack Startup Script
echo "🎤 Starting Canary STT Full-Stack Application..."

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
pkill -f "python.*main.py" 2>/dev/null || true
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
    echo "❌ Backend port 8000 is busy. Please stop the process using it."
    exit 1
fi

if ! check_port 3000; then
    echo "❌ Frontend port 3000 is busy. Please stop the process using it."
    exit 1
fi

# Navigate to project directory
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

# Test hardware configuration
echo "Testing hardware configuration..."
cd backend
$PYTHON_CMD -c "
from hardware_config import hardware_optimizer
print(f'✅ Hardware detected: {len(hardware_optimizer.gpu_devices)} GPUs, {hardware_optimizer.total_system_memory_gb:.1f}GB RAM')
for i, gpu in enumerate(hardware_optimizer.gpu_devices):
    print(f'   GPU {i}: {gpu.name} ({gpu.total_memory_gb:.1f}GB)')
" || {
    echo "❌ Hardware configuration test failed"
    exit 1
}

# Start backend
echo ""
echo "🚀 Starting FastAPI backend on 0.0.0.0:8000..."
PYTORCH_CUDA_ALLOC_CONF=expandable_segments:True $PYTHON_CMD main.py &
BACKEND_PID=$!

# Wait for backend to start
echo "Waiting for backend to initialize..."
sleep 8

# Check if backend process is still running
if ! kill -0 $BACKEND_PID 2>/dev/null; then
    echo "❌ Backend process died immediately"
    exit 1
fi

# Check if backend is responding
echo "Testing backend connectivity..."
for i in {1..10}; do
    if curl -s http://localhost:8000/ > /dev/null; then
        echo "✅ Backend started successfully!"
        break
    fi
    if [ $i -eq 10 ]; then
        echo "❌ Backend failed to start or is not responding after 10 attempts"
        kill $BACKEND_PID 2>/dev/null || true
        exit 1
    fi
    echo "   Attempt $i/10 - waiting for backend to respond..."
    sleep 2
done

# Start frontend
echo ""
echo "🌐 Starting React frontend on 0.0.0.0:3000..."
cd /home/makodev58/DataEngg/canary-stt/frontend

# Check if package.json exists
if [ ! -f "package.json" ]; then
    echo "❌ package.json not found in frontend directory"
    kill $BACKEND_PID 2>/dev/null || true
    exit 1
fi

# Check if node_modules exists
if [ ! -d "node_modules" ]; then
    echo "Installing frontend dependencies..."
    npm install
    if [ $? -ne 0 ]; then
        echo "❌ Failed to install frontend dependencies"
        kill $BACKEND_PID 2>/dev/null || true
        exit 1
    fi
fi

# Set API URL for frontend
export REACT_APP_API_BASE_URL="http://$SERVER_IP:8000"
echo "Frontend will connect to backend at: $REACT_APP_API_BASE_URL"

# Start frontend with error handling
HOST=0.0.0.0 npm start &
FRONTEND_PID=$!

# Wait for frontend to start
echo "Waiting for frontend to initialize..."
sleep 15

# Check if frontend process is still running
if ! kill -0 $FRONTEND_PID 2>/dev/null; then
    echo "❌ Frontend process died immediately"
    kill $BACKEND_PID 2>/dev/null || true
    exit 1
fi

# Test frontend connectivity
echo "Testing frontend connectivity..."
for i in {1..5}; do
    if curl -s http://localhost:3000/ > /dev/null; then
        echo "✅ Frontend started successfully!"
        break
    fi
    if [ $i -eq 5 ]; then
        echo "⚠️  Frontend may still be starting (this is normal for React apps)"
        break
    fi
    echo "   Attempt $i/5 - waiting for frontend to respond..."
    sleep 3
done

echo ""
echo "🎉 Canary STT Full-Stack Application is running!"
echo ""
echo "📡 Backend API: http://$SERVER_IP:8000"
echo "🌐 Frontend UI: http://$SERVER_IP:3000"
echo "📚 API Documentation: http://$SERVER_IP:8000/docs"
echo ""
echo "🌍 Network Access URLs:"
echo "   • Web Interface: http://$SERVER_IP:3000"
echo "   • API Endpoint:  http://$SERVER_IP:8000"
echo "   • API Docs:      http://$SERVER_IP:8000/docs"
echo ""
echo "🖥️  Hardware Status:"
curl -s http://localhost:8000/ | python3 -c "
import sys, json
try:
    data = json.load(sys.stdin)
    hw = data.get('hardware', {})
    print(f\"   • GPUs: {hw.get('gpus', 'unknown')}\")
    print(f\"   • RAM:  {hw.get('system_memory_gb', 0):.1f}GB\")
    print(f\"   • Workers: {hw.get('max_workers', 'unknown')}\")
except:
    print('   • Hardware info available at API endpoint')
" 2>/dev/null || echo "   • Hardware info available at API endpoint"
echo ""
echo "🎯 Ready for speech-to-text processing!"
echo "   Upload audio files via the web interface or API"
echo ""
echo "Press Ctrl+C to stop both services"

# Trap Ctrl+C and cleanup
trap 'echo ""; echo "🛑 Stopping services..."; kill $BACKEND_PID $FRONTEND_PID 2>/dev/null || true; echo "✅ Services stopped"; exit 0' INT

# Wait for processes
wait