"""
Tests for scanner module.

Tests PyPI client, dependency parser, wheel extractor, and bootstrap functionality.
"""

import json
import tempfile
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from env_doctor.database.manager import DatabaseManager
from env_doctor.scanner import (
    DatabaseBootstrap,
    DependencyParser,
    PyPIClient,
    WheelExtractor,
)


class TestPyPIClient:
    """Tests for PyPIClient."""
    
    def test_init_default_cache(self) -> None:
        """Test client initialization with default cache directory."""
        client = PyPIClient()
        assert client.cache_dir.exists()
        assert "pypi" in str(client.cache_dir)
        client.close()
    
    def test_init_custom_cache(self) -> None:
        """Test client initialization with custom cache directory."""
        with tempfile.TemporaryDirectory() as tmpdir:
            client = PyPIClient(cache_dir=tmpdir)
            assert client.cache_dir == Path(tmpdir)
            client.close()
    
    def test_cache_path_normalization(self) -> None:
        """Test package name normalization in cache paths."""
        with tempfile.TemporaryDirectory() as tmpdir:
            client = PyPIClient(cache_dir=tmpdir)
            
            # Test case normalization
            path1 = client._get_cache_path("PyTorch")
            path2 = client._get_cache_path("pytorch")
            assert path1 == path2
            
            # Test underscore to dash conversion
            path3 = client._get_cache_path("my_package")
            path4 = client._get_cache_path("my-package")
            assert path3 == path4
            
            client.close()
    
    def test_cache_write_and_read(self) -> None:
        """Test cache writing and reading."""
        with tempfile.TemporaryDirectory() as tmpdir:
            client = PyPIClient(cache_dir=tmpdir, cache_ttl=3600)
            cache_path = client._get_cache_path("test-package")
            
            # Write cache
            metadata = {"info": {"name": "test-package", "version": "1.0.0"}}
            client._write_cache(cache_path, metadata)
            
            # Verify cache file exists
            assert cache_path.exists()
            
            # Read cache
            cached_data = client._read_cache(cache_path)
            assert cached_data == metadata
            
            client.close()
    
    def test_cache_validity(self) -> None:
        """Test cache validity checking."""
        with tempfile.TemporaryDirectory() as tmpdir:
            client = PyPIClient(cache_dir=tmpdir, cache_ttl=1)  # 1 second TTL
            cache_path = client._get_cache_path("test-package")
            
            # Write cache
            metadata = {"info": {"name": "test-package"}}
            client._write_cache(cache_path, metadata)
            
            # Should be valid immediately
            assert client._is_cache_valid(cache_path)
            
            # Manually modify cache to be expired
            with open(cache_path, "r") as f:
                cache_data = json.load(f)
            
            # Set cached_at to 2 seconds ago
            old_time = datetime.utcnow() - timedelta(seconds=2)
            cache_data["cached_at"] = old_time.isoformat()
            
            with open(cache_path, "w") as f:
                json.dump(cache_data, f)
            
            # Should be invalid now
            assert not client._is_cache_valid(cache_path)
            
            client.close()
    
    def test_clear_cache_specific(self) -> None:
        """Test clearing cache for specific package."""
        with tempfile.TemporaryDirectory() as tmpdir:
            client = PyPIClient(cache_dir=tmpdir)
            
            # Create cache for two packages
            path1 = client._get_cache_path("package1")
            path2 = client._get_cache_path("package2")
            
            client._write_cache(path1, {"info": {"name": "package1"}})
            client._write_cache(path2, {"info": {"name": "package2"}})
            
            assert path1.exists()
            assert path2.exists()
            
            # Clear cache for package1
            client.clear_cache("package1")
            
            assert not path1.exists()
            assert path2.exists()
            
            client.close()
    
    def test_clear_cache_all(self) -> None:
        """Test clearing all cache."""
        with tempfile.TemporaryDirectory() as tmpdir:
            client = PyPIClient(cache_dir=tmpdir)
            
            # Create cache for two packages
            path1 = client._get_cache_path("package1")
            path2 = client._get_cache_path("package2")
            
            client._write_cache(path1, {"info": {"name": "package1"}})
            client._write_cache(path2, {"info": {"name": "package2"}})
            
            # Clear all cache
            client.clear_cache()
            
            assert not path1.exists()
            assert not path2.exists()
            
            client.close()
    
    @patch("httpx.Client.get")
    def test_fetch_package_metadata_success(self, mock_get: MagicMock) -> None:
        """Test successful package metadata fetch."""
        with tempfile.TemporaryDirectory() as tmpdir:
            client = PyPIClient(cache_dir=tmpdir)
            
            # Mock response
            mock_response = MagicMock()
            mock_response.json.return_value = {
                "info": {"name": "test-package", "version": "1.0.0"}
            }
            mock_get.return_value = mock_response
            
            # Fetch metadata
            metadata = client.fetch_package_metadata("test-package", use_cache=False)
            
            assert metadata["info"]["name"] == "test-package"
            assert metadata["info"]["version"] == "1.0.0"
            
            client.close()
    
    @patch("httpx.Client.get")
    def test_get_package_versions(self, mock_get: MagicMock) -> None:
        """Test getting package versions."""
        with tempfile.TemporaryDirectory() as tmpdir:
            client = PyPIClient(cache_dir=tmpdir)
            
            # Mock response
            mock_response = MagicMock()
            mock_response.json.return_value = {
                "releases": {
                    "1.0.0": [{"filename": "pkg-1.0.0.tar.gz"}],
                    "1.1.0": [{"filename": "pkg-1.1.0.tar.gz"}],
                    "2.0.0": [{"filename": "pkg-2.0.0.tar.gz"}]
                }
            }
            mock_get.return_value = mock_response
            
            versions = client.get_package_versions("test-package")
            
            assert len(versions) == 3
            assert "1.0.0" in versions
            assert "2.0.0" in versions
            
            client.close()
    
    @patch("httpx.Client.get")
    def test_get_latest_version(self, mock_get: MagicMock) -> None:
        """Test getting latest version."""
        with tempfile.TemporaryDirectory() as tmpdir:
            client = PyPIClient(cache_dir=tmpdir)
            
            # Mock response
            mock_response = MagicMock()
            mock_response.json.return_value = {
                "info": {"version": "2.1.0"},
                "releases": {}
            }
            mock_get.return_value = mock_response
            
            latest = client.get_latest_version("test-package")
            
            assert latest == "2.1.0"
            
            client.close()


