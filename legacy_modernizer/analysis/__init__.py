"""Analysis sub-package — AST parsing, dependency graphs, dead-code filtering,
symbol extraction, philosophy extraction, and repository analysis."""

from .ast_parser import ASTParser
from .dependency_graph import DependencyGraph, FileDependencyGraph
from .dead_code_filter import DeadCodeFilter
from .symbol_extractor import SymbolExtractor, GlobalSymbolTable
from .philosophy_extractor import PhilosophyExtractor, RepoPhilosophy
from .repo_analyzer import RepoAnalyzer, RepoAnalysis

__all__ = [
    "ASTParser",
    "DependencyGraph",
    "FileDependencyGraph",
    "DeadCodeFilter",
    "SymbolExtractor",
    "GlobalSymbolTable",
    "PhilosophyExtractor",
    "RepoPhilosophy",
    "RepoAnalyzer",
    "RepoAnalysis",
]
