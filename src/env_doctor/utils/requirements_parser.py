"""
Requirements file parser for env-doctor.

Parses requirements.txt and pyproject.toml files to extract package dependencies.
"""

import re
from pathlib import Path
from typing import Any, Dict, List, Optional

from packaging.requirements import Requirement
from packaging.specifiers import SpecifierSet


def parse_requirements_txt(path: str) -> List[Dict[str, Any]]:
    """
    Parse requirements.txt file.
    
    Args:
        path: Path to requirements.txt file
        
    Returns:
        List of package dictionaries with name, version specifier, and extras
        
    Example:
        >>> packages = parse_requirements_txt("requirements.txt")
        >>> print(packages[0])
        {
            "name": "numpy",
            "specifier": ">=1.20.0",
            "extras": [],
            "line": "numpy>=1.20.0"
        }
        
    Raises:
        FileNotFoundError: If file doesn't exist
        ValueError: If file format is invalid
    """
    file_path = Path(path)
    
    if not file_path.exists():
        raise FileNotFoundError(f"Requirements file not found: {path}")
    
    packages = []
    
    with open(file_path, 'r', encoding='utf-8') as f:
        for line_num, line in enumerate(f, 1):
            # Strip whitespace and comments
            line = line.strip()
            if '#' in line:
                line = line.split('#')[0].strip()
            
            # Skip empty lines and pip options
            if not line or line.startswith('-'):
                continue
            
            # Skip URLs and git references
            if line.startswith(('http://', 'https://', 'git+', 'file://')):
                continue
            
            try:
                # Parse requirement
                req = Requirement(line)
                
                packages.append({
                    "name": req.name,
                    "specifier": str(req.specifier) if req.specifier else "",
                    "extras": list(req.extras) if req.extras else [],
                    "marker": str(req.marker) if req.marker else None,
                    "line": line,
                    "line_number": line_num
                })
                
            except Exception as e:
                # Log warning but continue parsing
                print(f"Warning: Could not parse line {line_num}: {line} ({e})")
                continue
    
    return packages


def parse_pyproject_toml(path: str) -> List[Dict[str, Any]]:
    """
    Parse pyproject.toml file for dependencies.
    
    Args:
        path: Path to pyproject.toml file
        
    Returns:
        List of package dictionaries
        
    Example:
        >>> packages = parse_pyproject_toml("pyproject.toml")
        >>> print(packages[0])
        {
            "name": "numpy",
            "specifier": ">=1.20.0",
            "extras": [],
            "group": "main"
        }
        
    Raises:
        FileNotFoundError: If file doesn't exist
        ValueError: If TOML format is invalid
    """
    file_path = Path(path)
    
    if not file_path.exists():
        raise FileNotFoundError(f"pyproject.toml not found: {path}")
    
    try:
        import tomli
    except ImportError:
        # Fallback to tomllib for Python 3.11+
        try:
            import tomllib as tomli  # type: ignore
        except ImportError:
            raise ImportError(
                "tomli or tomllib required to parse pyproject.toml. "
                "Install with: pip install tomli"
            )
    
    packages = []
    
    with open(file_path, 'rb') as f:
        data = tomli.load(f)
    
    # Parse [project.dependencies]
    project_deps = data.get('project', {}).get('dependencies', [])
    for dep_str in project_deps:
        try:
            req = Requirement(dep_str)
            packages.append({
                "name": req.name,
                "specifier": str(req.specifier) if req.specifier else "",
                "extras": list(req.extras) if req.extras else [],
                "marker": str(req.marker) if req.marker else None,
                "group": "main",
                "line": dep_str
            })
        except Exception as e:
            print(f"Warning: Could not parse dependency: {dep_str} ({e})")
            continue
    
    # Parse [project.optional-dependencies]
    optional_deps = data.get('project', {}).get('optional-dependencies', {})
    for group_name, deps in optional_deps.items():
        for dep_str in deps:
            try:
                req = Requirement(dep_str)
                packages.append({
                    "name": req.name,
                    "specifier": str(req.specifier) if req.specifier else "",
                    "extras": list(req.extras) if req.extras else [],
                    "marker": str(req.marker) if req.marker else None,
                    "group": group_name,
                    "line": dep_str
                })
            except Exception as e:
                print(f"Warning: Could not parse dependency: {dep_str} ({e})")
                continue
    
    # Parse [tool.poetry.dependencies] if present
    poetry_deps = data.get('tool', {}).get('poetry', {}).get('dependencies', {})
    for name, spec in poetry_deps.items():
        if name == 'python':
            continue
        
        try:
            # Poetry format can be string or dict
            if isinstance(spec, str):
                specifier = spec
            elif isinstance(spec, dict):
                specifier = spec.get('version', '')
            else:
                continue
            
            packages.append({
                "name": name,
                "specifier": specifier,
                "extras": [],
                "marker": None,
                "group": "main",
                "line": f"{name} = {spec}"
            })
        except Exception as e:
            print(f"Warning: Could not parse poetry dependency: {name} ({e})")
            continue
    
    return packages


