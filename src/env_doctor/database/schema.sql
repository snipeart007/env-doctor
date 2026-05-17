-- env-doctor Database Schema
-- SQLite schema for reference and documentation
-- Generated from SQLModel models

-- ============================================================================
-- Table: packages
-- Description: Package registry storing unique packages across ecosystems
-- ============================================================================
CREATE TABLE IF NOT EXISTS packages (
    uid VARCHAR(16) PRIMARY KEY,  -- SHA-256 hash of package name
    name VARCHAR NOT NULL UNIQUE,  -- Package name (e.g., 'torch')
    ecosystem VARCHAR NOT NULL DEFAULT 'python',  -- Package ecosystem
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_packages_name ON packages(name);

-- ============================================================================
-- Table: package_versions
-- Description: Version tracking for all package releases
-- ============================================================================
CREATE TABLE IF NOT EXISTS package_versions (
    uid VARCHAR(16) PRIMARY KEY,  -- SHA-256 hash of package+version
    package_uid VARCHAR(16) NOT NULL,  -- Foreign key to packages
    version VARCHAR NOT NULL,  -- Version string (e.g., '2.1.0')
    requires_python VARCHAR,  -- Python version requirement (e.g., '>=3.8')
    release_date TIMESTAMP,  -- Release date from PyPI
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (package_uid) REFERENCES packages(uid) ON DELETE CASCADE
);

CREATE INDEX idx_package_versions_package_uid ON package_versions(package_uid);

-- ============================================================================
-- Table: package_dependencies
-- Description: Dependency graph (auto-generated from PyPI metadata)
-- ============================================================================
CREATE TABLE IF NOT EXISTS package_dependencies (
    uid VARCHAR(16) PRIMARY KEY,  -- SHA-256 hash of pkg+ver+dep
    package_version_uid VARCHAR(16) NOT NULL,  -- Foreign key to package_versions
    dependency_name VARCHAR NOT NULL,  -- Dependency package name
    version_specifier VARCHAR NOT NULL,  -- Version constraint (e.g., '>=1.0,<2.0')
    extra VARCHAR,  -- Optional extra (e.g., 'dev', 'test')
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (package_version_uid) REFERENCES package_versions(uid) ON DELETE CASCADE
);

CREATE INDEX idx_package_dependencies_package_version_uid ON package_dependencies(package_version_uid);
CREATE INDEX idx_package_dependencies_dependency_name ON package_dependencies(dependency_name);

-- ============================================================================
-- Table: compatibility_rules
-- Description: Curated compatibility intelligence from community knowledge
-- ============================================================================
CREATE TABLE IF NOT EXISTS compatibility_rules (
    uid VARCHAR(16) PRIMARY KEY,  -- SHA-256 hash of rule
    package_name VARCHAR NOT NULL,  -- Package name
    package_version_range VARCHAR NOT NULL,  -- Package version range (e.g., '>=2.0,<2.2')
    dependency_name VARCHAR NOT NULL,  -- Dependency package name
    dependency_version_range VARCHAR NOT NULL,  -- Dependency version range
    cuda_version VARCHAR,  -- Target CUDA version (e.g., '12.1')
    env_system VARCHAR,  -- Operating system or environment info
    compatibility_type VARCHAR NOT NULL,  -- Type: compatible/incompatible/partial/runtime-risk/untested
    confidence_level VARCHAR NOT NULL,  -- Confidence: production-tested/stable/community-tested/experimental
    severity INTEGER NOT NULL CHECK(severity >= 0 AND severity <= 100),  -- Severity score (0-100)
    description TEXT NOT NULL,  -- Human-readable description
    workaround TEXT,  -- Workaround if available
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_compatibility_rules_package_name ON compatibility_rules(package_name);
CREATE INDEX idx_compatibility_rules_dependency_name ON compatibility_rules(dependency_name);

-- ============================================================================
-- Table: stable_stacks
-- Description: Curated, tested package combinations that work well together
-- ============================================================================
CREATE TABLE IF NOT EXISTS stable_stacks (
    uid VARCHAR(16) PRIMARY KEY,  -- SHA-256 hash of stack
    name VARCHAR NOT NULL UNIQUE,  -- Stack name (e.g., 'torch-2.1-transformers-4.38')
    cuda_version VARCHAR,  -- CUDA version (e.g., '11.8')
    env_system VARCHAR,  -- Operating system or environment info
    python_version VARCHAR NOT NULL,  -- Python version (e.g., '3.10')
    confidence_level VARCHAR NOT NULL,  -- Confidence: production-tested/stable/community-tested/experimental
    description TEXT NOT NULL,  -- Description of the stack and use cases
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_stable_stacks_name ON stable_stacks(name);

-- ============================================================================
-- Table: stable_stack_packages
-- Description: Links packages to stable stacks (many-to-many relationship)
-- ============================================================================
CREATE TABLE IF NOT EXISTS stable_stack_packages (
    uid VARCHAR(16) PRIMARY KEY,  -- SHA-256 hash
    stack_uid VARCHAR(16) NOT NULL,  -- Foreign key to stable_stacks
    package_name VARCHAR NOT NULL,  -- Package name
    version VARCHAR NOT NULL,  -- Specific version in this stack
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (stack_uid) REFERENCES stable_stacks(uid) ON DELETE CASCADE
);

CREATE INDEX idx_stable_stack_packages_stack_uid ON stable_stack_packages(stack_uid);

-- ============================================================================
-- Table: wheel_availability
-- Description: Tracks platform-specific wheel availability for packages
-- ============================================================================
CREATE TABLE IF NOT EXISTS wheel_availability (
    uid VARCHAR(16) PRIMARY KEY,  -- SHA-256 hash
    package_version_uid VARCHAR(16) NOT NULL,  -- Foreign key to package_versions
    python_tag VARCHAR NOT NULL,  -- Python tag (e.g., 'cp310', 'py3')
    abi_tag VARCHAR NOT NULL,  -- ABI tag (e.g., 'cp310', 'none')
    platform_tag VARCHAR NOT NULL,  -- Platform tag (e.g., 'win_amd64', 'manylinux2014_x86_64')
    available BOOLEAN NOT NULL DEFAULT TRUE,  -- Whether wheel is available
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (package_version_uid) REFERENCES package_versions(uid) ON DELETE CASCADE
);

CREATE INDEX idx_wheel_availability_package_version_uid ON wheel_availability(package_version_uid);

-- ============================================================================
-- Table: runtime_profiles
-- Description: Runtime-specific overhead multipliers for VRAM estimation
-- ============================================================================
CREATE TABLE IF NOT EXISTS runtime_profiles (
    uid VARCHAR(16) PRIMARY KEY,  -- SHA-256 hash of runtime name
    runtime_name VARCHAR NOT NULL UNIQUE,  -- Runtime name (e.g., 'transformers', 'vllm')
    kv_overhead_multiplier REAL NOT NULL DEFAULT 1.0,  -- KV cache overhead multiplier
    fragmentation_multiplier REAL NOT NULL DEFAULT 1.2,  -- Memory fragmentation multiplier
    description TEXT NOT NULL,  -- Description of the runtime and its characteristics
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_runtime_profiles_runtime_name ON runtime_profiles(runtime_name);

-- ============================================================================
-- Views (Optional - for convenience)
-- ============================================================================

-- View: package_with_latest_version
-- Shows packages with their latest version
CREATE VIEW IF NOT EXISTS package_with_latest_version AS
SELECT 
    p.uid,
    p.name,
    p.ecosystem,
    pv.version AS latest_version,
    pv.release_date AS latest_release_date
FROM packages p
LEFT JOIN package_versions pv ON p.uid = pv.package_uid
WHERE pv.release_date = (
    SELECT MAX(release_date)
    FROM package_versions
    WHERE package_uid = p.uid
);

-- View: compatibility_summary
-- Summarizes compatibility rules by package
CREATE VIEW IF NOT EXISTS compatibility_summary AS
SELECT 
    package_name,
    COUNT(*) AS total_rules,
    SUM(CASE WHEN compatibility_type = 'incompatible' THEN 1 ELSE 0 END) AS incompatible_count,
    SUM(CASE WHEN compatibility_type = 'compatible' THEN 1 ELSE 0 END) AS compatible_count,
    AVG(severity) AS avg_severity
FROM compatibility_rules
GROUP BY package_name;

-- ============================================================================
-- Triggers (Optional - for automatic timestamp updates)
-- ============================================================================

-- Trigger: update_packages_timestamp
-- Automatically updates updated_at when a package is modified
CREATE TRIGGER IF NOT EXISTS update_packages_timestamp
AFTER UPDATE ON packages
FOR EACH ROW
BEGIN
    UPDATE packages SET updated_at = CURRENT_TIMESTAMP WHERE uid = NEW.uid;
END;

-- ============================================================================
-- Sample Data Queries (for testing)
-- ============================================================================

-- Query: Get all packages with version count
-- SELECT p.name, COUNT(pv.uid) as version_count
-- FROM packages p
-- LEFT JOIN package_versions pv ON p.uid = pv.package_uid
-- GROUP BY p.uid, p.name
-- ORDER BY version_count DESC;

-- Query: Get compatibility rules for a specific package
-- SELECT * FROM compatibility_rules
-- WHERE package_name = 'torch'
-- ORDER BY severity DESC;

-- Query: Get stable stacks with package count
-- SELECT s.name, s.cuda_version, COUNT(sp.uid) as package_count
-- FROM stable_stacks s
-- LEFT JOIN stable_stack_packages sp ON s.uid = sp.stack_uid
-- GROUP BY s.uid, s.name, s.cuda_version;

-- ============================================================================
-- Database Metadata
-- ============================================================================

-- Schema Version: 1.0.0
-- Created: 2026-05-16
-- Description: Initial schema for env-doctor Phase 2
-- Tables: 8 core tables
-- Indexes: 10 indexes for query optimization
-- Views: 2 convenience views
-- Triggers: 1 timestamp update trigger

-- Made with Bob
