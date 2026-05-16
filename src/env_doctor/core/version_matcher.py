"""
Version matching and comparison utilities.

Uses the packaging library to handle PEP 440 version specifiers and comparisons.
"""

from typing import List, Optional

from packaging.specifiers import SpecifierSet, InvalidSpecifier
from packaging.version import Version, InvalidVersion


class VersionMatcher:
    """Version matching and comparison utilities."""
    
    @staticmethod
    def version_matches(version: str, specifier: str) -> bool:
        """
        Check if version matches specifier.
        
        Args:
            version: Version string (e.g., "2.1.0")
            specifier: Version specifier (e.g., ">=2.0.0,<3.0.0")
            
        Returns:
            True if version matches specifier
        """
        try:
            # Handle raw versions without operators as exact matches
            if specifier and not any(op in specifier for op in ['>', '<', '=', '!', '~']):
                specifier = f"=={specifier}"
                
            return Version(version) in SpecifierSet(specifier)
        except (InvalidVersion, InvalidSpecifier):
            return False
    
    @staticmethod
    def get_matching_versions(versions: List[str], specifier: str) -> List[str]:
        """
        Get all versions that match specifier.
        
        Args:
            versions: List of version strings
            specifier: Version specifier (e.g., ">=2.0.0,<3.0.0")
            
        Returns:
            List of versions that match the specifier, sorted in descending order
            
        Examples:
            >>> versions = ["1.9.0", "2.0.0", "2.1.0", "3.0.0"]
            >>> VersionMatcher.get_matching_versions(versions, ">=2.0.0,<3.0.0")
            ['2.1.0', '2.0.0']
        """
        try:
            spec_set = SpecifierSet(specifier)
            matching = []
            
            for version_str in versions:
                try:
                    version = Version(version_str)
                    if version in spec_set:
                        matching.append(version_str)
                except InvalidVersion:
                    continue
            
            # Sort in descending order (newest first)
            matching.sort(key=lambda v: Version(v), reverse=True)
            return matching
            
        except InvalidSpecifier:
            return []
    
    @staticmethod
    def is_compatible_range(range1: str, range2: str) -> bool:
        """
        Check if two version ranges overlap.
        
        Args:
            range1: First version specifier (e.g., ">=2.0.0,<3.0.0")
            range2: Second version specifier (e.g., ">=2.1.0,<4.0.0")
            
        Returns:
            True if the ranges have any overlap
            
        Examples:
            >>> VersionMatcher.is_compatible_range(">=2.0.0,<3.0.0", ">=2.1.0,<4.0.0")
            True
            >>> VersionMatcher.is_compatible_range(">=2.0.0,<3.0.0", ">=3.0.0,<4.0.0")
            False
        """
        try:
            spec1 = SpecifierSet(range1)
            spec2 = SpecifierSet(range2)
            
            # Generate a range of test versions to check for overlap
            # We'll test major versions from 0 to 20 with minor versions 0-9
            test_versions = []
            for major in range(21):
                for minor in range(10):
                    test_versions.append(f"{major}.{minor}.0")
            
            # Check if any version satisfies both specifiers
            for version_str in test_versions:
                try:
                    version = Version(version_str)
                    if version in spec1 and version in spec2:
                        return True
                except InvalidVersion:
                    continue
            
            return False
            
        except InvalidSpecifier:
            return False
    
    @staticmethod
    def normalize_version(version: str) -> str:
        """
        Normalize version string to PEP 440 format.
        
        Args:
            version: Version string (may be non-standard)
            
        Returns:
            Normalized version string
            
        Examples:
            >>> VersionMatcher.normalize_version("2.1")
            '2.1'
            >>> VersionMatcher.normalize_version("v2.1.0")
            '2.1.0'
        """
        try:
            # Remove common prefixes
            clean_version = version.lstrip('vV')
            
            # Parse and normalize using packaging
            return str(Version(clean_version))
        except InvalidVersion:
            # Return original if can't normalize
            return version
    
    @staticmethod
    def compare_versions(version1: str, version2: str) -> int:
        """
        Compare two versions.
        
        Args:
            version1: First version string
            version2: Second version string
            
        Returns:
            -1 if version1 < version2
             0 if version1 == version2
             1 if version1 > version2
            
        Examples:
            >>> VersionMatcher.compare_versions("2.0.0", "2.1.0")
            -1
            >>> VersionMatcher.compare_versions("2.1.0", "2.1.0")
            0
            >>> VersionMatcher.compare_versions("2.2.0", "2.1.0")
            1
        """
        try:
            v1 = Version(version1)
            v2 = Version(version2)
            
            if v1 < v2:
                return -1
            elif v1 > v2:
                return 1
            else:
                return 0
        except InvalidVersion:
            # Fallback to string comparison
            if version1 < version2:
                return -1
            elif version1 > version2:
                return 1
            else:
                return 0
    
    @staticmethod
    def get_latest_version(versions: List[str]) -> Optional[str]:
        """
        Get the latest version from a list.
        
        Args:
            versions: List of version strings
            
        Returns:
            Latest version string, or None if list is empty
            
        Examples:
            >>> VersionMatcher.get_latest_version(["1.0.0", "2.1.0", "2.0.0"])
            '2.1.0'
        """
        if not versions:
            return None
        
        valid_versions = []
        for version_str in versions:
            try:
                valid_versions.append((Version(version_str), version_str))
            except InvalidVersion:
                continue
        
        if not valid_versions:
            return None
        
        # Sort and return the latest
        valid_versions.sort(key=lambda x: x[0], reverse=True)
        return valid_versions[0][1]
    
    @staticmethod
    def is_prerelease(version: str) -> bool:
        """
        Check if version is a pre-release.
        
        Args:
            version: Version string
            
        Returns:
            True if version is a pre-release (alpha, beta, rc, etc.)
            
        Examples:
            >>> VersionMatcher.is_prerelease("2.1.0")
            False
            >>> VersionMatcher.is_prerelease("2.1.0rc1")
            True
        """
        try:
            return Version(version).is_prerelease
        except InvalidVersion:
            return False
    
    @staticmethod
    def satisfies_python_requirement(
        python_version: str,
        requires_python: Optional[str]
    ) -> bool:
        """
        Check if Python version satisfies requirement.
        
        Args:
            python_version: Python version (e.g., "3.10.0")
            requires_python: Python requirement specifier (e.g., ">=3.8")
            
        Returns:
            True if Python version satisfies requirement
            
        Examples:
            >>> VersionMatcher.satisfies_python_requirement("3.10.0", ">=3.8")
            True
            >>> VersionMatcher.satisfies_python_requirement("3.7.0", ">=3.8")
            False
        """
        if requires_python is None:
            return True
        
        return VersionMatcher.version_matches(python_version, requires_python)

# Made with Bob
