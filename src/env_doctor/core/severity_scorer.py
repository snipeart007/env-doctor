"""
Severity scoring for compatibility issues.

Provides consistent severity scoring across different types of compatibility issues.
"""

from typing import Dict, Optional

from ..database.models import CompatibilityRule


class SeverityScorer:
    """Calculate severity scores for compatibility issues."""
    
    # Severity levels
    CRITICAL = 100  # Will definitely break
    HIGH = 75       # Very likely to break
    MEDIUM = 50     # May break
    LOW = 25        # Minor issues
    INFO = 0        # Informational
    
    # Compatibility type base scores
    COMPATIBILITY_TYPE_SCORES = {
        "incompatible": CRITICAL,
        "runtime-risk": HIGH,
        "partial": MEDIUM,
        "untested": LOW,
        "compatible": INFO,
    }
    
    # Confidence level weights
    CONFIDENCE_WEIGHTS = {
        "production-tested": 1.0,
        "stable": 0.9,
        "community-tested": 0.7,
        "experimental": 0.5,
    }
    
    # Conflict type base scores
    CONFLICT_TYPE_SCORES = {
        "version_conflict": CRITICAL,      # Unsatisfiable constraints
        "abi_conflict": CRITICAL,          # CUDA/ABI mismatch
        "runtime_conflict": HIGH,          # Known broken combinations
        "dependency_conflict": MEDIUM,     # Transitive dependency issues
        "python_version": HIGH,            # Python version incompatibility
    }
    
    @staticmethod
    def score_compatibility_rule(rule: CompatibilityRule) -> int:
        """
        Score a compatibility rule based on type and confidence.
        
        Args:
            rule: CompatibilityRule from database
            
        Returns:
            Severity score (0-100)
            
        Examples:
            >>> rule = CompatibilityRule(
            ...     compatibility_type="incompatible",
            ...     confidence_level="production-tested",
            ...     severity=100
            ... )
            >>> SeverityScorer.score_compatibility_rule(rule)
            100
        """
        # Use the rule's own severity if provided
        if rule.severity is not None:
            return rule.severity
        
        # Otherwise calculate from type and confidence
        base_score = SeverityScorer.COMPATIBILITY_TYPE_SCORES.get(
            rule.compatibility_type,
            SeverityScorer.MEDIUM
        )
        
        return SeverityScorer.apply_confidence_weight(
            base_score,
            rule.confidence_level
        )
    
    @staticmethod
    def score_version_conflict(conflict: Dict) -> int:
        """
        Score a version conflict.
        
        Args:
            conflict: Conflict dictionary with details
            
        Returns:
            Severity score (0-100)
            
        Examples:
            >>> conflict = {
            ...     "package_name": "torch",
            ...     "conflicting_requirements": [">=2.0", "<2.0"]
            ... }
            >>> SeverityScorer.score_version_conflict(conflict)
            100
        """
        # Version conflicts are always critical - they cannot be satisfied
        return SeverityScorer.CRITICAL
    
    @staticmethod
    def score_abi_conflict(conflict: Dict) -> int:
        """
        Score an ABI conflict (CUDA version mismatch).
        
        Args:
            conflict: ABI conflict dictionary
            
        Returns:
            Severity score (0-100)
            
        Examples:
            >>> conflict = {
            ...     "package_name": "torch",
            ...     "required_cuda": "11.8",
            ...     "available_cuda": "12.0"
            ... }
            >>> SeverityScorer.score_abi_conflict(conflict)
            100
        """
        # ABI conflicts are critical - will cause runtime failures
        return SeverityScorer.CRITICAL
    
    @staticmethod
    def score_runtime_conflict(conflict: Dict, confidence: str = "stable") -> int:
        """
        Score a runtime conflict.
        
        Args:
            conflict: Runtime conflict dictionary
            confidence: Confidence level of the conflict information
            
        Returns:
            Severity score (0-100)
            
        Examples:
            >>> conflict = {
            ...     "package1": "torch",
            ...     "package2": "tensorflow"
            ... }
            >>> SeverityScorer.score_runtime_conflict(conflict, "production-tested")
            75
        """
        base_score = SeverityScorer.HIGH
        return SeverityScorer.apply_confidence_weight(base_score, confidence)
    
    @staticmethod
    def score_python_version_conflict(
        required: str,
        available: str
    ) -> int:
        """
        Score a Python version conflict.
        
        Args:
            required: Required Python version specifier
            available: Available Python version
            
        Returns:
            Severity score (0-100)
            
        Examples:
            >>> SeverityScorer.score_python_version_conflict(">=3.10", "3.9.0")
            75
        """
        # Python version conflicts are high severity
        return SeverityScorer.HIGH
    
    @staticmethod
    def apply_confidence_weight(
        base_score: int,
        confidence_level: str
    ) -> int:
        """
        Apply confidence weighting to score.
        
        Confidence weights:
        - production-tested: 1.0x (no reduction)
        - stable: 0.9x
        - community-tested: 0.7x
        - experimental: 0.5x
        
        Args:
            base_score: Base severity score
            confidence_level: Confidence level string
            
        Returns:
            Weighted severity score
            
        Examples:
            >>> SeverityScorer.apply_confidence_weight(100, "production-tested")
            100
            >>> SeverityScorer.apply_confidence_weight(100, "experimental")
            50
        """
        weight = SeverityScorer.CONFIDENCE_WEIGHTS.get(
            confidence_level,
            0.7  # Default to community-tested
        )
        
        return int(base_score * weight)
    
    @staticmethod
    def get_severity_label(score: int) -> str:
        """
        Get severity label from score.
        
        Args:
            score: Severity score (0-100)
            
        Returns:
            Severity label string
            
        Examples:
            >>> SeverityScorer.get_severity_label(100)
            'CRITICAL'
            >>> SeverityScorer.get_severity_label(50)
            'MEDIUM'
        """
        if score >= SeverityScorer.CRITICAL:
            return "CRITICAL"
        elif score >= SeverityScorer.HIGH:
            return "HIGH"
        elif score >= SeverityScorer.MEDIUM:
            return "MEDIUM"
        elif score >= SeverityScorer.LOW:
            return "LOW"
        else:
            return "INFO"
    
    @staticmethod
    def get_severity_color(score: int) -> str:
        """
        Get Rich color for severity level.
        
        Args:
            score: Severity score (0-100)
            
        Returns:
            Rich color string
            
        Examples:
            >>> SeverityScorer.get_severity_color(100)
            'red'
            >>> SeverityScorer.get_severity_color(50)
            'yellow'
        """
        if score >= SeverityScorer.CRITICAL:
            return "red"
        elif score >= SeverityScorer.HIGH:
            return "orange1"
        elif score >= SeverityScorer.MEDIUM:
            return "yellow"
        elif score >= SeverityScorer.LOW:
            return "blue"
        else:
            return "green"
    
    @staticmethod
    def get_severity_emoji(score: int) -> str:
        """
        Get emoji for severity level.
        
        Args:
            score: Severity score (0-100)
            
        Returns:
            Emoji string
            
        Examples:
            >>> SeverityScorer.get_severity_emoji(100)
            '🔴'
            >>> SeverityScorer.get_severity_emoji(50)
            '🟡'
        """
        if score >= SeverityScorer.CRITICAL:
            return "🔴"
        elif score >= SeverityScorer.HIGH:
            return "🟠"
        elif score >= SeverityScorer.MEDIUM:
            return "🟡"
        elif score >= SeverityScorer.LOW:
            return "🔵"
        else:
            return "🟢"
    
    @staticmethod
    def categorize_by_severity(
        issues: list,
        score_key: str = "severity"
    ) -> Dict[str, list]:
        """
        Categorize issues by severity level.
        
        Args:
            issues: List of issue dictionaries
            score_key: Key to access severity score in each issue
            
        Returns:
            Dictionary with keys: critical, high, medium, low, info
            
        Examples:
            >>> issues = [
            ...     {"severity": 100, "msg": "Critical issue"},
            ...     {"severity": 50, "msg": "Medium issue"}
            ... ]
            >>> result = SeverityScorer.categorize_by_severity(issues)
            >>> len(result["critical"])
            1
        """
        categorized = {
            "critical": [],
            "high": [],
            "medium": [],
            "low": [],
            "info": []
        }
        
        for issue in issues:
            score = issue.get(score_key, 0)
            label = SeverityScorer.get_severity_label(score).lower()
            categorized[label].append(issue)
        
        return categorized
    
    @staticmethod
    def get_max_severity(issues: list, score_key: str = "severity") -> int:
        """
        Get maximum severity from a list of issues.
        
        Args:
            issues: List of issue dictionaries
            score_key: Key to access severity score in each issue
            
        Returns:
            Maximum severity score, or 0 if no issues
            
        Examples:
            >>> issues = [
            ...     {"severity": 50},
            ...     {"severity": 100},
            ...     {"severity": 25}
            ... ]
            >>> SeverityScorer.get_max_severity(issues)
            100
        """
        if not issues:
            return 0
        
        return max(issue.get(score_key, 0) for issue in issues)

# Made with Bob
