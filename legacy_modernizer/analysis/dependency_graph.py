"""
DependencyGraph — build and query a call graph across an entire repository.

Given `ParseResult` objects from ASTParser, the graph connects functions to
their callees so we can extract the minimal *transitive closure* of code
required to understand any target function.
"""

from __future__ import annotations

import logging
from collections import defaultdict, deque
from dataclasses import dataclass, field

from legacy_modernizer.analysis.ast_parser import FunctionInfo, ParseResult

logger = logging.getLogger(__name__)


@dataclass
class DependencyNode:
    """A node in the dependency graph representing a single function."""
    function: FunctionInfo
    callees: list[str] = field(default_factory=list)
    callers: list[str] = field(default_factory=list)


class DependencyGraph:
    """
    Build a whole-repository dependency graph and answer reachability
    queries ("give me function A and everything it depends on").
    """

    def __init__(self) -> None:
        # qualified_name → DependencyNode
        self._nodes: dict[str, DependencyNode] = {}
        # short_name → list of qualified_names (handles name collisions)
        self._name_index: dict[str, list[str]] = defaultdict(list)

    # ------------------------------------------------------------------
    # Graph construction
    # ------------------------------------------------------------------

    def add_parse_result(self, result: ParseResult) -> None:
        """Register every function in *result* and wire up call edges."""
        for fn in result.functions:
            qname = f"{result.file_path}::{fn.name}"
            node = DependencyNode(function=fn, callees=list(fn.calls))
            self._nodes[qname] = node
            self._name_index[fn.name].append(qname)

    def build(self) -> None:
        """
        Resolve symbolic call references to qualified names and populate
        the `callers` lists (reverse edges).
        """
        for qname, node in self._nodes.items():
            resolved: list[str] = []
            for callee_name in node.callees:
                targets = self._name_index.get(callee_name, [])
                resolved.extend(targets)
            node.callees = resolved

            for callee_qname in resolved:
                if callee_qname in self._nodes:
                    self._nodes[callee_qname].callers.append(qname)

        logger.info(
            "Dependency graph built: %d nodes, %d edges",
            len(self._nodes),
            sum(len(n.callees) for n in self._nodes.values()),
        )

    # ------------------------------------------------------------------
    # Queries
    # ------------------------------------------------------------------

    def get_transitive_dependencies(
        self, function_name: str, max_depth: int = 10
    ) -> list[FunctionInfo]:
        """
        BFS from *function_name* and return all transitively-called functions
        (including the root itself), up to *max_depth* levels.
        """
        start_qnames = self._name_index.get(function_name, [])
        if not start_qnames:
            logger.warning("Function '%s' not found in graph", function_name)
            return []

        visited: set[str] = set()
        queue: deque[tuple[str, int]] = deque()

        for q in start_qnames:
            queue.append((q, 0))
            visited.add(q)

        result: list[FunctionInfo] = []
        while queue:
            current, depth = queue.popleft()
            node = self._nodes.get(current)
            if node is None:
                continue
            result.append(node.function)
            if depth < max_depth:
                for callee in node.callees:
                    if callee not in visited:
                        visited.add(callee)
                        queue.append((callee, depth + 1))

        return result

    def get_all_connected_code(self, entry_points: list[str]) -> list[FunctionInfo]:
        """
        Given a list of entry-point function names, collect all
        transitively-reachable code.
        """
        seen: set[str] = set()
        out: list[FunctionInfo] = []
        for name in entry_points:
            for fn in self.get_transitive_dependencies(name):
                key = f"{fn.file_path}::{fn.name}"
                if key not in seen:
                    seen.add(key)
                    out.append(fn)
        return out

    def get_unreachable_functions(self, entry_points: list[str]) -> list[FunctionInfo]:
        """Return functions NOT reachable from *entry_points*."""
        reachable = {
            f"{fn.file_path}::{fn.name}"
            for fn in self.get_all_connected_code(entry_points)
        }
        return [
            node.function
            for qname, node in self._nodes.items()
            if qname not in reachable
        ]

    @property
    def all_functions(self) -> list[FunctionInfo]:
        return [node.function for node in self._nodes.values()]

    @property
    def node_count(self) -> int:
        return len(self._nodes)


# ======================================================================
# File-level dependency graph  (Phase 1 — §1.1)
# ======================================================================

@dataclass
class FileNode:
    """A node in the file-level dependency graph."""
    file_path: str
    language: str
    size_bytes: int = 0
    role_type: str = ""       # "entry_point", "library", "config", "test", etc.


@dataclass
class FileEdge:
    """A typed edge between two files."""
    source: str               # file_path of source
    target: str               # file_path of target
    edge_type: str            # imports, calls, inherits, reads_config, writes_output


