from fastapi import FastAPI, File, UploadFile, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
import aiofiles
import asyncio
import uuid
import os
import time
from typing import Dict, Optional
from enum import Enum
import json
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor
from hardware_config import hardware_optimizer

app = FastAPI(title="Canary STT API", version="1.0.0")

# Initialize high-performance processing pool
max_workers = hardware_optimizer.get_optimal_workers()
executor = ThreadPoolExecutor(max_workers=max_workers)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Allow all origins for network access
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

class JobStatus(str, Enum):
    PENDING = "pending"
    PROCESSING = "processing" 
    COMPLETED = "completed"
    FAILED = "failed"

jobs: Dict[str, Dict] = {}

UPLOAD_DIR = Path("uploads")
UPLOAD_DIR.mkdir(exist_ok=True)

@app.get("/")
async def root():
    hardware_info = hardware_optimizer.monitor_memory_usage()
    return {
        "message": "Canary STT API is running",
        "hardware": {
            "gpus": len(hardware_optimizer.gpu_devices),
            "system_memory_gb": hardware_optimizer.total_system_memory_gb,
            "max_workers": max_workers,
            "gpu_names": [gpu.name for gpu in hardware_optimizer.gpu_devices]
        },
        "memory_usage": hardware_info
    }

SUPPORTED_FORMATS = {
    '.wav': 'WAV Audio',
    '.mp3': 'MP3 Audio', 
    '.m4a': 'M4A Audio',
    '.aac': 'AAC Audio',
    '.flac': 'FLAC Audio',
    '.ogg': 'OGG Audio',
    '.wma': 'WMA Audio',
    '.opus': 'OPUS Audio'
}

def get_file_extension(filename: str) -> str:
    """Get file extension in lowercase"""
    return Path(filename).suffix.lower()

def is_supported_audio_format(filename: str) -> tuple[bool, str]:
    """Check if audio format is supported"""
    ext = get_file_extension(filename)
    if ext in SUPPORTED_FORMATS:
        return True, SUPPORTED_FORMATS[ext]
    return False, f"Unsupported format: {ext}"

@app.post("/upload")
async def upload_audio(file: UploadFile = File(...)):
    # Validate file has extension
    if not file.filename or '.' not in file.filename:
        raise HTTPException(status_code=400, detail="File must have a valid extension")
    
    # Check if format is supported
    is_supported, format_info = is_supported_audio_format(file.filename)
    if not is_supported:
        supported_list = ', '.join(SUPPORTED_FORMATS.keys())
        raise HTTPException(
            status_code=400, 
            detail=f"{format_info}. Supported formats: {supported_list}"
        )
    
    job_id = str(uuid.uuid4())
    file_path = UPLOAD_DIR / f"{job_id}_{file.filename}"
    
    try:
        async with aiofiles.open(file_path, 'wb') as f:
            content = await file.read()
            await f.write(content)
        
        # Validate file size
        file_size = os.path.getsize(file_path)
        if file_size == 0:
            os.remove(file_path)
            raise HTTPException(status_code=400, detail="Uploaded file is empty")
        
        jobs[job_id] = {
            "id": job_id,
            "status": JobStatus.PENDING,
            "filename": file.filename,
            "file_path": str(file_path),
            "format": format_info,
            "file_size": file_size,
            "created_at": time.time(),  # Use actual Unix timestamp
            "result": None,
            "error": None
        }
        
        return {
            "job_id": job_id, 
            "status": JobStatus.PENDING,
            "filename": file.filename,
            "format": format_info,
            "file_size": file_size
        }
    
    except Exception as e:
        # Clean up file if upload failed
        if file_path.exists():
            os.remove(file_path)
        raise HTTPException(status_code=500, detail=f"Failed to upload file: {str(e)}")

@app.post("/transcribe/{job_id}")
async def transcribe_audio(job_id: str):
    if job_id not in jobs:
        raise HTTPException(status_code=404, detail="Job not found")
    
    job = jobs[job_id]
    if job["status"] != JobStatus.PENDING:
        raise HTTPException(status_code=400, detail="Job already processed or in progress")
    
    job["status"] = JobStatus.PROCESSING
    
    # Start transcription in background
    asyncio.create_task(process_transcription(job_id))
    
    return {"job_id": job_id, "status": JobStatus.PROCESSING}

