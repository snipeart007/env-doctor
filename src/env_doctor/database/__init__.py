"""
Database module for env-doctor.

Provides database models, manager, queries, UID generation, and YAML compiler.
"""

from .compiler import YAMLCompiler
from .manager import DatabaseManager, get_default_db_path, initialize_database
from .models import (
    CompatibilityRule,
    Package,
    PackageDependency,
    PackageVersion,
    RuntimeProfile,
    StableStack,
    StableStackPackage,
    WheelAvailability,
)
from .queries import (
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
from .uid_generator import (
    generate_compatibility_uid,
    generate_dependency_uid,
    generate_package_uid,
    generate_runtime_uid,
    generate_stack_uid,
    generate_version_uid,
    generate_wheel_uid,
)

__all__ = [
    # Manager
    "DatabaseManager",
    "get_default_db_path",
    "initialize_database",
    # Compiler
    "YAMLCompiler",
    # Models
    "Package",
    "PackageVersion",
    "PackageDependency",
    "CompatibilityRule",
    "StableStack",
    "StableStackPackage",
    "WheelAvailability",
    "RuntimeProfile",
    # Queries
    "get_package_by_name",
    "get_package_by_uid",
    "get_package_versions",
    "get_package_version",
    "get_compatibility_rules",
    "get_compatibility_rules_for_dependency",
    "get_stable_stacks",
    "get_stable_stack_by_name",
    "get_stable_stack_packages",
    "get_wheel_availability",
    "get_runtime_profile",
    "get_all_runtime_profiles",
    "search_packages",
    # UID Generators
    "generate_package_uid",
    "generate_version_uid",
    "generate_dependency_uid",
    "generate_compatibility_uid",
    "generate_stack_uid",
    "generate_wheel_uid",
    "generate_runtime_uid",
]

# Made with Bob
