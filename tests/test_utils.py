"""
Tests for utility modules (config and requirements_parser).
"""

import json
import tempfile
from pathlib import Path
from typing import Any, Dict

import pytest

from env_doctor.utils.config import (
    Config,
    get_default_config,
    load_config,
    save_config,
    get_cache_dir,
    get_db_path,
)
from env_doctor.utils.requirements_parser import (
    parse_requirements_txt,
    parse_pyproject_toml,
    normalize_package_name,
    parse_version_specifier,
    detect_file_type,
    parse_requirements_file,
    group_packages_by_name,
)


class TestRequirementsParser:
    """Test requirements parser functions."""
    
    def test_parse_requirements_txt_valid(self, tmp_path):
        """Test parsing valid requirements.txt."""
        req_file = tmp_path / "requirements.txt"
        req_file.write_text(
            "numpy>=1.20.0\n"
            "pandas>=1.3.0\n"
            "# Comment line\n"
            "requests[security]>=2.28.0\n"
            "\n"
            "matplotlib>=3.5.0\n"
        )
        
        packages = parse_requirements_txt(str(req_file))
        
        assert len(packages) == 4
        assert packages[0]["name"] == "numpy"
        assert packages[0]["specifier"] == ">=1.20.0"
        assert packages[1]["name"] == "pandas"
        assert packages[2]["name"] == "requests"
        assert "security" in packages[2]["extras"]
    
    def test_parse_requirements_txt_nonexistent(self):
        """Test parsing non-existent file."""
        with pytest.raises(FileNotFoundError):
            parse_requirements_txt("/nonexistent/file.txt")
    
    def test_parse_requirements_txt_with_markers(self, tmp_path):
        """Test parsing requirements with markers."""
        req_file = tmp_path / "requirements.txt"
        req_file.write_text(
            "numpy>=1.20.0; python_version >= '3.8'\n"
        )
        
        packages = parse_requirements_txt(str(req_file))
        
        assert len(packages) == 1
        assert packages[0]["name"] == "numpy"
        assert packages[0]["marker"] is not None
    
    def test_parse_requirements_txt_skip_urls(self, tmp_path):
        """Test that URLs are skipped."""
        req_file = tmp_path / "requirements.txt"
        req_file.write_text(
            "numpy>=1.20.0\n"
            "https://github.com/user/repo/archive/main.zip\n"
            "pandas>=1.3.0\n"
        )
        
        packages = parse_requirements_txt(str(req_file))
        
        assert len(packages) == 2
        assert packages[0]["name"] == "numpy"
        assert packages[1]["name"] == "pandas"
    
    def test_parse_requirements_txt_skip_options(self, tmp_path):
        """Test that pip options are skipped."""
        req_file = tmp_path / "requirements.txt"
        req_file.write_text(
            "-e git+https://github.com/user/repo.git#egg=package\n"
            "numpy>=1.20.0\n"
            "--index-url https://pypi.org/simple\n"
            "pandas>=1.3.0\n"
        )
        
        packages = parse_requirements_txt(str(req_file))
        
        assert len(packages) == 2
        assert packages[0]["name"] == "numpy"
        assert packages[1]["name"] == "pandas"


class TestParsePyprojectToml:
    """Test pyproject.toml parser."""
    
    def test_parse_pyproject_toml_valid(self, tmp_path):
        """Test parsing valid pyproject.toml."""
        pyproject = tmp_path / "pyproject.toml"
        pyproject.write_text(
            "[project]\n"
            "dependencies = [\n"
            '    "numpy>=1.20.0",\n'
            '    "pandas>=1.3.0",\n'
            "]\n"
        )
        
        packages = parse_pyproject_toml(str(pyproject))
        
        assert len(packages) >= 2
        names = [pkg["name"] for pkg in packages]
        assert "numpy" in names
        assert "pandas" in names
    
    def test_parse_pyproject_toml_with_optional_deps(self, tmp_path):
        """Test parsing pyproject.toml with optional dependencies."""
        pyproject = tmp_path / "pyproject.toml"
        pyproject.write_text(
            "[project]\n"
            "dependencies = [\n"
            '    "numpy>=1.20.0",\n'
            "]\n"
            "\n"
            "[project.optional-dependencies]\n"
            "dev = [\n"
            '    "pytest>=7.0.0",\n'
            '    "black>=22.0.0",\n'
            "]\n"
        )
        
        packages = parse_pyproject_toml(str(pyproject))
        
        assert len(packages) >= 3
        names = [pkg["name"] for pkg in packages]
        assert "numpy" in names
        assert "pytest" in names
        assert "black" in names
        
        # Check groups
        dev_packages = [pkg for pkg in packages if pkg.get("group") == "dev"]
        assert len(dev_packages) >= 2
    
    def test_parse_pyproject_toml_nonexistent(self):
        """Test parsing non-existent pyproject.toml."""
        with pytest.raises(FileNotFoundError):
            parse_pyproject_toml("/nonexistent/pyproject.toml")
    
    def test_parse_pyproject_toml_no_dependencies(self, tmp_path):
        """Test parsing pyproject.toml without dependencies."""
        pyproject = tmp_path / "pyproject.toml"
        pyproject.write_text(
            "[project]\n"
            'name = "test-project"\n'
            'version = "0.1.0"\n'
        )
        
        packages = parse_pyproject_toml(str(pyproject))
        assert packages == []
    
    def test_parse_pyproject_toml_poetry_format(self, tmp_path):
        """Test parsing Poetry-style pyproject.toml."""
        pyproject = tmp_path / "pyproject.toml"
        pyproject.write_text(
            "[tool.poetry.dependencies]\n"
            'python = "^3.8"\n'
            'numpy = "^1.20.0"\n'
            'pandas = {version = "^1.3.0"}\n'
        )
        
        packages = parse_pyproject_toml(str(pyproject))
        
        assert len(packages) >= 2
        names = [pkg["name"] for pkg in packages]
        assert "numpy" in names
        assert "pandas" in names


