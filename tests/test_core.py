"""
Tests for core compatibility analysis components.

Tests version matching, conflict detection, severity scoring, and analysis reporting.
"""

import pytest
from pathlib import Path

from env_doctor.core import (
    CompatibilityAnalyzer,
    ConflictDetector,
    VersionMatcher,
    SeverityScorer,
    AnalysisReport,
    Issue,
    DependencyGraph,
    merge_reports
)
from env_doctor.database.manager import DatabaseManager
from env_doctor.database.models import CompatibilityRule


class TestVersionMatcher:
    """Test version matching functionality."""
    
    def test_version_matches_simple(self):
        """Test simple version matching."""
        assert VersionMatcher.version_matches("2.1.0", ">=2.0.0")
        assert VersionMatcher.version_matches("2.1.0", ">=2.0.0,<3.0.0")
        assert not VersionMatcher.version_matches("1.9.0", ">=2.0.0")
    
    def test_version_matches_complex(self):
        """Test complex version specifiers."""
        assert VersionMatcher.version_matches("2.1.0", ">=2.0.0,<3.0.0,!=2.0.5")
        assert not VersionMatcher.version_matches("2.0.5", ">=2.0.0,!=2.0.5")
    
    def test_get_matching_versions(self):
        """Test getting matching versions."""
        versions = ["1.9.0", "2.0.0", "2.1.0", "3.0.0"]
        matching = VersionMatcher.get_matching_versions(versions, ">=2.0.0,<3.0.0")
        
        assert "2.1.0" in matching
        assert "2.0.0" in matching
        assert "1.9.0" not in matching
        assert "3.0.0" not in matching
        
        # Should be sorted newest first
        assert matching[0] == "2.1.0"
    
    def test_is_compatible_range(self):
        """Test range compatibility checking."""
        # Overlapping ranges
        assert VersionMatcher.is_compatible_range(">=2.0.0,<3.0.0", ">=2.1.0,<4.0.0")
        
        # Non-overlapping ranges
        assert not VersionMatcher.is_compatible_range(">=2.0.0,<3.0.0", ">=3.0.0,<4.0.0")
    
    def test_normalize_version(self):
        """Test version normalization."""
        assert VersionMatcher.normalize_version("2.1.0") == "2.1.0"
        assert VersionMatcher.normalize_version("v2.1.0") == "2.1.0"
        assert VersionMatcher.normalize_version("V2.1.0") == "2.1.0"
    
    def test_compare_versions(self):
        """Test version comparison."""
        assert VersionMatcher.compare_versions("2.0.0", "2.1.0") == -1
        assert VersionMatcher.compare_versions("2.1.0", "2.1.0") == 0
        assert VersionMatcher.compare_versions("2.2.0", "2.1.0") == 1
    
    def test_get_latest_version(self):
        """Test getting latest version."""
        versions = ["1.0.0", "2.1.0", "2.0.0", "1.9.0"]
        assert VersionMatcher.get_latest_version(versions) == "2.1.0"
        
        assert VersionMatcher.get_latest_version([]) is None
    
    def test_is_prerelease(self):
        """Test pre-release detection."""
        assert not VersionMatcher.is_prerelease("2.1.0")
        assert VersionMatcher.is_prerelease("2.1.0rc1")
        assert VersionMatcher.is_prerelease("2.1.0a1")
        assert VersionMatcher.is_prerelease("2.1.0b1")
    
    def test_satisfies_python_requirement(self):
        """Test Python version requirement checking."""
        assert VersionMatcher.satisfies_python_requirement("3.10.0", ">=3.8")
        assert not VersionMatcher.satisfies_python_requirement("3.7.0", ">=3.8")
        assert VersionMatcher.satisfies_python_requirement("3.10.0", None)


