#!/usr/bin/env python3

import os
import librosa
import soundfile as sf
import numpy as np

def test_m4a_loading():
    # Find the M4A file
    uploads_dir = "/home/makojetson/dataengg/canary-stt/backend/uploads"
    files = os.listdir(uploads_dir)
    m4a_files = [f for f in files if f.lower().endswith('.m4a')]
    
    if not m4a_files:
        print("No M4A files found")
        return
    
    test_file = os.path.join(uploads_dir, m4a_files[0])
    print(f"Testing: {test_file}")
    
    # Try different approaches
    approaches = [
        ("librosa default", lambda f: librosa.load(f)),
        ("librosa with sr=None", lambda f: librosa.load(f, sr=None)),
        ("librosa with audioread backend", lambda f: librosa.load(f, sr=16000)),
    ]
    
    for name, func in approaches:
        try:
            print(f"\n🧪 {name}:")
            audio, sr = func(test_file)
            print(f"   ✅ Success: {len(audio)/sr:.2f}s @ {sr}Hz")
            
            # Try to save a small sample
            sample_path = f"/tmp/test_{name.replace(' ', '_')}.wav"
            sf.write(sample_path, audio[:sr], sr)  # First second
            print(f"   Sample saved to: {sample_path}")
            break
            
        except Exception as e:
            print(f"   ❌ Failed: {e}")
    
    # Check file header
    print(f"\n📋 File analysis:")
    with open(test_file, 'rb') as f:
        header = f.read(20)
        print(f"   First 20 bytes: {header}")
        print(f"   As hex: {header.hex()}")

if __name__ == "__main__":
    test_m4a_loading()