"""
GPU detection module for identifying available GPUs and their VRAM capacity.

Supports NVIDIA GPUs via nvidia-ml-py (preferred) or nvidia-smi fallback.
Provides information about VRAM capacity and current usage.
"""

import subprocess
import re
from dataclasses import dataclass
from typing import List, Optional
import platform


@dataclass
class GPUInfo:
    """Information about a detected GPU."""
    
    index: int
    name: str
    total_memory_mb: int
    used_memory_mb: int
    free_memory_mb: int
    driver_version: Optional[str] = None
    cuda_version: Optional[str] = None
    
    @property
    def total_memory_gb(self) -> float:
        """Total memory in GB."""
        return self.total_memory_mb / 1024.0
    
    @property
    def used_memory_gb(self) -> float:
        """Used memory in GB."""
        return self.used_memory_mb / 1024.0
    
    @property
    def free_memory_gb(self) -> float:
        """Free memory in GB."""
        return self.free_memory_mb / 1024.0
    
    @property
    def utilization_percent(self) -> float:
        """Memory utilization percentage."""
        if self.total_memory_mb == 0:
            return 0.0
        return (self.used_memory_mb / self.total_memory_mb) * 100.0


class GPUDetector:
    """Detects available GPUs and queries their specifications."""
    
    def __init__(self) -> None:
        """Initialize GPU detector."""
        self._pynvml_available = False
        self._nvml_initialized = False
        
        # Try to import and initialize pynvml
        try:
            import pynvml
            self._pynvml = pynvml
            self._pynvml.nvmlInit()
            self._pynvml_available = True
            self._nvml_initialized = True
        except (ImportError, Exception):
            self._pynvml = None
            self._pynvml_available = False
    
    def __del__(self) -> None:
        """Cleanup NVML if initialized."""
        if self._nvml_initialized and self._pynvml:
            try:
                self._pynvml.nvmlShutdown()
            except Exception:
                pass
    
    def detect_gpus(self) -> List[GPUInfo]:
        """
        Detect all available GPUs.
        
        Returns:
            List of GPUInfo objects, empty list if no GPUs found
        """
        if self._pynvml_available:
            return self._detect_with_pynvml()
        else:
            return self._detect_with_nvidia_smi()
    
    def get_gpu(self, index: int = 0) -> Optional[GPUInfo]:
        """
        Get information about a specific GPU.
        
        Args:
            index: GPU index (0-based)
            
        Returns:
            GPUInfo if GPU exists, None otherwise
        """
        gpus = self.detect_gpus()
        if 0 <= index < len(gpus):
            return gpus[index]
        return None
    
    def _detect_with_pynvml(self) -> List[GPUInfo]:
        """Detect GPUs using pynvml library."""
        gpus = []
        
        try:
            device_count = self._pynvml.nvmlDeviceGetCount()
            driver_version = self._pynvml.nvmlSystemGetDriverVersion()
            
            for i in range(device_count):
                handle = self._pynvml.nvmlDeviceGetHandleByIndex(i)
                name = self._pynvml.nvmlDeviceGetName(handle)
                
                # Get memory info
                mem_info = self._pynvml.nvmlDeviceGetMemoryInfo(handle)
                total_mb = mem_info.total // (1024 * 1024)
                used_mb = mem_info.used // (1024 * 1024)
                free_mb = mem_info.free // (1024 * 1024)
                
                # Try to get CUDA version
                cuda_version = None
                try:
                    cuda_version = self._pynvml.nvmlSystemGetCudaDriverVersion()
                    if cuda_version:
                        major = cuda_version // 1000
                        minor = (cuda_version % 1000) // 10
                        cuda_version = f"{major}.{minor}"
                except Exception:
                    pass
                
                # Decode name if bytes
                if isinstance(name, bytes):
                    name = name.decode('utf-8')
                if isinstance(driver_version, bytes):
                    driver_version = driver_version.decode('utf-8')
                
                gpus.append(GPUInfo(
                    index=i,
                    name=name,
                    total_memory_mb=total_mb,
                    used_memory_mb=used_mb,
                    free_memory_mb=free_mb,
                    driver_version=driver_version,
                    cuda_version=cuda_version
                ))
                
        except Exception:
            # Fall back to nvidia-smi if pynvml fails
            return self._detect_with_nvidia_smi()
        
        return gpus
    
    def _detect_with_nvidia_smi(self) -> List[GPUInfo]:
        """Detect GPUs using nvidia-smi command."""
        gpus = []
        
        try:
            # Try to run nvidia-smi
            cmd = [
                'nvidia-smi',
                '--query-gpu=index,name,memory.total,memory.used,memory.free,driver_version',
                '--format=csv,noheader,nounits'
            ]
            
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=5,
                check=False
            )
            
            if result.returncode != 0:
                return []
            
            # Parse output
            for line in result.stdout.strip().split('\n'):
                if not line.strip():
                    continue
                
                parts = [p.strip() for p in line.split(',')]
                if len(parts) < 6:
                    continue
                
                try:
                    index = int(parts[0])
                    name = parts[1]
                    total_mb = int(float(parts[2]))
                    used_mb = int(float(parts[3]))
                    free_mb = int(float(parts[4]))
                    driver_version = parts[5]
                    
                    gpus.append(GPUInfo(
                        index=index,
                        name=name,
                        total_memory_mb=total_mb,
                        used_memory_mb=used_mb,
                        free_memory_mb=free_mb,
                        driver_version=driver_version
                    ))
                except (ValueError, IndexError):
                    continue
            
        except (subprocess.TimeoutExpired, FileNotFoundError, Exception):
            # nvidia-smi not available or failed
            pass
        
        return gpus
    
    def is_cuda_available(self) -> bool:
        """Check if CUDA is available."""
        gpus = self.detect_gpus()
        return len(gpus) > 0
    
    def get_total_vram_gb(self) -> float:
        """
        Get total VRAM across all GPUs in GB.
        
        Returns:
            Total VRAM in GB, 0.0 if no GPUs
        """
        gpus = self.detect_gpus()
        return sum(gpu.total_memory_gb for gpu in gpus)
    
    def get_free_vram_gb(self, gpu_index: Optional[int] = None) -> float:
        """
        Get free VRAM in GB.
        
        Args:
            gpu_index: Specific GPU index, or None for total across all GPUs
            
        Returns:
            Free VRAM in GB
        """
        if gpu_index is not None:
            gpu = self.get_gpu(gpu_index)
            return gpu.free_memory_gb if gpu else 0.0
        
        gpus = self.detect_gpus()
        return sum(gpu.free_memory_gb for gpu in gpus)
    
    def get_recommended_gpu(self, required_vram_gb: float) -> Optional[GPUInfo]:
        """
        Get the best GPU for a given VRAM requirement.
        
        Prefers GPUs with enough free memory, then falls back to
        GPUs with enough total memory.
        
        Args:
            required_vram_gb: Required VRAM in GB
            
        Returns:
            Best matching GPU or None
        """
        gpus = self.detect_gpus()
        if not gpus:
            return None
        
        # First, try to find a GPU with enough free memory
        suitable_gpus = [gpu for gpu in gpus if gpu.free_memory_gb >= required_vram_gb]
        if suitable_gpus:
            # Return the one with most free memory
            return max(suitable_gpus, key=lambda g: g.free_memory_gb)
        
        # Fall back to GPU with enough total memory
        suitable_gpus = [gpu for gpu in gpus if gpu.total_memory_gb >= required_vram_gb]
        if suitable_gpus:
            # Return the one with most total memory
            return max(suitable_gpus, key=lambda g: g.total_memory_gb)
        
        # No suitable GPU, return the largest one
        return max(gpus, key=lambda g: g.total_memory_gb)

# Made with Bob
