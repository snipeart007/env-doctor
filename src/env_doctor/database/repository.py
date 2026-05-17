"""
Repository manager for env-doctor database.

Handles fetching and updating compatibility intelligence from Git repositories
or local directories.
"""

import logging
import os
import shutil
import subprocess
from pathlib import Path
from typing import Optional, Union

from env_doctor.utils.config import Config

logger = logging.getLogger(__name__)


class RepositoryManager:
    """
    Manages database intelligence repositories.
    
    Supports:
    - Git URLs (https, ssh)
    - GitHub shorthand (owner/repo)
    - Local directory paths
    """
    
    def __init__(self, config: Config):
        """
        Initialize repository manager.
        
        Args:
            config: Application configuration
        """
        self.config = config
        self.repo_cache_dir = config.get_expanded_repo_cache_dir()
        self.repo_cache_dir.mkdir(parents=True, exist_ok=True)
    
    def resolve_repo_path(self) -> Path:
        """
        Resolve the current repository source to a local filesystem path.
        
        If it's a Git source, it will clone/update it in the cache.
        If it's a local path, it will verify it exists.
        
        Returns:
            Path to the local repository directory
        
        Raises:
            ValueError: If repository source is invalid or unreachable
        """
        source = self.config.repo_source
        
        # 1. Check if it's a local path
        local_path = Path(source).expanduser().resolve()
        if local_path.is_dir():
            logger.info(f"Using local repository directory: {local_path}")
            return local_path
        
        # 2. Check if it's a Git URL or shorthand
        git_url = self._get_git_url(source)
        repo_name = self._get_repo_name(source)
        cached_path = self.repo_cache_dir / repo_name
        
        if cached_path.exists():
            self._update_git_repo(cached_path)
        else:
            self._clone_git_repo(git_url, cached_path)
            
        return cached_path
    
    def _get_git_url(self, source: str) -> str:
        """Convert shorthand or URL to full Git URL."""
        if source.startswith(("http://", "https://", "git@", "ssh://")):
            return source
        
        # Assume GitHub shorthand
        if "/" in source and len(source.split("/")) == 2:
            return f"https://github.com/{source}.git"
            
        raise ValueError(f"Invalid repository source: {source}")
    
    def _get_repo_name(self, source: str) -> str:
        """Generate a stable local name for the repository."""
        import hashlib
        # Use MD5 hash of source to avoid filesystem issues with special characters
        hash_val = hashlib.md5(source.encode()).hexdigest()[:8]
        
        clean_name = source.replace("/", "_").replace(":", "_").replace("@", "_")
        if len(clean_name) > 32:
            clean_name = clean_name[:32]
            
        return f"{clean_name}_{hash_val}"
    
    def _clone_git_repo(self, url: str, path: Path) -> None:
        """Clone a Git repository."""
        logger.info(f"Cloning repository {url} to {path}")
        try:
            subprocess.run(
                ["git", "clone", "--depth", "1", "--branch", self.config.github_branch, url, str(path)],
                check=True,
                capture_output=True,
                text=True
            )
        except subprocess.CalledProcessError as e:
            logger.error(f"Failed to clone repository: {e.stderr}")
            raise ValueError(f"Failed to clone repository: {e.stderr}")
            
    def _update_git_repo(self, path: Path) -> None:
        """Update an existing Git repository."""
        logger.info(f"Updating repository in {path}")
        try:
            # Check if it's actually a git repo
            if not (path / ".git").exists():
                logger.warning(f"Path {path} exists but is not a Git repository. Re-cloning.")
                shutil.rmtree(path)
                self._clone_git_repo(self._get_git_url(self.config.repo_source), path)
                return
                
            subprocess.run(
                ["git", "-C", str(path), "pull", "origin", self.config.github_branch],
                check=True,
                capture_output=True,
                text=True
            )
        except subprocess.CalledProcessError as e:
            logger.warning(f"Failed to update repository: {e.stderr}. Using cached version.")
            
    def list_yaml_files(self, repo_path: Path) -> list[Path]:
        """List all YAML files in the repository."""
        return list(repo_path.glob("*.yaml")) + list(repo_path.glob("*.yml"))

    def get_worker_url(self) -> Optional[str]:
        """
        Read the Cloudflare Worker URL from worker.txt in the repository.
        
        Returns:
            The worker URL or None if not found
        """
        try:
            repo_path = self.resolve_repo_path()
            worker_file = repo_path / "worker.txt"
            
            if worker_file.exists():
                with open(worker_file, "r", encoding="utf-8") as f:
                    url = f.read().strip()
                    if url:
                        logger.info(f"Discovered worker URL: {url}")
                        return url
            
            logger.warning(f"worker.txt not found in repository: {repo_path}")
            return None
        except Exception as e:
            logger.error(f"Error reading worker.txt: {e}")
            return None


# Made with Bob