class FileDependencyGraph:
    """
    Build a whole-repository **file-level** dependency graph.

    Nodes = files, edges = typed cross-file relationships.
    Supports topological sorting for leaf-first translation ordering.
    """

    def __init__(self) -> None:
        self._nodes: dict[str, FileNode] = {}
        self._edges: list[FileEdge] = []
        # Adjacency: file_path → list of (target_path, edge_type)
        self._adj: dict[str, list[tuple[str, str]]] = defaultdict(list)
        # Reverse adjacency for callers
        self._rev: dict[str, list[tuple[str, str]]] = defaultdict(list)

    # ------------------------------------------------------------------
    # Graph construction
    # ------------------------------------------------------------------

    def add_file(self, file_path: str, language: str,
                 size_bytes: int = 0, role_type: str = "") -> None:
        """Register a file node."""
        self._nodes[file_path] = FileNode(
            file_path=file_path, language=language,
            size_bytes=size_bytes, role_type=role_type,
        )

    def add_edge(self, source: str, target: str, edge_type: str) -> None:
        """Add a typed directed edge between two files."""
        edge = FileEdge(source=source, target=target, edge_type=edge_type)
        self._edges.append(edge)
        self._adj[source].append((target, edge_type))
        self._rev[target].append((source, edge_type))

    def build_from_parse_results(self, parse_results: list[ParseResult],
                                  file_language_map: dict[str, str] | None = None) -> None:
        """
        Populate edges from parsed cross-file references.

        Steps:
        1. Build an index of which symbols are defined in which files.
        2. For each file's imports/calls/inheritance, resolve target files.
        """
        # Index: symbol_name → file_path
        symbol_index: dict[str, str] = {}
        class_index: dict[str, str] = {}

        for pr in parse_results:
            for fn in pr.functions:
                symbol_index[fn.name] = pr.file_path
            for cls in pr.classes:
                class_index[cls] = pr.file_path

        # Wire edges
        for pr in parse_results:
            # Import-based edges
            for imp in pr.imports:
                # Try to resolve the import to a file in the repo
                short_name = imp.split(".")[-1]
                target = symbol_index.get(short_name) or class_index.get(short_name)
                if target and target != pr.file_path:
                    self.add_edge(pr.file_path, target, "imports")

            # Cross-file function calls
            for call in pr.external_calls:
                target = symbol_index.get(call)
                if target and target != pr.file_path:
                    self.add_edge(pr.file_path, target, "calls")

            # Inheritance edges
            for base in pr.inherited_classes:
                target = class_index.get(base)
                if target and target != pr.file_path:
                    self.add_edge(pr.file_path, target, "inherits")

            # Config reads
            for cfg in pr.config_reads:
                if cfg in self._nodes:
                    self.add_edge(pr.file_path, cfg, "reads_config")

    # ------------------------------------------------------------------
    # Queries
    # ------------------------------------------------------------------

    def get_dependencies(self, file_path: str) -> list[str]:
        """Return all files that *file_path* depends on (outgoing edges)."""
        return list(set(t for t, _ in self._adj.get(file_path, [])))

    def get_dependents(self, file_path: str) -> list[str]:
        """Return all files that depend on *file_path* (incoming edges)."""
        return list(set(s for s, _ in self._rev.get(file_path, [])))

    def topological_sort(self) -> list[str]:
        """
        Return files in **leaf-first** order (topological sort).

        Files with no dependencies come first. Files that depend
        on others come later. This is the correct order for translation.
        """
        in_degree: dict[str, int] = {f: 0 for f in self._nodes}
        for edge in self._edges:
            if edge.target in in_degree:
                in_degree[edge.target] = in_degree.get(edge.target, 0)
                # We need reverse: files with no dependents translated first
                # Actually, for leaf-first: files with no dependencies first
                pass

        # Kahn's algorithm — leaf-first means "no outgoing deps first"
        out_degree: dict[str, int] = {f: 0 for f in self._nodes}
        reverse_adj: dict[str, list[str]] = defaultdict(list)
        for edge in self._edges:
            if edge.source in self._nodes and edge.target in self._nodes:
                out_degree[edge.source] = out_degree.get(edge.source, 0) + 1
                reverse_adj[edge.target].append(edge.source)

        queue: deque[str] = deque()
        for f, deg in out_degree.items():
            if deg == 0:
                queue.append(f)

        result: list[str] = []
        while queue:
            node = queue.popleft()
            result.append(node)
            # For each file that depends on this one, decrement out-degree
            for dependent in reverse_adj.get(node, []):
                out_degree[dependent] -= 1
                if out_degree[dependent] == 0:
                    queue.append(dependent)

        # Add any remaining files (cycles)
        for f in self._nodes:
            if f not in result:
                result.append(f)

        return result

    # ------------------------------------------------------------------
    # Serialisation
    # ------------------------------------------------------------------

    def to_adjacency_json(self) -> dict:
        """Serialize the graph as a JSON adjacency list."""
        adj: dict[str, dict] = {}
        for file_path, node in self._nodes.items():
            edges_out = [
                {"target": t, "type": et}
                for t, et in self._adj.get(file_path, [])
            ]
            adj[file_path] = {
                "language": node.language,
                "size_bytes": node.size_bytes,
                "role_type": node.role_type,
                "edges": edges_out,
            }
        return adj

    @property
    def file_count(self) -> int:
        return len(self._nodes)

    @property
    def edge_count(self) -> int:
        return len(self._edges)

    @property
    def all_files(self) -> list[str]:
        return list(self._nodes.keys())
