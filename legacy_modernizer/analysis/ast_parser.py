"""
ASTParser — Extract functions, classes, imports, and call-sites from source code.

Supports Python and Java via the built-in `ast` module (Python) and a
lightweight regex/heuristic approach (Java, COBOL, and other languages).
"""

from __future__ import annotations

import ast
import re
import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)


# ------------------------------------------------------------------
# Data classes
# ------------------------------------------------------------------

@dataclass
class FunctionInfo:
    """Metadata about a single function / method / paragraph."""
    name: str
    file_path: str
    start_line: int
    end_line: int
    calls: list[str] = field(default_factory=list)
    language: str = "unknown"
    body: str = ""


@dataclass
class COBOLFieldInfo:
    """Metadata about a single COBOL data field."""
    name: str
    level: int
    pic: str = ""                   # raw PIC string, e.g. "S9(7)V99"
    field_type: str = "group"       # numeric, alphanumeric, alphabetic, currency, group
    length: int = 0                 # total character width
    decimals: int = 0               # digits after V
    signed: bool = False
    display_format: str = ""        # edit-mask PIC, e.g. "$ZZ,ZZ9.99"
    children: list[COBOLFieldInfo] = field(default_factory=list)


@dataclass
class COBOLSortKey:
    """A SORT key extracted from PROCEDURE DIVISION."""
    field_name: str
    order: str = "ASCENDING"        # ASCENDING or DESCENDING
    field_type: str = ""            # resolved from PIC if available
    pic_summary: str = ""           # e.g. "numeric(7.2)"


@dataclass
class COBOLMetadata:
    """Structured metadata extracted from a COBOL program."""
    program_id: str = ""
    file_control: dict[str, str] = field(default_factory=dict)   # logical → physical
    file_org: dict[str, str] = field(default_factory=dict)       # logical → organization
    fields: list[COBOLFieldInfo] = field(default_factory=list)    # flat list of all fields
    record_hierarchy: list[COBOLFieldInfo] = field(default_factory=list)  # top-level 01 records
    sort_keys: list[COBOLSortKey] = field(default_factory=list)

    def render(self) -> str:
        """Render metadata as a human-readable block for LLM context."""
        parts: list[str] = []

        parts.append(f"PROGRAM-ID: {self.program_id}")

        if self.file_control:
            parts.append("\nFILE-CONTROL:")
            for logical, physical in self.file_control.items():
                org = self.file_org.get(logical, "")
                org_str = f"  ({org})" if org else ""
                parts.append(f"  {logical} → {physical}{org_str}")

        if self.fields:
            parts.append("\nDATA FIELDS:")
            for f in self.fields:
                if f.field_type == "group":
                    continue  # groups shown in hierarchy only
                desc = f"  {f.name}: type={f.field_type} length={f.length}"
                if f.decimals:
                    desc += f" decimals={f.decimals}"
                if f.signed:
                    desc += " signed=True"
                if f.display_format:
                    desc += f" display=\"{f.display_format}\""
                parts.append(desc)

        if self.sort_keys:
            parts.append("\nSORT KEYS:")
            for sk in self.sort_keys:
                summary = f"  {sk.field_name}: order={sk.order}"
                if sk.pic_summary:
                    summary += f" {sk.pic_summary}"
                parts.append(summary)

        if self.record_hierarchy:
            parts.append("\nRECORD HIERARCHY:")
            for rec in self.record_hierarchy:
                self._render_hierarchy(rec, indent=2, parts=parts)

        return "\n".join(parts)

    @staticmethod
    def _render_hierarchy(f: COBOLFieldInfo, indent: int, parts: list[str]) -> None:
        prefix = " " * indent
        pic_str = f" PIC {f.pic}" if f.pic else ""
        parts.append(f"{prefix}{f.level:02d} {f.name}{pic_str}")
        for child in f.children:
            COBOLMetadata._render_hierarchy(child, indent + 4, parts)