def normalize_package_name(name: str) -> str:
    """
    Normalize package name according to PEP 503.
    
    Args:
        name: Package name
        
    Returns:
        Normalized package name (lowercase, hyphens replaced with underscores)
        
    Example:
        >>> normalize_package_name("Scikit-Learn")
        'scikit_learn'
    """
    return re.sub(r"[-_.]+", "_", name).lower()


def parse_version_specifier(specifier: str) -> Dict[str, Any]:
    """
    Parse version specifier into structured format.
    
    Args:
        specifier: Version specifier string (e.g., ">=1.20.0,<2.0.0")
        
    Returns:
        Dictionary with parsed specifier information
        
    Example:
        >>> parse_version_specifier(">=1.20.0,<2.0.0")
        {
            "raw": ">=1.20.0,<2.0.0",
            "operators": [">=", "<"],
            "versions": ["1.20.0", "2.0.0"],
            "min_version": "1.20.0",
            "max_version": "2.0.0"
        }
    """
    if not specifier:
        return {
            "raw": "",
            "operators": [],
            "versions": [],
            "min_version": None,
            "max_version": None
        }
    
    try:
        spec_set = SpecifierSet(specifier)
        operators = []
        versions = []
        min_version = None
        max_version = None
        
        for spec in spec_set:
            operators.append(spec.operator)
            versions.append(spec.version)
            
            # Track min/max versions
            if spec.operator in ('>=', '>'):
                if min_version is None or spec.version > min_version:
                    min_version = spec.version
            elif spec.operator in ('<=', '<'):
                if max_version is None or spec.version < max_version:
                    max_version = spec.version
            elif spec.operator == '==':
                min_version = max_version = spec.version
        
        return {
            "raw": specifier,
            "operators": operators,
            "versions": versions,
            "min_version": min_version,
            "max_version": max_version
        }
        
    except Exception:
        return {
            "raw": specifier,
            "operators": [],
            "versions": [],
            "min_version": None,
            "max_version": None
        }


def detect_file_type(path: str) -> str:
    """
    Detect requirements file type.
    
    Args:
        path: Path to requirements file
        
    Returns:
        File type: "requirements.txt", "pyproject.toml", or "unknown"
    """
    file_path = Path(path)
    name = file_path.name.lower()
    
    if name == "pyproject.toml" or name.endswith(".toml"):
        return "pyproject.toml"
    elif name.endswith(('.txt', '.in')) or 'requirements' in name:
        return "requirements.txt"
    else:
        return "unknown"


def parse_requirements_file(path: str) -> List[Dict[str, Any]]:
    """
    Auto-detect and parse requirements file.
    
    Args:
        path: Path to requirements file
        
    Returns:
        List of package dictionaries
        
    Raises:
        FileNotFoundError: If file doesn't exist
        ValueError: If file type is not supported
    """
    file_type = detect_file_type(path)
    
    if file_type == "requirements.txt":
        return parse_requirements_txt(path)
    elif file_type == "pyproject.toml":
        return parse_pyproject_toml(path)
    else:
        raise ValueError(f"Unsupported file type: {path}")


def group_packages_by_name(packages: List[Dict[str, Any]]) -> Dict[str, List[Dict[str, Any]]]:
    """
    Group packages by name (handles duplicates).
    
    Args:
        packages: List of package dictionaries
        
    Returns:
        Dictionary mapping package name to list of entries
    """
    grouped: Dict[str, List[Dict[str, Any]]] = {}
    
    for pkg in packages:
        name = normalize_package_name(pkg["name"])
        if name not in grouped:
            grouped[name] = []
        grouped[name].append(pkg)
    
    return grouped


# Made with Bob