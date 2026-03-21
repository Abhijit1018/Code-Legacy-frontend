"""
PromptTemplates — system and user prompt templates for the LLM.

All prompts instruct the model to return structured JSON so that the
response can be parsed deterministically.
"""

from __future__ import annotations


class PromptTemplates:
    """Collection of prompt templates used by the modernisation pipeline."""

    # ------------------------------------------------------------------
    # System prompt
    # ------------------------------------------------------------------

    _SYSTEM_TEMPLATE = """\
You are an expert legacy-code modernisation assistant.

You will receive optimised context extracted from a legacy codebase.
Before performing any translation, you must analyze the workflow of the repository, identify which files represent executable programs versus data structures, and detect dependencies.

Your job is to:
1. Summarise the overall workflow and what the legacy code does.
2. Explain dependencies between functions/modules.
3. Produce a modern **{target_language}** equivalent that preserves the actual logic.
4. Write developer documentation.

**Translation Rules for COBOL (if applicable)**:
- Do NOT convert field definitions blindly into meaningless classes. Interpret the complete program workflow.
- IDENTIFICATION DIVISION → map to module metadata or docstrings.
- DATA DIVISION → map to data structures (e.g., dataclasses, structs, or dictionaries).
- WORKING-STORAGE → extract all variables, hardcoded constants, and hardcoded nested JSON strings accurately. Preserve them in modern variables.
- PROCEDURE DIVISION → map to the explicit executable program functions, keeping the sequential operations and logic exactly intact.
- COBOL FILE operations → map to modern file handling or structured data processing.
- COBOL DISPLAY → map to standard `print()` or logging statements including string formatting.
- COBOL JSON PARSE → map to native JSON parsing (e.g., `json.loads()`). Extract the nested fields completely.
- OCCURS arrays → map to Python lists or Go slices.
- COBOL loops and record access → map to native Python/Go loops (e.g., iterating through parsed JSON arrays).
- COBOL SORT/MERGE → use modern sorting and merging operations on lists/arrays.
- Ensure the complete procedural behavior of the original program is preserved. Do not ignore structural blocks, variables, loop logic, or generate partial fragments/placeholders.

**Using COBOL Metadata Headers (if present)**:
The input context may contain structured COBOL metadata headers before the source code. These headers include:
- **PROGRAM-ID**: The program identifier — use this for module/class naming.
- **FILE-CONTROL mappings**: Logical file names mapped to physical file paths and their organization (e.g., LINE SEQUENTIAL). Use these as the authoritative source for file I/O operations — open the physical file name, not the logical name.
- **DATA FIELDS**: Pre-parsed PIC clause information including type (numeric, alphanumeric, alphabetic, currency), length, decimal positions, and signedness. Use these as the authoritative source for variable types and formatting — do not re-interpret PIC clauses yourself.
- **SORT KEYS**: Field names used in SORT statements with their data types. If a sort key is numeric, sort numerically (not lexicographically).
- **RECORD HIERARCHY**: The nested structure of COBOL records (level 01, 05, 10, etc.). Map group items to classes/dataclasses and elementary items to fields with correct types and sizes.
When these metadata headers are present, treat them as ground truth for field types, file mappings, numeric precision, and record structure. Do not contradict the metadata with your own interpretation of the raw PIC clauses.

**Response format — reply with a single JSON object** (no extra text):

```json
{{
  "summary": "<plain-English summary of the complete workflow and functionality>",
  "dependency_explanation": "<detailed explanation of how functions/modules/data depend on each other>",
  "python_code": "<complete modern Python implementation or empty string if not requested>",
  "go_code": "<complete modern Go implementation or empty string if not requested>",
  "documentation": "<developer-facing Markdown documentation capturing the detailed translation logic>"
}}
```

Guidelines:
- Preserve business logic exactly.
- Use idiomatic, production-quality code.
- Add comments explaining non-obvious parts.
- Handle errors gracefully.
- Do NOT hallucinate functionality not present in the original code.
- Only generate code for the requested target language ({target_language}). Set the other language field to an empty string.
"""

    # Keep a class-level constant for backward compat (defaults to Python)
    SYSTEM_PROMPT = _SYSTEM_TEMPLATE.format(target_language="Python")

    @classmethod
    def system_prompt(cls, target_language: str = "python") -> str:
        """Return the system prompt, customised for *target_language*."""
        label = target_language.capitalize()
        return cls._SYSTEM_TEMPLATE.format(target_language=label)

    # ------------------------------------------------------------------
    # User prompt templates
    # ------------------------------------------------------------------

    @staticmethod
    def analyze_prompt(context: str, target_language: str = "python") -> str:
        """Build the user prompt for full analysis + conversion."""
        label = target_language.capitalize()
        return (
            f"Analyse the following legacy code context and convert it to "
            f"modern **{label}**. Produce the JSON response described in "
            f"your instructions.\n\n"
            f"--- BEGIN LEGACY CONTEXT ---\n{context}\n--- END LEGACY CONTEXT ---"
        )

    @staticmethod
    def explain_prompt(context: str) -> str:
        """Build a user prompt requesting explanation only (no code gen)."""
        return (
            "Explain the following legacy code.  Return a JSON object with "
            "the keys 'summary', 'dependency_explanation', and 'documentation'. "
            "Leave 'python_code' and 'go_code' as empty strings.\n\n"
            f"--- BEGIN LEGACY CONTEXT ---\n{context}\n--- END LEGACY CONTEXT ---"
        )

    @staticmethod
    def convert_prompt(context: str, target_language: str = "python") -> str:
        """Build a user prompt requesting conversion to a single target language."""
        return (
            f"Convert the following legacy code to modern **{target_language}**.  "
            "Return the full JSON object with all five keys.\n\n"
            f"--- BEGIN LEGACY CONTEXT ---\n{context}\n--- END LEGACY CONTEXT ---"
        )

    # ------------------------------------------------------------------
    # Phase 2 — Contextual translation prompt
    # ------------------------------------------------------------------

    @staticmethod
    def contextual_translate_prompt(
        source_code: str,
        file_path: str,
        target_language: str,
        philosophy_text: str = "",
        symbol_table_text: str = "",
        translated_deps: dict[str, str] | None = None,
        additional_instructions: str = "",
    ) -> str:
        """
        Build a richly-contextual user prompt for translating a single file.

        Includes:
        1. Repo philosophy (architectural patterns, data flow, etc.)
        2. Global symbol table (types, functions from other files)
        3. Already-translated dependencies (so the model can reference them)
        4. The source code to translate

        This is the primary prompt used in the Phase 2 topological
        translation pipeline.
        """
        sections: list[str] = []

        # 1. Philosophy context
        if philosophy_text:
            sections.append(
                f"[REPO PHILOSOPHY]\n{philosophy_text}\n"
            )

        # 2. Symbol table context
        if symbol_table_text:
            sections.append(
                f"[GLOBAL SYMBOL TABLE]\n{symbol_table_text}\n"
            )

        # 3. Already translated dependencies
        if translated_deps:
            deps_text = ""
            for dep_path, dep_code in translated_deps.items():
                # Cap each dep to prevent token explosion
                snippet = dep_code[:2000]
                if len(dep_code) > 2000:
                    snippet += "\n# ... (truncated)"
                deps_text += f"\n--- {dep_path} ---\n{snippet}\n"

            sections.append(
                f"[ALREADY TRANSLATED DEPENDENCIES]\n"
                f"These files have already been translated. You can reference "
                f"their functions, classes, and imports.\n{deps_text}"
            )

        # 4. Source file to translate
        label = target_language.capitalize()
        sections.append(
            f"[FILE TO TRANSLATE]\n"
            f"File: {file_path}\n"
            f"--- BEGIN SOURCE ---\n{source_code}\n--- END SOURCE ---\n"
        )

        # 5. Instructions
        instructions = (
            f"[INSTRUCTIONS]\n"
            f"Translate this file to modern **{label}**.\n"
            f"- Preserve ALL business logic exactly.\n"
            f"- Use the symbol table to correctly import/reference external types.\n"
            f"- Use translated dependencies to ensure consistent function signatures.\n"
            f"- Return the JSON response with all five keys.\n"
        )
        if additional_instructions:
            instructions += f"- Additional: {additional_instructions}\n"

        sections.append(instructions)

        return "\n".join(sections)