@dataclass
class ParseResult:
    """Container for all entities extracted from a single file."""
    file_path: str
    language: str
    functions: list[FunctionInfo] = field(default_factory=list)
    imports: list[str] = field(default_factory=list)
    classes: list[str] = field(default_factory=list)
    cobol_metadata: Optional[COBOLMetadata] = None
    # Cross-file reference tracking (Phase 1)
    external_calls: list[str] = field(default_factory=list)
    inherited_classes: list[str] = field(default_factory=list)
    config_reads: list[str] = field(default_factory=list)
    output_writes: list[str] = field(default_factory=list)


class ASTParser:
    """Language-aware source-code parser that extracts structural information."""

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def parse(self, source: str, file_path: str, language: str) -> ParseResult:
        """
        Parse *source* and return structured metadata.

        Dispatches to the appropriate language-specific parser.
        """
        handler = {
            "python": self._parse_python,
            "java": self._parse_java,
            "cobol": self._parse_cobol,
        }.get(language, self._parse_generic)

        try:
            return handler(source, file_path, language)
        except Exception as exc:
            logger.warning("Parsing failed for %s: %s", file_path, exc)
            return ParseResult(file_path=file_path, language=language)

    # ------------------------------------------------------------------
    # Python parser (full AST)
    # ------------------------------------------------------------------

    def _parse_python(self, source: str, file_path: str, language: str) -> ParseResult:
        result = ParseResult(file_path=file_path, language=language)
        tree = ast.parse(source, filename=file_path)
        lines = source.splitlines()

        for node in ast.walk(tree):
            # Imports
            if isinstance(node, (ast.Import, ast.ImportFrom)):
                for alias in node.names:
                    result.imports.append(alias.name)

            # Classes
            elif isinstance(node, ast.ClassDef):
                result.classes.append(node.name)

            # Functions / methods
            elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                calls = self._extract_python_calls(node)
                start = node.lineno - 1
                end = node.end_lineno if node.end_lineno else start + 1
                body = "\n".join(lines[start:end])

                result.functions.append(FunctionInfo(
                    name=node.name,
                    file_path=file_path,
                    start_line=node.lineno,
                    end_line=end,
                    calls=calls,
                    language=language,
                    body=body,
                ))

        return result

    @staticmethod
    def _extract_python_calls(node: ast.AST) -> list[str]:
        """Walk *node* and collect names of all function calls."""
        calls: list[str] = []
        for child in ast.walk(node):
            if isinstance(child, ast.Call):
                if isinstance(child.func, ast.Name):
                    calls.append(child.func.id)
                elif isinstance(child.func, ast.Attribute):
                    calls.append(child.func.attr)
        return calls

    # ------------------------------------------------------------------
    # Java parser (regex heuristic)
    # ------------------------------------------------------------------

    _JAVA_METHOD_RE = re.compile(
        r"(?:public|private|protected|static|\s)+"
        r"[\w<>\[\]]+\s+"       # return type
        r"(\w+)\s*\([^)]*\)\s*" # method name + params
        r"\{",
        re.MULTILINE,
    )
    _JAVA_CALL_RE = re.compile(r"(\w+)\s*\(")
    _JAVA_IMPORT_RE = re.compile(r"import\s+([\w.]+);")
    _JAVA_CLASS_RE = re.compile(r"class\s+(\w+)")
    _JAVA_EXTENDS_RE = re.compile(r"class\s+\w+\s+extends\s+(\w+)")
    _JAVA_IMPLEMENTS_RE = re.compile(r"implements\s+([\w,\s]+)")
    _JAVA_CONFIG_RE = re.compile(
        r'(?:Properties|FileInputStream|getResource|getenv|System\.getProperty)'
        r"""\s*\(\s*["']([^"']+)["']""",
    )

    def _parse_java(self, source: str, file_path: str, language: str) -> ParseResult:
        result = ParseResult(file_path=file_path, language=language)
        lines = source.splitlines()

        result.imports = self._JAVA_IMPORT_RE.findall(source)
        result.classes = self._JAVA_CLASS_RE.findall(source)

        # Cross-file references: inheritance
        result.inherited_classes = self._JAVA_EXTENDS_RE.findall(source)
        for m in self._JAVA_IMPLEMENTS_RE.finditer(source):
            ifaces = [i.strip() for i in m.group(1).split(",") if i.strip()]
            result.inherited_classes.extend(ifaces)

        # Cross-file references: config reads
        result.config_reads = self._JAVA_CONFIG_RE.findall(source)

        for m in self._JAVA_METHOD_RE.finditer(source):
            name = m.group(1)
            start_line = source[:m.start()].count("\n") + 1
            # Find matching closing brace (simple brace-counting)
            end_line = self._find_brace_end(lines, start_line - 1)
            body = "\n".join(lines[start_line - 1 : end_line])
            calls = [c for c in self._JAVA_CALL_RE.findall(body) if c != name]

            result.functions.append(FunctionInfo(
                name=name,
                file_path=file_path,
                start_line=start_line,
                end_line=end_line,
                calls=calls,
                language=language,
                body=body,
            ))

        return result

    # ------------------------------------------------------------------
    # COBOL parser (enhanced with structured metadata)
    # ------------------------------------------------------------------

    _COBOL_PROGRAM_ID_RE = re.compile(r"PROGRAM-ID\.\s+([\w-]+)", re.IGNORECASE)
    _COBOL_CALL_RE = re.compile(r"CALL\s+['\"]?([\w-]+)", re.IGNORECASE)
    _COBOL_COPY_RE = re.compile(r"COPY\s+([\w-]+)", re.IGNORECASE)
    _COBOL_PERFORM_RE = re.compile(r"PERFORM\s+([\w-]+)", re.IGNORECASE)

    # FILE-CONTROL: SELECT logical ASSIGN TO physical
    _COBOL_SELECT_RE = re.compile(
        r"SELECT\s+([\w-]+)\s+ASSIGN\s+TO\s+['\"]?([\w-]+)['\"]?",
        re.IGNORECASE,
    )
    _COBOL_ORG_RE = re.compile(
        r"SELECT\s+([\w-]+)\s+.*?ORGANIZATION\s+IS\s+([\w\s]+?)(?:\.|$)",
        re.IGNORECASE | re.DOTALL,
    )

    # DATA DIVISION field with PIC
    _COBOL_FIELD_RE = re.compile(
        r"^\s*(\d{2})\s+([\w-]+)\s+PIC\s+(.+?)\.?\s*$",
        re.IGNORECASE | re.MULTILINE,
    )
    # Group-level entries (no PIC)
    _COBOL_GROUP_RE = re.compile(
        r"^\s*(\d{2})\s+([\w-]+)\s*\.\s*$",
        re.MULTILINE,
    )

    # SORT statement
    _COBOL_SORT_RE = re.compile(
        r"SORT\s+[\w-]+\s+ON\s+(ASCENDING|DESCENDING)\s+KEY\s+([\w-]+)",
        re.IGNORECASE,
    )

    def _parse_cobol(self, source: str, file_path: str, language: str) -> ParseResult:
        result = ParseResult(file_path=file_path, language=language)
        lines = source.splitlines()

        # --- Extract PROGRAM-ID ---
        prog_match = self._COBOL_PROGRAM_ID_RE.search(source)
        prog_name = prog_match.group(1) if prog_match else Path(file_path).stem

        # --- Extract CALL dependencies ---
        calls = list(set(self._COBOL_CALL_RE.findall(source)))

        # --- Extract COPY (cross-file includes) ---
        result.external_calls = list(set(self._COBOL_COPY_RE.findall(source)))

        # --- Extract file output references ---
        result.output_writes = []

        # --- Build COBOLMetadata ---
        metadata = COBOLMetadata(program_id=prog_name)

        # FILE-CONTROL mappings
        for m in self._COBOL_SELECT_RE.finditer(source):
            logical = m.group(1).strip()
            physical = m.group(2).strip()
            metadata.file_control[logical] = physical

        for m in self._COBOL_ORG_RE.finditer(source):
            logical = m.group(1).strip()
            org = m.group(2).strip()
            metadata.file_org[logical] = org

        # Collect all fields (with and without PIC), preserving source order
        # so hierarchy building uses correct nesting.
        position_fields: list[tuple[int, COBOLFieldInfo]] = []

        for m in self._COBOL_FIELD_RE.finditer(source):
            level = int(m.group(1))
            name = m.group(2).strip()
            pic_raw = m.group(3).strip().rstrip(".")
            finfo = self._parse_pic(name, level, pic_raw)
            position_fields.append((m.start(), finfo))

        for m in self._COBOL_GROUP_RE.finditer(source):
            level = int(m.group(1))
            name = m.group(2).strip()
            # Skip division/section headers that match the pattern
            upper = name.upper()
            if any(kw in upper for kw in (
                "DIVISION", "SECTION", "PROCEDURE", "ENVIRONMENT",
                "IDENTIFICATION", "CONFIGURATION", "INPUT-OUTPUT",
                "FILE-CONTROL",
            )):
                continue
            position_fields.append((m.start(), COBOLFieldInfo(
                name=name, level=level, field_type="group",
            )))

        # Sort by source position to get correct document order
        position_fields.sort(key=lambda x: x[0])
        raw_fields = [f for _, f in position_fields]

        metadata.fields = raw_fields
        metadata.record_hierarchy = self._build_hierarchy(raw_fields)

        # SORT keys
        field_lookup = {f.name.upper(): f for f in raw_fields}
        for m in self._COBOL_SORT_RE.finditer(source):
            order = m.group(1).upper()
            key_name = m.group(2).strip()
            fld = field_lookup.get(key_name.upper())
            pic_summary = ""
            fld_type = ""
            if fld:
                fld_type = fld.field_type
                if fld.field_type in ("numeric", "currency"):
                    dec = f".{fld.decimals}" if fld.decimals else ""
                    pic_summary = f"numeric({fld.length}{dec})"
                else:
                    pic_summary = f"{fld.field_type}({fld.length})"
            metadata.sort_keys.append(COBOLSortKey(
                field_name=key_name, order=order,
                field_type=fld_type, pic_summary=pic_summary,
            ))

        result.cobol_metadata = metadata

        # Treat the entire COBOL program as a single contextual unit
        result.functions.append(FunctionInfo(
            name=prog_name,
            file_path=file_path,
            start_line=1,
            end_line=len(lines),
            calls=calls,
            language=language,
            body=source,
        ))

        return result

    # ------------------------------------------------------------------
    # COBOL helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _parse_pic(name: str, level: int, pic_raw: str) -> COBOLFieldInfo:
        """Parse a PIC clause string into a COBOLFieldInfo."""
        pic_upper = pic_raw.upper().replace(" ", "")

        # Detect display / currency format (contains $, Z, *, or commas)
        is_display = bool(re.search(r"[$Z*,]", pic_upper))

        signed = pic_upper.startswith("S")
        decimals = 0
        length = 0

        if is_display:
            # Currency / edit mask — compute display width from raw characters
            # Strip outer parens groupings and count character positions
            expanded = ASTParser._expand_pic(pic_upper)
            length = len(expanded)
            # Decimals: count digits after the decimal point character
            if "." in expanded:
                decimals = len(expanded.split(".")[-1])
            return COBOLFieldInfo(
                name=name, level=level, pic=pic_raw,
                field_type="currency", length=length,
                decimals=decimals, signed=signed,
                display_format=pic_raw,
            )

        # Strip leading S for computation
        core = pic_upper.lstrip("S")

        # Count digits before V (integer part) and after V (decimal part)
        if "V" in core:
            int_part, dec_part = core.split("V", 1)
            decimals = ASTParser._count_positions(dec_part)
        else:
            int_part = core
            decimals = 0

        int_len = ASTParser._count_positions(int_part)
        length = int_len + decimals

        # Determine type
        if re.match(r"^[9()\d]+$", int_part):
            ftype = "numeric"
        elif re.match(r"^[A()\d]+$", int_part):
            ftype = "alphabetic"
        else:
            ftype = "alphanumeric"

        return COBOLFieldInfo(
            name=name, level=level, pic=pic_raw,
            field_type=ftype, length=length,
            decimals=decimals, signed=signed,
        )

    @staticmethod
    def _count_positions(pic_fragment: str) -> int:
        """Count the number of character positions in a PIC fragment like '9(5)' or 'XXX'."""
        total = 0
        i = 0
        while i < len(pic_fragment):
            ch = pic_fragment[i]
            if ch in "9XAZ*$":
                # Check for repeat notation: 9(5)
                if i + 1 < len(pic_fragment) and pic_fragment[i + 1] == "(":
                    close = pic_fragment.find(")", i + 2)
                    if close != -1:
                        try:
                            total += int(pic_fragment[i + 2 : close])
                        except ValueError:
                            total += 1
                        i = close + 1
                        continue
                total += 1
            i += 1
        return total

    @staticmethod
    def _expand_pic(pic_upper: str) -> str:
        """
        Expand PIC shorthand like $$(5)9.99 into individual characters
        for display-width calculation.
        """
        result: list[str] = []
        i = 0
        while i < len(pic_upper):
            ch = pic_upper[i]
            if i + 1 < len(pic_upper) and pic_upper[i + 1] == "(":
                close = pic_upper.find(")", i + 2)
                if close != -1:
                    try:
                        count = int(pic_upper[i + 2 : close])
                    except ValueError:
                        count = 1
                    result.append(ch * count)
                    i = close + 1
                    continue
            result.append(ch)
            i += 1
        return "".join(result)

    @staticmethod
    def _build_hierarchy(fields: list[COBOLFieldInfo]) -> list[COBOLFieldInfo]:
        """
        Build a nested tree from the flat list of fields using COBOL level numbers.
        Returns top-level (01) records with children populated.
        """
        import copy
        if not fields:
            return []

        # Deep copy so we don't mutate originals
        items = [copy.deepcopy(f) for f in fields]

        roots: list[COBOLFieldInfo] = []
        stack: list[COBOLFieldInfo] = []

        for item in items:
            item.children = []  # reset for fresh build

            # Pop stack until we find a parent with a lower level number
            while stack and stack[-1].level >= item.level:
                stack.pop()

            if stack:
                stack[-1].children.append(item)
            else:
                roots.append(item)

            stack.append(item)

        return roots

    # ------------------------------------------------------------------
    # Generic / fallback parser
    # ------------------------------------------------------------------

    _GENERIC_FUNC_RE = re.compile(
        r"(?:func|function|def|sub|procedure)\s+(\w+)", re.IGNORECASE
    )

    def _parse_generic(self, source: str, file_path: str, language: str) -> ParseResult:
        result = ParseResult(file_path=file_path, language=language)
        for m in self._GENERIC_FUNC_RE.finditer(source):
            start = source[:m.start()].count("\n") + 1
            result.functions.append(FunctionInfo(
                name=m.group(1),
                file_path=file_path,
                start_line=start,
                end_line=start,
                language=language,
            ))
        return result

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _find_brace_end(lines: list[str], start_idx: int) -> int:
        """Return the 1-based line number of the closing brace."""
        depth = 0
        for i in range(start_idx, len(lines)):
            depth += lines[i].count("{") - lines[i].count("}")
            if depth <= 0:
                return i + 1
        return len(lines)
