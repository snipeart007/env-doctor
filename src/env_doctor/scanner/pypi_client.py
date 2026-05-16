"""
PyPI client for fetching package metadata.

Provides caching and rate limiting for PyPI JSON API requests.
"""

import json
import time
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional

import httpx


class PyPIClient:
    """
    Client for fetching package metadata from PyPI JSON API.
    
    Features:
    - File-based caching with TTL
    - Rate limiting with exponential backoff
    - Graceful error handling
    - Connection pooling
    """
    
    def __init__(
        self,
        cache_dir: Optional[str] = None,
        cache_ttl: int = 86400,
        timeout: float = 30.0
    ) -> None:
        """
        Initialize PyPI client.
        
        Args:
            cache_dir: Cache directory path. Defaults to ~/.cache/env-doctor/pypi/
            cache_ttl: Cache time-to-live in seconds. Default: 24 hours (86400)
            timeout: HTTP request timeout in seconds. Default: 30.0
        """
        if cache_dir is None:
            cache_dir = str(Path.home() / ".cache" / "env-doctor" / "pypi")
        
        self.cache_dir = Path(cache_dir)
        self.cache_ttl = cache_ttl
        self.timeout = timeout
        
        # Create cache directory if it doesn't exist
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        
        # Initialize HTTP client with connection pooling
        self.client = httpx.Client(
            timeout=timeout,
            follow_redirects=True,
            limits=httpx.Limits(max_keepalive_connections=5, max_connections=10)
        )
    
    def _get_cache_path(self, package_name: str) -> Path:
        """
        Get cache file path for a package.
        
        Args:
            package_name: Package name
            
        Returns:
            Path to cache file
        """
        # Normalize package name (PyPI is case-insensitive)
        normalized = package_name.lower().replace("_", "-")
        return self.cache_dir / f"{normalized}.json"
    
    def _is_cache_valid(self, cache_path: Path) -> bool:
        """
        Check if cache file is valid (exists and not expired).
        
        Args:
            cache_path: Path to cache file
            
        Returns:
            True if cache is valid, False otherwise
        """
        if not cache_path.exists():
            return False
        
        try:
            with open(cache_path, "r", encoding="utf-8") as f:
                cache_data = json.load(f)
            
            # Check if cache has timestamp
            if "cached_at" not in cache_data:
                return False
            
            # Check if cache is expired
            cached_at = datetime.fromisoformat(cache_data["cached_at"])
            expiry = cached_at + timedelta(seconds=self.cache_ttl)
            
            return datetime.utcnow() < expiry
        except (json.JSONDecodeError, KeyError, ValueError):
            return False
        
        return False
    
    def _read_cache(self, cache_path: Path) -> Optional[Dict[str, Any]]:
        """
        Read metadata from cache.
        
        Args:
            cache_path: Path to cache file
            
        Returns:
            Cached metadata or None if invalid
        """
        try:
            with open(cache_path, "r", encoding="utf-8") as f:
                cache_data = json.load(f)
            return cache_data.get("metadata")
        except (json.JSONDecodeError, FileNotFoundError):
            return None
    
    def _write_cache(self, cache_path: Path, metadata: Dict[str, Any]) -> None:
        """
        Write metadata to cache.
        
        Args:
            cache_path: Path to cache file
            metadata: Package metadata to cache
        """
        cache_data = {
            "cached_at": datetime.utcnow().isoformat(),
            "metadata": metadata
        }
        
        with open(cache_path, "w", encoding="utf-8") as f:
            json.dump(cache_data, f, indent=2)
    
    def fetch_package_metadata(
        self,
        package_name: str,
        use_cache: bool = True
    ) -> Dict[str, Any]:
        """
        Fetch package metadata from PyPI.
        
        Args:
            package_name: Package name (e.g., "torch")
            use_cache: Whether to use cache. Default: True
            
        Returns:
            Package metadata dictionary
            
        Raises:
            httpx.HTTPStatusError: If package not found or API error
            httpx.RequestError: If network error occurs
            
        Example:
            >>> client = PyPIClient()
            >>> metadata = client.fetch_package_metadata("torch")
            >>> print(metadata["info"]["version"])
            '2.1.0'
        """
        cache_path = self._get_cache_path(package_name)
        
        # Check cache first
        if use_cache and self._is_cache_valid(cache_path):
            cached = self._read_cache(cache_path)
            if cached is not None:
                return cached
        
        # Fetch from PyPI with retry logic
        url = f"https://pypi.org/pypi/{package_name}/json"
        max_retries = 3
        base_delay = 1.0
        
        for attempt in range(max_retries):
            try:
                response = self.client.get(url)
                response.raise_for_status()
                
                metadata = response.json()
                
                # Cache the response
                if use_cache:
                    self._write_cache(cache_path, metadata)
                
                return metadata
                
            except httpx.HTTPStatusError as e:
                if e.response.status_code == 429:  # Rate limited
                    if attempt < max_retries - 1:
                        # Exponential backoff
                        delay = base_delay * (2 ** attempt)
                        time.sleep(delay)
                        continue
                raise
            except httpx.RequestError:
                if attempt < max_retries - 1:
                    delay = base_delay * (2 ** attempt)
                    time.sleep(delay)
                    continue
                raise
        
        # Should not reach here, but just in case
        raise httpx.RequestError(f"Failed to fetch metadata for {package_name} after {max_retries} attempts")
    
    def get_package_versions(self, package_name: str) -> List[str]:
        """
        Get all available versions for a package.
        
        Args:
            package_name: Package name
            
        Returns:
            List of version strings, sorted from oldest to newest
            
        Example:
            >>> client = PyPIClient()
            >>> versions = client.get_package_versions("torch")
            >>> print(versions[-1])  # Latest version
            '2.1.0'
        """
        metadata = self.fetch_package_metadata(package_name)
        
        # Extract versions from releases
        versions = list(metadata.get("releases", {}).keys())
        
        # Sort versions (simple string sort, could use packaging.version for proper sorting)
        versions.sort()
        
        return versions
    
    def get_latest_version(
        self,
        package_name: str,
        exclude_prerelease: bool = True
    ) -> str:
        """
        Get the latest stable version of a package.
        
        Args:
            package_name: Package name
            exclude_prerelease: Whether to exclude pre-release versions. Default: True
            
        Returns:
            Latest version string
            
        Example:
            >>> client = PyPIClient()
            >>> latest = client.get_latest_version("torch")
            >>> print(latest)
            '2.1.0'
        """
        metadata = self.fetch_package_metadata(package_name)
        
        # Get latest version from info
        latest = metadata.get("info", {}).get("version", "")
        
        if exclude_prerelease:
            # Check if it's a pre-release
            prerelease_markers = ["a", "b", "rc", "dev", "alpha", "beta"]
            if any(marker in latest.lower() for marker in prerelease_markers):
                # Fall back to releases and find latest stable
                versions = self.get_package_versions(package_name)
                for version in reversed(versions):
                    if not any(marker in version.lower() for marker in prerelease_markers):
                        return version
        
        return latest
    
    def clear_cache(self, package_name: Optional[str] = None) -> None:
        """
        Clear cache for specific package or all packages.
        
        Args:
            package_name: Package name to clear cache for. If None, clears all cache.
            
        Example:
            >>> client = PyPIClient()
            >>> client.clear_cache("torch")  # Clear torch cache
            >>> client.clear_cache()  # Clear all cache
        """
        if package_name is None:
            # Clear all cache
            for cache_file in self.cache_dir.glob("*.json"):
                cache_file.unlink()
        else:
            # Clear specific package cache
            cache_path = self._get_cache_path(package_name)
            if cache_path.exists():
                cache_path.unlink()
    
    def close(self) -> None:
        """Close HTTP client and cleanup resources."""
        self.client.close()
    
    def __enter__(self) -> "PyPIClient":
        """Context manager entry."""
        return self
    
    def __exit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        """Context manager exit - cleanup resources."""
        self.close()


# Made with Bob