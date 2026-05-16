"""
YAML Compiler for env-doctor.

Compiles YAML files from a local directory (resolved by RepositoryManager) into SQLite database.
Handles compatibility rules, stable stacks, and runtime profiles.
"""

import logging
from pathlib import Path
from typing import Any, Callable, Dict, Optional

import yaml
from pydantic import BaseModel, Field, ValidationError
from sqlmodel import select

from .manager import DatabaseManager
from .models import CompatibilityRule, RuntimeProfile, StableStack, StableStackPackage
from .repository import RepositoryManager
from .uid_generator import (
    generate_compatibility_uid,
    generate_runtime_uid,
    generate_stack_uid,
)

logger = logging.getLogger(__name__)


# Pydantic models for YAML validation
class CompatibilityRuleYAML(BaseModel):
    """Validation model for compatibility rule YAML."""
    
    package: str = Field(description="Package name")
    version_range: str = Field(description="Package version range")
    dependency: str = Field(description="Dependency package name")
    dependency_range: str = Field(description="Dependency version range")
    type: str = Field(description="Compatibility type")
    confidence: str = Field(description="Confidence level")
    severity: int = Field(ge=0, le=100, description="Severity score")
    description: str = Field(description="Rule description")
    workaround: Optional[str] = Field(default=None, description="Workaround if available")


class StackPackageYAML(BaseModel):
    """Validation model for stack package YAML."""
    
    name: str = Field(description="Package name")
    version: str = Field(description="Package version")


class StableStackYAML(BaseModel):
    """Validation model for stable stack YAML."""
    
    name: str = Field(description="Stack name")
    cuda_version: Optional[str] = Field(default=None, description="CUDA version")
    python_version: str = Field(description="Python version requirement")
    confidence: str = Field(description="Confidence level")
    description: str = Field(description="Stack description")
    packages: list[StackPackageYAML] = Field(description="List of packages in stack")


class RuntimeProfileYAML(BaseModel):
    """Validation model for runtime profile YAML."""
    
    runtime: str = Field(description="Runtime name")
    kv_overhead_multiplier: float = Field(default=1.0, description="KV cache overhead")
    fragmentation_multiplier: float = Field(default=1.2, description="Memory fragmentation")
    description: str = Field(description="Runtime description")


