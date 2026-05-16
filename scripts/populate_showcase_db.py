"""
Showcase database population script for env-doctor.

This script populates the local database with:
1. Core ML package metadata from PyPI (Automatic Layer)
2. Hand-crafted compatibility rules (Curated Intelligence Layer)
3. Verified stable stacks (Recommendation Layer)
4. Runtime profiles (VRAM Layer)
"""

import sys
from datetime import datetime, timedelta
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from env_doctor.database.manager import DatabaseManager
from env_doctor.database.models import (
    Package, 
    PackageVersion, 
    CompatibilityRule, 
    StableStack, 
    StableStackPackage,
    RuntimeProfile
)
from env_doctor.database.uid_generator import (
    generate_package_uid,
    generate_version_uid,
    generate_compatibility_uid,
    generate_stack_uid,
    generate_runtime_uid
)
from env_doctor.scanner.bootstrap import DatabaseBootstrap
from env_doctor.scanner.pypi_client import PyPIClient

def populate_intelligence_layer(db_manager: DatabaseManager):
    """Add hand-crafted compatibility rules and intelligence."""
    print("\n[2/4] Populating Curated Intelligence Layer...")
    
    rules = [
        {
            "package": "flash-attn",
            "version_range": ">=2.0.0",
            "dependency": "torch",
            "dependency_range": "<2.0.0",
            "type": "incompatible",
            "confidence": "production-tested",
            "severity": 100,
            "reason": "Flash Attention 2.0 requires Torch 2.0 or higher for CUDA graph support."
        },
        {
            "package": "bitsandbytes",
            "version_range": "<0.41.0",
            "dependency": "cuda",
            "dependency_range": ">=12.4",
            "type": "runtime-risk",
            "confidence": "community-tested",
            "severity": 80,
            "reason": "Older bitsandbytes versions have stability issues with CUDA 12.4+ drivers."
        },
        {
            "package": "transformers",
            "version_range": ">=4.40.0",
            "dependency": "tokenizers",
            "dependency_range": "<0.19.0",
            "type": "incompatible",
            "confidence": "stable",
            "severity": 90,
            "reason": "Transformers 4.40+ uses new tokenizer APIs only available in tokenizers 0.19+."
        },
        {
            "package": "unsloth",
            "version_range": ">=2024.4",
            "dependency": "torch",
            "dependency_range": "!=2.2.0,!=2.2.1",
            "type": "partial",
            "confidence": "production-tested",
            "severity": 60,
            "reason": "Unsloth has known performance regressions with Torch 2.2.0/2.2.1; 2.3.0+ recommended."
        }
    ]
    
    with db_manager.get_session() as session:
        for r in rules:
            uid = generate_compatibility_uid(r["package"], r["version_range"], r["dependency"], r["dependency_range"])
            rule = CompatibilityRule(
                uid=uid,
                package_name=r["package"],
                package_version_range=r["version_range"],
                dependency_name=r["dependency"],
                dependency_version_range=r["dependency_range"],
                compatibility_type=r["type"],
                confidence_level=r["confidence"],
                severity=r["severity"],
                description=r["reason"]
            )
            session.merge(rule)
        session.commit()
    print(f"✓ Added {len(rules)} compatibility rules")

