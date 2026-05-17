"""
Main compatibility analysis orchestrator.

Coordinates all compatibility checks and produces comprehensive analysis reports.
"""

from typing import List, Dict, Optional

from sqlmodel import select

from ..database.manager import DatabaseManager
from ..database.models import CompatibilityRule, PackageVersion
from .conflict_detector import ConflictDetector
from .severity_scorer import SeverityScorer
from .version_matcher import VersionMatcher
from .analysis import AnalysisReport, Issue
from .dependency_graph import DependencyGraph


class CompatibilityAnalyzer:
    """Analyze package compatibility."""
    
    def __init__(self, db_manager: DatabaseManager):
        """
        Initialize compatibility analyzer.
        
        Args:
            db_manager: Database manager instance
        """
        self.db_manager = db_manager
        self.conflict_detector = ConflictDetector(db_manager)
        self.severity_scorer = SeverityScorer()
        self.version_matcher = VersionMatcher()
        self.dependency_graph = DependencyGraph(db_manager)
    
    def analyze_dependencies(
        self,
        dependencies: List[Dict],
        cuda_version: Optional[str] = None,
        env_system: Optional[str] = None,
        python_version: Optional[str] = None,
        include_graph_analysis: bool = False
    ) -> AnalysisReport:
        """
        Perform complete compatibility analysis.
        
        Args:
            dependencies: List of dependency dictionaries
            cuda_version: Optional system CUDA version
            env_system: Optional system environment info
            python_version: Optional system Python version
            include_graph_analysis: Whether to include dependency graph analysis
        
        Returns:
            AnalysisReport with complete analysis results
        """
        # Detect all types of conflicts
        conflicts = self.conflict_detector.detect_all_conflicts(
            dependencies,
            cuda_version=cuda_version,
            env_system=env_system,
            python_version=python_version
        )
        
        # Collect all issues
        all_issues = []
        for conflict_type, issues in conflicts.items():
            all_issues.extend(issues)
        
        # Categorize by severity
        critical_issues = []
        warnings = []
        info = []
        
        for issue in all_issues:
            if issue.severity >= SeverityScorer.CRITICAL:
                critical_issues.append(issue)
            elif issue.severity >= SeverityScorer.MEDIUM:
                warnings.append(issue)
            else:
                info.append(issue)
        
        # Generate recommendations
        recommendations = self._generate_recommendations(
            critical_issues,
            warnings,
            dependencies
        )
        
        # Determine overall status
        if critical_issues:
            status = "errors"
            summary = f"Found {len(critical_issues)} critical compatibility issues"
        elif warnings:
            status = "warnings"
            summary = f"Found {len(warnings)} compatibility warnings"
        else:
            status = "ok"
            summary = "All dependencies are compatible"
        
        # Build details
        details = {
            "total_packages": len(dependencies),
            "conflicts_by_type": {
                conflict_type: len(issues)
                for conflict_type, issues in conflicts.items()
            }
        }
        
        # Add graph analysis if requested
        if include_graph_analysis:
            self.dependency_graph.build_graph(dependencies)
            graph_stats = self.dependency_graph.get_statistics()
            details["graph_statistics"] = graph_stats
            
            # Check for cycles
            cycles = self.dependency_graph.find_cycles()
            if cycles:
                for cycle in cycles:
                    issue = Issue(
                        severity=SeverityScorer.MEDIUM,
                        severity_label="MEDIUM",
                        type="circular_dependency",
                        package_name=cycle[0] if cycle else "unknown",
                        description=f"Circular dependency detected: {' -> '.join(cycle)}",
                        affected_packages=cycle,
                        details={"cycle": cycle}
                    )
                    warnings.append(issue)
        
        return AnalysisReport(
            status=status,
            summary=summary,
            critical_issues=critical_issues,
            warnings=warnings,
            info=info,
            recommendations=recommendations,
            details=details
        )
    
    def check_package_compatibility(
        self,
        package1: str,
        version1: str,
        package2: str,
        version2: str,
        cuda_version: Optional[str] = None,
        env_system: Optional[str] = None
    ) -> Optional[CompatibilityRule]:
        """
        Check if two specific package versions are compatible.
        
        Queries the database for compatibility rules between the packages.
        
        Args:
            package1: First package name
            version1: First package version
            package2: Second package name
            version2: Second package version
            cuda_version: Optional system CUDA version
            env_system: Optional system environment info
        
        Returns:
            CompatibilityRule if found, None otherwise
        """
        with self.db_manager.get_session() as session:
            # Check both directions (package1 -> package2 and package2 -> package1)
            
            # Direction 1: package1 depends on package2
            stmt1 = select(CompatibilityRule).where(
                CompatibilityRule.package_name == package1,
                CompatibilityRule.dependency_name == package2
            )
            
            # Add optional filters
            if cuda_version:
                stmt1 = stmt1.where(
                    (CompatibilityRule.cuda_version == cuda_version) |
                    (CompatibilityRule.cuda_version == None)
                )
            if env_system:
                stmt1 = stmt1.where(
                    (CompatibilityRule.env_system == env_system) |
                    (CompatibilityRule.env_system == None)
                )
                
            rules1 = session.exec(stmt1).all()
            
            for rule in rules1:
                if (self.version_matcher.version_matches(version1, rule.package_version_range) and
                    self.version_matcher.version_matches(version2, rule.dependency_version_range)):
                    return rule
            
            # Direction 2: package2 depends on package1
            stmt2 = select(CompatibilityRule).where(
                CompatibilityRule.package_name == package2,
                CompatibilityRule.dependency_name == package1
            )
            
            # Add optional filters
            if cuda_version:
                stmt2 = stmt2.where(
                    (CompatibilityRule.cuda_version == cuda_version) |
                    (CompatibilityRule.cuda_version == None)
                )
            if env_system:
                stmt2 = stmt2.where(
                    (CompatibilityRule.env_system == env_system) |
                    (CompatibilityRule.env_system == None)
                )
                
            rules2 = session.exec(stmt2).all()
            
            for rule in rules2:
                if (self.version_matcher.version_matches(version2, rule.package_version_range) and
                    self.version_matcher.version_matches(version1, rule.dependency_version_range)):
                    return rule
        
        return None
    
    def get_compatible_versions(
        self,
        package: str,
        dependencies: List[Dict],
        max_results: int = 10
    ) -> List[str]:
        """
        Get versions of package compatible with dependencies.
        
        Finds versions of the specified package that are compatible with
        all the given dependencies.
        
        Args:
            package: Package name to find versions for
            dependencies: List of dependency dictionaries
            max_results: Maximum number of versions to return
        
        Returns:
            List of compatible version strings, sorted newest first
            
        Examples:
            >>> deps = [
            ...     {"package_name": "numpy", "version": "1.24.0"}
            ... ]
            >>> versions = analyzer.get_compatible_versions("torch", deps)
            >>> print(versions[:3])
            ['2.1.0', '2.0.1', '2.0.0']
        """
        compatible_versions = []
        
        with self.db_manager.get_session() as session:
            # Get all versions of the package
            statement = select(PackageVersion).join(
                PackageVersion.package
            ).where(
                PackageVersion.package.has(name=package)
            )
            
            all_versions = session.exec(statement).all()
            
            # Check each version for compatibility
            for pkg_version in all_versions:
                is_compatible = True
                
                # Check against each dependency
                for dep in dependencies:
                    dep_name = dep.get("package_name", "")
                    dep_version = dep.get("version", "")
                    
                    if not dep_name or not dep_version:
                        continue
                    
                    # Check for compatibility rules
                    rule = self.check_package_compatibility(
                        package,
                        pkg_version.version,
                        dep_name,
                        dep_version
                    )
                    
                    if rule and rule.compatibility_type == "incompatible":
                        is_compatible = False
                        break
                
                if is_compatible:
                    compatible_versions.append(pkg_version.version)
        
        # Sort by version (newest first)
        compatible_versions.sort(
            key=lambda v: self.version_matcher.normalize_version(v),
            reverse=True
        )
        
        return compatible_versions[:max_results]
    
    def analyze_package_pair(
        self,
        package1: str,
        version1: str,
        package2: str,
        version2: str
    ) -> Dict:
        """
        Analyze compatibility between two specific packages.
        
        Args:
            package1: First package name
            version1: First package version
            package2: Second package name
            version2: Second package version
        
        Returns:
            Dictionary with analysis results:
                - compatible: bool
                - rule: Optional[CompatibilityRule]
                - issues: List[Issue]
                - recommendations: List[str]
        """
        issues = []
        recommendations = []
        
        # Check for compatibility rule
        rule = self.check_package_compatibility(
            package1, version1,
            package2, version2
        )
        
        compatible = True
        
        if rule:
            if rule.compatibility_type in ["incompatible", "runtime-risk"]:
                compatible = False
                severity = self.severity_scorer.score_compatibility_rule(rule)
                
                issue = Issue(
                    severity=severity,
                    severity_label=self.severity_scorer.get_severity_label(severity),
                    type="runtime_conflict",
                    package_name=package1,
                    description=rule.description,
                    workaround=rule.workaround,
                    affected_packages=[package1, package2],
                    details={
                        "compatibility_type": rule.compatibility_type,
                        "confidence_level": rule.confidence_level
                    }
                )
                issues.append(issue)
                
                if rule.workaround:
                    recommendations.append(rule.workaround)
        
        return {
            "compatible": compatible,
            "rule": rule,
            "issues": issues,
            "recommendations": recommendations
        }
    
    def validate_requirements(
        self,
        requirements: List[str],
        python_version: Optional[str] = None,
        cuda_version: Optional[str] = None
    ) -> AnalysisReport:
        """
        Validate a list of requirements.
        
        Parses requirement strings and performs compatibility analysis.
        
        Args:
            requirements: List of requirement strings (e.g., "torch>=2.0.0")
            python_version: Optional Python version
            cuda_version: Optional CUDA version
        
        Returns:
            AnalysisReport with validation results
        """
        # Parse requirements into dependencies
        # This is a simplified version - full implementation would use
        # the requirements parser from utils
        dependencies = []
        
        for req in requirements:
            # Simple parsing - just extract package name
            # Full implementation would handle version specifiers
            parts = req.split(">=")
            if len(parts) == 2:
                pkg_name = parts[0].strip()
                version = parts[1].strip().split(",")[0]
                dependencies.append({
                    "package_name": pkg_name,
                    "version": version
                })
        
        return self.analyze_dependencies(
            dependencies,
            cuda_version=cuda_version,
            python_version=python_version
        )
    
    # Helper methods
    
    def _generate_recommendations(
        self,
        critical_issues: List[Issue],
        warnings: List[Issue],
        dependencies: List[Dict]
    ) -> List[str]:
        """
        Generate actionable recommendations based on issues.
        
        Args:
            critical_issues: List of critical issues
            warnings: List of warnings
            dependencies: Original dependencies
        
        Returns:
            List of recommendation strings
        """
        recommendations = []
        
        # Add workarounds from issues
        for issue in critical_issues + warnings:
            if issue.workaround and issue.workaround not in recommendations:
                recommendations.append(issue.workaround)
        
        # General recommendations based on issue types
        issue_types = set(issue.type for issue in critical_issues + warnings)
        
        if "version_conflict" in issue_types:
            recommendations.append(
                "Review version constraints and consider relaxing overly strict requirements"
            )
        
        if "abi_conflict" in issue_types:
            recommendations.append(
                "Ensure all packages are built for the same CUDA version"
            )
        
        if "runtime_conflict" in issue_types:
            recommendations.append(
                "Consider using a tested stable stack configuration"
            )
        
        if "python_version" in issue_types:
            recommendations.append(
                "Upgrade Python to meet package requirements"
            )
        
        # If no issues, provide positive feedback
        if not critical_issues and not warnings:
            recommendations.append(
                "All dependencies are compatible - proceed with installation"
            )
        
        return recommendations

# Made with Bob
