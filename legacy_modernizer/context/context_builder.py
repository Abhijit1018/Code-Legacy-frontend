"""
ContextBuilder — assemble a minimal, structured context string from
the analysis results so it can be fed into Scaledown and then an LLM.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass

from legacy_modernizer.analysis.ast_parser import FunctionInfo

logger = logging.getLogger(__name__)


@dataclass
class BuiltContext:
    """The assembled context ready for compression."""
    text: str
    file_count: int
    function_count: int
    estimated_tokens: int  # rough estimate: chars / 4


class ContextBuilder:
    """
    Receives analysed functions and builds a structured prompt context.

    The context groups code by file and annotates each block with metadata
    (language, line numbers) so the LLM has clear provenance.
    """

    HEADER_TEMPLATE = (
        "=== LEGACY CODEBASE CONTEXT ===\n"
        "Files: {file_count} | Functions: {func_count} | Language(s): {languages}\n"
        "{'=' * 50}\n"
    )

    def build(self, functions: list[FunctionInfo]) -> BuiltContext:
        """
        Build a single context string from a list of `FunctionInfo`.

        Groups by file and emits fenced code blocks with metadata headers.
        """
        if not functions:
            return BuiltContext(text="", file_count=0, function_count=0, estimated_tokens=0)

        # Group functions by file
        by_file: dict[str, list[FunctionInfo]] = {}
        languages: set[str] = set()
        for fn in functions:
            by_file.setdefault(fn.file_path, []).append(fn)
            languages.add(fn.language)

        sections: list[str] = []

        # Header
        header = (
            f"=== LEGACY CODEBASE CONTEXT ===\n"
            f"Files: {len(by_file)} | Functions: {len(functions)} "
            f"| Languages: {', '.join(sorted(languages))}\n"
            f"{'=' * 50}"
        )
        sections.append(header)

        # Per-file sections
        for file_path, fns in sorted(by_file.items()):
            file_section = [f"\n--- FILE: {file_path} ({fns[0].language}) ---"]
            for fn in sorted(fns, key=lambda f: f.start_line):
                file_section.append(
                    f"\n# Function: {fn.name} "
                    f"(lines {fn.start_line}–{fn.end_line})"
                )
                if fn.calls:
                    file_section.append(f"# Calls: {', '.join(fn.calls)}")
                file_section.append(fn.body if fn.body else "# (body unavailable)")
            sections.append("\n".join(file_section))

        full_text = "\n\n".join(sections)

        return BuiltContext(
            text=full_text,
            file_count=len(by_file),
            function_count=len(functions),
            estimated_tokens=len(full_text) // 4,
        )

    def build_from_raw_files(
        self,
        file_contents: dict[str, str],
        language: str = "unknown",
    ) -> BuiltContext:
        """
        Build context directly from raw file contents (no AST step).

        Useful when AST parsing is unavailable for a given language.
        """
        sections: list[str] = []
        for path, content in sorted(file_contents.items()):
            sections.append(f"--- FILE: {path} ({language}) ---\n{content}")

        full_text = "\n\n".join(sections)
        return BuiltContext(
            text=full_text,
            file_count=len(file_contents),
            function_count=0,
            estimated_tokens=len(full_text) // 4,
        )
