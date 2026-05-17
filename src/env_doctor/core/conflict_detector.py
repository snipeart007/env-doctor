"""
Conflict detection for package dependencies.

Detects various types of conflicts including version conflicts, runtime conflicts,
and ABI conflicts.
"""

from typing import List, Dict, Optional, Set, Tuple
from collections import defaultdict

from sqlmodel import select

from ..database.manager import DatabaseManager
from ..database.models import CompatibilityRule
from .version_matcher import VersionMatcher
from .severity_scorer import SeverityScorer
from .analysis import Issue


class ConflictDetector:
    """Detect conflicts in package dependencies."""
    
    def __init__(self, db_manager: DatabaseManager):
        """
        Initialize conflict detector.
        
        Args:
            db_manager: Database manager instance
        """
        self.db_manager = db_manager
        self.version_matcher = VersionMatcher()
        self.severity_scorer = SeverityScorer()
    
    def detect_version_conflicts(
        self, 
        dependencies: List[Dict]
    ) -> List[Issue]:
        """
        Detect version conflicts (unsatisfiable constraints).
        
        Finds cases where multiple packages require incompatible versions
        of the same dependency.
        
        Args:
            dependencies: List of dependency dictionaries with keys:
                - package_name: str
                - version: str
                - requires: List[Dict] with dependency_name and version_specifier
        
        Returns:
            List of Issue objects for version conflicts
            
        Examples:
            >>> deps = [
            ...     {
            ...         "package_name": "pkg1",
            ...         "version": "1.0.0",
            ...         "requires": [{"dependency_name": "dep", "version_specifier": ">=2.0"}]
            ...     },
            ...     {
            ...         "package_name": "pkg2",
            ...         "version": "1.0.0",
            ...         "requires": [{"dependency_name": "dep", "version_specifier": "<2.0"}]
            ...     }
            ... ]
            >>> conflicts = detector.detect_version_conflicts(deps)
            >>> len(conflicts) > 0
            True
        """
        issues = []
        
        # Group requirements by dependency name
        requirements_by_package: Dict[str, List[Tuple[str, str]]] = defaultdict(list)
        
        for dep in dependencies:
            package_name = dep.get("package_name", "")
            requires = dep.get("requires", [])
            
            for req in requires:
                dep_name = req.get("dependency_name", "")
                version_spec = req.get("version_specifier", "")
                
                if dep_name and version_spec:
                    requirements_by_package[dep_name].append((package_name, version_spec))
        
        # Check for conflicts in each dependency
        for dep_name, requirements in requirements_by_package.items():
            if len(requirements) < 2:
                continue
            
            # Check if all requirements are compatible
            conflicting_specs = []
            for i, (pkg1, spec1) in enumerate(requirements):
                for pkg2, spec2 in requirements[i+1:]:
                    if not self.version_matcher.is_compatible_range(spec1, spec2):
                        conflicting_specs.append((pkg1, spec1, pkg2, spec2))
            
            if conflicting_specs:
                # Create issue for this conflict
                affected = list(set([pkg for conflict in conflicting_specs 
                                   for pkg in [conflict[0], conflict[2]]]))
                
                conflict_desc = []
                for pkg1, spec1, pkg2, spec2 in conflicting_specs:
                    conflict_desc.append(f"{pkg1} requires {spec1}, {pkg2} requires {spec2}")
                
                severity = self.severity_scorer.score_version_conflict({})
                
                issue = Issue(
                    severity=severity,
                    severity_label=self.severity_scorer.get_severity_label(severity),
                    type="version_conflict",
                    package_name=dep_name,
                    description=f"Conflicting version requirements: {'; '.join(conflict_desc)}",
                    affected_packages=affected,
                    details={
                        "conflicts": conflicting_specs,
                        "all_requirements": requirements
                    }
                )
                issues.append(issue)
        
        return issues
    
    def detect_runtime_conflicts(
        self,
        dependencies: List[Dict],
        cuda_version: Optional[str] = None,
        env_system: Optional[str] = None
    ) -> List[Issue]:
        """
        Detect runtime conflicts from compatibility rules.
        
        Queries the database for known incompatibilities between packages.
        
        Args:
            dependencies: List of dependency dictionaries with:
                - package_name: str
                - version: str
            cuda_version: Optional system CUDA version
            env_system: Optional system environment info
        
        Returns:
            List of Issue objects for runtime conflicts
        """
        issues = []
        
        # Build a map of package names to versions
        package_versions = {
            dep.get("package_name", ""): dep.get("version", "")
            for dep in dependencies
            if dep.get("package_name") and dep.get("version")
        }
        
        # Query compatibility rules for each package pair
        with self.db_manager.get_session() as session:
            for pkg_name, pkg_version in package_versions.items():
                # Find rules where this package is involved
                statement = select(CompatibilityRule).where(
                    CompatibilityRule.package_name == pkg_name
                )
                
                # Add optional filters
                if cuda_version:
                    statement = statement.where(
                        (CompatibilityRule.cuda_version == cuda_version) |
                        (CompatibilityRule.cuda_version == None)
                    )
                if env_system:
                    statement = statement.where(
                        (CompatibilityRule.env_system == env_system) |
                        (CompatibilityRule.env_system == None)
                    )
                    
                rules = session.exec(statement).all()
                
                for rule in rules:
                    # Check if the package version matches the rule's range
                    if not self.version_matcher.version_matches(
                        pkg_version,
                        rule.package_version_range
                    ):
                        continue
                    
                    # Check if the dependency is in our package list
                    dep_name = rule.dependency_name
                    if dep_name not in package_versions:
                        continue
                    
                    dep_version = package_versions[dep_name]
                    
                    # Check if dependency version matches the rule's range
                    if not self.version_matcher.version_matches(
                        dep_version,
                        rule.dependency_version_range
                    ):
                        continue
                    
                    # We have a match - check compatibility type
                    if rule.compatibility_type in ["incompatible", "runtime-risk", "partial"]:
                        severity = self.severity_scorer.score_compatibility_rule(rule)
                        
                        issue = Issue(
                            severity=severity,
                            severity_label=self.severity_scorer.get_severity_label(severity),
                            type="runtime_conflict",
                            package_name=pkg_name,
                            description=rule.description,
                            workaround=rule.workaround,
                            affected_packages=[pkg_name, dep_name],
                            details={
                                "package_version": pkg_version,
                                "dependency_name": dep_name,
                                "dependency_version": dep_version,
                                "compatibility_type": rule.compatibility_type,
                                "confidence_level": rule.confidence_level
                            }
                        )
                        issues.append(issue)
        
        return issues
    
    def detect_abi_conflicts(
        self,
        dependencies: List[Dict],
        cuda_version: Optional[str] = None
    ) -> List[Issue]:
        """
        Detect ABI conflicts (CUDA version mismatches).
        
        Checks for packages that require specific CUDA versions that don't match
        the system's CUDA version.
        
        Args:
            dependencies: List of dependency dictionaries
            cuda_version: System CUDA version (e.g., "11.8")
        
        Returns:
            List of Issue objects for ABI conflicts
        """
        issues = []
        
        if not cuda_version:
            # Can't detect CUDA conflicts without knowing system CUDA version
            return issues
        
        # Common CUDA-dependent packages and their version patterns
        cuda_packages = {
            "torch": self._extract_cuda_from_torch_version,
            "tensorflow": self._extract_cuda_from_tensorflow_version,
            "jax": self._extract_cuda_from_jax_version,
        }
        
        for dep in dependencies:
            pkg_name = dep.get("package_name", "")
            pkg_version = dep.get("version", "")
            
            if pkg_name in cuda_packages:
                extractor = cuda_packages[pkg_name]
                required_cuda = extractor(pkg_version)
                
                if required_cuda and required_cuda != cuda_version:
                    # Check if versions are compatible (e.g., 11.8 vs 11.7)
                    if not self._are_cuda_versions_compatible(required_cuda, cuda_version):
                        severity = self.severity_scorer.score_abi_conflict({})
                        
                        issue = Issue(
                            severity=severity,
                            severity_label=self.severity_scorer.get_severity_label(severity),
                            type="abi_conflict",
                            package_name=pkg_name,
                            description=(
                                f"{pkg_name} {pkg_version} requires CUDA {required_cuda}, "
                                f"but system has CUDA {cuda_version}"
                            ),
                            workaround=f"Install {pkg_name} version compatible with CUDA {cuda_version}",
                            affected_packages=[pkg_name],
                            details={
                                "package_version": pkg_version,
                                "required_cuda": required_cuda,
                                "system_cuda": cuda_version
                            }
                        )
                        issues.append(issue)
        
        return issues
    
    def detect_python_version_conflicts(
        self,
        dependencies: List[Dict],
        python_version: str
    ) -> List[Issue]:
        """
        Detect Python version conflicts.
        
        Args:
            dependencies: List of dependency dictionaries with requires_python
            python_version: System Python version (e.g., "3.10.0")
        
        Returns:
            List of Issue objects for Python version conflicts
        """
        issues = []
        
        for dep in dependencies:
            pkg_name = dep.get("package_name", "")
            pkg_version = dep.get("version", "")
            requires_python = dep.get("requires_python")
            
            if requires_python:
                if not self.version_matcher.satisfies_python_requirement(
                    python_version,
                    requires_python
                ):
                    severity = self.severity_scorer.score_python_version_conflict(
                        requires_python,
                        python_version
                    )
                    
                    issue = Issue(
                        severity=severity,
                        severity_label=self.severity_scorer.get_severity_label(severity),
                        type="python_version",
                        package_name=pkg_name,
                        description=(
                            f"{pkg_name} {pkg_version} requires Python {requires_python}, "
                            f"but system has Python {python_version}"
                        ),
                        workaround=f"Upgrade Python to satisfy {requires_python}",
                        affected_packages=[pkg_name],
                        details={
                            "package_version": pkg_version,
                            "requires_python": requires_python,
                            "system_python": python_version
                        }
                    )
                    issues.append(issue)
        
        return issues
    
    def detect_all_conflicts(
        self,
        dependencies: List[Dict],
        cuda_version: Optional[str] = None,
        env_system: Optional[str] = None,
        python_version: Optional[str] = None
    ) -> Dict[str, List[Issue]]:
        """
        Detect all types of conflicts.
        
        Args:
            dependencies: List of dependency dictionaries
            cuda_version: Optional system CUDA version
            env_system: Optional system environment info
            python_version: Optional system Python version
        
        Returns:
            Dictionary with conflict types as keys and lists of Issues as values:
            {
                "version_conflicts": [...],
                "runtime_conflicts": [...],
                "abi_conflicts": [...],
                "python_conflicts": [...]
            }
        """
        result = {
            "version_conflicts": self.detect_version_conflicts(dependencies),
            "runtime_conflicts": self.detect_runtime_conflicts(
                dependencies, cuda_version=cuda_version, env_system=env_system
            ),
            "abi_conflicts": [],
            "python_conflicts": []
        }
        
        if cuda_version:
            result["abi_conflicts"] = self.detect_abi_conflicts(dependencies, cuda_version)
        
        if python_version:
            result["python_conflicts"] = self.detect_python_version_conflicts(
                dependencies,
                python_version
            )
        
        return result
    
    # Helper methods for CUDA version extraction
    
    @staticmethod
    def _extract_cuda_from_torch_version(version: str) -> Optional[str]:
        """Extract CUDA version from PyTorch version string."""
        # PyTorch versions like "2.1.0+cu118" indicate CUDA 11.8
        if "+cu" in version:
            cuda_part = version.split("+cu")[1][:3]
            major = cuda_part[0:2]
            minor = cuda_part[2]
            return f"{major}.{minor}"
        return None
    
    @staticmethod
    def _extract_cuda_from_tensorflow_version(version: str) -> Optional[str]:
        """Extract CUDA version from TensorFlow version string."""
        # TensorFlow typically doesn't encode CUDA in version
        # Would need to check package metadata or documentation
        return None
    
    @staticmethod
    def _extract_cuda_from_jax_version(version: str) -> Optional[str]:
        """Extract CUDA version from JAX version string."""
        # JAX uses separate packages like jaxlib+cuda11
        return None
    
    @staticmethod
    def _are_cuda_versions_compatible(required: str, available: str) -> bool:
        """
        Check if CUDA versions are compatible.
        
        Generally, minor version differences within the same major version
        are acceptable (e.g., 11.7 and 11.8).
        """
        try:
            req_parts = required.split(".")
            avail_parts = available.split(".")
            
            # Major version must match
            if req_parts[0] != avail_parts[0]:
                return False
            
            # Minor version can differ by 1
            if len(req_parts) > 1 and len(avail_parts) > 1:
                req_minor = int(req_parts[1])
                avail_minor = int(avail_parts[1])
                
                if abs(req_minor - avail_minor) > 1:
                    return False
            
            return True
        except (ValueError, IndexError):
            return False

# Made with Bob
