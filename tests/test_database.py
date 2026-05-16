"""
Tests for database module.

Tests models, UID generation, manager, and queries.
"""

import tempfile
from datetime import datetime
from pathlib import Path

import pytest

from env_doctor.database import (
    CompatibilityRule,
    DatabaseManager,
    Package,
    PackageDependency,
    PackageVersion,
    RuntimeProfile,
    StableStack,
    StableStackPackage,
    WheelAvailability,
    generate_compatibility_uid,
    generate_dependency_uid,
    generate_package_uid,
    generate_runtime_uid,
    generate_stack_uid,
    generate_version_uid,
    generate_wheel_uid,
    get_compatibility_rules,
    get_package_by_name,
    get_package_versions,
    get_runtime_profile,
    get_stable_stacks,
)


class TestUIDGeneration:
    """Test UID generation functions."""

    def test_generate_package_uid_deterministic(self) -> None:
        """Test that package UIDs are deterministic."""
        uid1 = generate_package_uid("torch")
        uid2 = generate_package_uid("torch")
        assert uid1 == uid2
        assert len(uid1) == 16

    def test_generate_package_uid_case_insensitive(self) -> None:
        """Test that package UIDs are case-insensitive."""
        uid1 = generate_package_uid("torch")
        uid2 = generate_package_uid("TORCH")
        assert uid1 == uid2

    def test_generate_version_uid_deterministic(self) -> None:
        """Test that version UIDs are deterministic."""
        uid1 = generate_version_uid("torch", "2.1.0")
        uid2 = generate_version_uid("torch", "2.1.0")
        assert uid1 == uid2
        assert len(uid1) == 16

    def test_generate_version_uid_unique(self) -> None:
        """Test that different versions have different UIDs."""
        uid1 = generate_version_uid("torch", "2.1.0")
        uid2 = generate_version_uid("torch", "2.2.0")
        assert uid1 != uid2

    def test_generate_dependency_uid(self) -> None:
        """Test dependency UID generation."""
        uid = generate_dependency_uid("torch", "2.1.0", "numpy")
        assert len(uid) == 16

    def test_generate_compatibility_uid(self) -> None:
        """Test compatibility rule UID generation."""
        uid = generate_compatibility_uid("torch", ">=2.0", "transformers", ">=4.30")
        assert len(uid) == 16

    def test_generate_stack_uid(self) -> None:
        """Test stack UID generation."""
        uid1 = generate_stack_uid("torch-2.1-transformers-4.38", "11.8")
        uid2 = generate_stack_uid("torch-2.1-transformers-4.38", None)
        assert len(uid1) == 16
        assert len(uid2) == 16
        assert uid1 != uid2  # Different CUDA versions

    def test_generate_wheel_uid(self) -> None:
        """Test wheel UID generation."""
        uid = generate_wheel_uid("torch", "2.1.0", "cp310", "win_amd64")
        assert len(uid) == 16

    def test_generate_runtime_uid(self) -> None:
        """Test runtime UID generation."""
        uid = generate_runtime_uid("transformers")
        assert len(uid) == 16


class TestDatabaseManager:
    """Test database manager functionality."""

    def test_create_database(self) -> None:
        """Test database creation."""
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = str(Path(tmpdir) / "test.db")
            manager = DatabaseManager(db_path)
            manager.create_tables()
            
            # Verify database file was created
            assert Path(db_path).exists()
            manager.close()

    def test_session_context_manager(self) -> None:
        """Test session context manager."""
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = str(Path(tmpdir) / "test.db")
            manager = DatabaseManager(db_path)
            manager.create_tables()
            
            # Test session creation
            with manager.get_session() as session:
                assert session is not None
            
            manager.close()

    def test_database_manager_context_manager(self) -> None:
        """Test DatabaseManager as context manager."""
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = str(Path(tmpdir) / "test.db")
            
            with DatabaseManager(db_path) as manager:
                manager.create_tables()
                assert Path(db_path).exists()


