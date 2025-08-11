#!/usr/bin/env python3

import numpy as np
import soundfile as sf

# Create a simple test WAV file (1 second of sine wave)
sample_rate = 16000
duration = 2.0  # 2 seconds
frequency = 440  # A note

# Generate sine wave
t = np.linspace(0, duration, int(sample_rate * duration), False)
audio = np.sin(2 * np.pi * frequency * t) * 0.3  # 30% volume

# Save as WAV file
output_path = "/home/makojetson/dataengg/canary-stt/backend/uploads/test_audio.wav"
sf.write(output_path, audio, sample_rate)

print(f"Test WAV file created: {output_path}")
print(f"Duration: {duration}s, Sample rate: {sample_rate}Hz")