class TestNormalizePackageName:
    """Test package name normalization."""
    
    def test_normalize_simple_name(self):
        """Test normalizing simple package name."""
        assert normalize_package_name("numpy") == "numpy"
    
    def test_normalize_with_hyphens(self):
        """Test normalizing name with hyphens."""
        assert normalize_package_name("scikit-learn") == "scikit_learn"
    
    def test_normalize_with_underscores(self):
        """Test normalizing name with underscores."""
        assert normalize_package_name("scikit_learn") == "scikit_learn"
    
    def test_normalize_mixed_case(self):
        """Test normalizing mixed case name."""
        assert normalize_package_name("NumPy") == "numpy"
        assert normalize_package_name("Scikit-Learn") == "scikit_learn"
    
    def test_normalize_multiple_separators(self):
        """Test normalizing name with multiple separators."""
        assert normalize_package_name("my--package__name") == "my_package_name"


class TestParseVersionSpecifier:
    """Test version specifier parser."""
    
    def test_parse_simple_specifier(self):
        """Test parsing simple version specifier."""
        result = parse_version_specifier(">=1.20.0")
        
        assert result["raw"] == ">=1.20.0"
        assert ">=" in result["operators"]
        assert "1.20.0" in result["versions"]
        assert result["min_version"] == "1.20.0"
    
    def test_parse_range_specifier(self):
        """Test parsing range specifier."""
        result = parse_version_specifier(">=1.20.0,<2.0.0")
        
        assert result["raw"] == ">=1.20.0,<2.0.0"
        assert len(result["operators"]) == 2
        assert len(result["versions"]) == 2
        assert result["min_version"] is not None
        assert result["max_version"] is not None
    
    def test_parse_exact_version(self):
        """Test parsing exact version."""
        result = parse_version_specifier("==1.20.0")
        
        assert result["raw"] == "==1.20.0"
        assert "==" in result["operators"]
        assert result["min_version"] == "1.20.0"
        assert result["max_version"] == "1.20.0"
    
    def test_parse_empty_specifier(self):
        """Test parsing empty specifier."""
        result = parse_version_specifier("")
        
        assert result["raw"] == ""
        assert result["operators"] == []
        assert result["versions"] == []
        assert result["min_version"] is None
        assert result["max_version"] is None


class TestDetectFileType:
    """Test file type detection."""
    
    def test_detect_pyproject_toml(self):
        """Test detecting pyproject.toml."""
        assert detect_file_type("pyproject.toml") == "pyproject.toml"
        assert detect_file_type("/path/to/pyproject.toml") == "pyproject.toml"
    
    def test_detect_requirements_txt(self):
        """Test detecting requirements.txt."""
        assert detect_file_type("requirements.txt") == "requirements.txt"
        assert detect_file_type("requirements-dev.txt") == "requirements.txt"
        assert detect_file_type("requirements.in") == "requirements.txt"
    
    def test_detect_unknown_type(self):
        """Test detecting unknown file type."""
        assert detect_file_type("setup.py") == "unknown"
        assert detect_file_type("random.file") == "unknown"


