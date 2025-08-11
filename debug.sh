#!/bin/bash

echo "🔍 Debugging Canary STT Application..."

# Check directory structure
echo ""
echo "📁 Directory structure:"
ls -la /home/makojetson/dataengg/canary-stt/

echo ""
echo "📁 Backend directory:"
ls -la /home/makojetson/dataengg/canary-stt/backend/

echo ""
echo "📁 Frontend directory:"
ls -la /home/makojetson/dataengg/canary-stt/frontend/

# Check virtual environment
echo ""
echo "🐍 Virtual environment:"
if [ -d "canary-dev" ]; then
    echo "✅ canary-dev exists"
    echo "Python path: $(canary-dev/bin/python --version)"
else
    echo "❌ canary-dev missing"
fi

# Check if ports are in use
echo ""
echo "🌐 Port usage:"
echo "Port 8000: $(lsof -ti:8000 | wc -l) processes"
echo "Port 3000: $(lsof -ti:3000 | wc -l) processes"

# Test backend imports
echo ""
echo "🧪 Testing backend imports:"
source canary-dev/bin/activate
cd backend
python -c "
try:
    from main import app
    print('✅ FastAPI app imports successfully')
except Exception as e:
    print(f'❌ FastAPI import error: {e}')

try:
    from transcription_service import transcription_service  
    print('✅ Transcription service imports successfully')
except Exception as e:
    print(f'❌ Transcription service error: {e}')
" 2>&1

# Test frontend
echo ""
echo "🧪 Testing frontend:"
cd ../frontend
if [ -f "package.json" ]; then
    echo "✅ package.json exists"
    echo "Dependencies:"
    npm list --depth=0 2>/dev/null | head -10
else
    echo "❌ package.json missing"
fi

echo ""
echo "🔍 Debug complete"