class TestDependencyParser:
    """Tests for DependencyParser."""
    
    def test_parse_requires_dist_simple(self) -> None:
        """Test parsing simple requirements."""
        parser = DependencyParser()
        requires = [
            "numpy>=1.20.0",
            "torch>=2.0.0",
        ]
        
        deps = parser.parse_requires_dist(requires)
        
        assert len(deps) == 2
        assert deps[0]["name"] == "numpy"
        assert deps[0]["specifier"] == ">=1.20.0"
        assert deps[1]["name"] == "torch"
    
    def test_parse_requires_dist_with_extras(self) -> None:
        """Test parsing requirements with extras."""
        parser = DependencyParser()
        requires = [
            "numpy>=1.20.0",
            "pytest>=7.0.0; extra == 'dev'",
            "torch>=2.0.0; extra == 'cuda'"
        ]
        
        deps = parser.parse_requires_dist(requires)
        
        assert len(deps) == 3
        
        # Check main dependency
        numpy_dep = next(d for d in deps if d["name"] == "numpy")
        assert numpy_dep["extra_group"] is None
        
        # Check dev dependency
        pytest_dep = next(d for d in deps if d["name"] == "pytest")
        assert pytest_dep["extra_group"] == "dev"
        
        # Check cuda dependency
        torch_dep = next(d for d in deps if d["name"] == "torch")
        assert torch_dep["extra_group"] == "cuda"
    
    def test_parse_requires_python(self) -> None:
        """Test parsing Python version requirements."""
        parser = DependencyParser()
        
        assert parser.parse_requires_python(">=3.8") == ">=3.8"
        # SpecifierSet normalizes the order, so accept either order
        result = parser.parse_requires_python(">=3.8,<4.0")
        assert result in [">=3.8,<4.0", "<4.0,>=3.8"]
        assert parser.parse_requires_python(None) == ""
    
    def test_extract_dependencies(self) -> None:
        """Test extracting dependencies from metadata."""
        parser = DependencyParser()
        metadata = {
            "info": {
                "requires_dist": [
                    "numpy>=1.20.0",
                    "pytest>=7.0.0; extra == 'dev'",
                    "torch>=2.0.0; extra == 'cuda'"
                ]
            }
        }
        
        deps = parser.extract_dependencies(metadata)
        
        assert "main" in deps
        assert "dev" in deps
        assert "cuda" in deps
        
        assert len(deps["main"]) == 1
        assert deps["main"][0]["name"] == "numpy"
        
        assert len(deps["dev"]) == 1
        assert deps["dev"][0]["name"] == "pytest"
        
        assert len(deps["cuda"]) == 1
        assert deps["cuda"][0]["name"] == "torch"
    
    def test_get_runtime_dependencies(self) -> None:
        """Test getting runtime dependencies."""
        parser = DependencyParser()
        metadata = {
            "info": {
                "requires_dist": [
                    "numpy>=1.20.0",
                    "pytest>=7.0.0; extra == 'dev'",
                    "torch>=2.0.0; extra == 'cuda'"
                ]
            }
        }
        
        # Get main dependencies only
        runtime_deps = parser.get_runtime_dependencies(metadata)
        assert len(runtime_deps) == 1
        assert runtime_deps[0]["name"] == "numpy"
        
        # Get main + cuda dependencies
        runtime_deps = parser.get_runtime_dependencies(metadata, include_extras=["cuda"])
        assert len(runtime_deps) == 2
        names = [d["name"] for d in runtime_deps]
        assert "numpy" in names
        assert "torch" in names


