"""
Tests for recommendation engine.

Tests the scoring algorithms, migration path generation, and integration
with database queries.
"""

import pytest
from datetime import datetime, timedelta
from typing import Dict, List

from env_doctor.core.recommendations import (
    RecommendationEngine,
    MigrationPathGenerator,
    ScoredStack,
    MigrationStep,
    MigrationPlan,
)
from env_doctor.database.models import StableStack, StableStackPackage


# Test fixtures

@pytest.fixture
def sample_stack():
    """Create a sample stable stack for testing."""
    return StableStack(
        uid="test_stack_001",
        name="torch-2.1-transformers-4.38",
        cuda_version="12.1",
        python_version="3.10",
        confidence_level="production-tested",
        description="Production-tested PyTorch 2.1 with Transformers 4.38",
        created_at=datetime.utcnow() - timedelta(days=15)
    )


@pytest.fixture
def sample_packages():
    """Create sample packages for a stack."""
    return [
        StableStackPackage(
            uid="pkg_001",
            stack_uid="test_stack_001",
            package_name="torch",
            version="2.1.0",
            created_at=datetime.utcnow()
        ),
        StableStackPackage(
            uid="pkg_002",
            stack_uid="test_stack_001",
            package_name="transformers",
            version="4.38.0",
            created_at=datetime.utcnow()
        ),
        StableStackPackage(
            uid="pkg_003",
            stack_uid="test_stack_001",
            package_name="numpy",
            version="1.24.3",
            created_at=datetime.utcnow()
        ),
    ]


@pytest.fixture
def old_stack():
    """Create an old stack for recency testing."""
    return StableStack(
        uid="test_stack_002",
        name="old-stack",
        cuda_version="11.8",
        python_version="3.9",
        confidence_level="stable",
        description="Older stable stack",
        created_at=datetime.utcnow() - timedelta(days=400)
    )


@pytest.fixture
def experimental_stack():
    """Create an experimental stack for confidence testing."""
    return StableStack(
        uid="test_stack_003",
        name="experimental-stack",
        cuda_version="12.1",
        python_version="3.11",
        confidence_level="experimental",
        description="Experimental bleeding-edge stack",
        created_at=datetime.utcnow() - timedelta(days=5)
    )


# RecommendationEngine Tests

