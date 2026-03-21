"""
RepoAnalyzer — top-level orchestrator for Phase 1 repository analysis.

Accepts a ``ScanResult`` (from the ingestion layer) and coordinates:
  1. Parsing every file with ``ASTParser``.
  2. Building a file-level ``FileDependencyGraph``.
  3. Extracting ``GlobalSymbolTable`` via ``SymbolExtractor``.
  4. Extracting ``RepoPhilosophy`` via ``PhilosophyExtractor``.

Produces a ``RepoAnalysis`` dataclass containing all outputs.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Callable, Optional

from legacy_modernizer.analysis.ast_parser import ASTParser, ParseResult
from legacy_modernizer.analysis.dependency_graph import (
    DependencyGraph,
    FileDependencyGraph,
)
from legacy_modernizer.analysis.dead_code_filter import DeadCodeFilter
from legacy_modernizer.analysis.symbol_extractor import (
    SymbolExtractor,
    GlobalSymbolTable,
)
from legacy_modernizer.analysis.philosophy_extractor import (
    PhilosophyExtractor,
    RepoPhilosophy,
)
from legacy_modernizer.ingestion.file_scanner import ScanResult, SourceFile

logger = logging.getLogger(__name__)


# ------------------------------------------------------------------
# Result dataclass
# ------------------------------------------------------------------

@dataclass
class RepoAnalysis:
    """Complete analysis output for a repository."""
    # Parse results per file
    parse_results: list[ParseResult] = field(default_factory=list)

    # File-level dependency graph
    file_dependency_graph: Optional[FileDependencyGraph] = None

    # Function-level dependency graph (existing)
    function_dependency_graph: Optional[DependencyGraph] = None

    # Global symbol table
    symbol_table: Optional[GlobalSymbolTable] = None

    # Repository philosophy
    philosophy: Optional[RepoPhilosophy] = None

    # Translation order (leaf-first)
    translation_order: list[str] = field(default_factory=list)

    # File content map (cleaned source)
    file_contents: dict[str, str] = field(default_factory=dict)

    # Source files kept after filtering
    source_files: list[SourceFile] = field(default_factory=list)


# ------------------------------------------------------------------
# Orchestrator
# ------------------------------------------------------------------

class RepoAnalyzer:
    """
    Orchestrates the full Phase 1 analysis pipeline.

    Usage::

        analyzer = RepoAnalyzer(llm_fn=my_llm_callable)
        analysis = analyzer.analyze(scan_result)
    """

    def __init__(
        self,
        llm_fn: Optional[Callable[[str, str], str]] = None,
        remove_comments: bool = True,
        remove_tests: bool = True,
    ):
        """
        Args:
            llm_fn: Optional LLM callable for philosophy extraction.
                    Signature: ``(system_prompt, user_prompt) -> raw_text``.
            remove_comments: Strip comments from source before analysis.
            remove_tests: Exclude test files from analysis.
        """
        self._parser = ASTParser()
        self._dead_code_filter = DeadCodeFilter(
            remove_comments=remove_comments,
            remove_tests=remove_tests,
        )
        self._symbol_extractor = SymbolExtractor()
        self._philosophy_extractor = PhilosophyExtractor(llm_fn=llm_fn)

    def analyze(self, scan_result: ScanResult) -> RepoAnalysis:
        """
        Run the full Phase 1 pipeline on a scanned repository.

        1. Filter out test files / noise.
        2. Parse every file.
        3. Build file-level dependency graph.
        4. Build function-level dependency graph.
        5. Extract global symbol table.
        6. Extract repository philosophy (LLM).
        7. Compute translation order.
        """
        analysis = RepoAnalysis()

        # 1. Filter
        cleaned_files, filter_stats = self._dead_code_filter.filter_files(
            scan_result.files,
        )
        logger.info(
            "After filter: %d files (skipped %d test files)",
            len(cleaned_files), filter_stats.files_skipped,
        )
        analysis.source_files = cleaned_files

        # 2. Parse every file
        parse_results: list[ParseResult] = []
        file_contents: dict[str, str] = {}

        for sf in cleaned_files:
            try:
                raw_source = sf.read()
                cleaned_source, _ = self._dead_code_filter.clean_source(
                    raw_source, sf.language,
                )
                file_contents[sf.relative_path] = cleaned_source

                pr = self._parser.parse(cleaned_source, sf.relative_path, sf.language)
                parse_results.append(pr)
            except Exception as exc:
                logger.warning("Failed to parse %s: %s", sf.relative_path, exc)

        analysis.parse_results = parse_results
        analysis.file_contents = file_contents
        logger.info("Parsed %d files", len(parse_results))

        # 3. Build file-level dependency graph
        file_graph = FileDependencyGraph()
        for sf in cleaned_files:
            file_graph.add_file(
                file_path=sf.relative_path,
                language=sf.language,
                size_bytes=sf.size_bytes,
            )
        file_graph.build_from_parse_results(parse_results)
        analysis.file_dependency_graph = file_graph
        logger.info(
            "File dependency graph: %d files, %d edges",
            file_graph.file_count, file_graph.edge_count,
        )

        # 4. Build function-level dependency graph (existing capability)
        func_graph = DependencyGraph()
        for pr in parse_results:
            func_graph.add_parse_result(pr)
        func_graph.build()
        analysis.function_dependency_graph = func_graph

        # 5. Extract global symbol table
        analysis.symbol_table = self._symbol_extractor.extract(parse_results)
        logger.info(
            "Symbol table: %d types, %d functions",
            len(analysis.symbol_table.types),
            len(analysis.symbol_table.functions),
        )

        # 6. Extract repository philosophy
        dep_graph_json = file_graph.to_adjacency_json()
        # Select top-level / entry-point files as samples
        file_samples = self._select_sample_files(cleaned_files, file_contents)
        analysis.philosophy = self._philosophy_extractor.extract(
            dependency_graph_json=dep_graph_json,
            file_samples=file_samples,
        )
        logger.info(
            "Philosophy: pattern=%s",
            analysis.philosophy.architectural_pattern,
        )

        # 7. Compute translation order
        analysis.translation_order = file_graph.topological_sort()
        logger.info(
            "Translation order: %d files, first=%s, last=%s",
            len(analysis.translation_order),
            analysis.translation_order[0] if analysis.translation_order else "n/a",
            analysis.translation_order[-1] if analysis.translation_order else "n/a",
        )

        return analysis

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _select_sample_files(
        files: list[SourceFile],
        contents: dict[str, str],
        max_files: int = 5,
    ) -> dict[str, str]:
        """
        Pick the most important files as samples for the LLM.

        Heuristic: prefer entry points (main.*, app.*) and larger files.
        """
        import re

        entry_re = re.compile(r"(main|app|index|program|start)", re.IGNORECASE)

        # Score: entry-point hint = 100, else = file size
        scored = []
        for sf in files:
            score = sf.size_bytes
            if entry_re.search(sf.relative_path):
                score += 100_000
            scored.append((score, sf))

        scored.sort(key=lambda x: x[0], reverse=True)

        samples = {}
        for _, sf in scored[:max_files]:
            content = contents.get(sf.relative_path, "")
            samples[sf.relative_path] = content[:3000]  # Cap per file

        return samples