class TestWheelExtractor:
    """Tests for WheelExtractor."""
    
    def test_parse_wheel_filename(self) -> None:
        """Test parsing wheel filenames."""
        extractor = WheelExtractor()
        
        # Test valid wheel
        info = extractor.parse_wheel_filename("torch-2.1.0-cp310-cp310-win_amd64.whl")
        assert info is not None
        assert info["name"] == "torch"
        assert info["version"] == "2.1.0"
        assert info["python_tag"] == "cp310"
        assert info["abi_tag"] == "cp310"
        assert info["platform_tag"] == "win_amd64"
        
        # Test non-wheel file
        info = extractor.parse_wheel_filename("torch-2.1.0.tar.gz")
        assert info is None
    
    def test_extract_wheel_info(self) -> None:
        """Test extracting wheel info from metadata."""
        extractor = WheelExtractor()
        metadata = {
            "releases": {
                "2.1.0": [
                    {
                        "filename": "torch-2.1.0-cp310-cp310-win_amd64.whl",
                        "packagetype": "bdist_wheel"
                    },
                    {
                        "filename": "torch-2.1.0-cp311-cp311-win_amd64.whl",
                        "packagetype": "bdist_wheel"
                    },
                    {
                        "filename": "torch-2.1.0.tar.gz",
                        "packagetype": "sdist"
                    }
                ]
            }
        }
        
        wheels = extractor.extract_wheel_info(metadata)
        
        assert len(wheels) == 2  # Only wheels, not sdist
        assert all(w["version"] == "2.1.0" for w in wheels)
        assert all(w["available"] for w in wheels)
    
    def test_get_wheels_for_version(self) -> None:
        """Test getting wheels for specific version."""
        extractor = WheelExtractor()
        metadata = {
            "releases": {
                "2.0.0": [
                    {
                        "filename": "pkg-2.0.0-cp310-cp310-win_amd64.whl",
                        "packagetype": "bdist_wheel"
                    }
                ],
                "2.1.0": [
                    {
                        "filename": "pkg-2.1.0-cp310-cp310-win_amd64.whl",
                        "packagetype": "bdist_wheel"
                    }
                ]
            }
        }
        
        wheels = extractor.get_wheels_for_version(metadata, "2.1.0")
        
        assert len(wheels) == 1
        assert wheels[0]["version"] == "2.1.0"
    
    def test_check_wheel_availability(self) -> None:
        """Test checking wheel availability."""
        extractor = WheelExtractor()
        metadata = {
            "releases": {
                "2.1.0": [
                    {
                        "filename": "pkg-2.1.0-cp310-cp310-win_amd64.whl",
                        "packagetype": "bdist_wheel"
                    },
                    {
                        "filename": "pkg-2.1.0-py3-none-any.whl",
                        "packagetype": "bdist_wheel"
                    }
                ]
            }
        }
        
        # Check exact match
        assert extractor.check_wheel_availability(metadata, "2.1.0", "3.10", "win_amd64")
        
        # Check universal wheel (py3-none-any matches any platform)
        assert extractor.check_wheel_availability(metadata, "2.1.0", "3.11", "any")
        
        # Universal wheel (py3-none-any) matches linux too
        assert extractor.check_wheel_availability(metadata, "2.1.0", "3.10", "linux_x86_64")
        
        # Check truly non-existent (no wheels at all for this version)
        assert not extractor.check_wheel_availability(metadata, "1.0.0", "3.10", "win_amd64")
    
    def test_get_supported_platforms(self) -> None:
        """Test getting supported platforms."""
        extractor = WheelExtractor()
        metadata = {
            "releases": {
                "2.1.0": [
                    {
                        "filename": "pkg-2.1.0-cp310-cp310-win_amd64.whl",
                        "packagetype": "bdist_wheel"
                    },
                    {
                        "filename": "pkg-2.1.0-cp310-cp310-manylinux2014_x86_64.whl",
                        "packagetype": "bdist_wheel"
                    }
                ]
            }
        }
        
        platforms = extractor.get_supported_platforms(metadata, "2.1.0")
        
        assert len(platforms) == 2
        assert "win_amd64" in platforms
        assert "manylinux2014_x86_64" in platforms
    
    def test_has_source_distribution(self) -> None:
        """Test checking for source distribution."""
        extractor = WheelExtractor()
        
        # With sdist
        metadata_with_sdist = {
            "releases": {
                "2.1.0": [
                    {
                        "filename": "pkg-2.1.0.tar.gz",
                        "packagetype": "sdist"
                    }
                ]
            }
        }
        assert extractor.has_source_distribution(metadata_with_sdist, "2.1.0")
        
        # Without sdist
        metadata_without_sdist = {
            "releases": {
                "2.1.0": [
                    {
                        "filename": "pkg-2.1.0-cp310-cp310-win_amd64.whl",
                        "packagetype": "bdist_wheel"
                    }
                ]
            }
        }
        assert not extractor.has_source_distribution(metadata_without_sdist, "2.1.0")


