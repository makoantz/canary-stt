#!/usr/bin/env python3
"""
Simple hardware test to verify CUDA availability
"""

def test_cuda_availability():
    """Test if CUDA and GPUs are available"""
    try:
        import torch
        print("✅ PyTorch imported successfully")
        print(f"PyTorch version: {torch.__version__}")
        
        # Test CUDA
        cuda_available = torch.cuda.is_available()
        print(f"CUDA available: {cuda_available}")
        
        if cuda_available:
            device_count = torch.cuda.device_count()
            print(f"GPU devices detected: {device_count}")
            
            for i in range(device_count):
                props = torch.cuda.get_device_properties(i)
                memory_gb = props.total_memory / (1024**3)
                print(f"  GPU {i}: {props.name} ({memory_gb:.1f}GB)")
                
                # Test memory allocation
                try:
                    test_tensor = torch.zeros(100, 100, device=f'cuda:{i}')
                    print(f"    ✅ Memory test passed on GPU {i}")
                    del test_tensor
                    torch.cuda.empty_cache()
                except Exception as e:
                    print(f"    ❌ Memory test failed on GPU {i}: {e}")
        
        return cuda_available
        
    except ImportError:
        print("❌ PyTorch not available")
        return False
    except Exception as e:
        print(f"❌ Error testing CUDA: {e}")
        return False

def test_system_resources():
    """Test system resources"""
    try:
        import psutil
        
        # Memory info
        memory = psutil.virtual_memory()
        memory_gb = memory.total / (1024**3)
        available_gb = memory.available / (1024**3)
        print(f"System Memory: {memory_gb:.1f}GB total, {available_gb:.1f}GB available")
        
        # CPU info
        cpu_count = psutil.cpu_count()
        print(f"CPU cores: {cpu_count}")
        
        return True
        
    except ImportError:
        print("❌ psutil not available")
        return False
    except Exception as e:
        print(f"❌ Error checking system resources: {e}")
        return False

def main():
    print("Hardware Migration Test - RTX 3080 System")
    print("=" * 50)
    
    # Test system resources
    print("\n🖥️  System Resources:")
    system_ok = test_system_resources()
    
    # Test CUDA
    print("\n🚀 CUDA & GPU Test:")
    cuda_ok = test_cuda_availability()
    
    print("\n" + "=" * 50)
    if cuda_ok and system_ok:
        print("✅ Hardware migration successful!")
        print("System is ready for high-performance AI workloads")
        return True
    else:
        print("❌ Hardware migration needs attention")
        if not cuda_ok:
            print("  - CUDA/GPU issues detected")
        if not system_ok:
            print("  - System resource issues detected")
        return False

if __name__ == "__main__":
    success = main()
    exit(0 if success else 1)