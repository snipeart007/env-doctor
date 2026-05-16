"""
AI analyzer for incompatibility reports using watsonx.

Analyzes error reports using IBM watsonx AI to generate compatibility
insights and YAML entries for the env-doctor database.
"""

import json
import os
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class WatsonxConfig(BaseModel):
    """Configuration for watsonx AI integration."""
    
    api_key: Optional[str] = Field(
        default=None,
        description="IBM Cloud API key for watsonx"
    )
    project_id: Optional[str] = Field(
        default=None,
        description="watsonx project ID"
    )
    model_id: str = Field(
        default="ibm/granite-13b-chat-v2",
        description="Model ID to use for analysis"
    )
    api_url: str = Field(
        default="https://us-south.ml.cloud.ibm.com",
        description="watsonx API endpoint URL"
    )
    temperature: float = Field(
        default=0.7,
        description="Model temperature for generation"
    )
    max_tokens: int = Field(
        default=2000,
        description="Maximum tokens to generate"
    )
    mock_mode: bool = Field(
        default=False,
        description="Use mock responses for testing"
    )
    
    @classmethod
    def from_env(cls) -> "WatsonxConfig":
        """
        Create config from environment variables.
        
        Environment variables:
        - WATSONX_API_KEY: IBM Cloud API key
        - WATSONX_PROJECT_ID: watsonx project ID
        - WATSONX_MODEL_ID: Model ID (optional)
        - WATSONX_MOCK_MODE: Enable mock mode (true/false)
        
        Returns:
            WatsonxConfig instance
        """
        return cls(
            api_key=os.getenv("WATSONX_API_KEY"),
            project_id=os.getenv("WATSONX_PROJECT_ID"),
            model_id=os.getenv("WATSONX_MODEL_ID", cls.model_fields["model_id"].default),
            mock_mode=os.getenv("WATSONX_MOCK_MODE", "").lower() == "true"
        )


class AnalysisResult(BaseModel):
    """Result from AI analysis."""
    
    error_type: str = Field(description="Type of error encountered")
    root_cause: str = Field(description="Root cause analysis")
    affected_packages: List[str] = Field(description="List of affected packages")
    suggested_fix: str = Field(description="Suggested fix or workaround")
    confidence: float = Field(description="Confidence score (0-1)")
    compatibility_yaml: str = Field(description="Generated YAML entry")