class YAMLCompiler:
    """
    Compiles YAML files from a local directory into SQLite database.
    """
    
    def __init__(
        self,
        db_manager: DatabaseManager,
        repo_manager: Optional[RepositoryManager] = None
    ) -> None:
        """
        Initialize YAML compiler.
        
        Args:
            db_manager: Database manager instance
            repo_manager: Repository manager instance
        """
        self.db_manager = db_manager
        self.repo_manager = repo_manager
        
    def read_yaml_files_from_dir(self, repo_path: Path) -> Dict[str, str]:
        """
        Read all YAML files from a local directory.
        
        Args:
            repo_path: Path to the repository directory
            
        Returns:
            Dictionary mapping filename to YAML content
        """
        yaml_files: Dict[str, str] = {}
        
        # List of expected YAML files
        expected_files = [
            "compatibility_rules.yaml",
            "stable_stacks.yaml",
            "runtime_profiles.yaml"
        ]
        
        for filename in expected_files:
            file_path = repo_path / filename
            if file_path.exists():
                try:
                    logger.info(f"Reading {filename} from {file_path}")
                    with open(file_path, 'r', encoding='utf-8') as f:
                        yaml_files[filename] = f.read()
                    logger.info(f"Successfully read {filename}")
                except Exception as e:
                    logger.error(f"Error reading {filename}: {e}")
            else:
                logger.warning(f"File not found: {filename} in {repo_path}")
                
        return yaml_files

    def validate_yaml_structure(self, yaml_content: str, file_type: str) -> bool:
        """
        Validate YAML structure using pydantic models.
        
        Args:
            yaml_content: YAML content as string
            file_type: Type of YAML file (compatibility_rules, stable_stacks, runtime_profiles)
            
        Returns:
            True if valid
            
        Raises:
            ValidationError: If YAML structure is invalid
            yaml.YAMLError: If YAML parsing fails
        """
        try:
            data = yaml.safe_load(yaml_content)
            
            if not isinstance(data, dict):
                raise ValidationError("YAML root must be a dictionary")
            
            # Validate based on file type
            if file_type == "compatibility_rules":
                if "rules" not in data:
                    raise ValidationError("Missing 'rules' key in compatibility_rules.yaml")
                for rule in data["rules"]:
                    CompatibilityRuleYAML(**rule)
                    
            elif file_type == "stable_stacks":
                if "stacks" not in data:
                    raise ValidationError("Missing 'stacks' key in stable_stacks.yaml")
                for stack in data["stacks"]:
                    StableStackYAML(**stack)
                    
            elif file_type == "runtime_profiles":
                if "profiles" not in data:
                    raise ValidationError("Missing 'profiles' key in runtime_profiles.yaml")
                for profile in data["profiles"]:
                    RuntimeProfileYAML(**profile)
            else:
                raise ValidationError(f"Unknown file type: {file_type}")
                
            return True
            
        except yaml.YAMLError as e:
            logger.error(f"YAML parsing error: {e}")
            raise
        except ValidationError as e:
            logger.error(f"YAML validation error: {e}")
            raise
    
    def compile_compatibility_rules(self, yaml_data: dict) -> int:
        """
        Compile compatibility rules from YAML into database.
        
        Args:
            yaml_data: Parsed YAML data containing compatibility rules
            
        Returns:
            Number of rules processed
        """
        if "rules" not in yaml_data:
            logger.warning("No 'rules' key found in compatibility rules YAML")
            return 0
        
        rules_processed = 0
        
        with self.db_manager.get_session() as session:
            for rule_data in yaml_data["rules"]:
                try:
                    # Validate rule data
                    rule = CompatibilityRuleYAML(**rule_data)
                    
                    # Generate UID
                    uid = generate_compatibility_uid(
                        rule.package,
                        rule.version_range,
                        rule.dependency,
                        rule.dependency_range
                    )
                    
                    # Check if rule already exists
                    existing_rule = session.get(CompatibilityRule, uid)
                    
                    if existing_rule:
                        # Update existing rule
                        existing_rule.package_name = rule.package
                        existing_rule.package_version_range = rule.version_range
                        existing_rule.dependency_name = rule.dependency
                        existing_rule.dependency_version_range = rule.dependency_range
                        existing_rule.compatibility_type = rule.type
                        existing_rule.confidence_level = rule.confidence
                        existing_rule.severity = rule.severity
                        existing_rule.description = rule.description
                        existing_rule.workaround = rule.workaround
                        logger.debug(f"Updated compatibility rule: {uid}")
                    else:
                        # Create new rule
                        new_rule = CompatibilityRule(
                            uid=uid,
                            package_name=rule.package,
                            package_version_range=rule.version_range,
                            dependency_name=rule.dependency,
                            dependency_version_range=rule.dependency_range,
                            compatibility_type=rule.type,
                            confidence_level=rule.confidence,
                            severity=rule.severity,
                            description=rule.description,
                            workaround=rule.workaround
                        )
                        session.add(new_rule)
                        logger.debug(f"Created compatibility rule: {uid}")
                    
                    rules_processed += 1
                    
                except ValidationError as e:
                    logger.error(f"Validation error for rule: {e}")
                    continue
                except Exception as e:
                    logger.error(f"Error processing rule: {e}")
                    continue
            
            session.commit()
        
        logger.info(f"Processed {rules_processed} compatibility rules")
        return rules_processed
    
    def compile_stable_stacks(self, yaml_data: dict) -> int:
        """
        Compile stable stacks from YAML into database.
        
        Args:
            yaml_data: Parsed YAML data containing stable stacks
            
        Returns:
            Number of stacks processed
        """
        if "stacks" not in yaml_data:
            logger.warning("No 'stacks' key found in stable stacks YAML")
            return 0
        
        stacks_processed = 0
        
        with self.db_manager.get_session() as session:
            for stack_data in yaml_data["stacks"]:
                try:
                    # Validate stack data
                    stack = StableStackYAML(**stack_data)
                    
                    # Generate UID for stack
                    stack_uid = generate_stack_uid(stack.name, stack.cuda_version)
                    
                    # Check if stack already exists
                    existing_stack = session.get(StableStack, stack_uid)
                    
                    if existing_stack:
                        # Update existing stack
                        existing_stack.name = stack.name
                        existing_stack.cuda_version = stack.cuda_version
                        existing_stack.python_version = stack.python_version
                        existing_stack.confidence_level = stack.confidence
                        existing_stack.description = stack.description
                        
                        # Delete old packages for this stack
                        stmt = select(StableStackPackage).where(
                            StableStackPackage.stack_uid == stack_uid
                        )
                        old_packages = session.exec(stmt).all()
                        for pkg in old_packages:
                            session.delete(pkg)
                        
                        logger.debug(f"Updated stable stack: {stack_uid}")
                    else:
                        # Create new stack
                        new_stack = StableStack(
                            uid=stack_uid,
                            name=stack.name,
                            cuda_version=stack.cuda_version,
                            python_version=stack.python_version,
                            confidence_level=stack.confidence,
                            description=stack.description
                        )
                        session.add(new_stack)
                        logger.debug(f"Created stable stack: {stack_uid}")
                    
                    # Add packages to stack
                    for pkg_data in stack.packages:
                        # pkg_data is already a StackPackageYAML object from validation
                        if isinstance(pkg_data, dict):
                            pkg = StackPackageYAML(**pkg_data)
                        else:
                            pkg = pkg_data
                        
                        # Generate UID for stack package
                        pkg_uid = generate_compatibility_uid(
                            stack.name,
                            pkg.name,
                            pkg.version,
                            ""  # Empty string for consistency
                        )
                        
                        stack_package = StableStackPackage(
                            uid=pkg_uid,
                            stack_uid=stack_uid,
                            package_name=pkg.name,
                            version=pkg.version
                        )
                        session.add(stack_package)
                    
                    stacks_processed += 1
                    
                except ValidationError as e:
                    logger.error(f"Validation error for stack: {e}")
                    continue
                except Exception as e:
                    logger.error(f"Error processing stack: {e}")
                    continue
            
            session.commit()
        
        logger.info(f"Processed {stacks_processed} stable stacks")
        return stacks_processed
    
    def compile_runtime_profiles(self, yaml_data: dict) -> int:
        """
        Compile runtime profiles from YAML into database.
        
        Args:
            yaml_data: Parsed YAML data containing runtime profiles
            
        Returns:
            Number of profiles processed
        """
        if "profiles" not in yaml_data:
            logger.warning("No 'profiles' key found in runtime profiles YAML")
            return 0
        
        profiles_processed = 0
        
        with self.db_manager.get_session() as session:
            for profile_data in yaml_data["profiles"]:
                try:
                    # Validate profile data
                    profile = RuntimeProfileYAML(**profile_data)
                    
                    # Generate UID
                    uid = generate_runtime_uid(profile.runtime)
                    
                    # Check if profile already exists
                    existing_profile = session.get(RuntimeProfile, uid)
                    
                    if existing_profile:
                        # Update existing profile
                        existing_profile.runtime_name = profile.runtime
                        existing_profile.kv_overhead_multiplier = profile.kv_overhead_multiplier
                        existing_profile.fragmentation_multiplier = profile.fragmentation_multiplier
                        existing_profile.description = profile.description
                        logger.debug(f"Updated runtime profile: {uid}")
                    else:
                        # Create new profile
                        new_profile = RuntimeProfile(
                            uid=uid,
                            runtime_name=profile.runtime,
                            kv_overhead_multiplier=profile.kv_overhead_multiplier,
                            fragmentation_multiplier=profile.fragmentation_multiplier,
                            description=profile.description
                        )
                        session.add(new_profile)
                        logger.debug(f"Created runtime profile: {uid}")
                    
                    profiles_processed += 1
                    
                except ValidationError as e:
                    logger.error(f"Validation error for profile: {e}")
                    continue
                except Exception as e:
                    logger.error(f"Error processing profile: {e}")
                    continue
            
            session.commit()
        
        logger.info(f"Processed {profiles_processed} runtime profiles")
        return profiles_processed
    
    def compile_all(
        self,
        branch: str = "main",
        progress_callback: Optional[Callable[[str, int, int], None]] = None
    ) -> Dict[str, int]:
        """
        Main compilation method - resolve repository and compile all YAML files.
        
        Args:
            branch: Git branch to fetch from (passed to repo_manager)
            progress_callback: Optional callback function(stage, current, total)
                             for progress updates
            
        Returns:
            Dictionary with compilation statistics
        """
        stats: Dict[str, int] = {
            "files_fetched": 0,
            "rules_processed": 0,
            "stacks_processed": 0,
            "profiles_processed": 0,
            "errors": 0
        }
        
        try:
            if not self.repo_manager:
                raise ValueError("Repository manager not initialized")
                
            # Step 1: Resolve repository (clone/update if needed)
            if progress_callback:
                progress_callback("Resolving repository", 0, 3)
            
            logger.info("Resolving repository source...")
            repo_path = self.repo_manager.resolve_repo_path()
            
            # Step 2: Read YAML files
            if progress_callback:
                progress_callback("Reading YAML files", 1, 3)
            
            yaml_files = self.read_yaml_files_from_dir(repo_path)
            stats["files_fetched"] = len(yaml_files)
            
            if not yaml_files:
                logger.warning("No YAML files found in repository")
                return stats
            
            # Step 3: Process each file
            for idx, (filename, content) in enumerate(yaml_files.items(), 1):
                try:
                    # Determine file type
                    file_type = filename.replace(".yaml", "").replace(".yml", "")
                    
                    if progress_callback:
                        progress_callback(f"Processing {filename}", idx, len(yaml_files) + 1)
                    
                    logger.info(f"Processing {filename}...")
                    
                    # Validate YAML structure
                    self.validate_yaml_structure(content, file_type)
                    
                    # Parse YAML
                    yaml_data = yaml.safe_load(content)
                    
                    # Compile based on file type
                    if file_type == "compatibility_rules":
                        count = self.compile_compatibility_rules(yaml_data)
                        stats["rules_processed"] = count
                    elif file_type == "stable_stacks":
                        count = self.compile_stable_stacks(yaml_data)
                        stats["stacks_processed"] = count
                    elif file_type == "runtime_profiles":
                        count = self.compile_runtime_profiles(yaml_data)
                        stats["profiles_processed"] = count
                    else:
                        logger.warning(f"Unknown file type: {file_type}")
                        
                except Exception as e:
                    logger.error(f"Error processing {filename}: {e}")
                    stats["errors"] += 1
                    continue
            
            # Step 4: Complete
            if progress_callback:
                progress_callback("Compilation complete", len(yaml_files) + 1, len(yaml_files) + 1)
            
            logger.info("Compilation complete")
            logger.info(f"Statistics: {stats}")
            
        except Exception as e:
            logger.error(f"Fatal error during compilation: {e}")
            stats["errors"] += 1
            raise
        
        return stats


# Made with Bob
