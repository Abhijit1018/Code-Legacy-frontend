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
