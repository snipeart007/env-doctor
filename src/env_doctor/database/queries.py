"""
Basic database queries for env-doctor.

Provides common query functions and query classes for retrieving data from the database.
"""

from typing import List, Optional

from sqlmodel import Session, select

from .manager import DatabaseManager
from .models import (
    CompatibilityRule,
    Package,
    PackageVersion,
    RuntimeProfile,
    StableStack,
    StableStackPackage,
    WheelAvailability,
)


class CompatibilityQueries:
    """Query class for compatibility rules."""
    
    def __init__(self, db_manager: DatabaseManager):
        """Initialize with database manager."""
        self.db_manager = db_manager
    
    def find_incompatibilities(
        self,
        package1: str,
        version1: str,
        package2: str,
        version2: str,
        session: Optional[Session] = None
    ) -> List[CompatibilityRule]:
        """Find incompatibilities between two packages."""
        if session:
            return self._find_incompatibilities(session, package1, version1, package2, version2)
        
        with self.db_manager.get_session() as session:
            return self._find_incompatibilities(session, package1, version1, package2, version2)

    def _find_incompatibilities(
        self,
        session: Session,
        package1: str,
        version1: str,
        package2: str,
        version2: str
    ) -> List[CompatibilityRule]:
        from env_doctor.core.version_matcher import VersionMatcher
        
        # Query for rules where package1 conflicts with package2
        stmt = select(CompatibilityRule).where(
            CompatibilityRule.package_name == package1.lower(),
            CompatibilityRule.dependency_name == package2.lower()
        )
        candidates1 = list(session.exec(stmt).all())
        
        # Query for rules where package2 conflicts with package1
        stmt = select(CompatibilityRule).where(
            CompatibilityRule.package_name == package2.lower(),
            CompatibilityRule.dependency_name == package1.lower()
        )
        candidates2 = list(session.exec(stmt).all())
        
        all_candidates = candidates1 + candidates2
        matching_rules = []
        
        for rule in all_candidates:
            # Determine which input package matches the rule's primary package
            if rule.package_name == package1.lower():
                v1, v2 = version1, version2
            else:
                v1, v2 = version2, version1
                
            # Check if version ranges/specs overlap with rule ranges
            m1 = self._matches(v1, rule.package_version_range, VersionMatcher)
            m2 = self._matches(v2, rule.dependency_version_range, VersionMatcher)
            
            if m1 and m2:
                matching_rules.append(rule)
                
        return matching_rules

    def _matches(self, input_ver: str, rule_range: str, matcher) -> bool:
        """Check if input version (could be range) matches rule range."""
        if not input_ver or input_ver == "any":
            return True
            
        # Handle exact versions (including those with ==)
        clean_ver = input_ver.lstrip('= ')
        if not any(op in clean_ver for op in ['>', '<', '!', '~']):
            return matcher.version_matches(clean_ver, rule_range)
            
        # If both are ranges, check for overlap
        return matcher.is_compatible_range(input_ver, rule_range)