class TestDatabaseOperations:
    """Test database CRUD operations."""

    @pytest.fixture
    def db_manager(self) -> DatabaseManager:
        """Create a temporary database for testing."""
        tmpdir = tempfile.mkdtemp()
        db_path = str(Path(tmpdir) / "test.db")
        manager = DatabaseManager(db_path)
        manager.create_tables()
        yield manager
        manager.close()

    def test_create_package(self, db_manager: DatabaseManager) -> None:
        """Test creating a package."""
        with db_manager.get_session() as session:
            package = Package(
                uid=generate_package_uid("torch"),
                name="torch",
                ecosystem="python",
            )
            session.add(package)
            session.commit()
            
            # Verify package was created
            retrieved = get_package_by_name(session, "torch")
            assert retrieved is not None
            assert retrieved.name == "torch"

    def test_create_package_version(self, db_manager: DatabaseManager) -> None:
        """Test creating a package version."""
        with db_manager.get_session() as session:
            # Create package first
            package = Package(
                uid=generate_package_uid("torch"),
                name="torch",
                ecosystem="python",
            )
            session.add(package)
            session.commit()
            
            # Create version
            version = PackageVersion(
                uid=generate_version_uid("torch", "2.1.0"),
                package_uid=package.uid,
                version="2.1.0",
                requires_python=">=3.8",
            )
            session.add(version)
            session.commit()
            
            # Verify version was created
            versions = get_package_versions(session, package.uid)
            assert len(versions) == 1
            assert versions[0].version == "2.1.0"

    def test_create_compatibility_rule(self, db_manager: DatabaseManager) -> None:
        """Test creating a compatibility rule."""
        with db_manager.get_session() as session:
            rule = CompatibilityRule(
                uid=generate_compatibility_uid("torch", ">=2.0", "transformers", ">=4.30"),
                package_name="torch",
                package_version_range=">=2.0,<2.2",
                dependency_name="transformers",
                dependency_version_range=">=4.30",
                compatibility_type="compatible",
                confidence_level="production-tested",
                severity=0,
                description="Torch 2.x works well with Transformers 4.30+",
            )
            session.add(rule)
            session.commit()
            
            # Verify rule was created
            rules = get_compatibility_rules(session, "torch")
            assert len(rules) == 1
            assert rules[0].compatibility_type == "compatible"

    def test_create_stable_stack(self, db_manager: DatabaseManager) -> None:
        """Test creating a stable stack."""
        with db_manager.get_session() as session:
            stack = StableStack(
                uid=generate_stack_uid("torch-2.1-transformers-4.38", "11.8"),
                name="torch-2.1-transformers-4.38",
                cuda_version="11.8",
                python_version="3.10",
                confidence_level="production-tested",
                description="Stable stack for production use",
            )
            session.add(stack)
            session.commit()
            
            # Verify stack was created
            stacks = get_stable_stacks(session)
            assert len(stacks) == 1
            assert stacks[0].name == "torch-2.1-transformers-4.38"

    def test_create_runtime_profile(self, db_manager: DatabaseManager) -> None:
        """Test creating a runtime profile."""
        with db_manager.get_session() as session:
            profile = RuntimeProfile(
                uid=generate_runtime_uid("transformers"),
                runtime_name="transformers",
                kv_overhead_multiplier=1.0,
                fragmentation_multiplier=1.2,
                description="Standard Transformers runtime",
            )
            session.add(profile)
            session.commit()
            
            # Verify profile was created
            retrieved = get_runtime_profile(session, "transformers")
            assert retrieved is not None
            assert retrieved.runtime_name == "transformers"
            assert retrieved.kv_overhead_multiplier == 1.0


class TestModels:
    """Test model relationships and constraints."""

    @pytest.fixture
    def db_manager(self) -> DatabaseManager:
        """Create a temporary database for testing."""
        tmpdir = tempfile.mkdtemp()
        db_path = str(Path(tmpdir) / "test.db")
        manager = DatabaseManager(db_path)
        manager.create_tables()
        yield manager
        manager.close()

    def test_package_version_relationship(self, db_manager: DatabaseManager) -> None:
        """Test relationship between Package and PackageVersion."""
        with db_manager.get_session() as session:
            # Create package with versions
            package = Package(
                uid=generate_package_uid("torch"),
                name="torch",
                ecosystem="python",
            )
            session.add(package)
            session.commit()
            
            version1 = PackageVersion(
                uid=generate_version_uid("torch", "2.1.0"),
                package_uid=package.uid,
                version="2.1.0",
            )
            version2 = PackageVersion(
                uid=generate_version_uid("torch", "2.2.0"),
                package_uid=package.uid,
                version="2.2.0",
            )
            session.add(version1)
            session.add(version2)
            session.commit()
            
            # Verify relationship
            versions = get_package_versions(session, package.uid)
            assert len(versions) == 2


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

# Made with Bob
