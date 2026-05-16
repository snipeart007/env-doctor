"""
Recommendation engine for env-doctor.

Provides intelligent stack recommendations based on environment analysis,
package overlap, recency, and community adoption.
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Dict, List, Optional, Set, Tuple

from packaging.specifiers import SpecifierSet
from packaging.version import Version, InvalidVersion

from ..database.models import StableStack, StableStackPackage


@dataclass
class ScoredStack:
    """
    A stable stack with calculated recommendation score.
    
    Attributes:
        stack: The stable stack being scored
        packages: List of packages in the stack
        total_score: Overall recommendation score (0-100)
        confidence_score: Confidence level score (0-40)
        overlap_score: Package overlap score (0-30)
        recency_score: Recency score (0-20)
        adoption_score: Community adoption score (0-10)
        matching_packages: Set of package names that match requirements
        missing_packages: Set of required packages not in stack
        extra_packages: Set of packages in stack not required
        explanation: Human-readable explanation of the score
    """
    stack: StableStack
    packages: List[StableStackPackage]
    total_score: float
    confidence_score: float
    overlap_score: float
    recency_score: float
    adoption_score: float
    matching_packages: Set[str] = field(default_factory=set)
    missing_packages: Set[str] = field(default_factory=set)
    extra_packages: Set[str] = field(default_factory=set)
    explanation: str = ""
    
    def get_package_dict(self) -> Dict[str, str]:
        """Get packages as a dictionary mapping name to version."""
        return {pkg.package_name: pkg.version for pkg in self.packages}
    
    def get_match_percentage(self) -> float:
        """Get percentage of required packages that are matched."""
        total_required = len(self.matching_packages) + len(self.missing_packages)
        if total_required == 0:
            return 100.0
        return (len(self.matching_packages) / total_required) * 100


@dataclass
class MigrationStep:
    """
    A single step in a migration plan.
    
    Attributes:
        action: Type of action (install, upgrade, downgrade, remove)
        package_name: Name of the package
        from_version: Current version (None for install)
        to_version: Target version (None for remove)
        reason: Explanation for this step
        order: Execution order (lower numbers first)
    """
    action: str  # install, upgrade, downgrade, remove
    package_name: str
    from_version: Optional[str]
    to_version: Optional[str]
    reason: str
    order: int = 0
    
    def get_command(self) -> str:
        """Get pip command for this step."""
        if self.action == "install":
            return f"pip install {self.package_name}=={self.to_version}"
        elif self.action == "upgrade":
            return f"pip install --upgrade {self.package_name}=={self.to_version}"
        elif self.action == "downgrade":
            return f"pip install {self.package_name}=={self.to_version}"
        elif self.action == "remove":
            return f"pip uninstall -y {self.package_name}"
        return ""
    
    def __str__(self) -> str:
        """String representation of the step."""
        if self.action == "install":
            return f"Install {self.package_name}=={self.to_version}"
        elif self.action == "upgrade":
            return f"Upgrade {self.package_name} from {self.from_version} to {self.to_version}"
        elif self.action == "downgrade":
            return f"Downgrade {self.package_name} from {self.from_version} to {self.to_version}"
        elif self.action == "remove":
            return f"Remove {self.package_name} {self.from_version}"
        return ""


@dataclass
class MigrationPlan:
    """
    Complete migration plan from current environment to target stack.
    
    Attributes:
        target_stack: The target stable stack
        steps: List of migration steps in execution order
        estimated_time: Estimated time in minutes
        risk_level: Risk level (low, medium, high)
        warnings: List of warnings about the migration
        rollback_steps: Steps to rollback if migration fails
    """
    target_stack: ScoredStack
    steps: List[MigrationStep]
    estimated_time: int  # minutes
    risk_level: str  # low, medium, high
    warnings: List[str] = field(default_factory=list)
    rollback_steps: List[MigrationStep] = field(default_factory=list)
    
    def get_summary(self) -> str:
        """Get a summary of the migration plan."""
        action_counts = {}
        for step in self.steps:
            action_counts[step.action] = action_counts.get(step.action, 0) + 1
        
        parts = []
        for action, count in sorted(action_counts.items()):
            parts.append(f"{count} {action}")
        
        return f"{len(self.steps)} steps: {', '.join(parts)}"
    
    def get_full_command(self) -> str:
        """Get complete pip command for all steps."""
        commands = [step.get_command() for step in self.steps]
        return " && ".join(commands)


class RecommendationEngine:
    """
    Engine for scoring and ranking stable stacks.
    
    Uses a weighted scoring system:
    - Confidence: 40% (production-tested > stable > community-tested > experimental)
    - Package overlap: 30% (how many required packages are in the stack)
    - Recency: 20% (newer stacks preferred)
    - Community adoption: 10% (based on confidence level and stack age)
    """
    
    # Confidence level weights (out of 40 points)
    CONFIDENCE_WEIGHTS = {
        "production-tested": 40,
        "stable": 30,
        "community-tested": 20,
        "experimental": 10
    }
    
    def __init__(self):
        """Initialize the recommendation engine."""
        pass
    
    def score_stack(
        self,
        stack: StableStack,
        packages: List[StableStackPackage],
        required_packages: Optional[Dict[str, str]] = None,
        current_packages: Optional[Dict[str, str]] = None,
        python_version: Optional[str] = None,
        cuda_version: Optional[str] = None
    ) -> ScoredStack:
        """
        Score a stable stack based on multiple factors.
        
        Args:
            stack: The stable stack to score
            packages: List of packages in the stack
            required_packages: Dict of required package names to version specs
            current_packages: Dict of currently installed packages
            python_version: Target Python version
            cuda_version: Target CUDA version
            
        Returns:
            ScoredStack with calculated scores and explanation
        """
        required_packages = required_packages or {}
        current_packages = current_packages or {}
        
        # Calculate individual scores
        confidence_score = self._calculate_confidence_score(stack)
        overlap_score, matching, missing, extra = self._calculate_overlap_score(
            packages, required_packages
        )
        recency_score = self._calculate_recency_score(stack)
        adoption_score = self._calculate_adoption_score(stack)
        
        # Calculate total score
        total_score = confidence_score + overlap_score + recency_score + adoption_score
        
        # Generate explanation
        explanation = self._generate_explanation(
            stack, confidence_score, overlap_score, recency_score, adoption_score,
            matching, missing, extra
        )
        
        return ScoredStack(
            stack=stack,
            packages=packages,
            total_score=total_score,
            confidence_score=confidence_score,
            overlap_score=overlap_score,
            recency_score=recency_score,
            adoption_score=adoption_score,
            matching_packages=matching,
            missing_packages=missing,
            extra_packages=extra,
            explanation=explanation
        )
    
    def _calculate_confidence_score(self, stack: StableStack) -> float:
        """Calculate confidence score (0-40 points)."""
        return self.CONFIDENCE_WEIGHTS.get(stack.confidence_level, 10)
    
    def _calculate_overlap_score(
        self,
        packages: List[StableStackPackage],
        required_packages: Dict[str, str]
    ) -> Tuple[float, Set[str], Set[str], Set[str]]:
        """
        Calculate package overlap score (0-30 points).
        
        Returns:
            Tuple of (score, matching_packages, missing_packages, extra_packages)
        """
        if not required_packages:
            # No requirements specified, give full score
            return 30.0, set(), set(), set()
        
        stack_packages = {pkg.package_name.lower(): pkg.version for pkg in packages}
        required_lower = {name.lower(): spec for name, spec in required_packages.items()}
        
        matching = set()
        missing = set()
        
        for req_name, version_spec in required_lower.items():
            if req_name in stack_packages:
                stack_version = stack_packages[req_name]
                
                # Check if version matches the requirement
                if self._version_matches(stack_version, version_spec):
                    matching.add(req_name)
                else:
                    missing.add(req_name)
            else:
                missing.add(req_name)
        
        # Calculate extra packages (in stack but not required)
        extra = set(stack_packages.keys()) - set(required_lower.keys())
        
        # Score based on match percentage
        total_required = len(required_lower)
        match_percentage = len(matching) / total_required if total_required > 0 else 1.0
        
        # Full 30 points for 100% match, scaled down for partial matches
        score = match_percentage * 30.0
        
        return score, matching, missing, extra
    
    def _version_matches(self, version: str, spec: str) -> bool:
        """Check if a version matches a version specifier."""
        if not spec:
            return True
            
        try:
            # Handle simple version equality
            if not any(op in spec for op in ['>', '<', '=', '!', '~']):
                return version == spec
            
            # Use packaging library for complex specifiers
            specifier_set = SpecifierSet(spec)
            return Version(version) in specifier_set
        except (InvalidVersion, Exception):
            # Fallback to string comparison
            return version == spec
    
    def _calculate_recency_score(self, stack: StableStack) -> float:
        """Calculate recency score (0-20 points)."""
        # Score based on how recent the stack is
        now = datetime.utcnow()
        age_days = (now - stack.created_at).days
        
        # Full 20 points for stacks less than 30 days old
        # Linearly decrease to 0 points at 365 days
        if age_days <= 30:
            return 20.0
        elif age_days >= 365:
            return 0.0
        else:
            # Linear interpolation
            return 20.0 * (1 - (age_days - 30) / 335)
    
    def _calculate_adoption_score(self, stack: StableStack) -> float:
        """Calculate community adoption score (0-10 points)."""
        # Higher confidence levels indicate better adoption
        confidence_to_adoption = {
            "production-tested": 10,
            "stable": 7,
            "community-tested": 5,
            "experimental": 2
        }
        return confidence_to_adoption.get(stack.confidence_level, 2)
    
    def _generate_explanation(
        self,
        stack: StableStack,
        confidence_score: float,
        overlap_score: float,
        recency_score: float,
        adoption_score: float,
        matching: Set[str],
        missing: Set[str],
        extra: Set[str]
    ) -> str:
        """Generate human-readable explanation of the score."""
        parts = []
        
        # Confidence explanation
        parts.append(f"Confidence: {confidence_score:.1f}/40 ({stack.confidence_level})")
        
        # Overlap explanation
        if matching or missing:
            total_req = len(matching) + len(missing)
            parts.append(f"Package match: {overlap_score:.1f}/30 ({len(matching)}/{total_req} packages)")
        else:
            parts.append(f"Package match: {overlap_score:.1f}/30 (no requirements)")
        
        # Recency explanation
        age_days = (datetime.utcnow() - stack.created_at).days
        parts.append(f"Recency: {recency_score:.1f}/20 ({age_days} days old)")
        
        # Adoption explanation
        parts.append(f"Adoption: {adoption_score:.1f}/10")
        
        return " | ".join(parts)
    
    def rank_stacks(
        self,
        stacks: List[Tuple[StableStack, List[StableStackPackage]]],
        required_packages: Optional[Dict[str, str]] = None,
        current_packages: Optional[Dict[str, str]] = None,
        python_version: Optional[str] = None,
        cuda_version: Optional[str] = None,
        min_score: float = 0.0
    ) -> List[ScoredStack]:
        """
        Score and rank multiple stacks.
        
        Args:
            stacks: List of (stack, packages) tuples
            required_packages: Dict of required package names to version specs
            current_packages: Dict of currently installed packages
            python_version: Target Python version
            cuda_version: Target CUDA version
            min_score: Minimum score threshold
            
        Returns:
            List of ScoredStack instances, sorted by score (highest first)
        """
        scored_stacks = []
        
        for stack, packages in stacks:
            scored = self.score_stack(
                stack, packages, required_packages, current_packages,
                python_version, cuda_version
            )
            
            if scored.total_score >= min_score:
                scored_stacks.append(scored)
        
        # Sort by total score (descending)
        scored_stacks.sort(key=lambda x: x.total_score, reverse=True)
        
        return scored_stacks


class MigrationPathGenerator:
    """
    Generates migration plans from current environment to target stack.
    """
    
    def __init__(self):
        """Initialize the migration path generator."""
        pass
    
    def generate_migration_plan(
        self,
        current_packages: Dict[str, str],
        target_stack: ScoredStack
    ) -> MigrationPlan:
        """
        Generate a migration plan from current environment to target stack.
        
        Args:
            current_packages: Dict of currently installed packages (name -> version)
            target_stack: Target scored stack
            
        Returns:
            MigrationPlan with ordered steps
        """
        target_packages = target_stack.get_package_dict()
        steps = []
        warnings = []
        rollback_steps = []
        
        # Normalize package names to lowercase for comparison
        current_lower = {name.lower(): version for name, version in current_packages.items()}
        target_lower = {name.lower(): version for name, version in target_packages.items()}
        
        # Step 1: Identify packages to remove (in current but not in target)
        for pkg_name, version in current_lower.items():
            if pkg_name not in target_lower:
                steps.append(MigrationStep(
                    action="remove",
                    package_name=pkg_name,
                    from_version=version,
                    to_version=None,
                    reason=f"Not in target stack",
                    order=3  # Remove after downgrades
                ))
                rollback_steps.append(MigrationStep(
                    action="install",
                    package_name=pkg_name,
                    from_version=None,
                    to_version=version,
                    reason="Rollback: restore removed package",
                    order=1
                ))
        
        # Step 2: Identify packages to install (in target but not in current)
        for pkg_name, version in target_lower.items():
            if pkg_name not in current_lower:
                steps.append(MigrationStep(
                    action="install",
                    package_name=pkg_name,
                    from_version=None,
                    to_version=version,
                    reason=f"Required by target stack",
                    order=1  # Install first
                ))
                rollback_steps.append(MigrationStep(
                    action="remove",
                    package_name=pkg_name,
                    from_version=version,
                    to_version=None,
                    reason="Rollback: remove installed package",
                    order=3
                ))
        
        # Step 3: Identify packages to upgrade/downgrade
        for pkg_name in set(current_lower.keys()) & set(target_lower.keys()):
            current_version = current_lower[pkg_name]
            target_version = target_lower[pkg_name]
            
            if current_version != target_version:
                # Determine if upgrade or downgrade
                try:
                    is_upgrade = Version(target_version) > Version(current_version)
                    action = "upgrade" if is_upgrade else "downgrade"
                except InvalidVersion:
                    # Fallback to string comparison
                    action = "upgrade" if target_version > current_version else "downgrade"
                
                steps.append(MigrationStep(
                    action=action,
                    package_name=pkg_name,
                    from_version=current_version,
                    to_version=target_version,
                    reason=f"Version mismatch: {current_version} -> {target_version}",
                    order=2  # Upgrade/downgrade in middle
                ))
                rollback_steps.append(MigrationStep(
                    action="downgrade" if is_upgrade else "upgrade",
                    package_name=pkg_name,
                    from_version=target_version,
                    to_version=current_version,
                    reason=f"Rollback: restore version {current_version}",
                    order=2
                ))
                
                # Add warning for downgrades
                if action == "downgrade":
                    warnings.append(
                        f"Downgrading {pkg_name} from {current_version} to {target_version} "
                        f"may cause compatibility issues"
                    )
        
        # Sort steps by order
        steps.sort(key=lambda x: (x.order, x.package_name))
        rollback_steps.sort(key=lambda x: (x.order, x.package_name))
        
        # Calculate risk level
        risk_level = self._calculate_risk_level(steps, warnings)
        
        # Estimate time (rough estimate: 1 minute per package operation)
        estimated_time = len(steps)
        
        return MigrationPlan(
            target_stack=target_stack,
            steps=steps,
            estimated_time=estimated_time,
            risk_level=risk_level,
            warnings=warnings,
            rollback_steps=rollback_steps
        )
    
    def _calculate_risk_level(self, steps: List[MigrationStep], warnings: List[str]) -> str:
        """Calculate risk level based on migration steps."""
        # Count different types of operations
        downgrades = sum(1 for s in steps if s.action == "downgrade")
        removes = sum(1 for s in steps if s.action == "remove")
        total_changes = len(steps)
        
        # High risk: many downgrades or removals
        if downgrades >= 3 or removes >= 5 or len(warnings) >= 3:
            return "high"
        # Medium risk: some downgrades or many changes
        elif downgrades >= 1 or removes >= 2 or total_changes >= 10:
            return "medium"
        # Low risk: mostly installs and upgrades
        else:
            return "low"


# Made with Bob