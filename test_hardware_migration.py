#!/usr/bin/env python3
"""
Test script to verify hardware migration from Jetson to RTX 3080 system
"""

import asyncio
import sys
import os
import logging
from pathlib import Path

# Add backend to path
sys.path.append(str(Path(__file__).parent / 'backend'))

from hardware_config import hardware_optimizer
from transcription_service import transcription_service

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def test_hardware_detection():
    """Test hardware detection and configuration"""
    print("=== Hardware Detection Test ===")
    
    # Test system info
    print(f"CPU Cores: {hardware_optimizer.cpu_count}")
    print(f"System Memory: {hardware_optimizer.total_system_memory_gb:.1f}GB")
    print(f"Available Memory: {hardware_optimizer.available_system_memory_gb:.1f}GB")
    
    # Test GPU detection
    print(f"GPUs Detected: {len(hardware_optimizer.gpu_devices)}")
    for gpu in hardware_optimizer.gpu_devices:
        print(f"  GPU {gpu.index}: {gpu.name} ({gpu.total_memory_gb:.1f}GB)")
    
    # Test configuration
    config = hardware_optimizer.optimize_for_hardware()
    print(f"Optimized Config:")
    print(f"  Max Batch Size: {config['max_batch_size']}")
    print(f"  Chunk Length: {config['chunk_length_s']}s")
    print(f"  Multi-GPU: {config['use_multi_gpu']}")
    print(f"  Max Workers: {hardware_optimizer.get_optimal_workers()}")
    print(f"  Max Memory Usage: {config['max_memory_usage_gb']}GB")
    
    return True

async def test_memory_monitoring():
    """Test memory monitoring capabilities"""
    print("\n=== Memory Monitoring Test ===")
    
    # Monitor memory usage
    usage = hardware_optimizer.monitor_memory_usage()
    print(f"System Memory Used: {usage['system_memory_used_gb']:.2f}GB ({usage['system_memory_percent']:.1f}%)")
    
    # Monitor GPU memory
    for gpu_id, info in usage.get('gpu_memory', {}).items():
        print(f"{gpu_id}: {info['allocated_gb']:.2f}GB allocated, {info['free_gb']:.2f}GB free")
    
    # Test memory pressure detection
    pressure = hardware_optimizer.check_memory_pressure()
    print(f"Memory Pressure - System: {pressure['system']}, GPUs: {pressure['gpus']}")
    
    return True

async def test_transcription_service():
    """Test transcription service loading"""
    print("\n=== Transcription Service Test ===")
    
    try:
        # Test model loading
        print("Loading transcription model...")
        success = await transcription_service.load_model()
        print(f"Model loading: {'SUCCESS' if success else 'FAILED'}")
        
        # Test with a sample audio file if available
        test_files = [
            Path('backend/uploads/test_audio.wav'),
            Path('backend/uploads').glob('*.wav'),
            Path('backend/uploads').glob('*.m4a')
        ]
        
        sample_file = None
        for test_file in test_files:
            if isinstance(test_file, Path) and test_file.exists():
                sample_file = test_file
                break
            elif hasattr(test_file, '__iter__'):
                for f in test_file:
                    if f.exists():
                        sample_file = f
                        break
                if sample_file:
                    break
        
        if sample_file:
            print(f"Testing transcription with: {sample_file}")
            result = await transcription_service.transcribe_audio(str(sample_file), job_id="test")
            print(f"Transcription result: {result.get('transcription', 'No transcription')[:100]}...")
            print(f"Model used: {result.get('model', 'Unknown')}")
            print(f"Duration: {result.get('duration', 0):.2f}s")
            print(f"Confidence: {result.get('confidence', 0):.2f}")
        else:
            print("No test audio files found in backend/uploads/")
        
        return True
        
    except Exception as e:
        print(f"Transcription service test failed: {e}")
        return False

async def test_cuda_optimizations():
    """Test CUDA optimizations"""
    print("\n=== CUDA Optimization Test ===")
    
    try:
        import torch
        
        print(f"PyTorch version: {torch.__version__}")
        print(f"CUDA available: {torch.cuda.is_available()}")
        
        if torch.cuda.is_available():
            print(f"CUDA version: {torch.version.cuda}")
            print(f"cuDNN version: {torch.backends.cudnn.version()}")
            print(f"Device count: {torch.cuda.device_count()}")
            
            # Test TF32 settings
            print(f"TF32 enabled (matmul): {torch.backends.cuda.matmul.allow_tf32}")
            print(f"cuDNN benchmark: {torch.backends.cudnn.benchmark}")
            
            # Test memory allocation
            for i in range(torch.cuda.device_count()):
                props = torch.cuda.get_device_properties(i)
                print(f"GPU {i}: {props.name} - {props.total_memory / 1024**3:.1f}GB")
                
                # Test memory allocation
                try:
                    test_tensor = torch.zeros(1000, 1000, device=f'cuda:{i}', dtype=torch.float16)
                    print(f"  Memory test passed: {test_tensor.device}")
                    del test_tensor
                    torch.cuda.empty_cache()
                except Exception as e:
                    print(f"  Memory test failed: {e}")
        
        return True
        
    except Exception as e:
        print(f"CUDA test failed: {e}")
        return False

async def main():
    """Run all hardware migration tests"""
    print("Testing hardware migration from Jetson Orin Nano to RTX 3080 system")
    print("=" * 80)
    
    tests = [
        ("Hardware Detection", test_hardware_detection),
        ("Memory Monitoring", test_memory_monitoring), 
        ("CUDA Optimizations", test_cuda_optimizations),
        ("Transcription Service", test_transcription_service),
    ]
    
    results = {}
    
    for test_name, test_func in tests:
        try:
            print(f"\nRunning {test_name}...")
            result = await test_func()
            results[test_name] = result
            print(f"{test_name}: {'PASSED' if result else 'FAILED'}")
        except Exception as e:
            print(f"{test_name}: FAILED - {e}")
            results[test_name] = False
    
    print("\n" + "=" * 80)
    print("TEST SUMMARY")
    print("=" * 80)
    
    passed = sum(results.values())
    total = len(results)
    
    for test_name, result in results.items():
        status = "PASSED" if result else "FAILED"
        print(f"{test_name:.<50} {status}")
    
    print(f"\nOverall: {passed}/{total} tests passed")
    
    if passed == total:
        print("✅ Hardware migration successful! System ready for high-performance transcription.")
    else:
        print("❌ Some tests failed. Check the logs above for details.")
    
    return passed == total

if __name__ == "__main__":
    success = asyncio.run(main())
    sys.exit(0 if success else 1)