class StackQueries:
    """Query class for stable stacks."""
    
    def __init__(self, db_manager: DatabaseManager):
        """Initialize with database manager."""
        self.db_manager = db_manager
    
    def find_matching_stacks(
        self,
        cuda_version: Optional[str] = None,
        python_version: Optional[str] = None,
        required_packages: Optional[List[str]] = None,
        platform: Optional[str] = None,
        confidence_threshold: Optional[str] = None,
        session: Optional[Session] = None
    ) -> List[StableStack]:
        """Find stacks matching the given criteria."""
        if session:
            return self._find_matching_stacks(
                session, cuda_version, python_version, required_packages, 
                platform, confidence_threshold
            )
            
        with self.db_manager.get_session() as session:
            return self._find_matching_stacks(
                session, cuda_version, python_version, required_packages, 
                platform, confidence_threshold
            )

    def _find_matching_stacks(
        self,
        session: Session,
        cuda_version: Optional[str] = None,
        python_version: Optional[str] = None,
        required_packages: Optional[List[str]] = None,
        platform: Optional[str] = None,
        confidence_threshold: Optional[str] = None
    ) -> List[StableStack]:
        stmt = select(StableStack)
        
        # CUDA version filtering
        if cuda_version:
            stmt = stmt.where(
                (StableStack.cuda_version == cuda_version) |
                (StableStack.cuda_version == None)  # noqa: E711
            )
        
        stacks = list(session.exec(stmt).all())
        
        # Python version filtering (perform in memory for complex specifiers)
        if python_version:
            try:
                from packaging.specifiers import SpecifierSet
                from packaging.version import Version
                target_ver = Version(python_version)
                
                filtered_stacks = []
                for stack in stacks:
                    try:
                        spec = SpecifierSet(stack.python_version)
                        if target_ver in spec:
                            filtered_stacks.append(stack)
                    except Exception:
                        # Fallback to simple inclusion if not a valid specifier
                        if python_version in stack.python_version:
                            filtered_stacks.append(stack)
                stacks = filtered_stacks
            except Exception:
                pass
        
        # Confidence level filtering
        if confidence_threshold:
            confidence_order = {
                "production-tested": 4,
                "stable": 3,
                "community-tested": 2,
                "experimental": 1
            }
            threshold_level = confidence_order.get(confidence_threshold, 1)
            valid_levels = [
                level for level, order in confidence_order.items()
                if order >= threshold_level
            ]
            stacks = [s for s in stacks if s.confidence_level in valid_levels]
        
        # Filter by required packages if specified
        if required_packages:
            filtered_stacks = []
            for stack in stacks:
                stack_packages = self._get_stack_packages(session, stack.uid)
                stack_pkg_names = {pkg.package_name.lower() for pkg in stack_packages}
                if all(pkg.lower() in stack_pkg_names for pkg in required_packages):
                    filtered_stacks.append(stack)
            return filtered_stacks
        
        return stacks
    
    def get_stack_packages(self, stack_uid: str, session: Optional[Session] = None) -> List[StableStackPackage]:
        """Get all packages in a stack."""
        if session:
            return self._get_stack_packages(session, stack_uid)
            
        with self.db_manager.get_session() as session:
            return self._get_stack_packages(session, stack_uid)

    def _get_stack_packages(self, session: Session, stack_uid: str) -> List[StableStackPackage]:
        stmt = select(StableStackPackage).where(
            StableStackPackage.stack_uid == stack_uid
        )
        return list(session.exec(stmt).all())
    
    def find_stacks_with_package(
        self,
        package_name: str,
        version_spec: Optional[str] = None,
        session: Optional[Session] = None
    ) -> List[StableStack]:
        """Find stacks containing a specific package."""
        if session:
            return self._find_stacks_with_package(session, package_name, version_spec)
            
        with self.db_manager.get_session() as session:
            return self._find_stacks_with_package(session, package_name, version_spec)

    def _find_stacks_with_package(
        self,
        session: Session,
        package_name: str,
        version_spec: Optional[str] = None
    ) -> List[StableStack]:
        stmt = select(StableStackPackage).where(
            StableStackPackage.package_name == package_name.lower()
        )
        stack_packages = list(session.exec(stmt).all())
        
        if version_spec:
            try:
                from packaging.specifiers import SpecifierSet
                from packaging.version import Version
                specifier_set = SpecifierSet(version_spec)
                stack_packages = [
                    sp for sp in stack_packages
                    if Version(sp.version) in specifier_set
                ]
            except Exception:
                stack_packages = [
                    sp for sp in stack_packages
                    if sp.version == version_spec
                ]
        
        stack_uids = list(set(sp.stack_uid for sp in stack_packages))
        if not stack_uids:
            return []
        
        stmt = select(StableStack).where(StableStack.uid.in_(stack_uids))  # type: ignore
        return list(session.exec(stmt).all())
    
    def get_stacks_with_packages(
        self,
        include_packages: bool = True,
        session: Optional[Session] = None
    ) -> List[tuple[StableStack, List[StableStackPackage]]]:
        """Get all stacks with their packages."""
        if session:
            return self._get_stacks_with_packages(session, include_packages)
            
        with self.db_manager.get_session() as session:
            return self._get_stacks_with_packages(session, include_packages)

    def _get_stacks_with_packages(
        self,
        session: Session,
        include_packages: bool = True
    ) -> List[tuple[StableStack, List[StableStackPackage]]]:
        stacks = list(session.exec(select(StableStack)).all())
        if not include_packages:
            return [(stack, []) for stack in stacks]
        
        result = []
        for stack in stacks:
            packages = self._get_stack_packages(session, stack.uid)
            result.append((stack, packages))
        return result


