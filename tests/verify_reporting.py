"""
Standalone verification script for reporting functionality.

Tests all reporting components in mock mode without requiring external services.
"""

import sys
import time
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from env_doctor.reporting.submission_client import (
    SubmissionClient,
    SubmissionConfig,
    SubmissionStatus
)
from env_doctor.reporting.ai_analyzer import (
    AIAnalyzer,
    WatsonxConfig
)
from env_doctor.reporting.pr_creator import (
    PRCreator,
    GitHubConfig
)


def print_header(text: str) -> None:
    """Print a formatted header."""
    print("\n" + "=" * 70)
    print(f"  {text}")
    print("=" * 70)


def print_success(text: str) -> None:
    """Print success message."""
    print(f"[OK] {text}")


def print_error(text: str) -> None:
    """Print error message."""
    print(f"[FAIL] {text}")


def print_info(text: str) -> None:
    """Print info message."""
    print(f"  {text}")


def create_mock_report() -> dict:
    """Create a mock error report for testing."""
    return {
        "script_path": "test_script.py",
        "execution": {
            "success": False,
            "exit_code": 1,
            "stdout": "",
            "stderr": "Traceback (most recent call last):\n  File \"test_script.py\", line 1, in <module>\n    import torch\nImportError: No module named 'torch'",
            "error": "ImportError: No module named 'torch'",
            "traceback": "Traceback (most recent call last):\n  File \"test_script.py\", line 1, in <module>\n    import torch\nImportError: No module named 'torch'",
            "duration": 0.5
        },
        "parsed_error": {
            "error_type": "ImportError",
            "error_message": "No module named 'torch'",
            "file": "test_script.py",
            "line": 1,
            "function": "<module>"
        },
        "environment": {
            "python_version": "3.11.0",
            "platform": "Windows",
            "packages": {
                "numpy": "1.24.0",
                "pandas": "2.0.0",
                "scikit-learn": "1.3.0"
            }
        }
    }


def verify_submission_client() -> bool:
    """Verify submission client functionality."""
    print_header("Testing Submission Client")
    
    try:
        # Create config in mock mode
        config = SubmissionConfig(mock_mode=True)
        print_success("Created submission config")
        
        # Initialize client
        client = SubmissionClient(config)
        print_success("Initialized submission client")
        
        # Create mock report
        report = create_mock_report()
        print_success("Created mock error report")
        
        # Submit report
        submission_id = client.submit_report(report)
        print_success(f"Submitted report (ID: {submission_id})")
        
        # Check initial status
        status = client.check_submission_status(submission_id)
        print_success(f"Checked status: {status}")
        
        if status != SubmissionStatus.PENDING:
            print_error(f"Expected PENDING status, got {status}")
            return False
        
        # Wait for processing
        print_info("Waiting for mock processing (6 seconds)...")
        time.sleep(6)
        
        # Check completed status
        status = client.check_submission_status(submission_id)
        print_success(f"Checked status after wait: {status}")
        
        if status != SubmissionStatus.COMPLETED:
            print_error(f"Expected COMPLETED status, got {status}")
            return False
        
        # Get result
        result = client.get_submission_result(submission_id)
        print_success("Retrieved submission result")
        
        if not result:
            print_error("Result is None")
            return False
        
        # Verify result structure
        if "analysis" not in result:
            print_error("Result missing 'analysis' field")
            return False
        
        if "compatibility_yaml" not in result:
            print_error("Result missing 'compatibility_yaml' field")
            return False
        
        print_success("Result structure validated")
        
        # Test wait_for_completion
        submission_id2 = client.submit_report(report)
        result2 = client.wait_for_completion(submission_id2, max_wait=10, poll_interval=1)
        
        if not result2:
            print_error("wait_for_completion returned None")
            return False
        
        print_success("wait_for_completion works correctly")
        
        return True
        
    except Exception as e:
        print_error(f"Exception: {e}")
        import traceback
        traceback.print_exc()
        return False


def verify_ai_analyzer() -> bool:
    """Verify AI analyzer functionality."""
    print_header("Testing AI Analyzer")
    
    try:
        # Create config in mock mode
        config = WatsonxConfig(mock_mode=True)
        print_success("Created watsonx config")
        
        # Initialize analyzer
        analyzer = AIAnalyzer(config)
        print_success("Initialized AI analyzer")
        
        # Create mock report
        report = create_mock_report()
        print_success("Created mock error report")
        
        # Analyze report
        result = analyzer.analyze_error_report(report)
        print_success("Analyzed error report")
        
        # Verify result structure
        if not result.error_type:
            print_error("Result missing error_type")
            return False
        
        if not result.root_cause:
            print_error("Result missing root_cause")
            return False
        
        if not result.suggested_fix:
            print_error("Result missing suggested_fix")
            return False
        
        if not result.affected_packages:
            print_error("Result missing affected_packages")
            return False
        
        if not result.compatibility_yaml:
            print_error("Result missing compatibility_yaml")
            return False
        
        print_success(f"Error type: {result.error_type}")
        print_success(f"Confidence: {result.confidence:.2%}")
        print_success(f"Affected packages: {', '.join(result.affected_packages)}")
        
        # Validate analysis
        is_valid = analyzer.validate_analysis(result)
        
        if not is_valid:
            print_error("Analysis validation failed")
            return False
        
        print_success("Analysis validation passed")
        
        # Generate YAML
        yaml_content = analyzer.generate_compatibility_yaml(result, report)
        
        if not yaml_content:
            print_error("Generated YAML is empty")
            return False
        
        if "incompatibility:" not in yaml_content:
            print_error("Generated YAML missing 'incompatibility:' section")
            return False
        
        print_success("Generated compatibility YAML")
        print_info(f"YAML length: {len(yaml_content)} characters")
        
        return True
        
    except Exception as e:
        print_error(f"Exception: {e}")
        import traceback
        traceback.print_exc()
        return False


