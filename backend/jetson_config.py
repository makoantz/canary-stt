import os
import gc
import torch
import psutil
import logging
from typing import Dict, Any

logger = logging.getLogger(__name__)

class JetsonOptimizer:
    """Optimization configurations for NVIDIA Jetson Orin Nano Super"""
    
    def __init__(self):
        self.total_memory_gb = self.get_total_memory()
        self.available_memory_gb = self.get_available_memory()
        
    def get_total_memory(self) -> float:
        """Get total system memory in GB"""
        return psutil.virtual_memory().total / (1024**3)
    
    def get_available_memory(self) -> float:
        """Get available system memory in GB"""
        return psutil.virtual_memory().available / (1024**3)
    
    def get_cuda_memory_info(self) -> Dict[str, float]:
        """Get CUDA memory information"""
        if torch.cuda.is_available():
            return {
                'total_gb': torch.cuda.get_device_properties(0).total_memory / (1024**3),
                'allocated_gb': torch.cuda.memory_allocated() / (1024**3),
                'cached_gb': torch.cuda.memory_reserved() / (1024**3)
            }
        return {}
    
    def optimize_for_jetson(self) -> Dict[str, Any]:
        """Get optimal configuration for Jetson Orin Nano Super"""
        config = {
            # Memory optimizations
            'torch_dtype': torch.float16 if torch.cuda.is_available() else torch.float32,
            'device_map': 'auto' if torch.cuda.is_available() else 'cpu',
            'low_cpu_mem_usage': True,
            'use_cache': True,
            
            # Model optimizations
            'max_batch_size': 1,  # Process one audio file at a time
            'chunk_length_s': 30,  # Process audio in 30-second chunks
            'overlap_length_s': 2,  # 2-second overlap between chunks
            
            # Memory management
            'clear_cache_after_inference': True,
            'force_gc_after_inference': True,
            'max_memory_usage_gb': min(6.0, self.total_memory_gb * 0.75),
            
            # Audio processing
            'target_sample_rate': 16000,
            'mono_channel': True,
            'normalize_audio': True,
        }
        
        # Adjust based on available memory
        if self.available_memory_gb < 4.0:
            logger.warning(f"Low memory detected: {self.available_memory_gb:.1f}GB available")
            config.update({
                'chunk_length_s': 15,  # Smaller chunks
                'max_batch_size': 1,
                'use_cpu_offload': True
            })
        
        return config
    
    def setup_cuda_optimizations(self):
        """Setup CUDA optimizations for Jetson"""
        if not torch.cuda.is_available():
            logger.info("CUDA not available, using CPU optimizations")
            return
        
        # Enable TensorRT optimizations if available
        try:
            torch.backends.cudnn.benchmark = True
            torch.backends.cudnn.deterministic = False
            logger.info("CUDA optimizations enabled")
        except Exception as e:
            logger.warning(f"Could not enable CUDA optimizations: {e}")
    
    def cleanup_memory(self):
        """Aggressive memory cleanup for Jetson"""
        try:
            if torch.cuda.is_available():
                torch.cuda.empty_cache()
                torch.cuda.ipc_collect()
            
            # Force garbage collection
            gc.collect()
            
            # Log memory usage
            if torch.cuda.is_available():
                cuda_info = self.get_cuda_memory_info()
                logger.info(f"CUDA Memory - Allocated: {cuda_info.get('allocated_gb', 0):.2f}GB, "
                           f"Cached: {cuda_info.get('cached_gb', 0):.2f}GB")
            
            logger.info(f"System Memory - Available: {self.get_available_memory():.2f}GB")
            
        except Exception as e:
            logger.error(f"Memory cleanup failed: {e}")
    
    def monitor_memory_usage(self) -> Dict[str, float]:
        """Monitor current memory usage"""
        usage = {
            'system_memory_used_gb': (self.total_memory_gb - self.get_available_memory()),
            'system_memory_percent': psutil.virtual_memory().percent
        }
        
        if torch.cuda.is_available():
            cuda_info = self.get_cuda_memory_info()
            usage.update(cuda_info)
        
        return usage
    
    def check_memory_pressure(self) -> bool:
        """Check if system is under memory pressure"""
        available_gb = self.get_available_memory()
        memory_percent = psutil.virtual_memory().percent
        
        # Consider memory pressure if less than 1GB available or >90% used
        pressure = available_gb < 1.0 or memory_percent > 90
        
        if pressure:
            logger.warning(f"Memory pressure detected - Available: {available_gb:.2f}GB, "
                          f"Used: {memory_percent:.1f}%")
        
        return pressure
    
    def get_optimal_workers(self) -> int:
        """Get optimal number of worker processes for Jetson"""
        # For audio processing, limit to 1-2 workers to avoid memory issues
        cpu_count = os.cpu_count() or 1
        memory_based = max(1, int(self.available_memory_gb / 2))  # 2GB per worker
        
        return min(2, cpu_count, memory_based)

# Global optimizer instance
jetson_optimizer = JetsonOptimizer()