class TestDatabaseBootstrap:
    """Tests for DatabaseBootstrap."""
    
    def test_get_core_packages(self) -> None:
        """Test getting core packages list."""
        packages = DatabaseBootstrap.get_core_packages()
        
        assert isinstance(packages, list)
        assert len(packages) > 0
        assert "torch" in packages
        assert "transformers" in packages
        assert "accelerate" in packages
    
    @patch.object(PyPIClient, "fetch_package_metadata")
    def test_bootstrap_package(self, mock_fetch: MagicMock) -> None:
        """Test bootstrapping a single package."""
        # Create temporary database
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = str(Path(tmpdir) / "test.db")
            db_manager = DatabaseManager(db_path)
            db_manager.create_tables()
            
            # Mock PyPI response
            mock_fetch.return_value = {
                "info": {
                    "name": "test-package",
                    "version": "1.0.0",
                    "requires_python": ">=3.8",
                    "requires_dist": ["numpy>=1.20.0"]
                },
                "releases": {
                    "1.0.0": [
                        {
                            "filename": "test-package-1.0.0-py3-none-any.whl",
                            "packagetype": "bdist_wheel",
                            "upload_time_iso_8601": "2024-01-01T00:00:00Z"
                        }
                    ]
                }
            }
            
            # Bootstrap package
            bootstrap = DatabaseBootstrap(db_manager)
            bootstrap.bootstrap_package("test-package")
            
            # Verify package was created
            with db_manager.get_session() as session:
                from env_doctor.database.models import Package
                from env_doctor.database.uid_generator import generate_package_uid
                
                pkg_uid = generate_package_uid("test-package")
                package = session.get(Package, pkg_uid)
                
                assert package is not None
                assert package.name == "test-package"
            
            db_manager.close()


# Made with Bob