"""
Dependency parser for PyPI package metadata.

Parses requires_dist and requires_python fields from PyPI metadata.
"""

from typing import Any, Dict, List, Optional

from packaging.markers import Marker
from packaging.requirements import Requirement
from packaging.specifiers import SpecifierSet


class DependencyParser:
    """
    Parser for package dependency specifications.
    
    Extracts and structures dependency information from PyPI metadata,
    including version specifiers, extras, and environment markers.
    """
    
    @staticmethod
    def parse_requires_dist(requires_dist: List[str]) -> List[Dict[str, Any]]:
        """
        Parse requires_dist field from PyPI metadata.
        
        Args:
            requires_dist: List of requirement strings from PyPI
            
        Returns:
            List of structured dependency dictionaries
            
        Example:
            >>> parser = DependencyParser()
            >>> requires = [
            ...     "numpy>=1.20.0",
            ...     "torch>=2.0.0; extra == 'cuda'",
            ...     "pytest>=7.0.0; extra == 'dev'"
            ... ]
            >>> deps = parser.parse_requires_dist(requires)
            >>> print(deps[0])
            {
                'name': 'numpy',
                'specifier': '>=1.20.0',
                'extras': None,
                'marker': None,
                'extra_group': None
            }
        """
        dependencies = []
        
        for req_str in requires_dist:
            try:
                req = Requirement(req_str)
                
                # Extract extra group from marker if present
                extra_group = None
                marker_str = None
                
                if req.marker:
                    marker_str = str(req.marker)
                    # Try to extract extra from marker
                    # Common pattern: extra == "dev" or extra == 'dev'
                    if "extra ==" in marker_str:
                        # Simple extraction - could be more robust
                        parts = marker_str.split("extra ==")
                        if len(parts) > 1:
                            extra_part = parts[1].strip()
                            # Remove quotes and any trailing conditions
                            extra_group = extra_part.strip("'\"").split()[0].strip("'\"")
                
                dep_dict = {
                    "name": req.name,
                    "specifier": str(req.specifier) if req.specifier else "",
                    "extras": list(req.extras) if req.extras else None,
                    "marker": marker_str,
                    "extra_group": extra_group
                }
                
                dependencies.append(dep_dict)
                
            except Exception:
                # Skip invalid requirement strings
                continue
        
        return dependencies
    
    @staticmethod
    def parse_requires_python(requires_python: Optional[str]) -> str:
        """
        Parse and normalize Python version constraint.
        
        Args:
            requires_python: Python version specifier (e.g., ">=3.8")
            
        Returns:
            Normalized specifier string
            
        Example:
            >>> parser = DependencyParser()
            >>> parser.parse_requires_python(">=3.8,<4.0")
            '>=3.8,<4.0'
            >>> parser.parse_requires_python(None)
            ''
        """
        if not requires_python:
            return ""
        
        try:
            # Parse and normalize using packaging library
            spec = SpecifierSet(requires_python)
            return str(spec)
        except Exception:
            # Return as-is if parsing fails
            return requires_python
    
    @staticmethod
    def extract_dependencies(metadata: Dict[str, Any]) -> Dict[str, List[Dict[str, Any]]]:
        """
        Extract all dependencies from PyPI metadata.
        
        Groups dependencies by type (main, dev, optional extras).
        
        Args:
            metadata: Full PyPI metadata dictionary
            
        Returns:
            Dictionary mapping dependency groups to dependency lists
            
        Example:
            >>> parser = DependencyParser()
            >>> metadata = {
            ...     "info": {
            ...         "requires_dist": [
            ...             "numpy>=1.20.0",
            ...             "pytest>=7.0.0; extra == 'dev'"
            ...         ]
            ...     }
            ... }
            >>> deps = parser.extract_dependencies(metadata)
            >>> print(deps.keys())
            dict_keys(['main', 'dev'])
        """
        info = metadata.get("info", {})
        requires_dist = info.get("requires_dist", [])
        
        if not requires_dist:
            return {"main": []}
        
        # Parse all dependencies
        all_deps = DependencyParser.parse_requires_dist(requires_dist)
        
        # Group by extra
        grouped: Dict[str, List[Dict[str, Any]]] = {"main": []}
        
        for dep in all_deps:
            extra_group = dep.get("extra_group")
            
            if extra_group:
                # Add to specific extra group
                if extra_group not in grouped:
                    grouped[extra_group] = []
                grouped[extra_group].append(dep)
            else:
                # Check if marker has other conditions (not just extra)
                marker = dep.get("marker")
                if marker and "extra ==" not in marker:
                    # Has environment marker but not extra-specific
                    # Still add to main but keep marker info
                    grouped["main"].append(dep)
                elif not marker:
                    # No marker at all - definitely main dependency
                    grouped["main"].append(dep)
                # If marker only has "extra ==" but we didn't extract it,
                # it's likely a parsing issue, skip it
        
        return grouped
    
    @staticmethod
    def get_runtime_dependencies(
        metadata: Dict[str, Any],
        include_extras: Optional[List[str]] = None
    ) -> List[Dict[str, Any]]:
        """
        Get runtime dependencies (main + specified extras).
        
        Args:
            metadata: Full PyPI metadata dictionary
            include_extras: List of extra groups to include (e.g., ['cuda', 'dev'])
            
        Returns:
            List of runtime dependencies
            
        Example:
            >>> parser = DependencyParser()
            >>> deps = parser.get_runtime_dependencies(metadata, include_extras=['cuda'])
            >>> # Returns main dependencies + cuda extra dependencies
        """
        all_deps = DependencyParser.extract_dependencies(metadata)
        
        # Start with main dependencies
        runtime_deps = all_deps.get("main", []).copy()
        
        # Add specified extras
        if include_extras:
            for extra in include_extras:
                if extra in all_deps:
                    runtime_deps.extend(all_deps[extra])
        
        return runtime_deps
    
    @staticmethod
    def filter_by_environment(
        dependencies: List[Dict[str, Any]],
        python_version: Optional[str] = None,
        platform: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """
        Filter dependencies by environment markers.
        
        Args:
            dependencies: List of dependency dictionaries
            python_version: Python version to check against (e.g., "3.10")
            platform: Platform to check against (e.g., "linux", "win32")
            
        Returns:
            Filtered list of dependencies applicable to the environment
            
        Example:
            >>> parser = DependencyParser()
            >>> deps = [
            ...     {"name": "numpy", "marker": None},
            ...     {"name": "pywin32", "marker": "sys_platform == 'win32'"}
            ... ]
            >>> filtered = parser.filter_by_environment(deps, platform="linux")
            >>> # Returns only numpy (pywin32 filtered out)
        """
        if not python_version and not platform:
            # No filtering needed
            return dependencies
        
        filtered = []
        
        for dep in dependencies:
            marker_str = dep.get("marker")
            
            if not marker_str:
                # No marker - always include
                filtered.append(dep)
                continue
            
            try:
                marker = Marker(marker_str)
                
                # Build environment dict for evaluation
                env: Dict[str, str] = {}
                
                if python_version:
                    # Add Python version info
                    env["python_version"] = python_version
                    env["python_full_version"] = python_version
                
                if platform:
                    env["sys_platform"] = platform
                
                # Evaluate marker
                # Note: This is a simplified check. Full evaluation would need
                # complete environment info (os_name, platform_machine, etc.)
                if marker.evaluate(env):
                    filtered.append(dep)
                    
            except Exception:
                # If marker evaluation fails, include the dependency
                # (better to over-include than miss dependencies)
                filtered.append(dep)
        
        return filtered


# Made with Bob