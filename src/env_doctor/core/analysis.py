"""
Analysis report data structures.

Provides structured representations of compatibility analysis results.
"""

from dataclasses import dataclass, field, asdict
from typing import List, Dict, Optional
import json

from .severity_scorer import SeverityScorer


@dataclass
class Issue:
    """
    Compatibility issue.
    
    Represents a single compatibility problem found during analysis.
    """
    severity: int
    severity_label: str
    type: str  # version_conflict, runtime_conflict, abi_conflict, etc.
    package_name: str
    description: str
    workaround: Optional[str] = None
    affected_packages: Optional[List[str]] = None
    details: Optional[Dict] = None
    
    def __post_init__(self):
        """Ensure affected_packages is a list."""
        if self.affected_packages is None:
            self.affected_packages = []
        if self.details is None:
            self.details = {}
    
    def to_dict(self) -> Dict:
        """Convert to dictionary."""
        return asdict(self)
    
    def get_color(self) -> str:
        """Get Rich color for this issue's severity."""
        return SeverityScorer.get_severity_color(self.severity)
    
    def get_emoji(self) -> str:
        """Get emoji for this issue's severity."""
        return SeverityScorer.get_severity_emoji(self.severity)
    
    @classmethod
    def from_dict(cls, data: Dict) -> "Issue":
        """Create Issue from dictionary."""
        return cls(**data)


@dataclass
class AnalysisReport:
    """
    Complete compatibility analysis report.
    
    Contains all findings from a compatibility analysis, organized by severity.
    """
    status: str  # ok, warnings, errors
    summary: str
    critical_issues: List[Issue] = field(default_factory=list)
    warnings: List[Issue] = field(default_factory=list)
    info: List[Issue] = field(default_factory=list)
    recommendations: List[str] = field(default_factory=list)
    details: Dict = field(default_factory=dict)
    
    def has_critical_issues(self) -> bool:
        """
        Check if report has critical issues.
        
        Returns:
            True if there are any critical issues
        """
        return len(self.critical_issues) > 0
    
    def has_warnings(self) -> bool:
        """
        Check if report has warnings.
        
        Returns:
            True if there are any warnings
        """
        return len(self.warnings) > 0
    
    def has_any_issues(self) -> bool:
        """
        Check if report has any issues (critical or warnings).
        
        Returns:
            True if there are any issues
        """
        return self.has_critical_issues() or self.has_warnings()
    
    def get_exit_code(self) -> int:
        """
        Get appropriate exit code.
        
        Returns:
            0: No issues
            1: Warnings only
            2: Critical issues
        """
        if self.has_critical_issues():
            return 2
        elif self.has_warnings():
            return 1
        else:
            return 0
    
    def get_total_issue_count(self) -> int:
        """
        Get total number of issues.
        
        Returns:
            Total count of all issues
        """
        return len(self.critical_issues) + len(self.warnings) + len(self.info)
    
    def get_max_severity(self) -> int:
        """
        Get maximum severity score across all issues.
        
        Returns:
            Maximum severity score, or 0 if no issues
        """
        all_issues = self.critical_issues + self.warnings + self.info
        if not all_issues:
            return 0
        return max(issue.severity for issue in all_issues)
    
    def to_dict(self) -> Dict:
        """
        Convert to dictionary for JSON output.
        
        Returns:
            Dictionary representation of the report
        """
        return {
            "status": self.status,
            "summary": self.summary,
            "exit_code": self.get_exit_code(),
            "total_issues": self.get_total_issue_count(),
            "max_severity": self.get_max_severity(),
            "critical_issues": [issue.to_dict() for issue in self.critical_issues],
            "warnings": [issue.to_dict() for issue in self.warnings],
            "info": [issue.to_dict() for issue in self.info],
            "recommendations": self.recommendations,
            "details": self.details
        }
    
    def to_json(self, indent: int = 2) -> str:
        """
        Convert to JSON string.
        
        Args:
            indent: JSON indentation level
            
        Returns:
            JSON string representation
        """
        return json.dumps(self.to_dict(), indent=indent)
    
    def format_rich(self) -> str:
        """
        Format for Rich console output.
        
        Returns:
            Rich-formatted string for console display
        """
        from rich.console import Console
        from rich.panel import Panel
        from rich.table import Table
        from rich.text import Text
        from io import StringIO
        
        console = Console(file=StringIO(), force_terminal=True)
        
        # Status header
        status_color = "green" if self.status == "ok" else "yellow" if self.status == "warnings" else "red"
        console.print(f"\n[bold {status_color}]Analysis Status: {self.status.upper()}[/bold {status_color}]")
        console.print(f"[dim]{self.summary}[/dim]\n")
        
        # Critical issues
        if self.critical_issues:
            console.print("[bold red]Critical Issues:[/bold red]")
            for issue in self.critical_issues:
                console.print(f"  {issue.get_emoji()} [{issue.get_color()}]{issue.package_name}[/{issue.get_color()}]: {issue.description}")
                if issue.workaround:
                    console.print(f"    [dim]Workaround: {issue.workaround}[/dim]")
            console.print()
        
        # Warnings
        if self.warnings:
            console.print("[bold yellow]Warnings:[/bold yellow]")
            for issue in self.warnings:
                console.print(f"  {issue.get_emoji()} [{issue.get_color()}]{issue.package_name}[/{issue.get_color()}]: {issue.description}")
                if issue.workaround:
                    console.print(f"    [dim]Workaround: {issue.workaround}[/dim]")
            console.print()
        
        # Info
        if self.info:
            console.print("[bold blue]Information:[/bold blue]")
            for issue in self.info:
                console.print(f"  {issue.get_emoji()} {issue.package_name}: {issue.description}")
            console.print()
        
        # Recommendations
        if self.recommendations:
            console.print("[bold cyan]Recommendations:[/bold cyan]")
            for i, rec in enumerate(self.recommendations, 1):
                console.print(f"  {i}. {rec}")
            console.print()
        
        return console.file.getvalue()
    
    def format_summary(self) -> str:
        """
        Format a brief summary.
        
        Returns:
            Brief summary string
        """
        parts = []
        
        if self.critical_issues:
            parts.append(f"{len(self.critical_issues)} critical")
        if self.warnings:
            parts.append(f"{len(self.warnings)} warnings")
        if self.info:
            parts.append(f"{len(self.info)} info")
        
        if not parts:
            return "No issues found"
        
        return f"Found: {', '.join(parts)}"
    
    @classmethod
    def from_dict(cls, data: Dict) -> "AnalysisReport":
        """
        Create AnalysisReport from dictionary.
        
        Args:
            data: Dictionary representation
            
        Returns:
            AnalysisReport instance
        """
        return cls(
            status=data["status"],
            summary=data["summary"],
            critical_issues=[Issue.from_dict(i) for i in data.get("critical_issues", [])],
            warnings=[Issue.from_dict(i) for i in data.get("warnings", [])],
            info=[Issue.from_dict(i) for i in data.get("info", [])],
            recommendations=data.get("recommendations", []),
            details=data.get("details", {})
        )
    
    @classmethod
    def from_json(cls, json_str: str) -> "AnalysisReport":
        """
        Create AnalysisReport from JSON string.
        
        Args:
            json_str: JSON string representation
            
        Returns:
            AnalysisReport instance
        """
        data = json.loads(json_str)
        return cls.from_dict(data)
    
    @classmethod
    def create_ok(cls, summary: str = "No compatibility issues found") -> "AnalysisReport":
        """
        Create a report with no issues.
        
        Args:
            summary: Summary message
            
        Returns:
            AnalysisReport with ok status
        """
        return cls(
            status="ok",
            summary=summary,
            recommendations=["All dependencies are compatible"]
        )
    
    @classmethod
    def create_error(
        cls,
        summary: str,
        critical_issues: List[Issue],
        recommendations: Optional[List[str]] = None
    ) -> "AnalysisReport":
        """
        Create a report with critical issues.
        
        Args:
            summary: Summary message
            critical_issues: List of critical issues
            recommendations: Optional recommendations
            
        Returns:
            AnalysisReport with errors status
        """
        return cls(
            status="errors",
            summary=summary,
            critical_issues=critical_issues,
            recommendations=recommendations or []
        )
    
    @classmethod
    def create_warning(
        cls,
        summary: str,
        warnings: List[Issue],
        recommendations: Optional[List[str]] = None
    ) -> "AnalysisReport":
        """
        Create a report with warnings.
        
        Args:
            summary: Summary message
            warnings: List of warning issues
            recommendations: Optional recommendations
            
        Returns:
            AnalysisReport with warnings status
        """
        return cls(
            status="warnings",
            summary=summary,
            warnings=warnings,
            recommendations=recommendations or []
        )