class TestSeverityScorer:
    """Test severity scoring functionality."""
    
    def test_severity_levels(self):
        """Test severity level constants."""
        assert SeverityScorer.CRITICAL == 100
        assert SeverityScorer.HIGH == 75
        assert SeverityScorer.MEDIUM == 50
        assert SeverityScorer.LOW == 25
        assert SeverityScorer.INFO == 0
    
    def test_score_version_conflict(self):
        """Test version conflict scoring."""
        conflict = {"package_name": "torch"}
        score = SeverityScorer.score_version_conflict(conflict)
        assert score == SeverityScorer.CRITICAL
    
    def test_score_abi_conflict(self):
        """Test ABI conflict scoring."""
        conflict = {"package_name": "torch"}
        score = SeverityScorer.score_abi_conflict(conflict)
        assert score == SeverityScorer.CRITICAL
    
    def test_score_runtime_conflict(self):
        """Test runtime conflict scoring."""
        conflict = {"package1": "torch", "package2": "tensorflow"}
        score = SeverityScorer.score_runtime_conflict(conflict, "production-tested")
        assert score == SeverityScorer.HIGH
    
    def test_apply_confidence_weight(self):
        """Test confidence weighting."""
        base_score = 100
        
        assert SeverityScorer.apply_confidence_weight(base_score, "production-tested") == 100
        assert SeverityScorer.apply_confidence_weight(base_score, "stable") == 90
        assert SeverityScorer.apply_confidence_weight(base_score, "community-tested") == 70
        assert SeverityScorer.apply_confidence_weight(base_score, "experimental") == 50
    
    def test_get_severity_label(self):
        """Test severity label generation."""
        assert SeverityScorer.get_severity_label(100) == "CRITICAL"
        assert SeverityScorer.get_severity_label(75) == "HIGH"
        assert SeverityScorer.get_severity_label(50) == "MEDIUM"
        assert SeverityScorer.get_severity_label(25) == "LOW"
        assert SeverityScorer.get_severity_label(0) == "INFO"
    
    def test_get_severity_color(self):
        """Test severity color generation."""
        assert SeverityScorer.get_severity_color(100) == "red"
        assert SeverityScorer.get_severity_color(75) == "orange1"
        assert SeverityScorer.get_severity_color(50) == "yellow"
        assert SeverityScorer.get_severity_color(25) == "blue"
        assert SeverityScorer.get_severity_color(0) == "green"
    
    def test_categorize_by_severity(self):
        """Test issue categorization."""
        issues = [
            {"severity": 100, "msg": "Critical"},
            {"severity": 75, "msg": "High"},
            {"severity": 50, "msg": "Medium"},
            {"severity": 25, "msg": "Low"},
            {"severity": 0, "msg": "Info"}
        ]
        
        categorized = SeverityScorer.categorize_by_severity(issues)
        
        assert len(categorized["critical"]) == 1
        assert len(categorized["high"]) == 1
        assert len(categorized["medium"]) == 1
        assert len(categorized["low"]) == 1
        assert len(categorized["info"]) == 1
    
    def test_get_max_severity(self):
        """Test maximum severity calculation."""
        issues = [
            {"severity": 50},
            {"severity": 100},
            {"severity": 25}
        ]
        
        assert SeverityScorer.get_max_severity(issues) == 100
        assert SeverityScorer.get_max_severity([]) == 0


class TestIssue:
    """Test Issue data structure."""
    
    def test_issue_creation(self):
        """Test creating an issue."""
        issue = Issue(
            severity=100,
            severity_label="CRITICAL",
            type="version_conflict",
            package_name="torch",
            description="Version conflict detected"
        )
        
        assert issue.severity == 100
        assert issue.severity_label == "CRITICAL"
        assert issue.type == "version_conflict"
        assert issue.package_name == "torch"
    
    def test_issue_to_dict(self):
        """Test converting issue to dictionary."""
        issue = Issue(
            severity=100,
            severity_label="CRITICAL",
            type="version_conflict",
            package_name="torch",
            description="Version conflict detected"
        )
        
        data = issue.to_dict()
        assert data["severity"] == 100
        assert data["package_name"] == "torch"
    
    def test_issue_get_color(self):
        """Test getting issue color."""
        issue = Issue(
            severity=100,
            severity_label="CRITICAL",
            type="version_conflict",
            package_name="torch",
            description="Test"
        )
        
        assert issue.get_color() == "red"
    
    def test_issue_from_dict(self):
        """Test creating issue from dictionary."""
        data = {
            "severity": 100,
            "severity_label": "CRITICAL",
            "type": "version_conflict",
            "package_name": "torch",
            "description": "Test"
        }
        
        issue = Issue.from_dict(data)
        assert issue.severity == 100
        assert issue.package_name == "torch"


