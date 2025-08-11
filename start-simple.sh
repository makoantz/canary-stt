#!/bin/bash

echo "🎤 Starting Canary STT Application (Simple Mode)..."
echo ""

# Get IP address
JETSON_IP=$(hostname -I | tr ' ' '\n' | grep -E '^192\.168\.(80|1)\.' | grep -v '^192\.168\.1\.1$' | head -1)
if [ -z "$JETSON_IP" ]; then
    JETSON_IP=$(ip route get 1 | awk '{print $7; exit}')
fi

echo "🌐 Detected IP: $JETSON_IP"
echo ""

# Clean up any existing processes
echo "🧹 Cleaning up existing processes..."
pkill -f "python.*main.py" 2>/dev/null || true
lsof -ti:3000 | xargs kill -9 2>/dev/null || true
lsof -ti:8000 | xargs kill -9 2>/dev/null || true
sleep 2

# Start backend
echo "🔧 Starting backend..."
cd /home/makojetson/dataengg/canary-stt
source canary-dev/bin/activate
cd backend

echo "Backend starting at: $(date)"
python main.py > ../backend.log 2>&1 &
BACKEND_PID=$!

echo "Backend PID: $BACKEND_PID"

# Wait and check backend
sleep 5
if ! kill -0 $BACKEND_PID 2>/dev/null; then
    echo "❌ Backend died. Log:"
    cat ../backend.log
    exit 1
fi

echo "✅ Backend started"

# Start frontend
echo "🎨 Starting frontend..."
cd /home/makojetson/dataengg/canary-stt/frontend

echo "Frontend starting at: $(date)"
HOST=0.0.0.0 PORT=3000 npm start > ../frontend.log 2>&1 &
FRONTEND_PID=$!

echo "Frontend PID: $FRONTEND_PID"

# Wait and check frontend
sleep 8
if ! kill -0 $FRONTEND_PID 2>/dev/null; then
    echo "❌ Frontend died. Log:"
    cat ../frontend.log | tail -20
    kill $BACKEND_PID 2>/dev/null || true
    exit 1
fi

echo "✅ Frontend started"

echo ""
echo "🚀 Application ready!"
echo "📡 Backend API: http://$JETSON_IP:8000"
echo "🌐 Frontend UI: http://$JETSON_IP:3000"
echo "📖 API Docs: http://$JETSON_IP:8000/docs"
echo ""
echo "📋 Process IDs:"
echo "   Backend: $BACKEND_PID"
echo "   Frontend: $FRONTEND_PID"
echo ""
echo "📝 Logs:"
echo "   Backend: backend.log"
echo "   Frontend: frontend.log"
echo ""
echo "Press Ctrl+C to stop services"

# Wait for interrupt
trap 'echo ""; echo "Stopping services..."; kill $BACKEND_PID $FRONTEND_PID 2>/dev/null || true; exit 0' INT
wait