import os
import gc
import torch
import psutil
import logging
from typing import Dict, Any, List
from dataclasses import dataclass
import torch.distributed as dist

logger = logging.getLogger(__name__)

@dataclass
class GPUInfo:
    """Information about a GPU device"""
    index: int
    name: str
    total_memory_gb: float
    compute_capability: tuple
    is_available: bool = True

class HardwareOptimizer:
    """Hardware optimization for high-performance x86_64 systems with multi-GPU support"""
    
    def __init__(self):
        self.total_system_memory_gb = self.get_total_memory()
        self.available_system_memory_gb = self.get_available_memory()
        self.gpu_devices = self.detect_gpus()
        self.cpu_count = os.cpu_count() or 1
        
        logger.info(f"System: {self.cpu_count} CPU cores, {self.total_system_memory_gb:.1f}GB RAM")
        logger.info(f"GPUs detected: {len(self.gpu_devices)}")
        for gpu in self.gpu_devices:
            logger.info(f"  GPU {gpu.index}: {gpu.name} ({gpu.total_memory_gb:.1f}GB)")
    
    def get_total_memory(self) -> float:
        """Get total system memory in GB"""
        return psutil.virtual_memory().total / (1024**3)
    
    def get_available_memory(self) -> float:
        """Get available system memory in GB"""
        return psutil.virtual_memory().available / (1024**3)
    
    def detect_gpus(self) -> List[GPUInfo]:
        """Detect available GPU devices"""
        gpus = []
        if not torch.cuda.is_available():
            logger.warning("CUDA not available")
            return gpus
        
        gpu_count = torch.cuda.device_count()
        logger.info(f"Detected {gpu_count} CUDA devices")
        
        for i in range(gpu_count):
            try:
                props = torch.cuda.get_device_properties(i)
                gpu = GPUInfo(
                    index=i,
                    name=props.name,
                    total_memory_gb=props.total_memory / (1024**3),
                    compute_capability=(props.major, props.minor)
                )
                gpus.append(gpu)
                logger.info(f"GPU {i}: {gpu.name} - {gpu.total_memory_gb:.1f}GB - Compute {gpu.compute_capability}")
            except Exception as e:
                logger.warning(f"Failed to get info for GPU {i}: {e}")
        
        return gpus
    
    def get_cuda_memory_info(self, device_id: int = 0) -> Dict[str, float]:
        """Get CUDA memory information for specific device"""
        if not torch.cuda.is_available() or device_id >= len(self.gpu_devices):
            return {}
        
        try:
            torch.cuda.set_device(device_id)
            return {
                'device_id': device_id,
                'total_gb': torch.cuda.get_device_properties(device_id).total_memory / (1024**3),
                'allocated_gb': torch.cuda.memory_allocated(device_id) / (1024**3),
                'cached_gb': torch.cuda.memory_reserved(device_id) / (1024**3),
                'free_gb': (torch.cuda.get_device_properties(device_id).total_memory - 
                           torch.cuda.memory_reserved(device_id)) / (1024**3)
            }
        except Exception as e:
            logger.error(f"Failed to get CUDA memory info for device {device_id}: {e}")
            return {}
    
    def optimize_for_hardware(self) -> Dict[str, Any]:
        """Get optimal configuration for high-performance hardware"""
        
        # Base configuration for powerful hardware
        config = {
            # Memory optimizations - much more aggressive with 128GB RAM
            'torch_dtype': torch.float16,  # Use FP16 for speed
            'device_map': 'auto',
            'low_cpu_mem_usage': False,  # We have plenty of RAM
            'use_cache': True,
            
            # Model optimizations - can handle larger batches
            'max_batch_size': 8 if len(self.gpu_devices) >= 2 else 4,
            'chunk_length_s': 60,  # Larger chunks with powerful GPUs
            'overlap_length_s': 5,  # More overlap for better accuracy
            
            # Memory management - liberal with 128GB RAM
            'clear_cache_after_inference': False,  # Keep models in memory
            'force_gc_after_inference': False,
            'max_memory_usage_gb': min(100.0, self.total_system_memory_gb * 0.8),
            
            # Audio processing
            'target_sample_rate': 16000,
            'mono_channel': True,
            'normalize_audio': True,
            
            # Multi-GPU configuration
            'use_multi_gpu': len(self.gpu_devices) > 1,
            'gpu_devices': [gpu.index for gpu in self.gpu_devices],
            'primary_gpu': 0,
            'secondary_gpu': 1 if len(self.gpu_devices) > 1 else None,
            
            # Performance optimizations
            'enable_mixed_precision': True,
            'use_torch_compile': True,  # PyTorch 2.0+ compilation
            'dataloader_num_workers': min(8, self.cpu_count // 2),
            'pin_memory': True,
            'non_blocking': True,
            
            # Parallel processing
            'max_concurrent_jobs': min(6, len(self.gpu_devices) * 3),
            'worker_processes': min(8, self.cpu_count // 2),
        }
        
        # GPU-specific optimizations
        if self.gpu_devices:
            total_vram = sum(gpu.total_memory_gb for gpu in self.gpu_devices)
            config.update({
                'total_vram_gb': total_vram,
                'vram_per_gpu': [gpu.total_memory_gb for gpu in self.gpu_devices],
                'max_model_size_gb': min(16.0, total_vram * 0.7),  # Use up to 70% of total VRAM
            })
            
            # Dual RTX 3080 specific optimizations
            if len(self.gpu_devices) == 2 and all('RTX 3080' in gpu.name for gpu in self.gpu_devices):
                logger.info("Optimizing for dual RTX 3080 setup")
                config.update({
                    'batch_size_per_gpu': 4,
                    'model_parallel': True,
                    'gradient_checkpointing': False,  # We have enough VRAM
                    'max_sequence_length': 8192,  # Longer sequences
                    'use_flash_attention': True,
                })
        
        # Adjust for available system memory
        available_gb = self.get_available_memory()
        if available_gb > 64.0:  # Plenty of RAM
            logger.info(f"High memory system detected: {available_gb:.1f}GB available")
            config.update({
                'preload_models': True,
                'cache_preprocessed_audio': True,
                'large_batch_processing': True,
                'chunk_length_s': 120,  # Even larger chunks
            })
        
        return config
    
    def setup_multi_gpu(self) -> bool:
        """Setup multi-GPU configuration"""
        if len(self.gpu_devices) < 2:
            logger.info("Single GPU detected, multi-GPU disabled")
            return False
        
        try:
            # Initialize distributed processing if not already done
            if not dist.is_initialized() and torch.cuda.is_available():
                logger.info("Setting up multi-GPU distributed processing")
                # Note: Full distributed setup would require process launching
                # For now, we'll use DataParallel which is simpler for inference
                return True
                
        except Exception as e:
            logger.warning(f"Multi-GPU setup failed: {e}")
            return False
        
        return len(self.gpu_devices) > 1
    
    def setup_cuda_optimizations(self):
        """Setup CUDA optimizations for RTX 3080"""
        if not torch.cuda.is_available():
            logger.info("CUDA not available, using CPU optimizations")
            return
        
        try:
            # RTX 3080 (Ampere) optimizations
            torch.backends.cudnn.benchmark = True
            torch.backends.cudnn.deterministic = False
            torch.backends.cudnn.allow_tf32 = True  # Enable TF32 for Ampere
            torch.backends.cuda.matmul.allow_tf32 = True
            
            # Enable memory optimization
            torch.cuda.empty_cache()
            
            # Set memory fraction per GPU (use 90% of each GPU)
            for gpu in self.gpu_devices:
                torch.cuda.set_per_process_memory_fraction(0.9, gpu.index)
            
            logger.info("CUDA optimizations enabled for RTX 3080")
            logger.info(f"TF32 enabled: {torch.backends.cuda.matmul.allow_tf32}")
            
        except Exception as e:
            logger.warning(f"Could not enable CUDA optimizations: {e}")
    
    def cleanup_memory(self, device_id: int = None):
        """Memory cleanup for specific GPU or all GPUs"""
        try:
            if torch.cuda.is_available():
                if device_id is not None:
                    torch.cuda.set_device(device_id)
                    torch.cuda.empty_cache()
                    torch.cuda.ipc_collect()
                else:
                    # Clean all GPUs
                    for gpu in self.gpu_devices:
                        torch.cuda.set_device(gpu.index)
                        torch.cuda.empty_cache()
                        torch.cuda.ipc_collect()
            
            # Light garbage collection (we have plenty of RAM)
            gc.collect()
            
            # Log memory usage
            for i, gpu in enumerate(self.gpu_devices):
                cuda_info = self.get_cuda_memory_info(i)
                logger.debug(f"GPU {i} Memory - Allocated: {cuda_info.get('allocated_gb', 0):.2f}GB, "
                           f"Free: {cuda_info.get('free_gb', 0):.2f}GB")
            
        except Exception as e:
            logger.error(f"Memory cleanup failed: {e}")
    
    def monitor_memory_usage(self) -> Dict[str, Any]:
        """Monitor current memory usage across all devices"""
        usage = {
            'system_memory_used_gb': (self.total_system_memory_gb - self.get_available_memory()),
            'system_memory_percent': psutil.virtual_memory().percent,
            'system_memory_available_gb': self.get_available_memory(),
            'gpu_memory': {}
        }
        
        for gpu in self.gpu_devices:
            cuda_info = self.get_cuda_memory_info(gpu.index)
            if cuda_info:
                usage['gpu_memory'][f'gpu_{gpu.index}'] = cuda_info
        
        return usage
    
    def check_memory_pressure(self) -> Dict[str, bool]:
        """Check if system is under memory pressure"""
        available_gb = self.get_available_memory()
        memory_percent = psutil.virtual_memory().percent
        
        # With 128GB RAM, pressure only if less than 8GB available or >95% used
        system_pressure = available_gb < 8.0 or memory_percent > 95
        
        gpu_pressure = {}
        for gpu in self.gpu_devices:
            cuda_info = self.get_cuda_memory_info(gpu.index)
            if cuda_info:
                # GPU pressure if less than 1GB free
                gpu_pressure[f'gpu_{gpu.index}'] = cuda_info.get('free_gb', 0) < 1.0
        
        if system_pressure:
            logger.warning(f"System memory pressure - Available: {available_gb:.2f}GB, "
                          f"Used: {memory_percent:.1f}%")
        
        for gpu_id, pressure in gpu_pressure.items():
            if pressure:
                logger.warning(f"{gpu_id} under memory pressure")
        
        return {
            'system': system_pressure,
            'gpus': gpu_pressure
        }
    
    def get_optimal_workers(self) -> int:
        """Get optimal number of worker processes for high-performance system"""
        # With 128GB RAM and dual GPUs, we can be aggressive
        cpu_based = min(8, self.cpu_count // 2)  # Use half the cores
        memory_based = max(4, int(self.available_system_memory_gb / 16))  # 16GB per worker
        gpu_based = len(self.gpu_devices) * 4  # 4 workers per GPU
        
        optimal = min(cpu_based, memory_based, gpu_based)
        logger.info(f"Optimal workers: {optimal} (CPU: {cpu_based}, Memory: {memory_based}, GPU: {gpu_based})")
        return optimal
    
    def get_device_for_job(self, job_id: str = None) -> int:
        """Get optimal GPU device for a job (load balancing)"""
        if not self.gpu_devices:
            return -1  # CPU
        
        if len(self.gpu_devices) == 1:
            return 0
        
        # Simple round-robin for now
        # In production, you might want to check actual GPU utilization
        job_hash = hash(job_id) if job_id else 0
        return job_hash % len(self.gpu_devices)

# Global optimizer instance
hardware_optimizer = HardwareOptimizer()