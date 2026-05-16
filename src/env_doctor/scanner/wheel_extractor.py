"""
Wheel metadata extractor for PyPI packages.

Extracts wheel availability information from PyPI metadata.
"""

from typing import Any, Dict, List, Optional

from packaging.utils import parse_wheel_filename


class WheelExtractor:
    """
    Extractor for wheel availability information.
    
    Parses wheel filenames and extracts platform compatibility tags.
    """
    
    @staticmethod
    def parse_wheel_filename(filename: str) -> Optional[Dict[str, Any]]:
        """
        Parse wheel filename to extract tags.
        
        Args:
            filename: Wheel filename (e.g., "torch-2.1.0-cp310-cp310-win_amd64.whl")
            
        Returns:
            Dictionary with parsed wheel information or None if not a wheel
            
        Example:
            >>> extractor = WheelExtractor()
            >>> info = extractor.parse_wheel_filename("torch-2.1.0-cp310-cp310-win_amd64.whl")
            >>> print(info)
            {
                'name': 'torch',
                'version': '2.1.0',
                'python_tag': 'cp310',
                'abi_tag': 'cp310',
                'platform_tag': 'win_amd64'
            }
        """
        if not filename.endswith(".whl"):
            return None
        
        try:
            # Use packaging library to parse wheel filename
            name, version, build, tags = parse_wheel_filename(filename)
            
            # Extract first tag (wheels can have multiple tags)
            if tags:
                tag = next(iter(tags))
                return {
                    "name": name,
                    "version": str(version),
                    "python_tag": tag.interpreter,
                    "abi_tag": tag.abi,
                    "platform_tag": tag.platform
                }
            
            return None
            
        except Exception:
            # Invalid wheel filename
            return None
    
    @staticmethod
    def extract_wheel_info(metadata: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        Extract wheel availability information from PyPI metadata.
        
        Args:
            metadata: Full PyPI metadata dictionary
            
        Returns:
            List of wheel availability records
            
        Example:
            >>> extractor = WheelExtractor()
            >>> metadata = {
            ...     "releases": {
            ...         "2.1.0": [
            ...             {
            ...                 "filename": "torch-2.1.0-cp310-cp310-win_amd64.whl",
            ...                 "packagetype": "bdist_wheel"
            ...             }
            ...         ]
            ...     }
            ... }
            >>> wheels = extractor.extract_wheel_info(metadata)
            >>> print(wheels[0])
            {
                'version': '2.1.0',
                'python_tag': 'cp310',
                'abi_tag': 'cp310',
                'platform_tag': 'win_amd64',
                'available': True
            }
        """
        releases = metadata.get("releases", {})
        wheel_records = []
        
        for version, files in releases.items():
            if not files:
                continue
            
            for file_info in files:
                # Only process wheel files
                if file_info.get("packagetype") != "bdist_wheel":
                    continue
                
                filename = file_info.get("filename", "")
                wheel_info = WheelExtractor.parse_wheel_filename(filename)
                
                if wheel_info:
                    wheel_record = {
                        "version": version,
                        "python_tag": wheel_info["python_tag"],
                        "abi_tag": wheel_info["abi_tag"],
                        "platform_tag": wheel_info["platform_tag"],
                        "available": True
                    }
                    wheel_records.append(wheel_record)
        
        return wheel_records
    
    @staticmethod
    def get_wheels_for_version(
        metadata: Dict[str, Any],
        version: str
    ) -> List[Dict[str, Any]]:
        """
        Get all wheels for a specific version.
        
        Args:
            metadata: Full PyPI metadata dictionary
            version: Version string (e.g., "2.1.0")
            
        Returns:
            List of wheel records for the specified version
            
        Example:
            >>> extractor = WheelExtractor()
            >>> wheels = extractor.get_wheels_for_version(metadata, "2.1.0")
        """
        all_wheels = WheelExtractor.extract_wheel_info(metadata)
        return [w for w in all_wheels if w["version"] == version]
    
    @staticmethod
    def check_wheel_availability(
        metadata: Dict[str, Any],
        version: str,
        python_version: str,
        platform: str
    ) -> bool:
        """
        Check if a wheel is available for specific environment.
        
        Args:
            metadata: Full PyPI metadata dictionary
            version: Package version (e.g., "2.1.0")
            python_version: Python version (e.g., "3.10")
            platform: Platform tag (e.g., "win_amd64", "manylinux2014_x86_64")
            
        Returns:
            True if compatible wheel is available, False otherwise
            
        Example:
            >>> extractor = WheelExtractor()
            >>> available = extractor.check_wheel_availability(
            ...     metadata, "2.1.0", "3.10", "win_amd64"
            ... )
        """
        wheels = WheelExtractor.get_wheels_for_version(metadata, version)
        
        # Convert Python version to tag format (e.g., "3.10" -> "cp310")
        py_tag = f"cp{python_version.replace('.', '')}"
        
        for wheel in wheels:
            # Check for exact match or compatible tags
            wheel_py_tag = wheel["python_tag"]
            wheel_platform = wheel["platform_tag"]
            
            # Check Python tag compatibility
            py_compatible = (
                wheel_py_tag == py_tag or
                wheel_py_tag == "py3" or  # Universal Python 3 wheel
                wheel_py_tag == "py2.py3"  # Universal Python 2/3 wheel
            )
            
            # Check platform compatibility
            platform_compatible = (
                wheel_platform == platform or
                wheel_platform == "any"  # Platform-independent wheel
            )
            
            if py_compatible and platform_compatible:
                return True
        
        return False
    
    @staticmethod
    def get_supported_platforms(
        metadata: Dict[str, Any],
        version: str
    ) -> List[str]:
        """
        Get list of supported platforms for a version.
        
        Args:
            metadata: Full PyPI metadata dictionary
            version: Package version
            
        Returns:
            List of unique platform tags
            
        Example:
            >>> extractor = WheelExtractor()
            >>> platforms = extractor.get_supported_platforms(metadata, "2.1.0")
            >>> print(platforms)
            ['win_amd64', 'manylinux2014_x86_64', 'macosx_11_0_arm64']
        """
        wheels = WheelExtractor.get_wheels_for_version(metadata, version)
        platforms = list(set(w["platform_tag"] for w in wheels))
        return sorted(platforms)
    
    @staticmethod
    def get_supported_python_versions(
        metadata: Dict[str, Any],
        version: str
    ) -> List[str]:
        """
        Get list of supported Python versions for a package version.
        
        Args:
            metadata: Full PyPI metadata dictionary
            version: Package version
            
        Returns:
            List of unique Python tags
            
        Example:
            >>> extractor = WheelExtractor()
            >>> py_versions = extractor.get_supported_python_versions(metadata, "2.1.0")
            >>> print(py_versions)
            ['cp38', 'cp39', 'cp310', 'cp311']
        """
        wheels = WheelExtractor.get_wheels_for_version(metadata, version)
        py_tags = list(set(w["python_tag"] for w in wheels))
        return sorted(py_tags)
    
    @staticmethod
    def has_source_distribution(
        metadata: Dict[str, Any],
        version: str
    ) -> bool:
        """
        Check if a source distribution is available for a version.
        
        Args:
            metadata: Full PyPI metadata dictionary
            version: Package version
            
        Returns:
            True if source distribution exists, False otherwise
            
        Example:
            >>> extractor = WheelExtractor()
            >>> has_sdist = extractor.has_source_distribution(metadata, "2.1.0")
        """
        releases = metadata.get("releases", {})
        files = releases.get(version, [])
        
        for file_info in files:
            if file_info.get("packagetype") == "sdist":
                return True
        
        return False
    
    @staticmethod
    def get_wheel_summary(
        metadata: Dict[str, Any],
        version: str
    ) -> Dict[str, Any]:
        """
        Get comprehensive wheel availability summary for a version.
        
        Args:
            metadata: Full PyPI metadata dictionary
            version: Package version
            
        Returns:
            Dictionary with wheel availability summary
            
        Example:
            >>> extractor = WheelExtractor()
            >>> summary = extractor.get_wheel_summary(metadata, "2.1.0")
            >>> print(summary)
            {
                'version': '2.1.0',
                'has_wheels': True,
                'has_source': True,
                'wheel_count': 12,
                'platforms': ['win_amd64', 'manylinux2014_x86_64'],
                'python_versions': ['cp38', 'cp39', 'cp310', 'cp311']
            }
        """
        wheels = WheelExtractor.get_wheels_for_version(metadata, version)
        
        return {
            "version": version,
            "has_wheels": len(wheels) > 0,
            "has_source": WheelExtractor.has_source_distribution(metadata, version),
            "wheel_count": len(wheels),
            "platforms": WheelExtractor.get_supported_platforms(metadata, version),
            "python_versions": WheelExtractor.get_supported_python_versions(metadata, version)
        }


# Made with Bob