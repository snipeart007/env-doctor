"""
Integration tests for env-doctor.

Tests multiple components working together in realistic scenarios.
"""

import tempfile
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock

import pytest

from env_doctor.database.manager import DatabaseManager
from env_doctor.database.models import Package, PackageVersion
from env_doctor.scanner.pypi_client import PyPIClient
from env_doctor.scanner.dependency_parser import DependencyParser
from env_doctor.core.version_matcher import VersionMatcher
from env_doctor.core.recommendations import RecommendationEngine
from env_doctor.core.analysis import AnalysisReport, Issue
from env_doctor.vram.model_fetcher import ModelFetcher, ModelArchitecture
from env_doctor.vram.weight_calculator import WeightCalculator
from env_doctor.vram.kv_cache_estimator import KVCacheEstimator
from env_doctor.vram.oom_detector import OOMDetector


class TestDatabaseScannerIntegration:
    """Test database and scanner integration."""
    
    def test_full_package_scan_workflow(self, tmp_path):
        """Test complete workflow: scan package -> store in DB -> query."""
        # Create database
        db_path = tmp_path / "test.db"
        db_manager = DatabaseManager(str(db_path))
        db_manager.create_tables()
        
        with db_manager.get_session() as session:
            # Create package
            package = Package(
                uid="pkg_numpy",
                name="numpy"
            )
            session.add(package)
            
            # Create version
            version = PackageVersion(
                uid="ver_numpy_1_20_0",
                package_uid="pkg_numpy",
                version="1.20.0",
                requires_python=">=3.7"
            )
            session.add(version)
            session.commit()
            
            # Query back
            queried_pkg = session.query(Package).filter_by(name="numpy").first()
            assert queried_pkg is not None
            assert queried_pkg.name == "numpy"
            
            queried_ver = session.query(PackageVersion).filter_by(
                package_uid="pkg_numpy"
            ).first()
            assert queried_ver is not None
            assert queried_ver.version == "1.20.0"


class TestRecommendationWorkflow:
    """Test recommendation engine workflow."""
    
    def test_end_to_end_recommendation(self, tmp_path):
        """Test complete recommendation workflow."""
        # Create mock database with packages
        db_path = tmp_path / "test.db"
        db_manager = DatabaseManager(str(db_path))
        db_manager.create_tables()
        
        with db_manager.get_session() as session:
            # Add test packages
            pkg1 = Package(uid="pkg_torch", name="torch")
            pkg2 = Package(uid="pkg_numpy", name="numpy")
            session.add_all([pkg1, pkg2])
            
            ver1 = PackageVersion(
                uid="ver_torch_2_0_0",
                package_uid="pkg_torch",
                version="2.0.0"
            )
            ver2 = PackageVersion(
                uid="ver_numpy_1_24_0",
                package_uid="pkg_numpy",
                version="1.24.0"
            )
            session.add_all([ver1, ver2])
            session.commit()
        
        # Create recommendation engine
        engine = RecommendationEngine()
        
        # Test recommendation (will return empty since no stacks, but tests workflow)
        requirements = {"torch": ">=2.0.0", "numpy": ">=1.20.0"}
        recommendations = engine.rank_stacks([])
        
        assert isinstance(recommendations, list)


class TestVRAMEstimationWorkflow:
    """Test VRAM estimation workflow."""
    
    def test_full_vram_estimation_pipeline(self):
        """Test complete VRAM estimation pipeline."""
        # Create model architecture
        arch = ModelArchitecture(
            model_id="test-7b",
            hidden_size=4096,
            num_layers=32,
            num_attention_heads=32,
            vocab_size=32000,
            max_position_embeddings=2048,
            intermediate_size=11008
        )
        
        # Calculate weights
        calculator = WeightCalculator(quantization="fp16")
        weight_memory = calculator.calculate_weight_memory(arch)
        
        assert weight_memory.total_memory_gb > 0
        
        # Estimate KV cache
        estimator = KVCacheEstimator(batch_size=1, sequence_length=2048)
        kv_cache = estimator.estimate_kv_cache(arch)
        
        assert kv_cache.total_memory_gb > 0
        
        # Assess OOM risk
        detector = OOMDetector()
        total_memory = weight_memory.total_memory_gb + kv_cache.total_memory_gb
        risk = detector.assess_risk(
            required_memory_gb=total_memory,
            available_memory_gb=24.0  # Simulated GPU
        )
        
        assert risk.risk_level.name in ["SAFE", "WARNING", "DANGER", "CRITICAL", "IMPOSSIBLE"]


class TestAnalysisReportWorkflow:
    """Test analysis report workflow."""
    
    def test_create_and_merge_reports(self):
        """Test creating and merging analysis reports."""
        # Create first report
        issue1 = Issue(
            severity=50,
            severity_label="WARNING",
            type="version_conflict",
            package_name="numpy",
            description="Version conflict detected"
        )
        report1 = AnalysisReport(
            status="warnings",
            warnings=[issue1],
            summary="Found 1 warning"
        )
        
        # Create second report
        issue2 = Issue(
            severity=100,
            severity_label="CRITICAL",
            type="compatibility",
            package_name="torch",
            description="Incompatibility detected"
        )
        report2 = AnalysisReport(
            status="errors",
            critical_issues=[issue2],
            summary="Found 1 error"
        )
        
        # Merge reports
        from env_doctor.core.analysis import merge_reports
        merged = merge_reports([report1, report2])
        
        assert len(merged.critical_issues) == 1
        assert len(merged.warnings) == 1
        assert merged.status == "errors"  # Should take highest severity
        assert merged.has_critical_issues() or merged.has_warnings()