class RuntimeQueries:
    """Query class for runtime profiles."""
    
    def __init__(self, db_manager: DatabaseManager):
        """Initialize with database manager."""
        self.db_manager = db_manager
    
    def get_runtime_profile(self, runtime_name: str) -> Optional[RuntimeProfile]:
        """Get runtime profile by name."""
        with self.db_manager.get_session() as session:
            stmt = select(RuntimeProfile).where(
                RuntimeProfile.runtime_name == runtime_name.lower()
            )
            return session.exec(stmt).first()


def get_package_by_name(session: Session, name: str) -> Optional[Package]:
    statement = select(Package).where(Package.name == name.lower())
    return session.exec(statement).first()

def get_package_by_uid(session: Session, uid: str) -> Optional[Package]:
    return session.get(Package, uid)

def get_package_versions(session: Session, package_uid: str) -> list[PackageVersion]:
    statement = select(PackageVersion).where(PackageVersion.package_uid == package_uid).order_by(PackageVersion.release_date.desc())
    return list(session.exec(statement).all())

def get_package_version(session: Session, package_name: str, version: str) -> Optional[PackageVersion]:
    package = get_package_by_name(session, package_name)
    if not package: return None
    statement = select(PackageVersion).where(PackageVersion.package_uid == package.uid, PackageVersion.version == version)
    return session.exec(statement).first()

def get_compatibility_rules(session: Session, package_name: str) -> list[CompatibilityRule]:
    statement = select(CompatibilityRule).where(CompatibilityRule.package_name == package_name.lower())
    return list(session.exec(statement).all())

def get_compatibility_rules_for_dependency(session: Session, package_name: str, dependency_name: str) -> list[CompatibilityRule]:
    statement = select(CompatibilityRule).where(CompatibilityRule.package_name == package_name.lower(), CompatibilityRule.dependency_name == dependency_name.lower())
    return list(session.exec(statement).all())

def get_stable_stacks(session: Session) -> list[StableStack]:
    statement = select(StableStack).order_by(StableStack.created_at.desc())
    return list(session.exec(statement).all())

def get_stable_stack_by_name(session: Session, name: str) -> Optional[StableStack]:
    statement = select(StableStack).where(StableStack.name == name)
    return session.exec(statement).first()

def get_stable_stack_packages(session: Session, stack_uid: str) -> list[StableStackPackage]:
    statement = select(StableStackPackage).where(StableStackPackage.stack_uid == stack_uid)
    return list(session.exec(statement).all())

def get_wheel_availability(session: Session, package_version_uid: str) -> list[WheelAvailability]:
    statement = select(WheelAvailability).where(WheelAvailability.package_version_uid == package_version_uid)
    return list(session.exec(statement).all())

def get_runtime_profile(session: Session, runtime_name: str) -> Optional[RuntimeProfile]:
    statement = select(RuntimeProfile).where(RuntimeProfile.runtime_name == runtime_name.lower())
    return session.exec(statement).first()

def get_all_runtime_profiles(session: Session) -> list[RuntimeProfile]:
    statement = select(RuntimeProfile)
    return list(session.exec(statement).all())

def search_packages(session: Session, query: str, limit: int = 10) -> list[Package]:
    statement = select(Package).where(Package.name.like(f"%{query.lower()}%")).limit(limit)
    return list(session.exec(statement).all())
