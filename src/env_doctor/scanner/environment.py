"""
Environment scanner for detecting system configuration.

Detects Python version, CUDA version, GPU information, and installed packages.
"""

import json
import platform
import subprocess
import sys
from typing import Any, Dict, List, Optional

try:
    import pkg_resources
except ImportError:
    pkg_resources = None  # type: ignore


def get_python_version() -> str:
    """
    Get current Python version.
    
    Returns:
        Python version string (e.g., "3.10.5")
    """
    return platform.python_version()


def get_cuda_version() -> Optional[str]:
    """
    Detect CUDA version if available.
    
    Returns:
        CUDA version string (e.g., "12.1") or None if not available
        
    Note:
        Tries multiple detection methods:
        1. nvidia-smi command
        2. nvcc --version
        3. torch.version.cuda (if torch is installed)
    """
    # Method 1: Try nvidia-smi
    try:
        result = subprocess.run(
            ["nvidia-smi", "--query-gpu=driver_version", "--format=csv,noheader"],
            capture_output=True,
            text=True,
            timeout=5,
            check=False
        )
        if result.returncode == 0 and result.stdout.strip():
            # nvidia-smi found, now get CUDA version
            result = subprocess.run(
                ["nvidia-smi"],
                capture_output=True,
                text=True,
                timeout=5,
                check=False
            )
            if result.returncode == 0:
                # Parse CUDA version from nvidia-smi output
                for line in result.stdout.split('\n'):
                    if "CUDA Version:" in line:
                        parts = line.split("CUDA Version:")
                        if len(parts) > 1:
                            version = parts[1].strip().split()[0]
                            return version
    except (subprocess.TimeoutExpired, FileNotFoundError, Exception):
        pass
    
    # Method 2: Try nvcc
    try:
        result = subprocess.run(
            ["nvcc", "--version"],
            capture_output=True,
            text=True,
            timeout=5,
            check=False
        )
        if result.returncode == 0:
            # Parse version from nvcc output
            for line in result.stdout.split('\n'):
                if "release" in line.lower():
                    parts = line.split("release")
                    if len(parts) > 1:
                        version = parts[1].strip().split(',')[0].strip()
                        return version
    except (subprocess.TimeoutExpired, FileNotFoundError, Exception):
        pass
    
    # Method 3: Try torch.version.cuda
    try:
        import torch
        if torch.cuda.is_available():
            cuda_version = torch.version.cuda
            if cuda_version:
                return cuda_version
    except (ImportError, Exception):
        pass
    
    return None


def get_gpu_info() -> Optional[Dict[str, Any]]:
    """
    Get GPU information if available.
    
    Returns:
        Dictionary with GPU information or None if no GPU detected
        
    Example:
        {
            "count": 1,
            "gpus": [
                {
                    "name": "NVIDIA GeForce RTX 3090",
                    "memory_total": "24576 MiB",
                    "driver_version": "535.104.05"
                }
            ]
        }
    """
    try:
        # Try nvidia-smi with JSON output
        result = subprocess.run(
            [
                "nvidia-smi",
                "--query-gpu=name,memory.total,driver_version",
                "--format=csv,noheader"
            ],
            capture_output=True,
            text=True,
            timeout=5,
            check=False
        )
        
        if result.returncode == 0 and result.stdout.strip():
            gpus = []
            for line in result.stdout.strip().split('\n'):
                parts = [p.strip() for p in line.split(',')]
                if len(parts) >= 3:
                    gpus.append({
                        "name": parts[0],
                        "memory_total": parts[1],
                        "driver_version": parts[2]
                    })
            
            if gpus:
                return {
                    "count": len(gpus),
                    "gpus": gpus
                }
    except (subprocess.TimeoutExpired, FileNotFoundError, Exception):
        pass
    
    # Try torch as fallback
    try:
        import torch
        if torch.cuda.is_available():
            gpu_count = torch.cuda.device_count()
            gpus = []
            for i in range(gpu_count):
                props = torch.cuda.get_device_properties(i)
                gpus.append({
                    "name": props.name,
                    "memory_total": f"{props.total_memory / (1024**3):.2f} GiB",
                    "compute_capability": f"{props.major}.{props.minor}"
                })
            
            return {
                "count": gpu_count,
                "gpus": gpus
            }
    except (ImportError, Exception):
        pass
    
    return None


def get_installed_packages() -> List[Dict[str, str]]:
    """
    Get list of installed Python packages.
    
    Returns:
        List of dictionaries with package name and version
        
    Example:
        [
            {"name": "numpy", "version": "1.24.3"},
            {"name": "torch", "version": "2.0.1"},
            ...
        ]
    """
    packages = []
    
    try:
        # Use pkg_resources to get installed packages
        if pkg_resources is not None:
            for dist in pkg_resources.working_set:
                packages.append({
                    "name": dist.project_name,
                    "version": dist.version
                })
            
            # Sort by name for consistent output
            packages.sort(key=lambda x: x["name"].lower())
        else:
            raise ImportError("pkg_resources not available")
        
    except Exception:
        # Fallback to pip list if pkg_resources fails
        try:
            result = subprocess.run(
                [sys.executable, "-m", "pip", "list", "--format=json"],
                capture_output=True,
                text=True,
                timeout=30,
                check=False
            )
            
            if result.returncode == 0:
                packages = json.loads(result.stdout)
        except Exception:
            pass
    
    return packages


def get_platform_info() -> Dict[str, str]:
    """
    Get platform information.
    
    Returns:
        Dictionary with platform details
        
    Example:
        {
            "system": "Linux",
            "release": "5.15.0-76-generic",
            "machine": "x86_64",
            "processor": "x86_64"
        }
    """
    return {
        "system": platform.system(),
        "release": platform.release(),
        "machine": platform.machine(),
        "processor": platform.processor() or platform.machine()
    }


def get_full_environment_info() -> Dict[str, Any]:
    """
    Get complete environment information.
    
    Returns:
        Dictionary with all environment details
        
    Example:
        {
            "python_version": "3.10.5",
            "cuda_version": "12.1",
            "gpu_info": {...},
            "platform": {...},
            "packages": [...]
        }
    """
    return {
        "python_version": get_python_version(),
        "cuda_version": get_cuda_version(),
        "gpu_info": get_gpu_info(),
        "platform": get_platform_info(),
        "packages": get_installed_packages()
    }


# Made with Bob