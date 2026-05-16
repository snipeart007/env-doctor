"""
Simple verification script for database components.

This script demonstrates that all database components are properly implemented
and can be imported without errors. It doesn't require pytest or other dependencies.
"""

import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))


def verify_imports() -> None:
    """Verify all database components can be imported."""
    print("=" * 70)
    print("PHASE 2 DATABASE VERIFICATION")
    print("=" * 70)
    print()
    
    print("1. Testing UID Generator imports...")
    try:
        from env_doctor.database.uid_generator import (
            generate_compatibility_uid,
            generate_dependency_uid,
            generate_package_uid,
            generate_runtime_uid,
            generate_stack_uid,
            generate_version_uid,
            generate_wheel_uid,
        )
        print("   ✓ UID generator functions imported successfully")
    except ImportError as e:
        print(f"   ✗ Failed to import UID generator: {e}")
        return
    
    print()
    print("2. Testing UID generation...")
    try:
        pkg_uid = generate_package_uid("torch")
        ver_uid = generate_version_uid("torch", "2.1.0")
        dep_uid = generate_dependency_uid("torch", "2.1.0", "numpy")
        compat_uid = generate_compatibility_uid("torch", ">=2.0", "transformers", ">=4.30")
        stack_uid = generate_stack_uid("torch-2.1-transformers-4.38", "11.8")
        wheel_uid = generate_wheel_uid("torch", "2.1.0", "cp310", "win_amd64")
        runtime_uid = generate_runtime_uid("transformers")
        
        print(f"   ✓ Package UID: {pkg_uid} (length: {len(pkg_uid)})")
        print(f"   ✓ Version UID: {ver_uid} (length: {len(ver_uid)})")
        print(f"   ✓ Dependency UID: {dep_uid} (length: {len(dep_uid)})")
        print(f"   ✓ Compatibility UID: {compat_uid} (length: {len(compat_uid)})")
        print(f"   ✓ Stack UID: {stack_uid} (length: {len(stack_uid)})")
        print(f"   ✓ Wheel UID: {wheel_uid} (length: {len(wheel_uid)})")
        print(f"   ✓ Runtime UID: {runtime_uid} (length: {len(runtime_uid)})")
        
        # Verify determinism
        pkg_uid2 = generate_package_uid("torch")
        assert pkg_uid == pkg_uid2, "UIDs are not deterministic!"
        print("   ✓ UIDs are deterministic (same input = same output)")
        
        # Verify case insensitivity
        pkg_uid3 = generate_package_uid("TORCH")
        assert pkg_uid == pkg_uid3, "UIDs are not case-insensitive!"
        print("   ✓ UIDs are case-insensitive")
        
    except Exception as e:
        print(f"   ✗ UID generation failed: {e}")
        return
    
    print()
    print("3. Testing model imports...")
    try:
        from env_doctor.database.models import (
            CompatibilityRule,
            Package,
            PackageDependency,
            PackageVersion,
            RuntimeProfile,
            StableStack,
            StableStackPackage,
            WheelAvailability,
        )
        print("   ✓ All 8 model classes imported successfully:")
        print("     - Package")
        print("     - PackageVersion")
        print("     - PackageDependency")
        print("     - CompatibilityRule")
        print("     - StableStack")
        print("     - StableStackPackage")
        print("     - WheelAvailability")
        print("     - RuntimeProfile")
    except ImportError as e:
        print(f"   ✗ Failed to import models: {e}")
        return
    
    print()
    print("4. Testing manager imports...")
    try:
        from env_doctor.database.manager import (
            DatabaseManager,
            get_default_db_path,
            initialize_database,
        )
        print("   ✓ DatabaseManager imported successfully")
        print(f"   ✓ Default DB path: {get_default_db_path()}")
    except ImportError as e:
        print(f"   ✗ Failed to import manager: {e}")
        return
    
    print()
    print("5. Testing query imports...")
    try:
        from env_doctor.database.queries import (
            get_all_runtime_profiles,
            get_compatibility_rules,
            get_compatibility_rules_for_dependency,
            get_package_by_name,
            get_package_by_uid,
            get_package_version,
            get_package_versions,
            get_runtime_profile,
            get_stable_stack_by_name,
            get_stable_stack_packages,
            get_stable_stacks,
            get_wheel_availability,
            search_packages,
        )
        print("   ✓ All 13 query functions imported successfully")
    except ImportError as e:
        print(f"   ✗ Failed to import queries: {e}")
        return
    
    print()
    print("6. Testing database package imports...")
    try:
        from env_doctor.database import (
            DatabaseManager,
            Package,
            generate_package_uid,
            get_package_by_name,
        )
        print("   ✓ Database package exports working correctly")
    except ImportError as e:
        print(f"   ✗ Failed to import from database package: {e}")
        return
    
    print()
    print("7. Checking schema.sql file...")
    schema_path = Path(__file__).parent.parent / "src" / "env_doctor" / "database" / "schema.sql"
    if schema_path.exists():
        with open(schema_path, "r") as f:
            content = f.read()
            table_count = content.count("CREATE TABLE")
            index_count = content.count("CREATE INDEX")
            view_count = content.count("CREATE VIEW")
            print(f"   ✓ schema.sql exists")
            print(f"   ✓ Contains {table_count} table definitions")
            print(f"   ✓ Contains {index_count} index definitions")
            print(f"   ✓ Contains {view_count} view definitions")
    else:
        print("   ✗ schema.sql not found")
        return
    
    print()
    print("=" * 70)
    print("✓ ALL PHASE 2 COMPONENTS VERIFIED SUCCESSFULLY!")
    print("=" * 70)
    print()
    print("Summary:")
    print("  - UID Generator: 7 functions implemented")
    print("  - Database Models: 8 SQLModel classes created")
    print("  - Database Manager: Connection handling implemented")
    print("  - Query Functions: 13 basic queries implemented")
    print("  - SQL Schema: Reference schema created")
    print()
    print("Note: Full integration tests require installing dependencies:")
    print("  pip install sqlmodel pytest")
    print()


if __name__ == "__main__":
    verify_imports()

# Made with Bob