class TestRecommendationEngine:
    """Tests for RecommendationEngine class."""
    
    def test_confidence_score_production_tested(self, sample_stack, sample_packages):
        """Test confidence scoring for production-tested stacks."""
        engine = RecommendationEngine()
        scored = engine.score_stack(sample_stack, sample_packages)
        
        assert scored.confidence_score == 40.0
        assert "production-tested" in scored.explanation
    
    def test_confidence_score_stable(self, old_stack, sample_packages):
        """Test confidence scoring for stable stacks."""
        engine = RecommendationEngine()
        scored = engine.score_stack(old_stack, sample_packages)
        
        assert scored.confidence_score == 30.0
    
    def test_confidence_score_experimental(self, experimental_stack, sample_packages):
        """Test confidence scoring for experimental stacks."""
        engine = RecommendationEngine()
        scored = engine.score_stack(experimental_stack, sample_packages)
        
        assert scored.confidence_score == 10.0
    
    def test_overlap_score_full_match(self, sample_stack, sample_packages):
        """Test overlap scoring with full package match."""
        engine = RecommendationEngine()
        required = {"torch": ">=2.0", "transformers": ">=4.0", "numpy": ">=1.20"}
        
        scored = engine.score_stack(
            sample_stack, sample_packages, required_packages=required
        )
        
        assert scored.overlap_score == 30.0
        assert len(scored.matching_packages) == 3
        assert len(scored.missing_packages) == 0
    
    def test_overlap_score_partial_match(self, sample_stack, sample_packages):
        """Test overlap scoring with partial package match."""
        engine = RecommendationEngine()
        required = {
            "torch": ">=2.0",
            "transformers": ">=4.0",
            "scipy": ">=1.0",  # Not in stack
            "pandas": ">=2.0"  # Not in stack
        }
        
        scored = engine.score_stack(
            sample_stack, sample_packages, required_packages=required
        )
        
        # 2 out of 4 packages matched = 50% = 15 points
        assert scored.overlap_score == 15.0
        assert len(scored.matching_packages) == 2
        assert len(scored.missing_packages) == 2
        assert "scipy" in scored.missing_packages
        assert "pandas" in scored.missing_packages
    
    def test_overlap_score_no_requirements(self, sample_stack, sample_packages):
        """Test overlap scoring with no requirements specified."""
        engine = RecommendationEngine()
        
        scored = engine.score_stack(sample_stack, sample_packages)
        
        # No requirements = full score
        assert scored.overlap_score == 30.0
        assert len(scored.matching_packages) == 0
        assert len(scored.missing_packages) == 0
    
    def test_recency_score_very_recent(self, sample_stack, sample_packages):
        """Test recency scoring for very recent stacks."""
        engine = RecommendationEngine()
        
        # Stack is 15 days old (from fixture)
        scored = engine.score_stack(sample_stack, sample_packages)
        
        # Should get full 20 points for stacks < 30 days
        assert scored.recency_score == 20.0
    
    def test_recency_score_old(self, old_stack, sample_packages):
        """Test recency scoring for old stacks."""
        engine = RecommendationEngine()
        
        # Stack is 400 days old (from fixture)
        scored = engine.score_stack(old_stack, sample_packages)
        
        # Should get 0 points for stacks > 365 days
        assert scored.recency_score == 0.0
    
    def test_recency_score_medium(self, sample_stack, sample_packages):
        """Test recency scoring for medium-age stacks."""
        engine = RecommendationEngine()
        
        # Modify stack to be 180 days old (middle of range)
        sample_stack.created_at = datetime.utcnow() - timedelta(days=180)
        scored = engine.score_stack(sample_stack, sample_packages)
        
        # Should be between 0 and 20
        assert 0 < scored.recency_score < 20
    
    def test_adoption_score(self, sample_stack, experimental_stack, sample_packages):
        """Test adoption scoring based on confidence level."""
        engine = RecommendationEngine()
        
        scored_prod = engine.score_stack(sample_stack, sample_packages)
        scored_exp = engine.score_stack(experimental_stack, sample_packages)
        
        # Production-tested should have higher adoption score
        assert scored_prod.adoption_score == 10.0
        assert scored_exp.adoption_score == 2.0
    
    def test_total_score_calculation(self, sample_stack, sample_packages):
        """Test that total score is sum of all component scores."""
        engine = RecommendationEngine()
        
        scored = engine.score_stack(sample_stack, sample_packages)
        
        expected_total = (
            scored.confidence_score +
            scored.overlap_score +
            scored.recency_score +
            scored.adoption_score
        )
        
        assert scored.total_score == expected_total
    
    def test_version_matching_exact(self, sample_stack, sample_packages):
        """Test version matching with exact version."""
        engine = RecommendationEngine()
        
        assert engine._version_matches("2.1.0", "2.1.0")
        assert not engine._version_matches("2.1.0", "2.0.0")
    
    def test_version_matching_specifier(self, sample_stack, sample_packages):
        """Test version matching with specifiers."""
        engine = RecommendationEngine()
        
        assert engine._version_matches("2.1.0", ">=2.0")
        assert engine._version_matches("2.1.0", ">=2.0,<3.0")
        assert not engine._version_matches("2.1.0", ">=3.0")
        assert not engine._version_matches("2.1.0", "<2.0")
    
    def test_rank_stacks_sorting(self, sample_stack, old_stack, experimental_stack, sample_packages):
        """Test that stacks are ranked by score (highest first)."""
        engine = RecommendationEngine()
        
        stacks = [
            (old_stack, sample_packages),
            (sample_stack, sample_packages),
            (experimental_stack, sample_packages),
        ]
        
        ranked = engine.rank_stacks(stacks)
        
        # Should be sorted by total_score descending
        assert len(ranked) == 3
        assert ranked[0].total_score >= ranked[1].total_score
        assert ranked[1].total_score >= ranked[2].total_score
        
        # Production-tested recent stack should rank highest
        assert ranked[0].stack.uid == sample_stack.uid
    
    def test_rank_stacks_min_score_filter(self, sample_stack, old_stack, sample_packages):
        """Test filtering by minimum score."""
        engine = RecommendationEngine()
        
        stacks = [
            (sample_stack, sample_packages),
            (old_stack, sample_packages),
        ]
        
        # Set high threshold that only sample_stack should pass
        ranked = engine.rank_stacks(stacks, min_score=70.0)
        
        # Only high-scoring stack should be included
        assert len(ranked) == 1
        assert ranked[0].stack.uid == sample_stack.uid
    
    def test_explanation_generation(self, sample_stack, sample_packages):
        """Test that explanation is generated correctly."""
        engine = RecommendationEngine()
        
        scored = engine.score_stack(sample_stack, sample_packages)
        
        assert scored.explanation != ""
        assert "Confidence:" in scored.explanation
        assert "Package match:" in scored.explanation
        assert "Recency:" in scored.explanation
        assert "Adoption:" in scored.explanation
    
    def test_get_match_percentage(self, sample_stack, sample_packages):
        """Test match percentage calculation."""
        engine = RecommendationEngine()
        required = {"torch": ">=2.0", "scipy": ">=1.0"}  # 1 match, 1 missing
        
        scored = engine.score_stack(
            sample_stack, sample_packages, required_packages=required
        )
        
        assert scored.get_match_percentage() == 50.0


