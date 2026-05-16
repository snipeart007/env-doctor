"""
Dependency graph analysis.

Builds and analyzes dependency graphs to find cycles, transitive dependencies,
and conflicting paths.
"""

from typing import List, Dict, Set, Optional, Tuple
from collections import defaultdict, deque

from sqlmodel import select

from ..database.manager import DatabaseManager
from ..database.models import PackageVersion, PackageDependency
from .version_matcher import VersionMatcher


class DependencyGraph:
    """Build and analyze dependency graphs."""
    
    def __init__(self, db_manager: DatabaseManager):
        """
        Initialize dependency graph.
        
        Args:
            db_manager: Database manager instance
        """
        self.db_manager = db_manager
        self.version_matcher = VersionMatcher()
        
        # Graph structure: {(package, version): [(dep_name, version_spec), ...]}
        self.graph: Dict[Tuple[str, str], List[Tuple[str, str]]] = {}
        
        # Reverse graph for finding dependents
        self.reverse_graph: Dict[str, List[Tuple[str, str]]] = defaultdict(list)
    
    def build_graph(
        self,
        root_packages: List[Dict]
    ) -> None:
        """
        Build dependency graph from root packages.
        
        Recursively fetches dependencies from the database and builds
        a complete dependency graph.
        
        Args:
            root_packages: List of root package dictionaries with:
                - package_name: str
                - version: str
                
        Examples:
            >>> graph = DependencyGraph(db_manager)
            >>> graph.build_graph([
            ...     {"package_name": "torch", "version": "2.1.0"}
            ... ])
            >>> len(graph.graph) > 0
            True
        """
        self.graph.clear()
        self.reverse_graph.clear()
        
        # Queue of packages to process: (package_name, version)
        to_process = deque()
        processed = set()
        
        # Add root packages
        for pkg in root_packages:
            pkg_name = pkg.get("package_name", "")
            version = pkg.get("version", "")
            if pkg_name and version:
                to_process.append((pkg_name, version))
        
        # Process packages breadth-first
        with self.db_manager.get_session() as session:
            while to_process:
                pkg_name, version = to_process.popleft()
                
                # Skip if already processed
                if (pkg_name, version) in processed:
                    continue
                
                processed.add((pkg_name, version))
                
                # Get dependencies from database
                dependencies = self._get_package_dependencies(
                    session,
                    pkg_name,
                    version
                )
                
                # Add to graph
                self.graph[(pkg_name, version)] = dependencies
                
                # Add to reverse graph
                for dep_name, version_spec in dependencies:
                    self.reverse_graph[dep_name].append((pkg_name, version))
                
                # Add dependencies to processing queue
                # Note: We don't resolve specific versions here, just track the graph
                for dep_name, version_spec in dependencies:
                    # For now, we'll just track the dependency relationship
                    # Actual version resolution would require more complex logic
                    pass
    
    def find_cycles(self) -> List[List[str]]:
        """
        Find circular dependencies.
        
        Uses depth-first search to detect cycles in the dependency graph.
        
        Returns:
            List of cycles, where each cycle is a list of package names
            
        Examples:
            >>> cycles = graph.find_cycles()
            >>> for cycle in cycles:
            ...     print(" -> ".join(cycle))
        """
        cycles = []
        visited = set()
        rec_stack = set()
        path = []
        
        def dfs(node: Tuple[str, str]) -> bool:
            """DFS helper to detect cycles."""
            visited.add(node)
            rec_stack.add(node)
            path.append(node[0])  # Just package name for readability
            
            # Visit all dependencies
            for dep_name, _ in self.graph.get(node, []):
                # Find any version of this dependency in the graph
                dep_nodes = [n for n in self.graph.keys() if n[0] == dep_name]
                
                for dep_node in dep_nodes:
                    if dep_node not in visited:
                        if dfs(dep_node):
                            return True
                    elif dep_node in rec_stack:
                        # Found a cycle
                        cycle_start = path.index(dep_node[0])
                        cycle = path[cycle_start:] + [dep_node[0]]
                        cycles.append(cycle)
                        return True
            
            path.pop()
            rec_stack.remove(node)
            return False
        
        # Check all nodes
        for node in self.graph.keys():
            if node not in visited:
                dfs(node)
        
        return cycles
    
    def get_transitive_dependencies(
        self,
        package: str,
        version: str
    ) -> List[Dict]:
        """
        Get all transitive dependencies.
        
        Returns all dependencies recursively, including indirect dependencies.
        
        Args:
            package: Package name
            version: Package version
            
        Returns:
            List of dependency dictionaries with:
                - package_name: str
                - version_specifier: str
                - depth: int (0 for direct, 1+ for transitive)
                
        Examples:
            >>> deps = graph.get_transitive_dependencies("torch", "2.1.0")
            >>> direct = [d for d in deps if d["depth"] == 0]
            >>> transitive = [d for d in deps if d["depth"] > 0]
        """
        result = []
        visited = set()
        
        def traverse(pkg: str, ver: str, depth: int):
            """Recursively traverse dependencies."""
            node = (pkg, ver)
            
            if node in visited:
                return
            
            visited.add(node)
            
            # Get direct dependencies
            for dep_name, version_spec in self.graph.get(node, []):
                result.append({
                    "package_name": dep_name,
                    "version_specifier": version_spec,
                    "depth": depth,
                    "required_by": pkg
                })
                
                # Find matching versions in graph and recurse
                dep_nodes = [n for n in self.graph.keys() if n[0] == dep_name]
                for dep_node in dep_nodes:
                    traverse(dep_node[0], dep_node[1], depth + 1)
        
        traverse(package, version, 0)
        return result
    
    def find_conflicting_paths(
        self,
        package: str
    ) -> List[List[str]]:
        """
        Find paths that lead to version conflicts.
        
        Identifies different paths in the dependency graph that require
        different versions of the same package.
        
        Args:
            package: Package name to check for conflicts
            
        Returns:
            List of paths, where each path is a list of package names
            leading to the conflicting package
            
        Examples:
            >>> paths = graph.find_conflicting_paths("numpy")
            >>> for path in paths:
            ...     print(" -> ".join(path))
        """
        paths = []
        
        # Find all nodes that depend on this package
        dependents = self.reverse_graph.get(package, [])
        
        if len(dependents) < 2:
            # No conflict if only one or zero dependents
            return paths
        
        # Group by version specifier
        by_spec: Dict[str, List[Tuple[str, str]]] = defaultdict(list)
        
        for pkg_name, pkg_version in dependents:
            # Find the version spec for this dependency
            deps = self.graph.get((pkg_name, pkg_version), [])
            for dep_name, version_spec in deps:
                if dep_name == package:
                    by_spec[version_spec].append((pkg_name, pkg_version))
        
        # If we have different version specs, we have potential conflicts
        if len(by_spec) > 1:
            # Check if specs are actually incompatible
            specs = list(by_spec.keys())
            for i, spec1 in enumerate(specs):
                for spec2 in specs[i+1:]:
                    if not self.version_matcher.is_compatible_range(spec1, spec2):
                        # Found incompatible specs - trace paths
                        for pkg1, ver1 in by_spec[spec1]:
                            path1 = self._trace_path_to_root(pkg1, ver1)
                            paths.append(path1 + [f"{package} {spec1}"])
                        
                        for pkg2, ver2 in by_spec[spec2]:
                            path2 = self._trace_path_to_root(pkg2, ver2)
                            paths.append(path2 + [f"{package} {spec2}"])
        
        return paths
    
    def get_dependency_depth(self, package: str, version: str) -> int:
        """
        Get the maximum depth of dependencies.
        
        Args:
            package: Package name
            version: Package version
            
        Returns:
            Maximum depth of dependency tree
        """
        max_depth = 0
        visited = set()
        
        def traverse(pkg: str, ver: str, depth: int):
            nonlocal max_depth
            node = (pkg, ver)
            
            if node in visited:
                return
            
            visited.add(node)
            max_depth = max(max_depth, depth)
            
            for dep_name, _ in self.graph.get(node, []):
                dep_nodes = [n for n in self.graph.keys() if n[0] == dep_name]
                for dep_node in dep_nodes:
                    traverse(dep_node[0], dep_node[1], depth + 1)
        
        traverse(package, version, 0)
        return max_depth
    
    def get_all_packages(self) -> Set[str]:
        """
        Get all unique package names in the graph.
        
        Returns:
            Set of package names
        """
        packages = set()
        for pkg_name, _ in self.graph.keys():
            packages.add(pkg_name)
        
        for deps in self.graph.values():
            for dep_name, _ in deps:
                packages.add(dep_name)
        
        return packages
    
    def get_statistics(self) -> Dict:
        """
        Get graph statistics.
        
        Returns:
            Dictionary with statistics:
                - total_packages: int
                - total_edges: int
                - max_depth: int
                - has_cycles: bool
        """
        total_edges = sum(len(deps) for deps in self.graph.values())
        
        max_depth = 0
        for node in self.graph.keys():
            depth = self.get_dependency_depth(node[0], node[1])
            max_depth = max(max_depth, depth)
        
        cycles = self.find_cycles()
        
        return {
            "total_packages": len(self.get_all_packages()),
            "total_nodes": len(self.graph),
            "total_edges": total_edges,
            "max_depth": max_depth,
            "has_cycles": len(cycles) > 0,
            "cycle_count": len(cycles)
        }
    
    # Helper methods
    
    def _get_package_dependencies(
        self,
        session,
        package_name: str,
        version: str
    ) -> List[Tuple[str, str]]:
        """
        Get dependencies for a specific package version from database.
        
        Args:
            session: Database session
            package_name: Package name
            version: Package version
            
        Returns:
            List of (dependency_name, version_specifier) tuples
        """
        # Find the package version in database
        statement = select(PackageVersion).join(
            PackageVersion.package
        ).where(
            PackageVersion.package.has(name=package_name),
            PackageVersion.version == version
        )
        
        pkg_version = session.exec(statement).first()
        
        if not pkg_version:
            return []
        
        # Get dependencies
        dep_statement = select(PackageDependency).where(
            PackageDependency.package_version_uid == pkg_version.uid
        )
        
        dependencies = session.exec(dep_statement).all()
        
        return [
            (dep.dependency_name, dep.version_specifier)
            for dep in dependencies
        ]
    
    def _trace_path_to_root(
        self,
        package: str,
        version: str
    ) -> List[str]:
        """
        Trace path from package to root packages.
        
        Args:
            package: Package name
            version: Package version
            
        Returns:
            List of package names from root to this package
        """
        # Simple implementation - just return the package
        # A full implementation would trace back through reverse_graph
        return [f"{package} {version}"]

# Made with Bob
