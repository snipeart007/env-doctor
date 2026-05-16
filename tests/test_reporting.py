"""
Unit tests for reporting modules.

Tests submission client, AI analyzer, and PR creator functionality.
"""

import json
import time
from pathlib import Path
from unittest.mock import Mock, patch

import pytest

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
    analyze_error_report
)
from env_doctor.reporting.pr_creator import (
    PRCreator,
    GitHubConfig,
    PRResult,
    create_pr_from_analysis
)
from env_doctor.reporting.executor import create_error_report


# Fixtures

@pytest.fixture
def mock_report():
    """Create a mock error report."""
    return {
        "script_path": "test.py",
        "execution": {
            "success": False,
            "exit_code": 1,
            "error": "ImportError: No module named 'torch'",
            "traceback": "Traceback...\nImportError: No module named 'torch'",
            "duration": 1.5
        },
        "parsed_error": {
            "error_type": "ImportError",
            "error_message": "No module named 'torch'",
            "file": "test.py",
            "line": 1,
            "function": "<module>"
        },
        "environment": {
            "python_version": "3.11.0",
            "platform": "Windows",
            "packages": {
                "numpy": "1.24.0",
                "pandas": "2.0.0"
            }
        }
    }


@pytest.fixture
def mock_analysis():
    """Create a mock analysis result."""
    return {
        "error_type": "ImportError",
        "root_cause": "Missing torch package",
        "affected_packages": ["torch", "numpy"],
        "suggested_fix": "Install torch: pip install torch",
        "confidence": 0.95
    }


# Submission Client Tests

def test_submission_config_from_env():
    """Test creating submission config from environment."""
    with patch.dict('os.environ', {
        'ENV_DOCTOR_ENDPOINT_URL': 'https://test.example.com',
        'ENV_DOCTOR_API_KEY': 'test_key',
        'ENV_DOCTOR_MOCK_MODE': 'true'
    }):
        config = SubmissionConfig.from_env()
        assert config.endpoint_url == 'https://test.example.com'
        assert config.api_key == 'test_key'
        assert config.mock_mode is True


def test_submission_client_init():
    """Test submission client initialization."""
    config = SubmissionConfig(mock_mode=True)
    client = SubmissionClient(config)
    assert client.config.mock_mode is True


def test_submit_report_mock(mock_report):
    """Test submitting report in mock mode."""
    config = SubmissionConfig(mock_mode=True)
    client = SubmissionClient(config)
    
    submission_id = client.submit_report(mock_report)
    
    assert submission_id is not None
    assert len(submission_id) > 0
    
    # Verify mock file was created
    mock_dir = Path.home() / ".cache" / "env-doctor" / "mock_submissions"
    submission_file = mock_dir / f"{submission_id}.json"
    assert submission_file.exists()


def test_check_submission_status_mock(mock_report):
    """Test checking submission status in mock mode."""
    config = SubmissionConfig(mock_mode=True)
    client = SubmissionClient(config)
    
    submission_id = client.submit_report(mock_report)
    
    # Initially should be pending
    status = client.check_submission_status(submission_id)
    assert status == SubmissionStatus.PENDING
    
    # After some time should be completed
    time.sleep(6)
    status = client.check_submission_status(submission_id)
    assert status == SubmissionStatus.COMPLETED


def test_get_submission_result_mock(mock_report):
    """Test getting submission result in mock mode."""
    config = SubmissionConfig(mock_mode=True)
    client = SubmissionClient(config)
    
    submission_id = client.submit_report(mock_report)
    
    # Wait for completion
    time.sleep(6)
    
    result = client.get_submission_result(submission_id)
    
    assert result is not None
    assert "analysis" in result
    assert "compatibility_yaml" in result
    assert result["status"] == SubmissionStatus.COMPLETED


def test_wait_for_completion_mock(mock_report):
    """Test waiting for completion in mock mode."""
    config = SubmissionConfig(mock_mode=True)
    client = SubmissionClient(config)
    
    submission_id = client.submit_report(mock_report)
    
    result = client.wait_for_completion(submission_id, max_wait=10, poll_interval=1)
    
    assert result is not None
    assert "analysis" in result


def test_submit_report_convenience_function(mock_report):
    """Test convenience function for submitting report."""
    config = SubmissionConfig(mock_mode=True)
    submission_id = submit_report(mock_report, config)
    
    assert submission_id is not None


# AI Analyzer Tests

def test_watsonx_config_from_env():
    """Test creating watsonx config from environment."""
    with patch.dict('os.environ', {
        'WATSONX_API_KEY': 'test_key',
        'WATSONX_PROJECT_ID': 'test_project',
        'WATSONX_MOCK_MODE': 'true'
    }):
        config = WatsonxConfig.from_env()
        assert config.api_key == 'test_key'
        assert config.project_id == 'test_project'
        assert config.mock_mode is True


def test_ai_analyzer_init():
    """Test AI analyzer initialization."""
    config = WatsonxConfig(mock_mode=True)
    analyzer = AIAnalyzer(config)
    assert analyzer.config.mock_mode is True


def test_analyze_error_report_mock(mock_report):
    """Test analyzing error report in mock mode."""
    config = WatsonxConfig(mock_mode=True)
    analyzer = AIAnalyzer(config)
    
    result = analyzer.analyze_error_report(mock_report)
    
    assert isinstance(result, AnalysisResult)
    assert result.error_type == "ImportError"
    assert len(result.root_cause) > 0
    assert len(result.suggested_fix) > 0
    assert 0 <= result.confidence <= 1
    assert len(result.affected_packages) > 0
    assert len(result.compatibility_yaml) > 0


