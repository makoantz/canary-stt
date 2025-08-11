# 🎤 Canary STT - Audio Transcription Application

A full-stack application for audio-to-text transcription using NVIDIA's Canary-Qwen-2.5B model, optimized for NVIDIA Jetson Orin Nano Super.

## 🚀 Features

- **SOTA Speech Recognition**: Uses NVIDIA Canary-Qwen-2.5B (5.63% WER on OpenASR leaderboard)
- **Full-Stack Architecture**: FastAPI backend + React TypeScript frontend
- **Jetson Optimized**: Memory management and performance tuning for 8GB RAM
- **Multi-Format Support**: MP3, WAV, M4A, FLAC, OGG
- **Real-time Processing**: Async transcription with progress tracking
- **Responsive UI**: Modern drag-and-drop interface with progress indicators

## 🏗️ Architecture

```
├── backend/                 # Python FastAPI backend
│   ├── main.py             # API endpoints
│   ├── transcription_service.py  # Canary model integration
│   ├── jetson_config.py    # Jetson optimization settings
│   └── requirements.txt    # Python dependencies
├── src/                    # React TypeScript frontend
│   ├── App.tsx            # Main application component
│   └── App.css            # Styling
├── canary-dev/            # Python virtual environment
└── start.sh              # Application launcher script
```

## 🛠️ Prerequisites

### Hardware Requirements
- NVIDIA Jetson Orin Nano Super (8GB RAM recommended)
- 16GB+ storage space
- microSD card or SSD for optimal performance

### Software Requirements
- Ubuntu 20.04+ on Jetson
- Python 3.8+
- Node.js 16+
- CUDA support (optional but recommended)

## 📦 Installation

### 1. Clone and Setup Environment

```bash
cd /home/$(whoami)
git clone <your-repo-url> canary-stt
cd canary-stt

# The virtual environment 'canary-dev' should already exist
# If not, create it:
uv venv canary-dev
```

### 2. Install Dependencies

```bash
# Activate virtual environment
source canary-dev/bin/activate

# Install Python dependencies
cd backend
pip install -r requirements.txt

# Install NeMo development version for Canary support
uv pip install git+https://github.com/NVIDIA/NeMo.git

# Install frontend dependencies
cd ../frontend
npm install
```

### 3. Optimize System for Jetson (Recommended)

```bash
# Increase swap to 16GB for better memory management
sudo fallocate -l 16G /swapfile
sudo chmod 600 /swapfile
sudo mkswap /swapfile
sudo swapon /swapfile

# Make swap permanent
echo '/swapfile none swap sw 0 0' | sudo tee -a /etc/fstab

# Install FFmpeg for audio processing
sudo apt update
sudo apt install ffmpeg

# Enable max performance mode
sudo nvpmodel -m 8  # Max performance mode
sudo jetson_clocks   # Max clocks
```

## 🌐 Network Configuration

The application is configured for network access:

- **Backend**: Binds to `0.0.0.0:8000` with CORS enabled for all origins
- **Frontend**: Uses environment variable for API URL configuration
- **Auto-detection**: Startup script automatically detects Jetson's IP address

### Network Access Points
```
http://192.168.80.242:8000  - Backend API
http://192.168.80.242:3000  - Frontend UI  
http://192.168.80.242:8000/docs - API Documentation
```

**Note**: The startup script automatically detects your Jetson's correct IP address (avoiding gateway/docker IPs).

### Firewall Configuration (if needed)
```bash
# Allow ports 3000 and 8000 through firewall
sudo ufw allow 3000
sudo ufw allow 8000
```

## 🚀 Usage

### Quick Start
```bash
# Make startup script executable (if not already)
chmod +x start.sh

# Launch the application
./start.sh
```

This will start:
- Backend API server on `http://0.0.0.0:8000` (accessible via network)
- Frontend React app on `http://0.0.0.0:3000` (accessible via network)

The script will display the actual IP addresses for network access.

### Manual Start

**Backend:**
```bash
source canary-dev/bin/activate
cd backend
# Backend already configured to bind to 0.0.0.0:8000
python main.py
```

**Frontend:**
```bash
cd frontend
# Start frontend accessible from network
HOST=0.0.0.0 npm start
```

### Using the Application

1. **Upload Audio Files**: 
   - Drag and drop audio files onto the upload area
   - Or click to select files (MP3, WAV, M4A, FLAC, OGG)

2. **Process Transcription**:
   - Click "Upload" to upload the file to the server
   - Click "Transcribe" to start processing
   - Monitor real-time progress

3. **View Results**:
   - Transcription text with confidence scores
   - Audio duration and processing metadata
   - Export options for transcription text

## 🎯 API Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/` | GET | Health check |
| `/upload` | POST | Upload audio file |
| `/transcribe/{job_id}` | POST | Start transcription |
| `/status/{job_id}` | GET | Get job status |
| `/result/{job_id}` | GET | Get transcription result |
| `/job/{job_id}` | DELETE | Delete job and cleanup |

## ⚡ Performance Tuning

### Memory Optimization
The application includes Jetson-specific optimizations:

- **Dynamic Memory Management**: Automatic cleanup after processing
- **Batch Processing**: Processes one file at a time to avoid OOM
- **Audio Chunking**: Large files processed in 30-second chunks
- **Model Quantization**: FP16 precision when CUDA available

### Monitoring
```bash
# Check system resources
htop

# Monitor GPU usage (if CUDA available)
nvidia-smi

# Check memory usage
free -h

# Monitor disk space
df -h
```

## 🔧 Configuration

### Jetson Configuration
Edit `backend/jetson_config.py` to adjust:
- Memory limits
- Chunk processing sizes  
- Audio preprocessing settings
- CUDA optimizations

### Model Configuration
The app automatically detects and uses:
- CUDA if available (GPU acceleration)
- CPU fallback with optimizations
- Mock mode for development/testing

## 🐛 Troubleshooting

### Common Issues

**Out of Memory Errors:**
```bash
# Check available memory
free -h

# Restart swap
sudo swapoff /swapfile && sudo swapon /swapfile

# Clear caches
sudo sh -c 'echo 3 > /proc/sys/vm/drop_caches'
```

**Model Loading Issues:**
```bash
# Check NeMo installation
python -c "from nemo.collections.speechlm2.models import SALM; print('NeMo OK')"

# Verify Canary model access
python -c "from transformers import AutoTokenizer; AutoTokenizer.from_pretrained('nvidia/canary-qwen-2.5b'); print('Model accessible')"
```

**Port Conflicts:**
```bash
# Kill existing processes
pkill -f uvicorn
pkill -f "npm.*start"

# Check port usage
lsof -i :8000
lsof -i :3000
```

### Performance Issues

**Slow Transcription:**
- Ensure sufficient swap space (16GB recommended)
- Use SSD instead of microSD if possible
- Enable max performance mode: `sudo jetson_clocks`
- Check CPU/GPU utilization with `htop` and `nvidia-smi`

**Frontend Not Loading:**
- Check if port 3000 is available
- Verify backend is running on port 8000
- Check browser console for errors

## 📊 System Requirements

| Component | Minimum | Recommended |
|-----------|---------|-------------|
| RAM | 8GB | 8GB + 16GB swap |
| Storage | 16GB | 64GB+ SSD |
| CPU | Jetson Orin Nano | Jetson Orin Nano Super |
| GPU | None | CUDA compatible |

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch
3. Make changes with proper testing
4. Submit a pull request

## 📝 License

This project is open source and available under the MIT License.

## 🙏 Acknowledgments

- NVIDIA for the Canary-Qwen-2.5B model
- NeMo framework team
- FastAPI and React communities