def populate_stable_stacks(db_manager: DatabaseManager):
    """Add verified stable stacks."""
    print("\n[3/4] Populating Verified Stable Stacks...")
    
    stacks = [
        {
            "name": "Llama-3-Production-Stack",
            "cuda": "12.1",
            "python": "3.10",
            "confidence": "production-tested",
            "desc": "Optimized stack for Llama 3 training and inference on H100/A100.",
            "packages": [
                ("torch", "2.3.0"),
                ("transformers", "4.41.0"),
                ("accelerate", "0.30.0"),
                ("bitsandbytes", "0.43.0"),
                ("flash-attn", "2.5.8")
            ]
        },
        {
            "name": "General-ML-Stable",
            "cuda": "11.8",
            "python": "3.9",
            "confidence": "stable",
            "desc": "Highly compatible stack for older GPUs and general NLP tasks.",
            "packages": [
                ("torch", "2.1.0"),
                ("transformers", "4.36.0"),
                ("accelerate", "0.25.0"),
                ("numpy", "1.26.0")
            ]
        }
    ]
    
    with db_manager.get_session() as session:
        for s in stacks:
            stack_uid = generate_stack_uid(s["name"], s["cuda"])
            stack = StableStack(
                uid=stack_uid,
                name=s["name"],
                cuda_version=s["cuda"],
                python_version=s["python"],
                confidence_level=s["confidence"],
                description=s["desc"],
                created_at=datetime.utcnow() - timedelta(days=10)
            )
            session.merge(stack)
            
            for pkg_name, pkg_ver in s["packages"]:
                pkg_uid = generate_compatibility_uid(s["name"], pkg_name, pkg_ver, "")
                stack_pkg = StableStackPackage(
                    uid=pkg_uid,
                    stack_uid=stack_uid,
                    package_name=pkg_name,
                    version=pkg_ver
                )
                session.merge(stack_pkg)
        session.commit()
    print(f"✓ Added {len(stacks)} stable stacks")

def populate_runtime_profiles(db_manager: DatabaseManager):
    """Add VRAM runtime profiles."""
    print("\n[4/4] Populating Runtime Profiles...")
    
    profiles = [
        {
            "name": "vllm",
            "kv": 0.85,
            "frag": 1.1,
            "desc": "vLLM with PagedAttention and optimized KV cache."
        },
        {
            "name": "transformers",
            "kv": 1.0,
            "frag": 1.2,
            "desc": "Standard HuggingFace Transformers eager execution."
        },
        {
            "name": "deepspeed",
            "kv": 0.9,
            "frag": 1.15,
            "desc": "DeepSpeed Inference with ZeRO-Inference."
        }
    ]
    
    with db_manager.get_session() as session:
        for p in profiles:
            uid = generate_runtime_uid(p["name"])
            profile = RuntimeProfile(
                uid=uid,
                runtime_name=p["name"],
                kv_overhead_multiplier=p["kv"],
                fragmentation_multiplier=p["frag"],
                description=p["desc"]
            )
            session.merge(profile)
        session.commit()
    print(f"✓ Added {len(profiles)} runtime profiles")

def main():
    print("=" * 60)
    print("env-doctor Showcase Database Population")
    print("=" * 60)
    
    # Use default DB path
    from env_doctor.utils.config import get_default_db_path
    db_path = get_default_db_path()
    
    # Ensure directory exists
    db_path.parent.mkdir(parents=True, exist_ok=True)
    
    db_manager = DatabaseManager(str(db_path))
    db_manager.create_tables()
    
    # 1. Automatic Layer (PyPI)
    print("\n[1/4] Bootstrapping Automatic Metadata Layer (Core Packages)...")
    print("      This fetches real data from PyPI. Please wait...")
    
    pypi_client = PyPIClient()
    bootstrap = DatabaseBootstrap(db_manager, pypi_client)
    
    # Bootstrap a subset for the showcase to keep it fast
    showcase_packages = ["torch", "transformers", "accelerate", "bitsandbytes", "flash-attn", "numpy", "tokenizers"]
    
    def progress(msg: str):
        print(f"      {msg}")
        
    bootstrap.bootstrap_packages(showcase_packages, progress_callback=progress)
    pypi_client.close()
    
    # 2. Intelligence Layer
    populate_intelligence_layer(db_manager)
    
    # 3. Stable Stacks
    populate_stable_stacks(db_manager)
    
    # 4. Runtime Profiles
    populate_runtime_profiles(db_manager)
    
    db_manager.close()
    
    print("\n" + "=" * 60)
    print("✨ Showcase database populated successfully!")
    print(f"Location: {db_path}")
    print("=" * 60)
    print("\nNext steps:")
    print("  uv run env-doctor inspect")
    print("  uv run env-doctor check pyproject.toml")
    print("  uv run env-doctor recommend --package torch==2.3.0")
    print("  uv run env-doctor vram --model meta-llama/Llama-2-7b-hf --runtime vllm")

if __name__ == "__main__":
    main()
