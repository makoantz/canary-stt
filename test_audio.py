#!/usr/bin/env python3

import asyncio
import sys
import os
sys.path.append('/home/makojetson/dataengg/canary-stt/backend')

from transcription_service import transcription_service

async def test_audio_processing():
    # Find the uploaded m4a file
    uploads_dir = "/home/makojetson/dataengg/canary-stt/backend/uploads"
    
    if not os.path.exists(uploads_dir):
        print("❌ Uploads directory not found")
        return
    
    files = os.listdir(uploads_dir)
    m4a_files = [f for f in files if f.lower().endswith('.m4a')]
    
    if not m4a_files:
        print("❌ No M4A files found in uploads directory")
        print("Available files:", files)
        return
    
    test_file = os.path.join(uploads_dir, m4a_files[0])
    print(f"🧪 Testing audio processing with: {test_file}")
    
    # Test preprocessing
    print("📋 Testing preprocess_audio...")
    processed_path = await transcription_service.preprocess_audio(test_file)
    
    if processed_path:
        print(f"✅ Preprocessing successful: {processed_path}")
        
        # Test full transcription
        print("📋 Testing full transcription...")
        result = await transcription_service.transcribe_audio(test_file)
        print("🎯 Transcription result:")
        print(f"   Status: {'✅ Success' if not result.get('error') else '❌ Error'}")
        print(f"   Text: {result.get('transcription', 'N/A')[:100]}...")
        print(f"   Duration: {result.get('duration', 'N/A')}s")
        print(f"   Confidence: {result.get('confidence', 'N/A')}")
        if result.get('error'):
            print(f"   Error: {result['error']}")
            
    else:
        print("❌ Preprocessing failed")

if __name__ == "__main__":
    asyncio.run(test_audio_processing())