class AIAnalyzer:
    """
    AI analyzer for incompatibility reports.
    
    Uses IBM watsonx to analyze error reports and generate compatibility
    insights and YAML entries for the env-doctor database.
    
    Example:
        >>> config = WatsonxConfig.from_env()
        >>> analyzer = AIAnalyzer(config)
        >>> result = analyzer.analyze_error_report(report)
        >>> print(result.root_cause)
        >>> print(result.compatibility_yaml)
    """
    
    def __init__(self, config: Optional[WatsonxConfig] = None):
        """
        Initialize AI analyzer.
        
        Args:
            config: watsonx configuration (uses env vars if None)
        """
        self.config = config or WatsonxConfig.from_env()
        self._client = None
        
        # Initialize watsonx client if not in mock mode
        if not self.config.mock_mode:
            self._initialize_client()
    
    def _initialize_client(self) -> None:
        """
        Initialize watsonx client.
        
        TODO: Implement actual watsonx client initialization
        This requires the ibm-watsonx-ai package and proper credentials.
        """
        # TODO: Uncomment when watsonx integration is ready
        # try:
        #     from ibm_watsonx_ai import APIClient
        #     from ibm_watsonx_ai.foundation_models import Model
        #     
        #     credentials = {
        #         "url": self.config.api_url,
        #         "apikey": self.config.api_key
        #     }
        #     
        #     self._client = APIClient(credentials)
        #     self._model = Model(
        #         model_id=self.config.model_id,
        #         credentials=credentials,
        #         project_id=self.config.project_id
        #     )
        # except ImportError:
        #     raise ImportError(
        #         "ibm-watsonx-ai package not installed. "
        #         "Install with: pip install ibm-watsonx-ai"
        #     )
        pass
    
    def analyze_error_report(self, report: Dict[str, Any]) -> AnalysisResult:
        """
        Analyze error report using AI.
        
        Args:
            report: Error report dictionary from create_error_report()
            
        Returns:
            AnalysisResult with AI-generated insights
            
        Example:
            >>> report = create_error_report(script_path, execution_result)
            >>> result = analyzer.analyze_error_report(report)
            >>> print(result.suggested_fix)
        """
        # Mock mode for testing
        if self.config.mock_mode or self._client is None:
            return self._mock_analyze(report)
        
        # TODO: Implement actual watsonx analysis
        # Extract relevant information from report
        parsed_error = report.get("parsed_error", {})
        environment = report.get("environment", {})
        
        # Build prompt for AI analysis
        prompt = self._build_analysis_prompt(parsed_error, environment)
        
        # TODO: Call watsonx API
        # response = self._model.generate(
        #     prompt=prompt,
        #     params={
        #         "temperature": self.config.temperature,
        #         "max_new_tokens": self.config.max_tokens
        #     }
        # )
        
        # For now, return mock result
        return self._mock_analyze(report)
    
    def generate_compatibility_yaml(
        self,
        analysis: AnalysisResult,
        report: Dict[str, Any]
    ) -> str:
        """
        Generate compatibility YAML entry from analysis.
        
        Args:
            analysis: Analysis result from analyze_error_report()
            report: Original error report
            
        Returns:
            YAML string for database entry
            
        Example:
            >>> yaml_content = analyzer.generate_compatibility_yaml(analysis, report)
            >>> with open("new_entry.yaml", "w") as f:
            ...     f.write(yaml_content)
        """
        parsed_error = report.get("parsed_error", {})
        environment = report.get("environment", {})
        
        # Extract package information
        packages = environment.get("packages", {})
        python_version = environment.get("python_version", "unknown")
        
        # Build YAML content
        yaml_lines = [
            "# Compatibility Entry",
            "# Generated by env-doctor AI analyzer",
            "",
            "incompatibility:",
            f"  error_type: {parsed_error.get('error_type', 'Unknown')}",
            f"  error_message: \"{parsed_error.get('error_message', '')}\"",
            f"  python_version: \"{python_version}\"",
            "",
            "  affected_packages:"
        ]
        
        # Add affected packages
        for pkg in analysis.affected_packages[:5]:  # Limit to 5 packages
            if pkg in packages:
                yaml_lines.append(f"    - package: {pkg}")
                yaml_lines.append(f"      version: \"{packages[pkg]}\"")
        
        yaml_lines.extend([
            "",
            "  analysis:",
            f"    root_cause: \"{analysis.root_cause}\"",
            f"    confidence: {analysis.confidence}",
            "",
            "  resolution:",
            "    type: version_constraint",
            f"    description: \"{analysis.suggested_fix}\"",
            "    fix: Update to compatible versions",
            ""
        ])
        
        return "\n".join(yaml_lines)
    
    def validate_analysis(self, analysis: AnalysisResult) -> bool:
        """
        Validate analysis result quality.
        
        Args:
            analysis: Analysis result to validate
            
        Returns:
            True if analysis meets quality standards
            
        Example:
            >>> if analyzer.validate_analysis(result):
            ...     print("Analysis is valid")
        """
        # Check confidence threshold
        if analysis.confidence < 0.5:
            return False
        
        # Check required fields are not empty
        if not analysis.root_cause or not analysis.suggested_fix:
            return False
        
        # Check affected packages list
        if not analysis.affected_packages:
            return False
        
        # Check YAML is not empty
        if not analysis.compatibility_yaml:
            return False
        
        return True
    
    def _build_analysis_prompt(
        self,
        parsed_error: Dict[str, Any],
        environment: Dict[str, Any]
    ) -> str:
        """
        Build prompt for AI analysis.
        
        Args:
            parsed_error: Parsed error information
            environment: Environment information
            
        Returns:
            Formatted prompt string
        """
        error_type = parsed_error.get("error_type", "Unknown")
        error_message = parsed_error.get("error_message", "")
        packages = environment.get("packages", {})
        python_version = environment.get("python_version", "unknown")
        
        prompt = f"""Analyze the following Python error and provide compatibility insights:

Error Type: {error_type}
Error Message: {error_message}
Python Version: {python_version}

Installed Packages:
{json.dumps(packages, indent=2)}

Please provide:
1. Root cause analysis
2. List of affected packages
3. Suggested fix or workaround
4. Confidence level (0-1)

Format your response as JSON with keys: root_cause, affected_packages, suggested_fix, confidence
"""
        return prompt
    
    def _mock_analyze(self, report: Dict[str, Any]) -> AnalysisResult:
        """
        Mock implementation for testing.
        
        Args:
            report: Error report
            
        Returns:
            Mock analysis result
        """
        parsed_error = report.get("parsed_error", {})
        environment = report.get("environment", {})
        
        error_type = parsed_error.get("error_type", "Unknown")
        error_message = parsed_error.get("error_message", "")
        
        # Extract some package names for mock affected packages
        packages = environment.get("packages", {})
        affected_packages = list(packages.keys())[:3] if packages else ["example-package"]
        
        # Generate mock analysis
        root_cause = f"Mock analysis: The {error_type} error typically occurs due to version incompatibilities or missing dependencies."
        suggested_fix = "Mock suggestion: Update affected packages to compatible versions or install missing dependencies."
        
        # Generate mock YAML
        yaml_content = self.generate_compatibility_yaml(
            AnalysisResult(
                error_type=error_type,
                root_cause=root_cause,
                affected_packages=affected_packages,
                suggested_fix=suggested_fix,
                confidence=0.85,
                compatibility_yaml=""
            ),
            report
        )
        
        return AnalysisResult(
            error_type=error_type,
            root_cause=root_cause,
            affected_packages=affected_packages,
            suggested_fix=suggested_fix,
            confidence=0.85,
            compatibility_yaml=yaml_content
        )


def analyze_error_report(
    report: Dict[str, Any],
    config: Optional[WatsonxConfig] = None
) -> AnalysisResult:
    """
    Convenience function to analyze error report.
    
    Args:
        report: Error report dictionary
        config: Optional watsonx configuration
        
    Returns:
        Analysis result
        
    Example:
        >>> report = create_error_report(script_path, execution_result)
        >>> result = analyze_error_report(report)
    """
    analyzer = AIAnalyzer(config)
    return analyzer.analyze_error_report(report)


def generate_compatibility_yaml(
    analysis: AnalysisResult,
    report: Dict[str, Any],
    config: Optional[WatsonxConfig] = None
) -> str:
    """
    Convenience function to generate compatibility YAML.
    
    Args:
        analysis: Analysis result
        report: Error report
        config: Optional watsonx configuration
        
    Returns:
        YAML string
    """
    analyzer = AIAnalyzer(config)
    return analyzer.generate_compatibility_yaml(analysis, report)


# Made with Bob