def verify_pr_creator() -> bool:
    """Verify PR creator functionality."""
    print_header("Testing PR Creator")
    
    try:
        # Create config in mock mode
        config = GitHubConfig(mock_mode=True)
        print_success("Created GitHub config")
        
        # Initialize creator
        creator = PRCreator(config)
        print_success("Initialized PR creator")
        
        # Create mock data
        report = create_mock_report()
        analysis = {
            "error_type": "ImportError",
            "root_cause": "Missing torch package in environment",
            "affected_packages": ["torch", "numpy"],
            "suggested_fix": "Install torch: pip install torch",
            "confidence": 0.95
        }
        yaml_content = "test: yaml\ndata: value"
        
        print_success("Created mock data")
        
        # Generate PR description
        description = creator.generate_pr_description(analysis, report)
        
        if not description:
            print_error("Generated description is empty")
            return False
        
        if "New Compatibility Entry" not in description:
            print_error("Description missing expected content")
            return False
        
        print_success("Generated PR description")
        print_info(f"Description length: {len(description)} characters")
        
        # Create PR
        pr_result = creator.create_pr_from_analysis(analysis, report, yaml_content)
        
        if not pr_result:
            print_error("PR result is None")
            return False
        
        if pr_result.pr_number <= 0:
            print_error("Invalid PR number")
            return False
        
        if not pr_result.pr_url:
            print_error("Missing PR URL")
            return False
        
        if not pr_result.branch_name:
            print_error("Missing branch name")
            return False
        
        print_success(f"Created PR #{pr_result.pr_number}")
        print_success(f"Branch: {pr_result.branch_name}")
        print_success(f"URL: {pr_result.pr_url}")
        
        return True
        
    except Exception as e:
        print_error(f"Exception: {e}")
        import traceback
        traceback.print_exc()
        return False


def verify_integration() -> bool:
    """Verify full integration flow."""
    print_header("Testing Full Integration Flow")
    
    try:
        # Create mock report
        report = create_mock_report()
        print_success("Created mock error report")
        
        # 1. Submit report
        submission_config = SubmissionConfig(mock_mode=True)
        client = SubmissionClient(submission_config)
        submission_id = client.submit_report(report)
        print_success(f"Step 1: Submitted report (ID: {submission_id})")
        
        # 2. Wait for analysis
        print_info("Step 2: Waiting for AI analysis...")
        result = client.wait_for_completion(submission_id, max_wait=10, poll_interval=1)
        
        if not result:
            print_error("Failed to get analysis result")
            return False
        
        print_success("Step 2: Received AI analysis")
        
        # 3. Validate analysis
        analysis = result.get("analysis", {})
        yaml_content = result.get("compatibility_yaml", "")
        
        if not analysis or not yaml_content:
            print_error("Analysis or YAML missing from result")
            return False
        
        print_success("Step 3: Validated analysis result")
        
        # 4. Create PR
        github_config = GitHubConfig(mock_mode=True)
        creator = PRCreator(github_config)
        pr_result = creator.create_pr_from_analysis(analysis, report, yaml_content)
        
        if not pr_result:
            print_error("Failed to create PR")
            return False
        
        print_success(f"Step 4: Created PR #{pr_result.pr_number}")
        
        print_success("Full integration flow completed successfully!")
        
        return True
        
    except Exception as e:
        print_error(f"Exception: {e}")
        import traceback
        traceback.print_exc()
        return False


def main() -> int:
    """Run all verification tests."""
    print("\n" + "=" * 70)
    print("  ENV-DOCTOR REPORTING VERIFICATION")
    print("  Testing all reporting components in mock mode")
    print("=" * 70)
    
    results = []
    
    # Run tests
    results.append(("Submission Client", verify_submission_client()))
    results.append(("AI Analyzer", verify_ai_analyzer()))
    results.append(("PR Creator", verify_pr_creator()))
    results.append(("Integration Flow", verify_integration()))
    
    # Print summary
    print_header("Verification Summary")
    
    all_passed = True
    for name, passed in results:
        if passed:
            print_success(f"{name}: PASSED")
        else:
            print_error(f"{name}: FAILED")
            all_passed = False
    
    print("\n" + "=" * 70)
    if all_passed:
        print("  [SUCCESS] ALL TESTS PASSED")
        print("=" * 70)
        return 0
    else:
        print("  [FAILURE] SOME TESTS FAILED")
        print("=" * 70)
        return 1


if __name__ == "__main__":
    sys.exit(main())


# Made with Bob