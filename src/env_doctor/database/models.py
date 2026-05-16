"""
Database models for env-doctor.

All models use SQLModel (SQLAlchemy + Pydantic) for ORM functionality.
UIDs are deterministic SHA-256 hashes for reproducibility.
"""

from datetime import datetime
from typing import Optional

from sqlmodel import Field, Relationship, SQLModel


class Package(SQLModel, table=True):
    """
    Package registry table.
    
    Stores unique packages across all ecosystems (primarily Python/PyPI).
    """
    
    __tablename__ = "packages"
    
    uid: str = Field(primary_key=True, max_length=16, description="SHA-256 hash of package name")
    name: str = Field(unique=True, index=True, description="Package name (e.g., 'torch')")
    ecosystem: str = Field(default="python", description="Package ecosystem (default: python)")
    created_at: datetime = Field(default_factory=datetime.utcnow, description="Record creation time")
    updated_at: datetime = Field(default_factory=datetime.utcnow, description="Last update time")
    
    # Relationships
    versions: list["PackageVersion"] = Relationship(back_populates="package")


class PackageVersion(SQLModel, table=True):
    """
    Package version tracking table.
    
    Stores all versions of a package with metadata.
    """
    
    __tablename__ = "package_versions"
    
    uid: str = Field(primary_key=True, max_length=16, description="SHA-256 hash of package+version")
    package_uid: str = Field(foreign_key="packages.uid", index=True, description="Reference to package")
    version: str = Field(description="Version string (e.g., '2.1.0')")
    requires_python: Optional[str] = Field(default=None, description="Python version requirement")
    release_date: Optional[datetime] = Field(default=None, description="Release date from PyPI")
    created_at: datetime = Field(default_factory=datetime.utcnow, description="Record creation time")
    
    # Relationships
    package: Optional[Package] = Relationship(back_populates="versions")
    dependencies: list["PackageDependency"] = Relationship(back_populates="package_version")
    wheels: list["WheelAvailability"] = Relationship(back_populates="package_version")


class PackageDependency(SQLModel, table=True):
    """
    Package dependency graph table.
    
    Stores dependencies for each package version (auto-generated from PyPI).
    """
    
    __tablename__ = "package_dependencies"
    
    uid: str = Field(primary_key=True, max_length=16, description="SHA-256 hash of pkg+ver+dep")
    package_version_uid: str = Field(
        foreign_key="package_versions.uid",
        index=True,
        description="Reference to package version"
    )
    dependency_name: str = Field(index=True, description="Dependency package name")
    version_specifier: str = Field(description="Version constraint (e.g., '>=1.0,<2.0')")
    extra: Optional[str] = Field(default=None, description="Optional extra (e.g., 'dev', 'test')")
    created_at: datetime = Field(default_factory=datetime.utcnow, description="Record creation time")
    
    # Relationships
    package_version: Optional[PackageVersion] = Relationship(back_populates="dependencies")


class CompatibilityRule(SQLModel, table=True):
    """
    Compatibility rules table (curated intelligence).
    
    Stores manually curated compatibility information from community knowledge.
    """
    
    __tablename__ = "compatibility_rules"
    
    uid: str = Field(primary_key=True, max_length=16, description="SHA-256 hash of rule")
    package_name: str = Field(index=True, description="Package name")
    package_version_range: str = Field(description="Package version range (e.g., '>=2.0,<2.2')")
    dependency_name: str = Field(index=True, description="Dependency package name")
    dependency_version_range: str = Field(description="Dependency version range")
    compatibility_type: str = Field(
        description="Type: compatible/incompatible/partial/runtime-risk/untested"
    )
    confidence_level: str = Field(
        description="Confidence: production-tested/stable/community-tested/experimental"
    )
    severity: int = Field(ge=0, le=100, description="Severity score (0-100)")
    description: str = Field(description="Human-readable description of the rule")
    workaround: Optional[str] = Field(default=None, description="Workaround if available")
    created_at: datetime = Field(default_factory=datetime.utcnow, description="Record creation time")


class StableStack(SQLModel, table=True):
    """
    Stable stack recommendations table.
    
    Stores curated, tested package combinations that work well together.
    """
    
    __tablename__ = "stable_stacks"
    
    uid: str = Field(primary_key=True, max_length=16, description="SHA-256 hash of stack")
    name: str = Field(unique=True, description="Stack name (e.g., 'torch-2.1-transformers-4.38')")
    cuda_version: Optional[str] = Field(default=None, description="CUDA version (e.g., '11.8')")
    python_version: str = Field(description="Python version (e.g., '3.10')")
    confidence_level: str = Field(
        description="Confidence: production-tested/stable/community-tested/experimental"
    )
    description: str = Field(description="Description of the stack and use cases")
    created_at: datetime = Field(default_factory=datetime.utcnow, description="Record creation time")
    
    # Relationships
    packages: list["StableStackPackage"] = Relationship(back_populates="stack")


class StableStackPackage(SQLModel, table=True):
    """
    Stable stack composition table.
    
    Links packages to stable stacks (many-to-many relationship).
    """
    
    __tablename__ = "stable_stack_packages"
    
    uid: str = Field(primary_key=True, max_length=16, description="SHA-256 hash")
    stack_uid: str = Field(
        foreign_key="stable_stacks.uid",
        index=True,
        description="Reference to stable stack"
    )
    package_name: str = Field(description="Package name")
    version: str = Field(description="Specific version in this stack")
    created_at: datetime = Field(default_factory=datetime.utcnow, description="Record creation time")
    
    # Relationships
    stack: Optional[StableStack] = Relationship(back_populates="packages")


class WheelAvailability(SQLModel, table=True):
    """
    Wheel availability table.
    
    Tracks platform-specific wheel availability for packages.
    """
    
    __tablename__ = "wheel_availability"
    
    uid: str = Field(primary_key=True, max_length=16, description="SHA-256 hash")
    package_version_uid: str = Field(
        foreign_key="package_versions.uid",
        index=True,
        description="Reference to package version"
    )
    python_tag: str = Field(description="Python tag (e.g., 'cp310', 'py3')")
    abi_tag: str = Field(description="ABI tag (e.g., 'cp310', 'none')")
    platform_tag: str = Field(description="Platform tag (e.g., 'win_amd64', 'manylinux2014_x86_64')")
    available: bool = Field(default=True, description="Whether wheel is available")
    created_at: datetime = Field(default_factory=datetime.utcnow, description="Record creation time")
    
    # Relationships
    package_version: Optional[PackageVersion] = Relationship(back_populates="wheels")


class RuntimeProfile(SQLModel, table=True):
    """
    Runtime profile table.
    
    Stores runtime-specific overhead multipliers for VRAM estimation.
    """
    
    __tablename__ = "runtime_profiles"
    
    uid: str = Field(primary_key=True, max_length=16, description="SHA-256 hash of runtime name")
    runtime_name: str = Field(unique=True, description="Runtime name (e.g., 'transformers', 'vllm')")
    kv_overhead_multiplier: float = Field(
        default=1.0,
        description="KV cache overhead multiplier"
    )
    fragmentation_multiplier: float = Field(
        default=1.2,
        description="Memory fragmentation multiplier"
    )
    description: str = Field(description="Description of the runtime and its characteristics")
    created_at: datetime = Field(default_factory=datetime.utcnow, description="Record creation time")

# Made with Bob
