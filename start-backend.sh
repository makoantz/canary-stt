#!/bin/bash

# Canary STT Backend-Only Startup Script
echo "🎤 Starting Canary STT Backend..."

# Function to check if port is in use
check_port() {
    if lsof -Pi :$1 -sTCP:LISTEN -t >/dev/null 2>&1; then
        echo "Port $1 is already in use"
        return 1
    fi
    return 0
}

# Kill any existing backend processes
echo "Stopping any existing backend processes..."
pkill -f "uvicorn.*main:app" 2>/dev/null || true
pkill -f "python.*main.py" 2>/dev/null || true

# Force kill processes on backend port
echo "Freeing up port 8000..."
lsof -ti:8000 | xargs kill -9 2>/dev/null || true

# Wait for port to be free
sleep 2

# Get the correct local IP address
SERVER_IP=$(hostname -I | tr ' ' '\n' | grep -E '^192\.168\.' | head -1)
if [ -z "$SERVER_IP" ]; then
    # Fallback: get primary network interface IP
    SERVER_IP=$(ip route get 1 | awk '{print $7; exit}')
fi
if [ -z "$SERVER_IP" ]; then
    SERVER_IP="localhost"
fi

# Check if required port is available
if ! check_port 8000; then
    echo "❌ Backend port 8000 is busy. Please stop the process using it."
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

# Test hardware configuration
echo "Testing hardware configuration..."
$PYTHON_CMD -c "
from hardware_config import hardware_optimizer
print(f'✅ Hardware detected: {len(hardware_optimizer.gpu_devices)} GPUs, {hardware_optimizer.total_system_memory_gb:.1f}GB RAM')
for i, gpu in enumerate(hardware_optimizer.gpu_devices):
    print(f'   GPU {i}: {gpu.name} ({gpu.total_memory_gb:.1f}GB)')
" || {
    echo "❌ Hardware configuration test failed"
    exit 1
}

# Start backend with error handling and memory optimization
echo "Starting backend server..."
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

echo ""
echo "🚀 Canary STT Backend is running!"
echo "📡 Backend API: http://$SERVER_IP:8000"
echo "📚 API Documentation: http://$SERVER_IP:8000/docs"
echo "🔍 Interactive API: http://$SERVER_IP:8000/redoc"
echo ""
echo "🖥️  Hardware Status:"
curl -s http://localhost:8000/ | python3 -m json.tool 2>/dev/null | grep -E "(gpus|system_memory_gb|max_workers|gpu_names)" || echo "   Hardware info available at API endpoint"
echo ""
echo "Press Ctrl+C to stop the backend service"

# Trap Ctrl+C and cleanup
trap 'echo ""; echo "Stopping backend..."; kill $BACKEND_PID 2>/dev/null || true; exit 0' INT

# Wait for process
wait $BACKEND_PID