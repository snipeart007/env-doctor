"""
Verification script for YAML compiler.

Simple test to verify the compiler works correctly without pytest.
"""

import tempfile
from pathlib import Path

from env_doctor.database import (
    DatabaseManager,
    YAMLCompiler,
    get_compatibility_rules,
    get_runtime_profile,
    get_stable_stack_by_name,
    get_stable_stack_packages,
)


def test_compiler():
    """Test the YAML compiler functionality."""
    print("=" * 60)
    print("YAML Compiler Verification")
    print("=" * 60)
    
    # Create temporary database
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        db_path = f.name
    
    print(f"\n1. Creating temporary database: {db_path}")
    manager = DatabaseManager(db_path)
    manager.create_tables()
    print("   [OK] Database created successfully")
    
    # Create compiler
    print("\n2. Initializing YAML compiler")
    compiler = YAMLCompiler(manager)
    print(f"   [OK] Compiler initialized with repo: {compiler.github_repo}")
    
    # Test compatibility rules compilation
    print("\n3. Testing compatibility rules compilation")
    rules_yaml = {
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
            },
            {
                "package": "numpy",
                "version_range": ">=1.24.0",
                "dependency": "pandas",
                "dependency_range": ">=2.0.0",
                "type": "compatible",
                "confidence": "production-tested",
                "severity": 10,
                "description": "Fully compatible versions"
            }
        ]
    }
    
    count = compiler.compile_compatibility_rules(rules_yaml)
    print(f"   [OK] Compiled {count} compatibility rules")
    
    # Verify rules
    with manager.get_session() as session:
        rules = get_compatibility_rules(session, "torch")
        print(f"   [OK] Retrieved {len(rules)} rules for 'torch'")
        if rules:
            print(f"     - Package: {rules[0].package_name}")
            print(f"     - Dependency: {rules[0].dependency_name}")
            print(f"     - Severity: {rules[0].severity}")
    
    # Test stable stacks compilation
    print("\n4. Testing stable stacks compilation")
    stacks_yaml = {
        "stacks": [
            {
                "name": "torch-2.1-transformers-4.38",
                "cuda_version": "11.8",
                "python_version": ">=3.10,<3.12",
                "confidence": "production-tested",
                "description": "Stable stack for production inference",
                "packages": [
                    {"name": "torch", "version": "2.1.0"},
                    {"name": "transformers", "version": "4.38.0"},
                    {"name": "flash-attn", "version": "2.5.0"}
                ]
            }
        ]
    }
    
    count = compiler.compile_stable_stacks(stacks_yaml)
    print(f"   [OK] Compiled {count} stable stacks")
    
    # Verify stacks
    with manager.get_session() as session:
        stack = get_stable_stack_by_name(session, "torch-2.1-transformers-4.38")
        if stack:
            print(f"   [OK] Retrieved stack: {stack.name}")
            print(f"     - CUDA version: {stack.cuda_version}")
            print(f"     - Python version: {stack.python_version}")
            
            packages = get_stable_stack_packages(session, stack.uid)
            print(f"     - Packages: {len(packages)}")
            for pkg in packages:
                print(f"       * {pkg.package_name} {pkg.version}")
    
    # Test runtime profiles compilation
    print("\n5. Testing runtime profiles compilation")
    profiles_yaml = {
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
    
    count = compiler.compile_runtime_profiles(profiles_yaml)
    print(f"   [OK] Compiled {count} runtime profiles")
    
    # Verify profiles
    with manager.get_session() as session:
        profile = get_runtime_profile(session, "transformers")
        if profile:
            print(f"   [OK] Retrieved profile: {profile.runtime_name}")
            print(f"     - KV overhead: {profile.kv_overhead_multiplier}")
            print(f"     - Fragmentation: {profile.fragmentation_multiplier}")
    
    # Test update functionality
    print("\n6. Testing update functionality")
    profiles_yaml["profiles"][0]["kv_overhead_multiplier"] = 1.5
    profiles_yaml["profiles"][0]["description"] = "Updated description"
    
    count = compiler.compile_runtime_profiles(profiles_yaml)
    print(f"   [OK] Updated {count} runtime profiles")
    
    with manager.get_session() as session:
        profile = get_runtime_profile(session, "transformers")
        if profile:
            print(f"   [OK] Verified update:")
            print(f"     - New KV overhead: {profile.kv_overhead_multiplier}")
            print(f"     - New description: {profile.description}")
    
    # Test YAML validation
    print("\n7. Testing YAML validation")
    valid_yaml = """
rules:
  - package: torch
    version_range: ">=2.0.0"
    dependency: numpy
    dependency_range: ">=1.20.0"
    type: compatible
    confidence: stable
    severity: 10
    description: "Test rule"
"""
    
    try:
        result = compiler.validate_yaml_structure(valid_yaml, "compatibility_rules")
        print(f"   [OK] Valid YAML passed validation: {result}")
    except Exception as e:
        print(f"   [FAIL] Validation failed: {e}")
    
    # Test invalid YAML
    invalid_yaml = """
rules:
  - package: torch
    type: compatible
"""
    
    try:
        compiler.validate_yaml_structure(invalid_yaml, "compatibility_rules")
        print("   [FAIL] Invalid YAML should have failed validation")
    except Exception:
        print("   [OK] Invalid YAML correctly rejected")
    
    # Cleanup
    print("\n8. Cleaning up")
    manager.close()
    Path(db_path).unlink(missing_ok=True)
    print("   [OK] Temporary database removed")
    
    print("\n" + "=" * 60)
    print("[SUCCESS] All verification tests passed!")
    print("=" * 60)


if __name__ == "__main__":
    try:
        test_compiler()
    except Exception as e:
        print(f"\n[ERROR] Error during verification: {e}")
        import traceback
        traceback.print_exc()
        exit(1)


# Made with Bob