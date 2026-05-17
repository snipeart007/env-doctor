"""
Configuration management for env-doctor.

Handles loading and saving user configuration from ~/.config/env-doctor/config.toml
"""

from pathlib import Path
from typing import Optional

from pydantic import BaseModel, Field


class Config(BaseModel):
    """Application configuration."""
    
    auto_update: bool = Field(
        default=True,
        description="Automatically update database on first run"
    )
    cache_dir: str = Field(
        default="~/.cache/env-doctor",
        description="Directory for cached data"
    )
    db_path: str = Field(
        default="~/.cache/env-doctor/env-doctor.db",
        description="Path to SQLite database"
    )
    verbosity: str = Field(
        default="info",
        description="Logging verbosity: debug, info, warning, error"
    )
    github_repo: str = Field(
        default="env-doctor/env-doctor-db",
        description="GitHub repository for database updates (deprecated, use repo_source)"
    )
    github_branch: str = Field(
        default="main",
        description="GitHub branch to fetch from"
    )
    repo_source: str = Field(
        default="env-doctor/env-doctor-db",
        description="Source for database repository (Git URL, local path, or owner/repo)"
    )
    update_check_interval: int = Field(
        default=86400,
        description="Seconds between update checks (default: 24 hours)"
    )
    
    # Reporting configuration
    endpoint_url: str = Field(
        default="https://api.env-doctor.dev",
        description="Serverless endpoint URL for report submission"
    )
    submission_timeout: int = Field(
        default=30,
        description="Timeout for submission requests in seconds"
    )
    submission_max_retries: int = Field(
        default=3,
        description="Maximum number of retry attempts for submissions"
    )
    analysis_wait_timeout: int = Field(
        default=300,
        description="Maximum wait time for AI analysis in seconds"
    )
    
    # AI analyzer configuration
    watsonx_model_id: str = Field(
        default="ibm/granite-13b-chat-v2",
        description="watsonx model ID for AI analysis"
    )
    watsonx_api_url: str = Field(
        default="https://us-south.ml.cloud.ibm.com",
        description="watsonx API endpoint URL"
    )
    
    # GitHub PR configuration
    github_pr_repo: str = Field(
        default="env-doctor/env-doctor-db",
        description="GitHub repository for PR submissions"
    )
    github_pr_base_branch: str = Field(
        default="main",
        description="Base branch for pull requests"
    )
    worker_url: Optional[str] = Field(
        default=None,
        description="URL for the secure proxy worker"
    )
    
    @classmethod
    def get_config_path(cls) -> Path:
        """
        Get configuration file path.
        
        Returns:
            Path to config.toml file
        """
        config_dir = Path.home() / ".config" / "env-doctor"
        return config_dir / "config.toml"
    
    @classmethod
    def load(cls) -> "Config":
        """
        Load configuration from file.
        
        Returns:
            Config instance with loaded or default values
            
        Example:
            >>> config = Config.load()
            >>> print(config.cache_dir)
            '~/.cache/env-doctor'
        """
        config_path = cls.get_config_path()
        
        if not config_path.exists():
            # Return default config
            return cls()
        
        try:
            import tomli
        except ImportError:
            # Fallback to tomllib for Python 3.11+
            try:
                import tomllib as tomli  # type: ignore
            except ImportError:
                # If no TOML parser available, return defaults
                return cls()
        
        try:
            with open(config_path, 'rb') as f:
                data = tomli.load(f)
            
            # Extract env-doctor config section
            config_data = data.get('env-doctor', {})
            
            return cls(**config_data)
            
        except Exception:
            # If loading fails, return defaults
            return cls()
    
    @classmethod
    def save(cls, config: "Config") -> None:
        """
        Save configuration to file.
        
        Args:
            config: Config instance to save
            
        Example:
            >>> config = Config.load()
            >>> config.auto_update = False
            >>> Config.save(config)
        """
        config_path = cls.get_config_path()
        
        # Ensure config directory exists
        config_path.parent.mkdir(parents=True, exist_ok=True)
        
        # Convert to TOML format
        toml_content = "[env-doctor]\n"
        toml_content += f'auto_update = {str(config.auto_update).lower()}\n'
        toml_content += f'cache_dir = "{config.cache_dir}"\n'
        toml_content += f'db_path = "{config.db_path}"\n'
        toml_content += f'verbosity = "{config.verbosity}"\n'
        toml_content += f'github_repo = "{config.github_repo}"\n'
        toml_content += f'github_branch = "{config.github_branch}"\n'
        toml_content += f'repo_source = "{config.repo_source}"\n'
        toml_content += f'update_check_interval = {config.update_check_interval}\n'
        toml_content += '\n# Reporting configuration\n'
        toml_content += f'endpoint_url = "{config.endpoint_url}"\n'
        toml_content += f'submission_timeout = {config.submission_timeout}\n'
        toml_content += f'submission_max_retries = {config.submission_max_retries}\n'
        toml_content += f'analysis_wait_timeout = {config.analysis_wait_timeout}\n'
        toml_content += '\n# AI analyzer configuration\n'
        toml_content += f'watsonx_model_id = "{config.watsonx_model_id}"\n'
        toml_content += f'watsonx_api_url = "{config.watsonx_api_url}"\n'
        toml_content += '\n# GitHub PR configuration\n'
        toml_content += f'github_pr_repo = "{config.github_pr_repo}"\n'
        toml_content += f'github_pr_base_branch = "{config.github_pr_base_branch}"\n'
        if config.worker_url:
            toml_content += f'worker_url = "{config.worker_url}"\n'
        
        # Write to file
        with open(config_path, 'w', encoding='utf-8') as f:
            f.write(toml_content)
    
    def get_expanded_cache_dir(self) -> Path:
        """
        Get cache directory with expanded path.
        
        Returns:
            Expanded Path object
        """
        return Path(self.cache_dir).expanduser().resolve()
    
    def get_expanded_db_path(self) -> Path:
        """
        Get database path with expanded path.
        
        Returns:
            Expanded Path object
        """
        return Path(self.db_path).expanduser().resolve()
    
    def get_expanded_repo_cache_dir(self) -> Path:
        """
        Get repository cache directory.
        
        Returns:
            Path to repository cache
        """
        return self.get_expanded_cache_dir() / "repos"
    
    def ensure_directories(self) -> None:
        """
        Ensure cache and config directories exist.
        
        Creates directories if they don't exist.
        """
        # Ensure cache directory exists
        cache_dir = self.get_expanded_cache_dir()
        cache_dir.mkdir(parents=True, exist_ok=True)
        
        # Ensure repo cache directory exists
        repo_cache_dir = self.get_expanded_repo_cache_dir()
        repo_cache_dir.mkdir(parents=True, exist_ok=True)
        
        # Ensure database directory exists
        db_path = self.get_expanded_db_path()
        db_path.parent.mkdir(parents=True, exist_ok=True)
        
        # Ensure config directory exists
        config_path = self.get_config_path()
        config_path.parent.mkdir(parents=True, exist_ok=True)


def get_default_config() -> Config:
    """
    Get default configuration.
    
    Returns:
        Config instance with default values
    """
    return Config()


def load_config() -> Config:
    """
    Load configuration from file or return defaults.
    
    Returns:
        Config instance
    """
    return Config.load()


def save_config(config: Config) -> None:
    """
    Save configuration to file.
    
    Args:
        config: Config instance to save
    """
    Config.save(config)


def get_cache_dir() -> Path:
    """
    Get cache directory path.
    
    Returns:
        Path to cache directory
    """
    config = load_config()
    return config.get_expanded_cache_dir()


def get_db_path() -> Path:
    """
    Get database file path.
    
    Returns:
        Path to database file
    """
    config = load_config()
    return config.get_expanded_db_path()


def get_default_db_path() -> Path:
    """
    Get default database path.
    
    Returns:
        Path to default database file
    """
    return Path("~/.cache/env-doctor/env-doctor.db").expanduser().resolve()


# Made with Bob