def merge_reports(reports: List[AnalysisReport]) -> AnalysisReport:
    """
    Merge multiple analysis reports into one.
    
    Args:
        reports: List of AnalysisReport instances
        
    Returns:
        Merged AnalysisReport
    """
    if not reports:
        return AnalysisReport.create_ok()
    
    if len(reports) == 1:
        return reports[0]
    
    # Merge all issues
    all_critical = []
    all_warnings = []
    all_info = []
    all_recommendations = []
    merged_details = {}
    
    for report in reports:
        all_critical.extend(report.critical_issues)
        all_warnings.extend(report.warnings)
        all_info.extend(report.info)
        all_recommendations.extend(report.recommendations)
        merged_details.update(report.details)
    
    # Determine overall status
    if all_critical:
        status = "errors"
        summary = f"Found {len(all_critical)} critical issues across {len(reports)} analyses"
    elif all_warnings:
        status = "warnings"
        summary = f"Found {len(all_warnings)} warnings across {len(reports)} analyses"
    else:
        status = "ok"
        summary = f"No issues found across {len(reports)} analyses"
    
    # Remove duplicate recommendations
    unique_recommendations = list(dict.fromkeys(all_recommendations))
    
    return AnalysisReport(
        status=status,
        summary=summary,
        critical_issues=all_critical,
        warnings=all_warnings,
        info=all_info,
        recommendations=unique_recommendations,
        details=merged_details
    )

# Made with Bob