class TestParseRequirementsFile:
    """Test auto-detect requirements file parser."""
    
    def test_parse_requirements_txt_auto(self, tmp_path):
        """Test auto-parsing requirements.txt."""
        req_file = tmp_path / "requirements.txt"
        req_file.write_text("numpy>=1.20.0\n")
        
        packages = parse_requirements_file(str(req_file))
        
        assert len(packages) >= 1
        assert packages[0]["name"] == "numpy"
    
    def test_parse_pyproject_toml_auto(self, tmp_path):
        """Test auto-parsing pyproject.toml."""
        pyproject = tmp_path / "pyproject.toml"
        pyproject.write_text(
            "[project]\n"
            'dependencies = ["numpy>=1.20.0"]\n'
        )
        
        packages = parse_requirements_file(str(pyproject))
        
        assert len(packages) >= 1
        assert packages[0]["name"] == "numpy"
    
    def test_parse_unsupported_file(self, tmp_path):
        """Test parsing unsupported file type."""
        setup_file = tmp_path / "setup.py"
        setup_file.write_text("# setup.py content")
        
        with pytest.raises(ValueError):
            parse_requirements_file(str(setup_file))


class TestGroupPackagesByName:
    """Test package grouping."""
    
    def test_group_unique_packages(self):
        """Test grouping unique packages."""
        packages = [
            {"name": "numpy", "specifier": ">=1.20.0"},
            {"name": "pandas", "specifier": ">=1.3.0"},
        ]
        
        grouped = group_packages_by_name(packages)
        
        assert len(grouped) == 2
        assert "numpy" in grouped
        assert "pandas" in grouped
    
    def test_group_duplicate_packages(self):
        """Test grouping duplicate packages."""
        packages = [
            {"name": "numpy", "specifier": ">=1.20.0"},
            {"name": "NumPy", "specifier": ">=1.21.0"},
            {"name": "pandas", "specifier": ">=1.3.0"},
        ]
        
        grouped = group_packages_by_name(packages)
        
        assert len(grouped) == 2
        assert len(grouped["numpy"]) == 2
        assert len(grouped["pandas"]) == 1


class TestConfig:
    """Test Config class."""
    
    def test_config_default_values(self):
        """Test config default values."""
        config = Config()
        
        assert config.auto_update is True
        assert config.cache_dir == "~/.cache/env-doctor"
        assert config.verbosity == "info"
    
    def test_config_custom_values(self):
        """Test config with custom values."""
        config = Config(
            auto_update=False,
            cache_dir="/custom/cache",
            verbosity="debug"
        )
        
        assert config.auto_update is False
        assert config.cache_dir == "/custom/cache"
        assert config.verbosity == "debug"
    
    def test_get_expanded_cache_dir(self):
        """Test getting expanded cache directory."""
        config = Config()
        cache_dir = config.get_expanded_cache_dir()
        
        assert isinstance(cache_dir, Path)
        assert "~" not in str(cache_dir)
    
    def test_get_expanded_db_path(self):
        """Test getting expanded database path."""
        config = Config()
        db_path = config.get_expanded_db_path()
        
        assert isinstance(db_path, Path)
        assert "~" not in str(db_path)
    
    def test_ensure_directories(self, tmp_path):
        """Test ensuring directories exist."""
        config = Config(
            cache_dir=str(tmp_path / "cache"),
            db_path=str(tmp_path / "db" / "test.db")
        )
        
        config.ensure_directories()
        
        assert (tmp_path / "cache").exists()
        assert (tmp_path / "db").exists()


class TestConfigFunctions:
    """Test config utility functions."""
    
    def test_get_default_config(self):
        """Test getting default config."""
        config = get_default_config()
        
        assert isinstance(config, Config)
        assert config.auto_update is True
    
    def test_load_config_no_file(self):
        """Test loading config when no file exists."""
        config = load_config()
        
        assert isinstance(config, Config)
        # Should return defaults
        assert config.auto_update is True
    
    def test_save_and_load_config(self, tmp_path, monkeypatch):
        """Test saving and loading config."""
        # Mock config path
        config_file = tmp_path / "config.toml"
        monkeypatch.setattr(
            "env_doctor.utils.config.Config.get_config_path",
            lambda: config_file
        )
        
        # Create and save config
        config = Config(auto_update=False, verbosity="debug")
        save_config(config)
        
        assert config_file.exists()
        
        # Load and verify
        loaded_config = load_config()
        assert loaded_config.auto_update is False
        assert loaded_config.verbosity == "debug"
    
    def test_get_cache_dir(self):
        """Test getting cache directory."""
        cache_dir = get_cache_dir()
        
        assert isinstance(cache_dir, Path)
    
    def test_get_db_path(self):
        """Test getting database path."""
        db_path = get_db_path()
        
        assert isinstance(db_path, Path)

# Made with Bob
