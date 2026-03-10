"""Analysis sub-package — AST parsing, dependency graphs, dead-code filtering."""

from .ast_parser import ASTParser
from .dependency_graph import DependencyGraph
from .dead_code_filter import DeadCodeFilter

__all__ = ["ASTParser", "DependencyGraph", "DeadCodeFilter"]