# MigrationPathGenerator Tests

class TestMigrationPathGenerator:
    """Tests for MigrationPathGenerator class."""
    
    def test_generate_plan_install_new_packages(self, sample_stack, sample_packages):
        """Test migration plan for installing new packages."""
        generator = MigrationPathGenerator()
        
        current = {}  # Empty environment
        scored = ScoredStack(
            stack=sample_stack,
            packages=sample_packages,
            total_score=80.0,
            confidence_score=40.0,
            overlap_score=30.0,
            recency_score=20.0,
            adoption_score=10.0
        )
        
        plan = generator.generate_migration_plan(current, scored)
        
        # Should have install steps for all packages
        assert len(plan.steps) == 3
        assert all(step.action == "install" for step in plan.steps)
        assert plan.risk_level == "low"
    
    def test_generate_plan_upgrade_packages(self, sample_stack, sample_packages):
        """Test migration plan for upgrading packages."""
        generator = MigrationPathGenerator()
        
        current = {
            "torch": "2.0.0",
            "transformers": "4.30.0",
            "numpy": "1.24.3"
        }
        
        scored = ScoredStack(
            stack=sample_stack,
            packages=sample_packages,
            total_score=80.0,
            confidence_score=40.0,
            overlap_score=30.0,
            recency_score=20.0,
            adoption_score=10.0
        )
        
        plan = generator.generate_migration_plan(current, scored)
        
        # Should have upgrade steps for torch and transformers
        upgrades = [s for s in plan.steps if s.action == "upgrade"]
        assert len(upgrades) == 2
        assert plan.risk_level == "low"
    
    def test_generate_plan_downgrade_packages(self, sample_stack, sample_packages):
        """Test migration plan for downgrading packages."""
        generator = MigrationPathGenerator()
        
        current = {
            "torch": "2.2.0",  # Newer than target
            "transformers": "4.40.0",  # Newer than target
            "numpy": "1.24.3"
        }
        
        scored = ScoredStack(
            stack=sample_stack,
            packages=sample_packages,
            total_score=80.0,
            confidence_score=40.0,
            overlap_score=30.0,
            recency_score=20.0,
            adoption_score=10.0
        )
        
        plan = generator.generate_migration_plan(current, scored)
        
        # Should have downgrade steps
        downgrades = [s for s in plan.steps if s.action == "downgrade"]
        assert len(downgrades) == 2
        
        # Should have warnings for downgrades
        assert len(plan.warnings) >= 2
        assert plan.risk_level in ["medium", "high"]
    
    def test_generate_plan_remove_packages(self, sample_stack, sample_packages):
        """Test migration plan for removing packages."""
        generator = MigrationPathGenerator()
        
        current = {
            "torch": "2.1.0",
            "transformers": "4.38.0",
            "numpy": "1.24.3",
            "scipy": "1.10.0",  # Not in target stack
            "pandas": "2.0.0"   # Not in target stack
        }
        
        scored = ScoredStack(
            stack=sample_stack,
            packages=sample_packages,
            total_score=80.0,
            confidence_score=40.0,
            overlap_score=30.0,
            recency_score=20.0,
            adoption_score=10.0
        )
        
        plan = generator.generate_migration_plan(current, scored)
        
        # Should have remove steps for scipy and pandas
        removes = [s for s in plan.steps if s.action == "remove"]
        assert len(removes) == 2
    
    def test_generate_plan_no_changes(self, sample_stack, sample_packages):
        """Test migration plan when environment already matches."""
        generator = MigrationPathGenerator()
        
        current = {
            "torch": "2.1.0",
            "transformers": "4.38.0",
            "numpy": "1.24.3"
        }
        
        scored = ScoredStack(
            stack=sample_stack,
            packages=sample_packages,
            total_score=80.0,
            confidence_score=40.0,
            overlap_score=30.0,
            recency_score=20.0,
            adoption_score=10.0
        )
        
        plan = generator.generate_migration_plan(current, scored)
        
        # Should have no steps
        assert len(plan.steps) == 0
        assert plan.risk_level == "low"
    
    def test_migration_step_ordering(self, sample_stack, sample_packages):
        """Test that migration steps are ordered correctly."""
        generator = MigrationPathGenerator()
        
        current = {
            "torch": "2.0.0",  # Upgrade
            "scipy": "1.10.0"  # Remove
        }
        
        scored = ScoredStack(
            stack=sample_stack,
            packages=sample_packages,
            total_score=80.0,
            confidence_score=40.0,
            overlap_score=30.0,
            recency_score=20.0,
            adoption_score=10.0
        )
        
        plan = generator.generate_migration_plan(current, scored)
        
        # Check order: installs (1) < upgrades (2) < removes (3)
        orders = [step.order for step in plan.steps]
        assert orders == sorted(orders)
    
    def test_rollback_steps_generation(self, sample_stack, sample_packages):
        """Test that rollback steps are generated."""
        generator = MigrationPathGenerator()
        
        current = {"torch": "2.0.0"}
        
        scored = ScoredStack(
            stack=sample_stack,
            packages=sample_packages,
            total_score=80.0,
            confidence_score=40.0,
            overlap_score=30.0,
            recency_score=20.0,
            adoption_score=10.0
        )
        
        plan = generator.generate_migration_plan(current, scored)
        
        # Should have rollback steps
        assert len(plan.rollback_steps) > 0
        
        # Rollback steps should reverse the migration
        for step in plan.steps:
            if step.action == "install":
                # Should have corresponding remove in rollback
                assert any(
                    rb.action == "remove" and rb.package_name == step.package_name
                    for rb in plan.rollback_steps
                )
    
    def test_migration_step_get_command(self):
        """Test pip command generation for migration steps."""
        install_step = MigrationStep(
            action="install",
            package_name="torch",
            from_version=None,
            to_version="2.1.0",
            reason="Test",
            order=1
        )
        assert install_step.get_command() == "pip install torch==2.1.0"
        
        upgrade_step = MigrationStep(
            action="upgrade",
            package_name="torch",
            from_version="2.0.0",
            to_version="2.1.0",
            reason="Test",
            order=2
        )
        assert upgrade_step.get_command() == "pip install --upgrade torch==2.1.0"
        
        remove_step = MigrationStep(
            action="remove",
            package_name="scipy",
            from_version="1.10.0",
            to_version=None,
            reason="Test",
            order=3
        )
        assert remove_step.get_command() == "pip uninstall -y scipy"
    
    def test_migration_plan_summary(self, sample_stack, sample_packages):
        """Test migration plan summary generation."""
        generator = MigrationPathGenerator()
        
        current = {
            "torch": "2.0.0",  # Upgrade
            "scipy": "1.10.0"  # Remove
        }
        
        scored = ScoredStack(
            stack=sample_stack,
            packages=sample_packages,
            total_score=80.0,
            confidence_score=40.0,
            overlap_score=30.0,
            recency_score=20.0,
            adoption_score=10.0
        )
        
        plan = generator.generate_migration_plan(current, scored)
        
        summary = plan.get_summary()
        assert "steps:" in summary.lower()
        assert "install" in summary or "upgrade" in summary or "remove" in summary
    
    def test_risk_level_calculation_high(self, sample_stack, sample_packages):
        """Test high risk level calculation."""
        generator = MigrationPathGenerator()
        
        # Many downgrades = high risk
        current = {
            "torch": "2.5.0",
            "transformers": "4.50.0",
            "numpy": "2.0.0",
            "scipy": "1.12.0"
        }
        
        scored = ScoredStack(
            stack=sample_stack,
            packages=sample_packages,
            total_score=80.0,
            confidence_score=40.0,
            overlap_score=30.0,
            recency_score=20.0,
            adoption_score=10.0
        )
        
        plan = generator.generate_migration_plan(current, scored)
        
        # Should be high risk due to multiple downgrades
        assert plan.risk_level == "high"


# Integration Tests

class TestRecommendationIntegration:
    """Integration tests for recommendation system."""
    
    def test_end_to_end_recommendation_flow(self, sample_stack, old_stack, sample_packages):
        """Test complete recommendation flow from scoring to migration."""
        engine = RecommendationEngine()
        generator = MigrationPathGenerator()
        
        # Score multiple stacks
        stacks = [
            (sample_stack, sample_packages),
            (old_stack, sample_packages),
        ]
        
        required = {"torch": ">=2.0", "transformers": ">=4.0"}
        current = {"torch": "2.0.0", "numpy": "1.20.0"}
        
        ranked = engine.rank_stacks(
            stacks,
            required_packages=required,
            current_packages=current
        )
        
        # Should have ranked results
        assert len(ranked) > 0
        
        # Generate migration plan for top recommendation
        top_recommendation = ranked[0]
        plan = generator.generate_migration_plan(current, top_recommendation)
        
        # Should have a valid migration plan
        assert plan.target_stack == top_recommendation
        assert len(plan.steps) > 0
        assert plan.risk_level in ["low", "medium", "high"]


# Made with Bob