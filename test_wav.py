#!/usr/bin/env python3

import asyncio
import sys
import os
sys.path.append('/home/makojetson/dataengg/canary-stt/backend')

from transcription_service import transcription_service

async def test_wav_processing():
    test_file = "/home/makojetson/dataengg/canary-stt/backend/uploads/test_audio.wav"
    
    if not os.path.exists(test_file):
        print("❌ Test WAV file not found")
        return
    
    print(f"🧪 Testing WAV processing with: {test_file}")
    
    # Test full transcription
    print("📋 Testing full transcription...")
    result = await transcription_service.transcribe_audio(test_file)
    
    print("🎯 Transcription result:")
    print(f"   Status: {'✅ Success' if not result.get('error') else '❌ Error'}")
    print(f"   Text: {result.get('transcription', 'N/A')}")
    print(f"   Duration: {result.get('duration', 'N/A')}s")
    print(f"   Confidence: {result.get('confidence', 'N/A')}")
    print(f"   Model: {result.get('model', 'N/A')}")
    
    if result.get('error'):
        print(f"   Error: {result['error']}")

if __name__ == "__main__":
    asyncio.run(test_wav_processing())