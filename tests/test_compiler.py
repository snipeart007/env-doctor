"""
Test suite for YAML compiler.

Tests the YAMLCompiler class functionality including YAML validation,
parsing, and database compilation.
"""

import tempfile
from pathlib import Path

import pytest
import yaml

from env_doctor.database import (
    DatabaseManager,
    YAMLCompiler,
    get_compatibility_rules,
    get_runtime_profile,
    get_stable_stack_by_name,
    get_stable_stack_packages,
)


@pytest.fixture
def temp_db():
    """Create a temporary database for testing."""
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        db_path = f.name
    
    manager = DatabaseManager(db_path)
    manager.create_tables()
    
    yield manager
    
    manager.close()
    Path(db_path).unlink(missing_ok=True)


@pytest.fixture
def compiler(temp_db):
    """Create a YAMLCompiler instance with temporary database."""
    return YAMLCompiler(temp_db)


def test_compiler_initialization(temp_db):
    """Test YAMLCompiler initialization."""
    compiler = YAMLCompiler(temp_db)
    assert compiler.db_manager == temp_db


def test_validate_compatibility_rules_yaml(compiler):
    """Test validation of compatibility rules YAML."""
    valid_yaml = """
rules:
  - package: torch
    version_range: ">=2.0.0,<2.1.0"
    dependency: transformers
    dependency_range: ">=4.30.0,<4.35.0"
    cuda_version: "12.1"
    env_system: "win32"
    type: incompatible
    confidence: community-tested
    severity: 90
    description: "Known CUDA kernel incompatibility"
    workaround: "Use torch 2.1.0+ or transformers <4.30.0"
"""
    
    # Should not raise exception
    assert compiler.validate_yaml_structure(valid_yaml, "compatibility_rules")


def test_validate_stable_stacks_yaml(compiler):
    """Test validation of stable stacks YAML."""
    valid_yaml = """
stacks:
  - name: torch-2.1-transformers-4.38
    cuda_version: "11.8"
    env_system: "linux"
    python_version: ">=3.10,<3.12"
    confidence: production-tested
    description: "Stable stack for production inference"
    packages:
      - name: torch
        version: "2.1.0"
      - name: transformers
        version: "4.38.0"
"""
    
    # Should not raise exception
    assert compiler.validate_yaml_structure(valid_yaml, "stable_stacks")


def test_validate_runtime_profiles_yaml(compiler):
    """Test validation of runtime profiles YAML."""
    valid_yaml = """
profiles:
  - runtime: transformers
    kv_overhead_multiplier: 1.0
    fragmentation_multiplier: 1.2
    description: "Standard HuggingFace transformers runtime"
  - runtime: vllm
    kv_overhead_multiplier: 1.1
    fragmentation_multiplier: 1.15
    description: "vLLM optimized runtime"
"""
    
    # Should not raise exception
    assert compiler.validate_yaml_structure(valid_yaml, "runtime_profiles")


def test_validate_invalid_yaml(compiler):
    """Test validation of invalid YAML."""
    invalid_yaml = """
rules:
  - package: torch
    # Missing required fields
    type: incompatible
"""
    
    with pytest.raises(Exception):  # Should raise ValidationError
        compiler.validate_yaml_structure(invalid_yaml, "compatibility_rules")


def test_compile_compatibility_rules(compiler, temp_db):
    """Test compilation of compatibility rules."""
    yaml_data = {
        "rules": [
            {
                "package": "torch",
                "version_range": ">=2.0.0,<2.1.0",
                "dependency": "transformers",
                "dependency_range": ">=4.30.0,<4.35.0",
                "type": "incompatible",
                "confidence": "community-tested",
                "severity": 90,
                "description": "Known CUDA kernel incompatibility",
                "workaround": "Use torch 2.1.0+ or transformers <4.30.0"
            }
        ]
    }
    
    count = compiler.compile_compatibility_rules(yaml_data)
    assert count == 1
    
    # Verify rule was inserted
    with temp_db.get_session() as session:
        rules = get_compatibility_rules(session, "torch")
        assert len(rules) == 1
        assert rules[0].package_name == "torch"
        assert rules[0].dependency_name == "transformers"
        assert rules[0].severity == 90


