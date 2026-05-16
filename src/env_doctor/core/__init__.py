"""
Core compatibility analysis modules.

This package provides the complete compatibility analysis engine for env-doctor,
including version matching, conflict detection, severity scoring, and reporting.
"""

from .compatibility import CompatibilityAnalyzer
from .conflict_detector import ConflictDetector
from .version_matcher import VersionMatcher
from .severity_scorer import SeverityScorer
from .analysis import AnalysisReport, Issue, merge_reports
from .dependency_graph import DependencyGraph

__all__ = [
    # Main analyzer
    "CompatibilityAnalyzer",
    
    # Core components
    "ConflictDetector",
    "VersionMatcher",
    "SeverityScorer",
    "DependencyGraph",
    
    # Report structures
    "AnalysisReport",
    "Issue",
    "merge_reports",
]

__version__ = "0.1.0"

# Made with Bob