class TestAnalysisReport:
    """Test AnalysisReport data structure."""
    
    def test_report_creation(self):
        """Test creating a report."""
        report = AnalysisReport(
            status="ok",
            summary="No issues found"
        )
        
        assert report.status == "ok"
        assert report.summary == "No issues found"
    
    def test_has_critical_issues(self):
        """Test checking for critical issues."""
        issue = Issue(
            severity=100,
            severity_label="CRITICAL",
            type="version_conflict",
            package_name="torch",
            description="Test"
        )
        
        report = AnalysisReport(
            status="errors",
            summary="Has errors",
            critical_issues=[issue]
        )
        
        assert report.has_critical_issues()
    
    def test_has_warnings(self):
        """Test checking for warnings."""
        issue = Issue(
            severity=50,
            severity_label="MEDIUM",
            type="runtime_conflict",
            package_name="torch",
            description="Test"
        )
        
        report = AnalysisReport(
            status="warnings",
            summary="Has warnings",
            warnings=[issue]
        )
        
        assert report.has_warnings()
    
    def test_get_exit_code(self):
        """Test exit code generation."""
        # No issues
        report_ok = AnalysisReport(status="ok", summary="OK")
        assert report_ok.get_exit_code() == 0
        
        # Warnings only
        issue_warning = Issue(
            severity=50, severity_label="MEDIUM",
            type="test", package_name="test", description="Test"
        )
        report_warning = AnalysisReport(
            status="warnings", summary="Warnings",
            warnings=[issue_warning]
        )
        assert report_warning.get_exit_code() == 1
        
        # Critical issues
        issue_critical = Issue(
            severity=100, severity_label="CRITICAL",
            type="test", package_name="test", description="Test"
        )
        report_error = AnalysisReport(
            status="errors", summary="Errors",
            critical_issues=[issue_critical]
        )
        assert report_error.get_exit_code() == 2
    
    def test_to_dict(self):
        """Test converting report to dictionary."""
        report = AnalysisReport(
            status="ok",
            summary="No issues"
        )
        
        data = report.to_dict()
        assert data["status"] == "ok"
        assert data["summary"] == "No issues"
        assert "exit_code" in data
    
    def test_to_json(self):
        """Test converting report to JSON."""
        report = AnalysisReport(
            status="ok",
            summary="No issues"
        )
        
        json_str = report.to_json()
        assert "ok" in json_str
        assert "No issues" in json_str
    
    def test_create_ok(self):
        """Test creating OK report."""
        report = AnalysisReport.create_ok()
        assert report.status == "ok"
        assert not report.has_critical_issues()
    
    def test_create_error(self):
        """Test creating error report."""
        issue = Issue(
            severity=100, severity_label="CRITICAL",
            type="test", package_name="test", description="Test"
        )
        
        report = AnalysisReport.create_error(
            "Has errors",
            [issue]
        )
        
        assert report.status == "errors"
        assert report.has_critical_issues()
    
    def test_merge_reports(self):
        """Test merging multiple reports."""
        report1 = AnalysisReport.create_ok()
        
        issue = Issue(
            severity=100, severity_label="CRITICAL",
            type="test", package_name="test", description="Test"
        )
        report2 = AnalysisReport.create_error("Error", [issue])
        
        merged = merge_reports([report1, report2])
        
        assert merged.status == "errors"
        assert merged.has_critical_issues()


