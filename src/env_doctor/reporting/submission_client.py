"""
Submission client for reporting incompatibilities to serverless endpoint.

Handles HTTP communication with the env-doctor serverless API for submitting
error reports and retrieving AI analysis results.
"""

import json
import os
import time
import uuid
from pathlib import Path
from typing import Any, Dict, Optional
from urllib.parse import urljoin

import httpx
from pydantic import BaseModel, Field


class SubmissionConfig(BaseModel):
    """Configuration for submission client."""
    
    endpoint_url: str = Field(
        default="https://api.env-doctor.dev",
        description="Base URL for serverless endpoint"
    )
    api_key: Optional[str] = Field(
        default=None,
        description="API key for authentication"
    )
    timeout: int = Field(
        default=30,
        description="Request timeout in seconds"
    )
    max_retries: int = Field(
        default=3,
        description="Maximum number of retry attempts"
    )
    retry_delay: float = Field(
        default=1.0,
        description="Delay between retries in seconds"
    )
    mock_mode: bool = Field(
        default=False,
        description="Use mock responses for testing"
    )
    
    @classmethod
    def from_env(cls) -> "SubmissionConfig":
        """
        Create config from environment variables.
        
        Environment variables:
        - ENV_DOCTOR_ENDPOINT_URL: API endpoint URL
        - ENV_DOCTOR_API_KEY: API key for authentication
        - ENV_DOCTOR_MOCK_MODE: Enable mock mode (true/false)
        
        Returns:
            SubmissionConfig instance
        """
        return cls(
            endpoint_url=os.getenv("ENV_DOCTOR_ENDPOINT_URL", cls.model_fields["endpoint_url"].default),
            api_key=os.getenv("ENV_DOCTOR_API_KEY"),
            mock_mode=os.getenv("ENV_DOCTOR_MOCK_MODE", "").lower() == "true"
        )


class SubmissionStatus:
    """Submission status constants."""
    
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"


