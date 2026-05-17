"""
Deterministic UID generation for database entities.

All UIDs are generated using SHA-256 hashing to ensure:
- Deterministic: Same input always produces same UID
- Collision-resistant: Extremely low probability of duplicates
- Reproducible: Can regenerate UIDs from source data
"""

import hashlib
from typing import Optional


def _hash_string(data: str) -> str:
    """
    Generate a deterministic UID from a string using SHA-256.
    
    Args:
        data: Input string to hash
        
    Returns:
        First 16 characters of SHA-256 hex digest
    """
    return hashlib.sha256(data.encode("utf-8")).hexdigest()[:16]


def generate_package_uid(name: str) -> str:
    """
    Generate deterministic UID for a package.
    
    Args:
        name: Package name (e.g., "torch")
        
    Returns:
        16-character UID
        
    Example:
        >>> generate_package_uid("torch")
        'a1b2c3d4e5f6g7h8'
    """
    canonical = f"package:{name.lower()}"
    return _hash_string(canonical)


def generate_version_uid(name: str, version: str) -> str:
    """
    Generate deterministic UID for a package version.
    
    Args:
        name: Package name (e.g., "torch")
        version: Version string (e.g., "2.1.0")
        
    Returns:
        16-character UID
        
    Example:
        >>> generate_version_uid("torch", "2.1.0")
        'x1y2z3a4b5c6d7e8'
    """
    canonical = f"version:{name.lower()}:{version}"
    return _hash_string(canonical)


def generate_dependency_uid(pkg: str, ver: str, dep: str) -> str:
    """
    Generate deterministic UID for a package dependency.
    
    Args:
        pkg: Package name (e.g., "torch")
        ver: Package version (e.g., "2.1.0")
        dep: Dependency name (e.g., "numpy")
        
    Returns:
        16-character UID
        
    Example:
        >>> generate_dependency_uid("torch", "2.1.0", "numpy")
        'p1q2r3s4t5u6v7w8'
    """
    canonical = f"dependency:{pkg.lower()}:{ver}:{dep.lower()}"
    return _hash_string(canonical)


def generate_compatibility_uid(
    pkg: str,
    pkg_range: str,
    dep: str,
    dep_range: str,
    cuda_ver: Optional[str] = None,
    env_sys: Optional[str] = None,
) -> str:
    """
    Generate deterministic UID for a compatibility rule.
    
    Args:
        pkg: Package name (e.g., "torch")
        pkg_range: Package version range (e.g., ">=2.0,<2.2")
        dep: Dependency name (e.g., "transformers")
        dep_range: Dependency version range (e.g., ">=4.30")
        cuda_ver: Target CUDA version (e.g., "12.1")
        env_sys: Environment system/OS info
        
    Returns:
        16-character UID
    """
    cuda_part = f":{cuda_ver}" if cuda_ver else ""
    env_part = f":{env_sys}" if env_sys else ""
    canonical = f"compat:{pkg.lower()}:{pkg_range}:{dep.lower()}:{dep_range}{cuda_part}{env_part}"
    return _hash_string(canonical)


def generate_stack_uid(
    name: str, cuda_ver: Optional[str], env_sys: Optional[str] = None
) -> str:
    """
    Generate deterministic UID for a stable stack.
    
    Args:
        name: Stack name (e.g., "torch-2.1-transformers-4.38")
        cuda_ver: CUDA version (e.g., "11.8") or None
        env_sys: Environment system/OS info
        
    Returns:
        16-character UID
    """
    cuda_part = f":{cuda_ver}" if cuda_ver else ""
    env_part = f":{env_sys}" if env_sys else ""
    canonical = f"stack:{name.lower()}{cuda_part}{env_part}"
    return _hash_string(canonical)


def generate_wheel_uid(pkg: str, ver: str, py_tag: str, platform_tag: str) -> str:
    """
    Generate deterministic UID for wheel availability.
    
    Args:
        pkg: Package name (e.g., "torch")
        ver: Version string (e.g., "2.1.0")
        py_tag: Python tag (e.g., "cp310")
        platform_tag: Platform tag (e.g., "win_amd64")
        
    Returns:
        16-character UID
        
    Example:
        >>> generate_wheel_uid("torch", "2.1.0", "cp310", "win_amd64")
        'c1d2e3f4g5h6i7j8'
    """
    canonical = f"wheel:{pkg.lower()}:{ver}:{py_tag}:{platform_tag}"
    return _hash_string(canonical)


def generate_runtime_uid(runtime: str) -> str:
    """
    Generate deterministic UID for a runtime profile.
    
    Args:
        runtime: Runtime name (e.g., "transformers", "vllm")
        
    Returns:
        16-character UID
        
    Example:
        >>> generate_runtime_uid("transformers")
        'k1l2m3n4o5p6q7r8'
    """
    canonical = f"runtime:{runtime.lower()}"
    return _hash_string(canonical)

# Made with Bob