class TestConflictDetector:
    """Test conflict detection functionality."""
    
    @pytest.fixture
    def db_manager(self, tmp_path):
        """Create a temporary database for testing."""
        db_path = tmp_path / "test.db"
        manager = DatabaseManager(str(db_path))
        manager.create_tables()
        return manager
    
    @pytest.fixture
    def detector(self, db_manager):
        """Create a conflict detector."""
        return ConflictDetector(db_manager)
    
    def test_detect_version_conflicts(self, detector):
        """Test version conflict detection."""
        dependencies = [
            {
                "package_name": "pkg1",
                "version": "1.0.0",
                "requires": [
                    {"dependency_name": "dep", "version_specifier": ">=2.0"}
                ]
            },
            {
                "package_name": "pkg2",
                "version": "1.0.0",
                "requires": [
                    {"dependency_name": "dep", "version_specifier": "<2.0"}
                ]
            }
        ]
        
        conflicts = detector.detect_version_conflicts(dependencies)
        
        # Should detect conflict on 'dep'
        assert len(conflicts) > 0
        assert conflicts[0].package_name == "dep"
        assert conflicts[0].type == "version_conflict"
    
    def test_detect_no_conflicts(self, detector):
        """Test when there are no conflicts."""
        dependencies = [
            {
                "package_name": "pkg1",
                "version": "1.0.0",
                "requires": [
                    {"dependency_name": "dep", "version_specifier": ">=2.0"}
                ]
            },
            {
                "package_name": "pkg2",
                "version": "1.0.0",
                "requires": [
                    {"dependency_name": "dep", "version_specifier": ">=2.1"}
                ]
            }
        ]
        
        conflicts = detector.detect_version_conflicts(dependencies)
        
        # Should not detect conflicts (ranges overlap)
        assert len(conflicts) == 0


class TestCompatibilityAnalyzer:
    """Test main compatibility analyzer."""
    
    @pytest.fixture
    def db_manager(self, tmp_path):
        """Create a temporary database for testing."""
        db_path = tmp_path / "test.db"
        manager = DatabaseManager(str(db_path))
        manager.create_tables()
        return manager
    
    @pytest.fixture
    def analyzer(self, db_manager):
        """Create a compatibility analyzer."""
        return CompatibilityAnalyzer(db_manager)
    
    def test_analyze_dependencies_no_issues(self, analyzer):
        """Test analyzing dependencies with no issues."""
        dependencies = [
            {"package_name": "numpy", "version": "1.24.0"},
            {"package_name": "pandas", "version": "2.0.0"}
        ]
        
        report = analyzer.analyze_dependencies(dependencies)
        
        assert report.status == "ok"
        assert not report.has_critical_issues()
    
    def test_analyze_dependencies_with_conflicts(self, analyzer):
        """Test analyzing dependencies with conflicts."""
        dependencies = [
            {
                "package_name": "pkg1",
                "version": "1.0.0",
                "requires": [
                    {"dependency_name": "dep", "version_specifier": ">=2.0"}
                ]
            },
            {
                "package_name": "pkg2",
                "version": "1.0.0",
                "requires": [
                    {"dependency_name": "dep", "version_specifier": "<2.0"}
                ]
            }
        ]
        
        report = analyzer.analyze_dependencies(dependencies)
        
        assert report.status == "errors"
        assert report.has_critical_issues()


def test_integration():
    """Test full integration of core components."""
    # Create temporary database
    import tempfile
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "test.db"
        db_manager = DatabaseManager(str(db_path))
        db_manager.create_tables()
        
        # Create analyzer
        analyzer = CompatibilityAnalyzer(db_manager)
        
        # Analyze some dependencies
        dependencies = [
            {"package_name": "torch", "version": "2.1.0"},
            {"package_name": "numpy", "version": "1.24.0"}
        ]
        
        report = analyzer.analyze_dependencies(dependencies)
        
        # Should complete without errors
        assert report is not None
        assert isinstance(report, AnalysisReport)
        
        # Clean up
        db_manager.close()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

# Made with Bob
