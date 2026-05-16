"""
Reporting module for env-doctor.

Provides functionality for executing scripts, capturing errors, and submitting
incompatibility reports to the serverless endpoint for AI analysis.
"""

from env_doctor.reporting.executor import (
    execute_script,
    execute_notebook,
    create_error_report,
    parse_error_traceback
)
from env_doctor.reporting.submission_client import (
    SubmissionClient,
    SubmissionConfig,
    SubmissionStatus,
    submit_report,
    check_submission_status,
    get_submission_result
)
from env_doctor.reporting.ai_analyzer import (
    AIAnalyzer,
    WatsonxConfig,
    AnalysisResult,
    analyze_error_report,
    generate_compatibility_yaml
)
from env_doctor.reporting.pr_creator import (
    PRCreator,
    GitHubConfig,
    PRResult,
    create_pr_from_analysis,
    generate_pr_description
)

__all__ = [
    # Executor
    "execute_script",
    "execute_notebook",
    "create_error_report",
    "parse_error_traceback",
    # Submission Client
    "SubmissionClient",
    "SubmissionConfig",
    "SubmissionStatus",
    "submit_report",
    "check_submission_status",
    "get_submission_result",
    # AI Analyzer
    "AIAnalyzer",
    "WatsonxConfig",
    "AnalysisResult",
    "analyze_error_report",
    "generate_compatibility_yaml",
    # PR Creator
    "PRCreator",
    "GitHubConfig",
    "PRResult",
    "create_pr_from_analysis",
    "generate_pr_description",
]


# Made with Bob