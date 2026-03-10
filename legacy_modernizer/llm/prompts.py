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