@app.get("/status/{job_id}")
async def get_job_status(job_id: str):
    if job_id not in jobs:
        raise HTTPException(status_code=404, detail="Job not found")
    
    job = jobs[job_id]
    response = {
        "job_id": job_id,
        "status": job["status"],
        "filename": job["filename"],
        "created_at": job["created_at"]
    }
    
    # Add progress information if available
    if "progress" in job:
        response["progress"] = job["progress"]
    
    return response

@app.get("/result/{job_id}")
async def get_transcription_result(job_id: str):
    if job_id not in jobs:
        raise HTTPException(status_code=404, detail="Job not found")
    
    job = jobs[job_id]
    if job["status"] == JobStatus.COMPLETED:
        return {
            "job_id": job_id,
            "status": job["status"],
            "result": job["result"],
            "filename": job["filename"]
        }
    elif job["status"] == JobStatus.FAILED:
        return {
            "job_id": job_id,
            "status": job["status"],
            "error": job["error"]
        }
    else:
        return {
            "job_id": job_id,
            "status": job["status"],
            "message": "Transcription still in progress"
        }

@app.get("/download/{job_id}")
async def download_transcription(job_id: str):
    """Download transcription as a text file"""
    if job_id not in jobs:
        raise HTTPException(status_code=404, detail="Job not found")
    
    job = jobs[job_id]
    if job["status"] != JobStatus.COMPLETED or not job.get("result"):
        raise HTTPException(status_code=400, detail="Transcription not completed or not available")
    
    transcription_text = job["result"].get("transcription", "")
    if not transcription_text:
        raise HTTPException(status_code=400, detail="No transcription text available")
    
    # Create filename based on original file
    original_filename = Path(job["filename"]).stem
    download_filename = f"{original_filename}_transcription.txt"
    
    # Format the timestamp as a human-readable date
    from datetime import datetime
    created_timestamp = job.get("created_at", time.time())
    if isinstance(created_timestamp, (int, float)):
        # Convert from timestamp to readable date
        created_date = datetime.fromtimestamp(created_timestamp).strftime("%Y-%m-%d %H:%M:%S")
    else:
        created_date = str(created_timestamp)
    
    # Create transcription content with metadata
    content = f"""Transcription of: {job["filename"]}
Generated on: {created_date}
Duration: {job["result"].get("duration", "Unknown")} seconds
Confidence: {job["result"].get("confidence", "Unknown")}
Model: {job["result"].get("model", "Unknown")}

--- TRANSCRIPTION ---

{transcription_text}
"""
    
    from fastapi.responses import Response
    return Response(
        content=content,
        media_type="text/plain",
        headers={
            "Content-Disposition": f"attachment; filename={download_filename}"
        }
    )

@app.delete("/job/{job_id}")
async def delete_job(job_id: str):
    if job_id not in jobs:
        raise HTTPException(status_code=404, detail="Job not found")
    
    job = jobs[job_id]
    
    # Clean up file
    try:
        if os.path.exists(job["file_path"]):
            os.remove(job["file_path"])
    except Exception:
        pass
    
    del jobs[job_id]
    return {"message": "Job deleted successfully"}

async def process_transcription(job_id: str):
    """Background task to process transcription with GPU load balancing"""
    try:
        from transcription_service import transcription_service
        
        job = jobs[job_id]
        audio_path = job["file_path"]
        
        # Add progress tracking
        job["progress"] = {"stage": "preprocessing", "percent": 10}
        
        # Get optimal GPU for this job
        optimal_gpu = hardware_optimizer.get_device_for_job(job_id)
        if optimal_gpu >= 0:
            job["assigned_gpu"] = optimal_gpu
            job["progress"]["gpu"] = optimal_gpu
        
        # Perform actual transcription
        result = await transcription_service.transcribe_audio(audio_path, job_id=job_id)
        
        job["result"] = result
        job["status"] = JobStatus.COMPLETED
        job["progress"] = {"stage": "completed", "percent": 100}
        
    except Exception as e:
        jobs[job_id]["status"] = JobStatus.FAILED
        jobs[job_id]["error"] = str(e)
        jobs[job_id]["progress"] = {"stage": "failed", "percent": 0}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)