#!/usr/bin/env python3
"""
Test script for the save transcription feature
"""
import requests
import time
import os
from pathlib import Path

API_BASE_URL = "http://localhost:8000"

def test_save_feature():
    """Test the complete workflow including save functionality"""
    
    print("🧪 Testing Save Transcription Feature")
    print("=" * 50)
    
    # Check if server is running
    try:
        response = requests.get(f"{API_BASE_URL}/")
        print(f"✅ Server is running: {response.json()['message']}")
    except Exception as e:
        print(f"❌ Server not running: {e}")
        return False
    
    # Check if we have a test audio file
    test_files = [
        "test_audio.wav",
        "backend/uploads/test_audio.wav",
        "create_test_wav.py"
    ]
    
    test_file = None
    for file_path in test_files:
        if os.path.exists(file_path):
            if file_path.endswith('.wav'):
                test_file = file_path
                break
    
    if not test_file:
        print("📁 Creating test audio file...")
        # Create a simple test WAV file
        try:
            exec(open("create_test_wav.py").read())
            test_file = "test_audio.wav"
            print(f"✅ Created test file: {test_file}")
        except Exception as e:
            print(f"❌ Could not create test file: {e}")
            return False
    
    print(f"📄 Using test file: {test_file}")
    
    # Step 1: Upload file
    print("\n📤 Step 1: Uploading file...")
    try:
        with open(test_file, 'rb') as f:
            files = {'file': (os.path.basename(test_file), f, 'audio/wav')}
            response = requests.post(f"{API_BASE_URL}/upload", files=files)
        
        if response.status_code == 200:
            job_data = response.json()
            job_id = job_data['job_id']
            print(f"✅ Upload successful - Job ID: {job_id}")
        else:
            print(f"❌ Upload failed: {response.text}")
            return False
    except Exception as e:
        print(f"❌ Upload error: {e}")
        return False
    
    # Step 2: Start transcription
    print(f"\n🎤 Step 2: Starting transcription for job {job_id}...")
    try:
        response = requests.post(f"{API_BASE_URL}/transcribe/{job_id}")
        if response.status_code == 200:
            print("✅ Transcription started")
        else:
            print(f"❌ Transcription start failed: {response.text}")
            return False
    except Exception as e:
        print(f"❌ Transcription start error: {e}")
        return False
    
    # Step 3: Wait for completion and monitor progress
    print("\n⏳ Step 3: Waiting for transcription to complete...")
    max_attempts = 30
    attempt = 0
    
    while attempt < max_attempts:
        try:
            response = requests.get(f"{API_BASE_URL}/status/{job_id}")
            status_data = response.json()
            status = status_data['status']
            
            if 'progress' in status_data:
                progress = status_data['progress']
                print(f"   Progress: {progress['stage']} - {progress['percent']}%")
            
            if status == 'completed':
                print("✅ Transcription completed!")
                break
            elif status == 'failed':
                result_response = requests.get(f"{API_BASE_URL}/result/{job_id}")
                error_data = result_response.json()
                print(f"❌ Transcription failed: {error_data.get('error', 'Unknown error')}")
                return False
            elif status == 'processing':
                print(f"   Status: {status}")
            
            time.sleep(2)
            attempt += 1
            
        except Exception as e:
            print(f"❌ Status check error: {e}")
            time.sleep(2)
            attempt += 1
    
    if attempt >= max_attempts:
        print("❌ Transcription timed out")
        return False
    
    # Step 4: Get transcription result
    print("\n📜 Step 4: Getting transcription result...")
    try:
        response = requests.get(f"{API_BASE_URL}/result/{job_id}")
        if response.status_code == 200:
            result_data = response.json()
            transcription = result_data['result']['transcription']
            print(f"✅ Transcription result:")
            print(f"   Text: {transcription[:100]}...")
            print(f"   Confidence: {result_data['result'].get('confidence', 'N/A')}")
            print(f"   Model: {result_data['result'].get('model', 'N/A')}")
        else:
            print(f"❌ Failed to get result: {response.text}")
            return False
    except Exception as e:
        print(f"❌ Result retrieval error: {e}")
        return False
    
    # Step 5: Test save/download functionality
    print("\n💾 Step 5: Testing save functionality...")
    try:
        response = requests.get(f"{API_BASE_URL}/download/{job_id}")
        if response.status_code == 200:
            # Save the downloaded content
            filename = f"test_transcription_{job_id[:8]}.txt"
            with open(filename, 'wb') as f:
                f.write(response.content)
            
            print(f"✅ Transcription saved to: {filename}")
            
            # Show content preview
            with open(filename, 'r') as f:
                content = f.read()
                print(f"📄 File content preview:")
                print(content[:200] + "..." if len(content) > 200 else content)
            
            # Check file size
            file_size = os.path.getsize(filename)
            print(f"📊 File size: {file_size} bytes")
            
        else:
            print(f"❌ Download failed: {response.text}")
            return False
    except Exception as e:
        print(f"❌ Download error: {e}")
        return False
    
    # Cleanup
    print(f"\n🧹 Cleaning up job {job_id}...")
    try:
        response = requests.delete(f"{API_BASE_URL}/job/{job_id}")
        if response.status_code == 200:
            print("✅ Job cleaned up successfully")
        else:
            print(f"⚠️  Cleanup warning: {response.text}")
    except Exception as e:
        print(f"⚠️  Cleanup error: {e}")
    
    print("\n🎉 All tests passed! Save transcription feature is working correctly.")
    return True

if __name__ == "__main__":
    success = test_save_feature()
    if success:
        print("\n✅ TEST PASSED: Save feature working correctly!")
    else:
        print("\n❌ TEST FAILED: Check the issues above")
    
    exit(0 if success else 1)
