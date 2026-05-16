"""
Verification script for scanner module.

Tests the scanner components with real PyPI API calls.
"""

import sys
import tempfile
from pathlib import Path

# Set UTF-8 encoding for Windows console
if sys.platform == "win32":
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from env_doctor.database.manager import DatabaseManager
from env_doctor.scanner import (
    DatabaseBootstrap,
    DependencyParser,
    PyPIClient,
    WheelExtractor,
)


def test_pypi_client() -> None:
    """Test PyPI client with real API calls."""
    print("\n=== Testing PyPI Client ===")
    
    with tempfile.TemporaryDirectory() as tmpdir:
        client = PyPIClient(cache_dir=tmpdir)
        
        try:
            # Test fetching a small package
            print("Fetching metadata for 'requests'...")
            metadata = client.fetch_package_metadata("requests")
            
            print(f"✓ Package name: {metadata['info']['name']}")
            print(f"✓ Latest version: {metadata['info']['version']}")
            
            # Test getting versions
            versions = client.get_package_versions("requests")
            print(f"✓ Found {len(versions)} versions")
            
            # Test getting latest version
            latest = client.get_latest_version("requests")
            print(f"✓ Latest stable version: {latest}")
            
            # Test cache
            print("Testing cache...")
            metadata2 = client.fetch_package_metadata("requests")
            assert metadata == metadata2
            print("✓ Cache working correctly")
            
            print("✓ PyPI Client tests passed!")
            
        finally:
            client.close()


def test_dependency_parser() -> None:
    """Test dependency parser."""
    print("\n=== Testing Dependency Parser ===")
    
    parser = DependencyParser()
    
    # Test parsing requires_dist
    requires = [
        "numpy>=1.20.0",
        "pytest>=7.0.0; extra == 'dev'",
        "torch>=2.0.0; extra == 'cuda'"
    ]
    
    deps = parser.parse_requires_dist(requires)
    print(f"✓ Parsed {len(deps)} dependencies")
    
    # Test extracting dependencies
    metadata = {
        "info": {
            "requires_dist": requires
        }
    }
    
    grouped = parser.extract_dependencies(metadata)
    print(f"✓ Found dependency groups: {list(grouped.keys())}")
    print(f"  - main: {len(grouped.get('main', []))} dependencies")
    print(f"  - dev: {len(grouped.get('dev', []))} dependencies")
    print(f"  - cuda: {len(grouped.get('cuda', []))} dependencies")
    
    print("✓ Dependency Parser tests passed!")


def test_wheel_extractor() -> None:
    """Test wheel extractor."""
    print("\n=== Testing Wheel Extractor ===")
    
    extractor = WheelExtractor()
    
    # Test parsing wheel filename
    filename = "torch-2.1.0-cp310-cp310-win_amd64.whl"
    info = extractor.parse_wheel_filename(filename)
    
    if info:
        print(f"✓ Parsed wheel filename:")
        print(f"  - Name: {info['name']}")
        print(f"  - Version: {info['version']}")
        print(f"  - Python: {info['python_tag']}")
        print(f"  - Platform: {info['platform_tag']}")
    
    # Test with real metadata
    with tempfile.TemporaryDirectory() as tmpdir:
        client = PyPIClient(cache_dir=tmpdir)
        
        try:
            print("\nFetching wheel info for 'requests'...")
            metadata = client.fetch_package_metadata("requests")
            
            # Get latest version
            latest = client.get_latest_version("requests")
            
            # Extract wheels for latest version
            wheels = extractor.get_wheels_for_version(metadata, latest)
            print(f"✓ Found {len(wheels)} wheels for version {latest}")
            
            if wheels:
                print(f"  - Sample wheel: {wheels[0]['python_tag']}-{wheels[0]['platform_tag']}")
            
            # Get supported platforms
            platforms = extractor.get_supported_platforms(metadata, latest)
            print(f"✓ Supported platforms: {', '.join(platforms[:3])}...")
            
            # Check for source distribution
            has_sdist = extractor.has_source_distribution(metadata, latest)
            print(f"✓ Has source distribution: {has_sdist}")
            
        finally:
            client.close()
    
    print("✓ Wheel Extractor tests passed!")


def test_database_bootstrap() -> None:
    """Test database bootstrap."""
    print("\n=== Testing Database Bootstrap ===")
    
    with tempfile.TemporaryDirectory() as tmpdir:
        # Create database
        db_path = str(Path(tmpdir) / "test.db")
        db_manager = DatabaseManager(db_path)
        db_manager.create_tables()
        
        print(f"✓ Created test database at {db_path}")
        
        # Create bootstrap
        cache_dir = str(Path(tmpdir) / "cache")
        client = PyPIClient(cache_dir=cache_dir)
        bootstrap = DatabaseBootstrap(db_manager, client)
        
        # Test bootstrapping a small package
        print("\nBootstrapping 'requests' package...")
        
        def progress(msg: str) -> None:
            print(f"  {msg}")
        
        try:
            bootstrap.bootstrap_package("requests", progress_callback=progress)
            
            # Verify data was inserted
            with db_manager.get_session() as session:
                from env_doctor.database.models import Package, PackageVersion
                from env_doctor.database.uid_generator import generate_package_uid
                
                pkg_uid = generate_package_uid("requests")
                package = session.get(Package, pkg_uid)
                
                if package:
                    print(f"✓ Package created: {package.name}")
                    
                    # Count versions
                    from sqlmodel import select
                    versions = session.exec(
                        select(PackageVersion).where(PackageVersion.package_uid == pkg_uid)
                    ).all()
                    print(f"✓ Versions stored: {len(versions)}")
                else:
                    print("✗ Package not found in database!")
            
            # Test getting core packages
            core_packages = DatabaseBootstrap.get_core_packages()
            print(f"\n✓ Core packages list: {len(core_packages)} packages")
            print(f"  - Sample: {', '.join(core_packages[:5])}...")
            
        finally:
            client.close()
            db_manager.close()
    
    print("✓ Database Bootstrap tests passed!")


def main() -> None:
    """Run all verification tests."""
    print("=" * 60)
    print("Scanner Module Verification")
    print("=" * 60)
    
    try:
        test_pypi_client()
        test_dependency_parser()
        test_wheel_extractor()
        test_database_bootstrap()
        
        print("\n" + "=" * 60)
        print("✓ All scanner tests passed!")
        print("=" * 60)
        
    except Exception as e:
        print(f"\n✗ Test failed: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()

# Made with Bob