class SubmissionClient:
    """
    Client for submitting error reports to serverless endpoint.
    
    Handles HTTP communication, retries, and error handling for
    submitting incompatibility reports and retrieving analysis results.
    
    Example:
        >>> config = SubmissionConfig.from_env()
        >>> client = SubmissionClient(config)
        >>> submission_id = client.submit_report(report_data)
        >>> status = client.check_submission_status(submission_id)
        >>> if status == SubmissionStatus.COMPLETED:
        ...     result = client.get_submission_result(submission_id)
    """
    
    def __init__(self, config: Optional[SubmissionConfig] = None):
        """
        Initialize submission client.
        
        Args:
            config: Submission configuration (uses env vars if None)
        """
        self.config = config or SubmissionConfig.from_env()
        
        # Set default headers
        self._headers = {
            "Content-Type": "application/json",
            "User-Agent": "env-doctor-client/1.0"
        }
        
        # Add API key if provided
        if self.config.api_key:
            self._headers["Authorization"] = f"Bearer {self.config.api_key}"
    
    def submit_report(self, report: Dict[str, Any]) -> str:
        """
        Submit error report to serverless endpoint.
        
        Args:
            report: Error report dictionary from create_error_report()
            
        Returns:
            Submission ID for tracking
            
        Raises:
            requests.RequestException: If submission fails after retries
            
        Example:
            >>> report = create_error_report(script_path, execution_result)
            >>> submission_id = client.submit_report(report)
            >>> print(f"Submitted with ID: {submission_id}")
        """
        # Generate submission ID
        submission_id = str(uuid.uuid4())
        
        # Mock mode for testing
        if self.config.mock_mode:
            return self._mock_submit_report(submission_id, report)
        
        # Prepare submission payload
        payload = {
            "submission_id": submission_id,
            "report": report,
            "timestamp": time.time()
        }
        
        # Submit with retries
        url = urljoin(self.config.endpoint_url, "/api/v1/submissions")
        
        for attempt in range(self.config.max_retries):
            try:
                with httpx.Client() as client:
                    response = client.post(
                        url,
                        json=payload,
                        headers=self._headers,
                        timeout=self.config.timeout
                    )
                    response.raise_for_status()
                    
                    result = response.json()
                    return result.get("submission_id", submission_id)
                
            except httpx.HTTPError as e:
                if attempt == self.config.max_retries - 1:
                    raise
                
                # Wait before retry
                time.sleep(self.config.retry_delay * (attempt + 1))
        
        return submission_id
    
    def check_submission_status(self, submission_id: str) -> str:
        """
        Check status of submitted report.
        
        Args:
            submission_id: Submission ID from submit_report()
            
        Returns:
            Status string (pending, processing, completed, failed)
            
        Example:
            >>> status = client.check_submission_status(submission_id)
            >>> if status == SubmissionStatus.COMPLETED:
            ...     print("Analysis complete!")
        """
        # Mock mode for testing
        if self.config.mock_mode:
            return self._mock_check_status(submission_id)
        
        url = urljoin(
            self.config.endpoint_url,
            f"/api/v1/submissions/{submission_id}/status"
        )
        
        try:
            with httpx.Client() as client:
                response = client.get(
                    url,
                    headers=self._headers,
                    timeout=self.config.timeout
                )
                response.raise_for_status()
                
                result = response.json()
                return result.get("status", SubmissionStatus.PENDING)
            
        except httpx.HTTPError:
            # Return pending if check fails
            return SubmissionStatus.PENDING
    
    def get_submission_result(self, submission_id: str) -> Optional[Dict[str, Any]]:
        """
        Get analysis result for completed submission.
        
        Args:
            submission_id: Submission ID from submit_report()
            
        Returns:
            Analysis result dictionary or None if not ready
            
        Example:
            >>> result = client.get_submission_result(submission_id)
            >>> if result:
            ...     print(result["analysis"])
            ...     print(result["compatibility_yaml"])
        """
        # Mock mode for testing
        if self.config.mock_mode:
            return self._mock_get_result(submission_id)
        
        url = urljoin(
            self.config.endpoint_url,
            f"/api/v1/submissions/{submission_id}/result"
        )
        
        try:
            with httpx.Client() as client:
                response = client.get(
                    url,
                    headers=self._headers,
                    timeout=self.config.timeout
                )
                response.raise_for_status()
                
                return response.json()
            
        except httpx.HTTPError:
            return None
    
    def wait_for_completion(
        self,
        submission_id: str,
        max_wait: int = 300,
        poll_interval: int = 5
    ) -> Optional[Dict[str, Any]]:
        """
        Wait for submission to complete and return result.
        
        Args:
            submission_id: Submission ID from submit_report()
            max_wait: Maximum wait time in seconds
            poll_interval: Seconds between status checks
            
        Returns:
            Analysis result or None if timeout/failed
            
        Example:
            >>> result = client.wait_for_completion(submission_id, max_wait=120)
            >>> if result:
            ...     print("Analysis completed!")
        """
        start_time = time.time()
        
        while time.time() - start_time < max_wait:
            status = self.check_submission_status(submission_id)
            
            if status == SubmissionStatus.COMPLETED:
                return self.get_submission_result(submission_id)
            
            if status == SubmissionStatus.FAILED:
                return None
            
            time.sleep(poll_interval)
        
        return None
    
    # Mock implementations for testing
    
    def _mock_submit_report(self, submission_id: str, report: Dict[str, Any]) -> str:
        """Mock implementation of submit_report for testing."""
        # Store mock submission in temp directory
        mock_dir = Path.home() / ".cache" / "env-doctor" / "mock_submissions"
        mock_dir.mkdir(parents=True, exist_ok=True)
        
        submission_file = mock_dir / f"{submission_id}.json"
        with open(submission_file, 'w', encoding='utf-8') as f:
            json.dump({
                "submission_id": submission_id,
                "report": report,
                "status": SubmissionStatus.PENDING,
                "timestamp": time.time()
            }, f, indent=2)
        
        return submission_id
    
    def _mock_check_status(self, submission_id: str) -> str:
        """Mock implementation of check_submission_status for testing."""
        mock_dir = Path.home() / ".cache" / "env-doctor" / "mock_submissions"
        submission_file = mock_dir / f"{submission_id}.json"
        
        if not submission_file.exists():
            return SubmissionStatus.FAILED
        
        try:
            with open(submission_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            # Simulate processing: pending -> processing -> completed
            timestamp = data.get("timestamp", 0)
            elapsed = time.time() - timestamp
            
            if elapsed < 2:
                return SubmissionStatus.PENDING
            elif elapsed < 5:
                return SubmissionStatus.PROCESSING
            else:
                return SubmissionStatus.COMPLETED
                
        except Exception:
            return SubmissionStatus.FAILED
    
    def _mock_get_result(self, submission_id: str) -> Optional[Dict[str, Any]]:
        """Mock implementation of get_submission_result for testing."""
        mock_dir = Path.home() / ".cache" / "env-doctor" / "mock_submissions"
        submission_file = mock_dir / f"{submission_id}.json"
        
        if not submission_file.exists():
            return None
        
        try:
            with open(submission_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            report = data.get("report", {})
            parsed_error = report.get("parsed_error", {})
            
            # Generate mock analysis result
            return {
                "submission_id": submission_id,
                "status": SubmissionStatus.COMPLETED,
                "analysis": {
                    "error_type": parsed_error.get("error_type", "Unknown"),
                    "root_cause": "Mock analysis: This is a simulated AI analysis result.",
                    "suggested_fix": "Mock suggestion: Update dependencies or check compatibility.",
                    "confidence": 0.85
                },
                "compatibility_yaml": self._generate_mock_yaml(parsed_error),
                "pr_url": None,
                "timestamp": time.time()
            }
            
        except Exception:
            return None
    
    def _generate_mock_yaml(self, parsed_error: Dict[str, Any]) -> str:
        """Generate mock compatibility YAML."""
        error_type = parsed_error.get("error_type", "Unknown")
        error_message = parsed_error.get("error_message", "")
        
        yaml_content = f"""# Mock Compatibility Entry
# Generated by env-doctor mock analyzer

incompatibility:
  error_type: {error_type}
  error_message: "{error_message}"
  affected_packages:
    - package: example-package
      version: "1.0.0"
  resolution:
    type: version_constraint
    description: Mock resolution suggestion
    fix: Update to compatible version
"""
        return yaml_content


def submit_report(
    report: Dict[str, Any],
    config: Optional[SubmissionConfig] = None
) -> str:
    """
    Convenience function to submit error report.
    
    Args:
        report: Error report dictionary
        config: Optional submission configuration
        
    Returns:
        Submission ID
        
    Example:
        >>> report = create_error_report(script_path, execution_result)
        >>> submission_id = submit_report(report)
    """
    client = SubmissionClient(config)
    return client.submit_report(report)


def check_submission_status(
    submission_id: str,
    config: Optional[SubmissionConfig] = None
) -> str:
    """
    Convenience function to check submission status.
    
    Args:
        submission_id: Submission ID
        config: Optional submission configuration
        
    Returns:
        Status string
    """
    client = SubmissionClient(config)
    return client.check_submission_status(submission_id)


def get_submission_result(
    submission_id: str,
    config: Optional[SubmissionConfig] = None
) -> Optional[Dict[str, Any]]:
    """
    Convenience function to get submission result.
    
    Args:
        submission_id: Submission ID
        config: Optional submission configuration
        
    Returns:
        Analysis result or None
    """
    client = SubmissionClient(config)
    return client.get_submission_result(submission_id)


# Made with Bob