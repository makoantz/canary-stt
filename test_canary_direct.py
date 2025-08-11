#!/usr/bin/env python3

import asyncio
import sys
import os
sys.path.append('/home/makojetson/dataengg/canary-stt/backend')

async def test_canary_loading():
    """Test Canary model loading directly"""
    try:
        print("🧪 Testing Canary model loading...")
        
        # Import and test
        from transcription_service import CanaryTranscriptionService
        
        service = CanaryTranscriptionService()
        print(f"✅ Service created, device: {service.device}")
        
        # Try to load the model
        print("📥 Attempting to load Canary model...")
        success = await service.load_model()
        
        if success:
            print("✅ Model loading reported success!")
            print(f"Model type: {type(service.model)}")
            
            if service.model != "mock" and service.model != "whisper":
                print("🎯 Canary model loaded! Testing transcription...")
                
                # Find WAV file to test
                uploads_dir = "/home/makojetson/dataengg/canary-stt/backend/uploads"
                files = os.listdir(uploads_dir)
                wav_files = [f for f in files if f.lower().endswith('.wav')]
                
                if wav_files:
                    test_file = os.path.join(uploads_dir, wav_files[0])
                    print(f"Testing with: {test_file}")
                    
                    result = await service.transcribe_audio(test_file)
                    print("🎯 Canary transcription result:")
                    print(f"   Model: {result.get('model', 'N/A')}")
                    print(f"   Text: {result.get('transcription', 'N/A')}")
                    print(f"   Error: {result.get('error', 'None')}")
                else:
                    print("No WAV files found for testing")
            else:
                print(f"🔄 Fallback model used: {service.model}")
        else:
            print("❌ Model loading failed")
            
    except Exception as e:
        print(f"❌ Test failed: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(test_canary_loading())