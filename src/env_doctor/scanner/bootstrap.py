"""
Database bootstrap module for populating PyPI metadata.

Fetches package metadata from PyPI and populates the database.
"""

import concurrent.futures
from datetime import datetime
from typing import Any, Callable, Dict, List, Optional

from ..database.manager import DatabaseManager
from ..database.models import Package, PackageDependency, PackageVersion, WheelAvailability
from ..database.uid_generator import (
    generate_dependency_uid,
    generate_package_uid,
    generate_version_uid,
    generate_wheel_uid,
)
from .dependency_parser import DependencyParser
from .pypi_client import PyPIClient
from .wheel_extractor import WheelExtractor


class DatabaseBootstrap:
    """
    Bootstrap database with PyPI metadata.
    
    Fetches package information from PyPI and populates database tables
    with packages, versions, dependencies, and wheel availability.
    """
    
    def __init__(
        self,
        db_manager: DatabaseManager,
        pypi_client: Optional[PyPIClient] = None
    ) -> None:
        """
        Initialize database bootstrap.
        
        Args:
            db_manager: Database manager instance
            pypi_client: Optional PyPI client. Creates new one if not provided.
        """
        self.db_manager = db_manager
        self.pypi_client = pypi_client or PyPIClient()
        self.dependency_parser = DependencyParser()
        self.wheel_extractor = WheelExtractor()
    
    def bootstrap_package(
        self,
        package_name: str,
        progress_callback: Optional[Callable[[str], None]] = None
    ) -> None:
        """
        Bootstrap a single package into the database.
        
        Fetches metadata from PyPI and populates:
        - Package table
        - PackageVersion table
        - PackageDependency table
        - WheelAvailability table
        
        Args:
            package_name: Package name (e.g., "torch")
            progress_callback: Optional callback for progress updates
            
        Raises:
            Exception: If package fetch or database operation fails
            
        Example:
            >>> manager = DatabaseManager("~/.cache/env-doctor/db.sqlite")
            >>> bootstrap = DatabaseBootstrap(manager)
            >>> bootstrap.bootstrap_package("torch")
        """
        if progress_callback:
            progress_callback(f"Fetching metadata for {package_name}...")
        
        try:
            # Fetch metadata from PyPI
            metadata = self.pypi_client.fetch_package_metadata(package_name)
            
            if progress_callback:
                progress_callback(f"Processing {package_name}...")
            
            # Use transaction for atomicity
            with self.db_manager.get_session() as session:
                # 1. Create/update Package record
                package_uid = generate_package_uid(package_name)
                package = session.get(Package, package_uid)
                
                if package is None:
                    package = Package(
                        uid=package_uid,
                        name=package_name,
                        ecosystem="python",
                        created_at=datetime.utcnow(),
                        updated_at=datetime.utcnow()
                    )
                    session.add(package)
                else:
                    package.updated_at = datetime.utcnow()
                
                # 2. Process all versions
                releases = metadata.get("releases", {})
                version_count = 0
                
                for version, files in releases.items():
                    # Skip empty releases
                    if not files:
                        continue
                    
                    version_uid = generate_version_uid(package_name, version)
                    
                    # Check if version already exists
                    existing_version = session.get(PackageVersion, version_uid)
                    if existing_version:
                        continue  # Skip already processed versions
                    
                    # Extract release date from first file
                    release_date = None
                    if files and "upload_time_iso_8601" in files[0]:
                        try:
                            release_date = datetime.fromisoformat(
                                files[0]["upload_time_iso_8601"].replace("Z", "+00:00")
                            )
                        except (ValueError, KeyError):
                            pass
                    
                    # Get requires_python for this version
                    requires_python = None
                    info = metadata.get("info", {})
                    if info.get("version") == version:
                        requires_python = self.dependency_parser.parse_requires_python(
                            info.get("requires_python")
                        )
                    
                    # Create PackageVersion record
                    package_version = PackageVersion(
                        uid=version_uid,
                        package_uid=package_uid,
                        version=version,
                        requires_python=requires_python or None,
                        release_date=release_date,
                        created_at=datetime.utcnow()
                    )
                    session.add(package_version)
                    version_count += 1
                    
                    # 3. Process dependencies for this version
                    # Note: PyPI only provides requires_dist for the latest version
                    # For other versions, we'd need to download and parse metadata
                    if info.get("version") == version:
                        self._process_dependencies(
                            session,
                            package_name,
                            version,
                            version_uid,
                            metadata
                        )
                    
                    # 4. Process wheel availability
                    self._process_wheels(
                        session,
                        package_name,
                        version,
                        version_uid,
                        files
                    )
                
                if progress_callback:
                    progress_callback(
                        f"Completed {package_name}: {version_count} versions processed"
                    )
                
        except Exception as e:
            if progress_callback:
                progress_callback(f"Error processing {package_name}: {str(e)}")
            raise
    
    def _process_dependencies(
        self,
        session: Any,
        package_name: str,
        version: str,
        version_uid: str,
        metadata: Dict[str, Any]
    ) -> None:
        """
        Process and store dependencies for a package version.
        
        Args:
            session: Database session
            package_name: Package name
            version: Version string
            version_uid: Version UID
            metadata: PyPI metadata
        """
        # Extract dependencies
        dependencies = self.dependency_parser.extract_dependencies(metadata)
        
        # Process all dependency groups
        for extra_group, deps in dependencies.items():
            for dep in deps:
                dep_uid = generate_dependency_uid(
                    package_name,
                    version,
                    dep["name"]
                )
                
                # Check if dependency already exists
                existing_dep = session.get(PackageDependency, dep_uid)
                if existing_dep:
                    continue
                
                # Create PackageDependency record
                package_dep = PackageDependency(
                    uid=dep_uid,
                    package_version_uid=version_uid,
                    dependency_name=dep["name"],
                    version_specifier=dep["specifier"] or "",
                    extra=extra_group if extra_group != "main" else None,
                    created_at=datetime.utcnow()
                )
                session.add(package_dep)
    
    def _process_wheels(
        self,
        session: Any,
        package_name: str,
        version: str,
        version_uid: str,
        files: List[Dict[str, Any]]
    ) -> None:
        """
        Process and store wheel availability for a package version.
        
        Args:
            session: Database session
            package_name: Package name
            version: Version string
            version_uid: Version UID
            files: List of file information from PyPI
        """
        for file_info in files:
            # Only process wheel files
            if file_info.get("packagetype") != "bdist_wheel":
                continue
            
            filename = file_info.get("filename", "")
            wheel_info = self.wheel_extractor.parse_wheel_filename(filename)
            
            if not wheel_info:
                continue
            
            # Generate wheel UID
            wheel_uid = generate_wheel_uid(
                package_name,
                version,
                wheel_info["python_tag"],
                wheel_info["platform_tag"]
            )
            
            # Check if wheel record already exists
            existing_wheel = session.get(WheelAvailability, wheel_uid)
            if existing_wheel:
                continue
            
            # Create WheelAvailability record
            wheel = WheelAvailability(
                uid=wheel_uid,
                package_version_uid=version_uid,
                python_tag=wheel_info["python_tag"],
                abi_tag=wheel_info["abi_tag"],
                platform_tag=wheel_info["platform_tag"],
                available=True,
                created_at=datetime.utcnow()
            )
            session.add(wheel)
    
    def bootstrap_packages(
        self,
        package_list: List[str],
        parallel: bool = True,
        max_workers: int = 5,
        progress_callback: Optional[Callable[[str], None]] = None
    ) -> Dict[str, str]:
        """
        Bootstrap multiple packages into the database.
        
        Args:
            package_list: List of package names
            parallel: Whether to use parallel processing. Default: True
            max_workers: Maximum number of parallel workers. Default: 5
            progress_callback: Optional callback for progress updates
            
        Returns:
            Dictionary mapping package names to status ("success" or error message)
            
        Example:
            >>> manager = DatabaseManager("~/.cache/env-doctor/db.sqlite")
            >>> bootstrap = DatabaseBootstrap(manager)
            >>> packages = ["torch", "transformers", "accelerate"]
            >>> results = bootstrap.bootstrap_packages(packages)
            >>> print(results)
            {'torch': 'success', 'transformers': 'success', 'accelerate': 'success'}
        """
        results: Dict[str, str] = {}
        
        if not parallel:
            # Sequential processing
            for package_name in package_list:
                try:
                    self.bootstrap_package(package_name, progress_callback)
                    results[package_name] = "success"
                except Exception as e:
                    results[package_name] = f"error: {str(e)}"
        else:
            # Parallel processing using ThreadPoolExecutor
            with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
                # Submit all tasks
                future_to_package = {
                    executor.submit(
                        self.bootstrap_package,
                        package_name,
                        progress_callback
                    ): package_name
                    for package_name in package_list
                }
                
                # Collect results as they complete
                for future in concurrent.futures.as_completed(future_to_package):
                    package_name = future_to_package[future]
                    try:
                        future.result()
                        results[package_name] = "success"
                    except Exception as e:
                        results[package_name] = f"error: {str(e)}"
        
        return results
    
    @staticmethod
    def get_core_packages() -> List[str]:
        """
        Get list of core ML packages to bootstrap.
        
        Returns:
            List of core package names
            
        Example:
            >>> packages = DatabaseBootstrap.get_core_packages()
            >>> print(packages)
            ['torch', 'transformers', 'accelerate', ...]
        """
        return [
            "torch",
            "transformers",
            "accelerate",
            "bitsandbytes",
            "flash-attn",
            "vllm",
            "safetensors",
            "tokenizers",
            "datasets",
            "peft",
            "trl",
            "diffusers",
            "numpy",
            "scipy",
            "pandas",
            "scikit-learn",
            "tensorflow",
            "jax",
            "flax",
            "optax"
        ]
    
    def bootstrap_core_packages(
        self,
        progress_callback: Optional[Callable[[str], None]] = None
    ) -> Dict[str, str]:
        """
        Bootstrap all core ML packages.
        
        Args:
            progress_callback: Optional callback for progress updates
            
        Returns:
            Dictionary mapping package names to status
            
        Example:
            >>> manager = DatabaseManager("~/.cache/env-doctor/db.sqlite")
            >>> bootstrap = DatabaseBootstrap(manager)
            >>> results = bootstrap.bootstrap_core_packages()
        """
        core_packages = self.get_core_packages()
        
        if progress_callback:
            progress_callback(f"Bootstrapping {len(core_packages)} core packages...")
        
        return self.bootstrap_packages(
            core_packages,
            parallel=True,
            progress_callback=progress_callback
        )


# Made with Bob