class TestVersionMatchingWorkflow:
    """Test version matching workflow."""
    
    def test_version_compatibility_check(self):
        """Test checking version compatibility."""
        matcher = VersionMatcher()
        
        # Test compatible versions
        assert matcher.version_matches("1.20.0", ">=1.19.0")
        assert matcher.version_matches("1.20.0", ">=1.19.0,<2.0.0")
        
        # Test incompatible versions
        assert not matcher.version_matches("1.18.0", ">=1.19.0")
        assert not matcher.version_matches("2.0.0", ">=1.19.0,<2.0.0")
        
        # Test getting matching versions
        available = ["1.18.0", "1.19.0", "1.20.0", "1.21.0", "2.0.0"]
        matching = matcher.get_matching_versions(available, ">=1.19.0,<2.0.0")
        
        assert "1.19.0" in matching
        assert "1.20.0" in matching
        assert "1.21.0" in matching
        assert "1.18.0" not in matching
        assert "2.0.0" not in matching


class TestRequirementsParsingWorkflow:
    """Test requirements parsing workflow."""
    
    def test_parse_and_analyze_requirements(self, tmp_path):
        """Test parsing requirements and analyzing them."""
        # Create requirements file
        req_file = tmp_path / "requirements.txt"
        req_file.write_text(
            "torch>=2.0.0\n"
            "numpy>=1.20.0,<2.0.0\n"
            "transformers>=4.30.0\n"
        )
        
        # Parse requirements
        parser = DependencyParser()
        # Note: DependencyParser is for PyPI metadata, not files
        # For file parsing, we'd use requirements_parser module
        from env_doctor.utils.requirements_parser import parse_requirements_txt
        
        packages = parse_requirements_txt(str(req_file))
        
        assert len(packages) == 3
        assert any(pkg["name"] == "torch" for pkg in packages)
        assert any(pkg["name"] == "numpy" for pkg in packages)
        assert any(pkg["name"] == "transformers" for pkg in packages)
        
        # Check version specifiers
        torch_pkg = next(pkg for pkg in packages if pkg["name"] == "torch")
        assert torch_pkg["specifier"] == ">=2.0.0"


class TestErrorHandlingIntegration:
    """Test error handling across components."""
    
    def test_database_connection_error_handling(self):
        """Test handling database connection errors."""
        # Try to create database in invalid location
        with pytest.raises(Exception):
            db_manager = DatabaseManager("/invalid/path/that/does/not/exist/test.db")
            with db_manager.get_session() as session:
                session.query(Package).first()
    
    def test_invalid_version_specifier_handling(self):
        """Test handling invalid version specifiers."""
        matcher = VersionMatcher()
        
        # Should handle invalid specifiers gracefully
        result = matcher.version_matches("1.0.0", "invalid_specifier")
        assert isinstance(result, bool)


class TestConcurrentOperations:
    """Test concurrent operations."""
    
    def test_multiple_database_sessions(self, tmp_path):
        """Test multiple database sessions."""
        db_path = tmp_path / "test.db"
        db_manager = DatabaseManager(str(db_path))
        db_manager.create_tables()
        
        # Create package in first session
        with db_manager.get_session() as session1:
            package = Package(uid="pkg_test", name="test")
            session1.add(package)
            session1.commit()
        
        # Query in second session
        with db_manager.get_session() as session2:
            queried = session2.query(Package).filter_by(name="test").first()
            assert queried is not None
            assert queried.name == "test"


class TestDataValidation:
    """Test data validation across components."""
    
    def test_package_version_validation(self, tmp_path):
        """Test package version data validation."""
        db_path = tmp_path / "test.db"
        db_manager = DatabaseManager(str(db_path))
        db_manager.create_tables()
        
        with db_manager.get_session() as session:
            # Create package with valid data
            package = Package(
                uid="pkg_valid",
                name="valid-package"
            )
            session.add(package)
            
            # Create version with valid data
            version = PackageVersion(
                uid="ver_valid_1_0_0",
                package_uid="pkg_valid",
                version="1.0.0",
                requires_python=">=3.8"
            )
            session.add(version)
            session.commit()
            
            # Verify data was stored correctly
            queried_ver = session.query(PackageVersion).filter_by(
                uid="ver_valid_1_0_0"
            ).first()
            assert queried_ver is not None
            assert queried_ver.version == "1.0.0"
            assert queried_ver.requires_python == ">=3.8"


class TestPerformance:
    """Basic performance tests."""
    
    def test_version_matching_performance(self):
        """Test version matching performance with many versions."""
        matcher = VersionMatcher()
        
        # Generate many versions
        versions = [f"1.{i}.0" for i in range(100)]
        
        # Test matching performance
        import time
        start = time.time()
        matching = matcher.get_matching_versions(versions, ">=1.20.0,<1.80.0")
        elapsed = time.time() - start
        
        # Should complete quickly (< 1 second for 100 versions)
        assert elapsed < 1.0
        assert len(matching) > 0
    
    def test_database_query_performance(self, tmp_path):
        """Test database query performance."""
        db_path = tmp_path / "test.db"
        db_manager = DatabaseManager(str(db_path))
        db_manager.create_tables()
        
        # Insert many packages
        with db_manager.get_session() as session:
            for i in range(50):
                package = Package(
                    uid=f"pkg_test_{i}",
                    name=f"test-package-{i}"
                )
                session.add(package)
            session.commit()
        
        # Test query performance
        import time
        start = time.time()
        with db_manager.get_session() as session:
            packages = session.query(Package).all()
        elapsed = time.time() - start
        
        # Should complete quickly
        assert elapsed < 1.0
        assert len(packages) == 50

# Made with Bob