def test_generate_compatibility_yaml(mock_report):
    """Test generating compatibility YAML."""
    config = WatsonxConfig(mock_mode=True)
    analyzer = AIAnalyzer(config)
    
    analysis = analyzer.analyze_error_report(mock_report)
    yaml_content = analyzer.generate_compatibility_yaml(analysis, mock_report)
    
    assert "incompatibility:" in yaml_content
    assert "error_type:" in yaml_content
    assert "affected_packages:" in yaml_content
    assert "resolution:" in yaml_content


def test_validate_analysis(mock_report):
    """Test validating analysis result."""
    config = WatsonxConfig(mock_mode=True)
    analyzer = AIAnalyzer(config)
    
    result = analyzer.analyze_error_report(mock_report)
    
    assert analyzer.validate_analysis(result) is True
    
    # Test invalid analysis
    invalid_result = AnalysisResult(
        error_type="Test",
        root_cause="",
        affected_packages=[],
        suggested_fix="",
        confidence=0.3,
        compatibility_yaml=""
    )
    assert analyzer.validate_analysis(invalid_result) is False


def test_analyze_error_report_convenience_function(mock_report):
    """Test convenience function for analyzing report."""
    config = WatsonxConfig(mock_mode=True)
    result = analyze_error_report(mock_report, config)
    
    assert isinstance(result, AnalysisResult)


# PR Creator Tests

def test_github_config_from_env():
    """Test creating GitHub config from environment."""
    with patch.dict('os.environ', {
        'GITHUB_TOKEN': 'test_token',
        'GITHUB_REPOSITORY': 'test/repo',
        'GITHUB_MOCK_MODE': 'true'
    }):
        config = GitHubConfig.from_env()
        assert config.token == 'test_token'
        assert config.repository == 'test/repo'
        assert config.mock_mode is True


def test_pr_creator_init():
    """Test PR creator initialization."""
    config = GitHubConfig(mock_mode=True)
    creator = PRCreator(config)
    assert creator.config.mock_mode is True


def test_create_pr_from_analysis_mock(mock_analysis, mock_report):
    """Test creating PR in mock mode."""
    config = GitHubConfig(mock_mode=True)
    creator = PRCreator(config)
    
    yaml_content = "test: yaml"
    result = creator.create_pr_from_analysis(mock_analysis, mock_report, yaml_content)
    
    assert isinstance(result, PRResult)
    assert result.pr_number > 0
    assert len(result.pr_url) > 0
    assert len(result.branch_name) > 0
    assert len(result.commit_sha) > 0


def test_generate_pr_description(mock_analysis, mock_report):
    """Test generating PR description."""
    config = GitHubConfig(mock_mode=True)
    creator = PRCreator(config)
    
    description = creator.generate_pr_description(mock_analysis, mock_report)
    
    assert "New Compatibility Entry" in description
    assert "ImportError" in description
    assert "Root Cause" in description
    assert "Suggested Fix" in description


def test_create_branch_mock():
    """Test creating branch in mock mode."""
    config = GitHubConfig(mock_mode=True)
    creator = PRCreator(config)
    
    branch_name = "test-branch"
    sha = creator.create_branch(branch_name)
    
    assert sha is not None
    assert len(sha) > 0


def test_commit_file_mock():
    """Test committing file in mock mode."""
    config = GitHubConfig(mock_mode=True)
    creator = PRCreator(config)
    
    sha = creator.commit_file(
        "test-branch",
        "test.yaml",
        "content",
        "Test commit"
    )
    
    assert sha is not None
    assert len(sha) > 0


def test_create_pull_request_mock():
    """Test creating pull request in mock mode."""
    config = GitHubConfig(mock_mode=True)
    creator = PRCreator(config)
    
    result = creator.create_pull_request(
        "test-branch",
        "Test PR",
        "Test description"
    )
    
    assert isinstance(result, PRResult)
    assert result.pr_number > 0


def test_create_pr_convenience_function(mock_analysis, mock_report):
    """Test convenience function for creating PR."""
    config = GitHubConfig(mock_mode=True)
    yaml_content = "test: yaml"
    
    result = create_pr_from_analysis(mock_analysis, mock_report, yaml_content, config)
    
    assert isinstance(result, PRResult)


# Integration Tests

def test_full_reporting_flow_mock(mock_report):
    """Test full reporting flow in mock mode."""
    # 1. Submit report
    submission_config = SubmissionConfig(mock_mode=True)
    client = SubmissionClient(submission_config)
    submission_id = client.submit_report(mock_report)
    
    assert submission_id is not None
    
    # 2. Wait for analysis
    result = client.wait_for_completion(submission_id, max_wait=10)
    
    assert result is not None
    assert "analysis" in result
    
    # 3. Create PR
    github_config = GitHubConfig(mock_mode=True)
    creator = PRCreator(github_config)
    
    analysis = result["analysis"]
    yaml_content = result["compatibility_yaml"]
    
    pr_result = creator.create_pr_from_analysis(analysis, mock_report, yaml_content)
    
    assert pr_result is not None
    assert pr_result.pr_number > 0


def test_error_handling_invalid_submission_id():
    """Test error handling for invalid submission ID."""
    config = SubmissionConfig(mock_mode=True)
    client = SubmissionClient(config)
    
    status = client.check_submission_status("invalid_id")
    assert status == SubmissionStatus.FAILED


def test_error_handling_missing_config():
    """Test error handling for missing configuration."""
    # Test without API key (should work in mock mode)
    config = SubmissionConfig(mock_mode=True, api_key=None)
    client = SubmissionClient(config)
    
    # Should still work in mock mode
    assert client.config.mock_mode is True


# Made with Bob