def test_compile_stable_stacks(compiler, temp_db):
    """Test compilation of stable stacks."""
    yaml_data = {
        "stacks": [
            {
                "name": "torch-2.1-transformers-4.38",
                "cuda_version": "11.8",
                "python_version": ">=3.10,<3.12",
                "confidence": "production-tested",
                "description": "Stable stack for production inference",
                "packages": [
                    {"name": "torch", "version": "2.1.0"},
                    {"name": "transformers", "version": "4.38.0"}
                ]
            }
        ]
    }
    
    count = compiler.compile_stable_stacks(yaml_data)
    assert count == 1
    
    # Verify stack was inserted
    with temp_db.get_session() as session:
        stack = get_stable_stack_by_name(session, "torch-2.1-transformers-4.38")
        assert stack is not None
        assert stack.cuda_version == "11.8"
        
        packages = get_stable_stack_packages(session, stack.uid)
        assert len(packages) == 2
        package_names = [pkg.package_name for pkg in packages]
        assert "torch" in package_names
        assert "transformers" in package_names


def test_compile_runtime_profiles(compiler, temp_db):
    """Test compilation of runtime profiles."""
    yaml_data = {
        "profiles": [
            {
                "runtime": "transformers",
                "kv_overhead_multiplier": 1.0,
                "fragmentation_multiplier": 1.2,
                "description": "Standard HuggingFace transformers runtime"
            },
            {
                "runtime": "vllm",
                "kv_overhead_multiplier": 1.1,
                "fragmentation_multiplier": 1.15,
                "description": "vLLM optimized runtime"
            }
        ]
    }
    
    count = compiler.compile_runtime_profiles(yaml_data)
    assert count == 2
    
    # Verify profiles were inserted
    with temp_db.get_session() as session:
        profile1 = get_runtime_profile(session, "transformers")
        assert profile1 is not None
        assert profile1.kv_overhead_multiplier == 1.0
        assert profile1.fragmentation_multiplier == 1.2
        
        profile2 = get_runtime_profile(session, "vllm")
        assert profile2 is not None
        assert profile2.kv_overhead_multiplier == 1.1


def test_compile_updates_existing_records(compiler, temp_db):
    """Test that compilation updates existing records instead of creating duplicates."""
    yaml_data = {
        "profiles": [
            {
                "runtime": "transformers",
                "kv_overhead_multiplier": 1.0,
                "fragmentation_multiplier": 1.2,
                "description": "Original description"
            }
        ]
    }
    
    # First compilation
    count1 = compiler.compile_runtime_profiles(yaml_data)
    assert count1 == 1
    
    # Update the data
    yaml_data["profiles"][0]["description"] = "Updated description"
    yaml_data["profiles"][0]["kv_overhead_multiplier"] = 1.5
    
    # Second compilation
    count2 = compiler.compile_runtime_profiles(yaml_data)
    assert count2 == 1
    
    # Verify update
    with temp_db.get_session() as session:
        profile = get_runtime_profile(session, "transformers")
        assert profile is not None
        assert profile.description == "Updated description"
        assert profile.kv_overhead_multiplier == 1.5


def test_compile_empty_yaml(compiler):
    """Test compilation with empty YAML data."""
    # Empty rules
    count = compiler.compile_compatibility_rules({})
    assert count == 0
    
    # Empty stacks
    count = compiler.compile_stable_stacks({})
    assert count == 0
    
    # Empty profiles
    count = compiler.compile_runtime_profiles({})
    assert count == 0


def test_compile_with_invalid_data(compiler):
    """Test compilation with invalid data."""
    yaml_data = {
        "rules": [
            {
                "package": "torch",
                # Missing required fields
                "type": "incompatible"
            }
        ]
    }
    
    # Should handle validation errors gracefully
    count = compiler.compile_compatibility_rules(yaml_data)
    assert count == 0  # No rules should be processed


if __name__ == "__main__":
    pytest.main([__file__, "-v"])


# Made with Bob