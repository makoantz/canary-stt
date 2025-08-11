#!/usr/bin/env python3

import asyncio
import sys
import os
sys.path.append('/home/makojetson/dataengg/canary-stt/backend')

from transcription_service import transcription_service

async def test_whisper():
    # Find the WAV file
    uploads_dir = "/home/makojetson/dataengg/canary-stt/backend/uploads"
    
    if not os.path.exists(uploads_dir):
        print("❌ Uploads directory not found")
        return
    
    files = os.listdir(uploads_dir)
    wav_files = [f for f in files if f.lower().endswith('.wav')]
    
    if not wav_files:
        print("❌ No WAV files found in uploads directory")
        print("Available files:", files)
        return
    
    # Use the Recording.wav file if available
    test_file = None
    for f in wav_files:
        if 'Recording' in f:
            test_file = os.path.join(uploads_dir, f)
            break
    
    if not test_file:
        test_file = os.path.join(uploads_dir, wav_files[0])
    
    print(f"🧪 Testing Whisper transcription with: {test_file}")
    
    # Test transcription
    result = await transcription_service.transcribe_audio(test_file)
    
    print("🎯 Transcription result:")
    print(f"   Status: {'✅ Success' if not result.get('error') else '❌ Error'}")
    print(f"   Model: {result.get('model', 'N/A')}")
    print(f"   Duration: {result.get('duration', 'N/A')}s")
    print(f"   Confidence: {result.get('confidence', 'N/A')}")
    print(f"   Language: {result.get('language', 'N/A')}")
    print("\n📝 Transcribed Text:")
    print(f"   \"{result.get('transcription', 'N/A')}\"")
    
    if result.get('error'):
        print(f"\n❌ Error: {result['error']}")

if __name__ == "__main__":
    asyncio.run(test_whisper())