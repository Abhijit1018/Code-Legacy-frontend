"""
SymbolExtractor — build a global symbol table from all parsed files.

Walks every ``ParseResult`` from the analysis phase and collects:
  • All globally defined types, classes, structs, enums, and constants.
  • Function / method signatures with argument types and return types.
  • Shared data formats (COBOL record layouts, Java POJOs).

The resulting ``GlobalSymbolTable`` is serialisable to JSON
(``global_context.json``) and injected as mandatory context into
every LLM translation prompt so the model knows the full type landscape.
"""

from __future__ import annotations

import ast
import re
import json
import logging
from dataclasses import dataclass, field

from legacy_modernizer.analysis.ast_parser import ParseResult, FunctionInfo, COBOLMetadata

logger = logging.getLogger(__name__)


# ------------------------------------------------------------------
# Data classes
# ------------------------------------------------------------------

@dataclass
class SymbolSignature:
    """A single function / method signature."""
    name: str
    file_path: str
    language: str
    parameters: list[str] = field(default_factory=list)
    return_type: str = ""


@dataclass
class TypeDefinition:
    """A type / class / struct / enum / constant."""
    name: str
    file_path: str
    language: str
    kind: str = "class"          # class, struct, enum, constant, record
    fields: list[str] = field(default_factory=list)
    base_classes: list[str] = field(default_factory=list)


@dataclass
class GlobalSymbolTable:
    """Aggregated symbol table across an entire repository."""
    types: list[TypeDefinition] = field(default_factory=list)
    functions: list[SymbolSignature] = field(default_factory=list)

    def to_dict(self) -> dict:
        """Serialise to a JSON-friendly dictionary."""
        return {
            "types": [
                {
                    "name": t.name,
                    "file_path": t.file_path,
                    "language": t.language,
                    "kind": t.kind,
                    "fields": t.fields,
                    "base_classes": t.base_classes,
                }
                for t in self.types
            ],
            "functions": [
                {
                    "name": f.name,
                    "file_path": f.file_path,
                    "language": f.language,
                    "parameters": f.parameters,
                    "return_type": f.return_type,
                }
                for f in self.functions
            ],
        }

    def to_json(self, indent: int = 2) -> str:
        return json.dumps(self.to_dict(), indent=indent)

    def render_for_prompt(self, relevant_files: list[str] | None = None) -> str:
        """
        Render a human-readable subset of the symbol table for LLM context.

        If *relevant_files* is given, only symbols from those files are included.
        """
        parts: list[str] = ["=== GLOBAL SYMBOL TABLE ==="]

        types = self.types
        funcs = self.functions
        if relevant_files:
            file_set = set(relevant_files)
            types = [t for t in types if t.file_path in file_set]
            funcs = [f for f in funcs if f.file_path in file_set]

        if types:
            parts.append("\n--- Types / Classes ---")
            for t in types:
                bases = f" extends {', '.join(t.base_classes)}" if t.base_classes else ""
                parts.append(f"  {t.kind} {t.name}{bases}  [{t.file_path}]")
                for fld in t.fields[:10]:
                    parts.append(f"    - {fld}")

        if funcs:
            parts.append("\n--- Functions / Methods ---")
            for f in funcs:
                params = ", ".join(f.parameters) if f.parameters else ""
                ret = f" -> {f.return_type}" if f.return_type else ""
                parts.append(f"  {f.name}({params}){ret}  [{f.file_path}]")

        return "\n".join(parts)


# ------------------------------------------------------------------
# Extractor
# ------------------------------------------------------------------

class SymbolExtractor:
    """Build a ``GlobalSymbolTable`` from ``ParseResult`` objects."""

    def extract(self, parse_results: list[ParseResult]) -> GlobalSymbolTable:
        table = GlobalSymbolTable()

        for pr in parse_results:
            handler = {
                "python": self._extract_python,
                "java": self._extract_java,
                "cobol": self._extract_cobol,
            }.get(pr.language, self._extract_generic)
            handler(pr, table)

        logger.info(
            "Global symbol table: %d types, %d functions",
            len(table.types), len(table.functions),
        )
        return table

    # ------------------------------------------------------------------
    # Language-specific extractors
    # ------------------------------------------------------------------

    def _extract_python(self, pr: ParseResult, table: GlobalSymbolTable) -> None:
        """Extract Python classes and function signatures via re-parsing."""
        for cls_name in pr.classes:
            table.types.append(TypeDefinition(
                name=cls_name, file_path=pr.file_path,
                language="python", kind="class",
            ))

        for fn in pr.functions:
            sig = self._python_signature(fn)
            table.functions.append(sig)

    def _extract_java(self, pr: ParseResult, table: GlobalSymbolTable) -> None:
        for cls_name in pr.classes:
            table.types.append(TypeDefinition(
                name=cls_name, file_path=pr.file_path,
                language="java", kind="class",
                base_classes=pr.inherited_classes,
            ))

        for fn in pr.functions:
            table.functions.append(SymbolSignature(
                name=fn.name, file_path=pr.file_path,
                language="java",
            ))

    def _extract_cobol(self, pr: ParseResult, table: GlobalSymbolTable) -> None:
        if pr.cobol_metadata:
            # Record layouts become types
            for rec in pr.cobol_metadata.record_hierarchy:
                fields = [f"{c.name} PIC {c.pic}" for c in rec.children if c.pic]
                table.types.append(TypeDefinition(
                    name=rec.name, file_path=pr.file_path,
                    language="cobol", kind="record",
                    fields=fields,
                ))

        for fn in pr.functions:
            table.functions.append(SymbolSignature(
                name=fn.name, file_path=pr.file_path,
                language="cobol",
            ))

    def _extract_generic(self, pr: ParseResult, table: GlobalSymbolTable) -> None:
        for fn in pr.functions:
            table.functions.append(SymbolSignature(
                name=fn.name, file_path=pr.file_path,
                language=pr.language,
            ))

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _python_signature(fn: FunctionInfo) -> SymbolSignature:
        """Try to extract parameter names and return type from a Python function body."""
        params: list[str] = []
        return_type = ""
        try:
            # Parse just the function def line
            first_line = fn.body.split("\n")[0] if fn.body else ""
            # Extract params from def foo(a, b, c):
            m = re.search(r"def\s+\w+\s*\(([^)]*)\)", first_line)
            if m:
                raw_params = m.group(1)
                for p in raw_params.split(","):
                    p = p.strip()
                    if p and p != "self" and p != "cls":
                        params.append(p)
            # Extract return type annotation
            m2 = re.search(r"\)\s*->\s*(.+?):", first_line)
            if m2:
                return_type = m2.group(1).strip()
        except Exception:
            pass

        return SymbolSignature(
            name=fn.name, file_path=fn.file_path,
            language="python", parameters=params,
            return_type=return_type,
        )
