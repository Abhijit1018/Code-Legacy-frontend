"""
PhilosophyExtractor — use an LLM to extract the architectural philosophy
of a legacy repository.

Takes the file dependency graph + a sample of top-level files and prompts
the LLM to produce a structured ``RepoPhilosophy`` analysis containing:
  • Architectural pattern (MVC, layered, pipeline, etc.)
  • Primary data flow
  • Configuration strategy
  • Error handling philosophy
  • Entry points and execution order
  • Domain-specific business logic patterns

The result is serialisable to ``repo_philosophy.json`` and is injected
into every subsequent translation prompt.
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)


# ------------------------------------------------------------------
# Data classes
# ------------------------------------------------------------------

@dataclass
class RepoPhilosophy:
    """Structured output from the philosophy extraction LLM call."""
    architectural_pattern: str = ""
    primary_data_flow: str = ""
    configuration_strategy: str = ""
    error_handling_philosophy: str = ""
    entry_points: list[str] = field(default_factory=list)
    domain_patterns: list[str] = field(default_factory=list)
    execution_order: str = ""
    raw_response: str = ""

    def to_dict(self) -> dict:
        return {
            "architectural_pattern": self.architectural_pattern,
            "primary_data_flow": self.primary_data_flow,
            "configuration_strategy": self.configuration_strategy,
            "error_handling_philosophy": self.error_handling_philosophy,
            "entry_points": self.entry_points,
            "domain_patterns": self.domain_patterns,
            "execution_order": self.execution_order,
        }

    def to_json(self, indent: int = 2) -> str:
        return json.dumps(self.to_dict(), indent=indent)

    def render_for_prompt(self) -> str:
        """Render the philosophy as a compact block for LLM context."""
        parts = ["=== REPOSITORY PHILOSOPHY ==="]
        if self.architectural_pattern:
            parts.append(f"Architecture: {self.architectural_pattern}")
        if self.primary_data_flow:
            parts.append(f"Data Flow: {self.primary_data_flow}")
        if self.configuration_strategy:
            parts.append(f"Configuration: {self.configuration_strategy}")
        if self.error_handling_philosophy:
            parts.append(f"Error Handling: {self.error_handling_philosophy}")
        if self.entry_points:
            parts.append(f"Entry Points: {', '.join(self.entry_points)}")
        if self.execution_order:
            parts.append(f"Execution Order: {self.execution_order}")
        if self.domain_patterns:
            parts.append(f"Domain Patterns: {'; '.join(self.domain_patterns)}")
        return "\n".join(parts)


# ------------------------------------------------------------------
# Extraction prompt
# ------------------------------------------------------------------

PHILOSOPHY_SYSTEM_PROMPT = """\
You are a senior software architect. Analyze this repository's structure and extract:
1. The architectural pattern (MVC, layered, event-driven, monolith, microservice, pipeline, etc.)
2. The primary data flow (e.g., "reads batch files → transforms → writes to DB")
3. Configuration strategy (hardcoded, env vars, config files)
4. Error handling philosophy (fail-fast, retry loops, logging strategy)
5. Entry points and execution order
6. Any domain-specific business logic patterns

Return a JSON object with these exact keys:
{
  "architectural_pattern": "...",
  "primary_data_flow": "...",
  "configuration_strategy": "...",
  "error_handling_philosophy": "...",
  "entry_points": ["file1", "file2"],
  "domain_patterns": ["pattern1", "pattern2"],
  "execution_order": "..."
}

Be precise. Return ONLY the JSON object, no additional text.\
"""


# ------------------------------------------------------------------
# Extractor
# ------------------------------------------------------------------

class PhilosophyExtractor:
    """
    Extract repository philosophy using an LLM.

    Accepts an LLM callable (``llm_fn``) with the signature:
        ``llm_fn(system_prompt: str, user_prompt: str) -> str``

    This decouples the extractor from the specific LLM client
    implementation, allowing it to work with both the existing
    ``OpenRouterClient`` and the future ``LLMClient``.
    """

    def __init__(self, llm_fn=None):
        """
        Args:
            llm_fn: Callable(system_prompt, user_prompt) -> raw_text.
                    If None, returns a placeholder philosophy.
        """
        self._llm_fn = llm_fn

    def extract(
        self,
        dependency_graph_json: dict,
        file_samples: dict[str, str],
    ) -> RepoPhilosophy:
        """
        Extract philosophy from the repository.

        Args:
            dependency_graph_json: The file-level dependency graph as
                                   a JSON-serialisable dict.
            file_samples: A dict of ``{file_path: content}`` for the
                          top-level / most important files.
        """
        user_prompt = self._build_user_prompt(dependency_graph_json, file_samples)

        if self._llm_fn is None:
            logger.warning("No LLM function provided; returning placeholder philosophy")
            return RepoPhilosophy(
                architectural_pattern="unknown",
                primary_data_flow="unknown",
            )

        try:
            raw = self._llm_fn(PHILOSOPHY_SYSTEM_PROMPT, user_prompt)
            return self._parse_response(raw)
        except Exception as exc:
            logger.error("Philosophy extraction failed: %s", exc)
            return RepoPhilosophy(raw_response=str(exc))

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _build_user_prompt(
        dep_graph: dict,
        file_samples: dict[str, str],
    ) -> str:
        parts = [
            "=== DEPENDENCY GRAPH ===",
            json.dumps(dep_graph, indent=2)[:8000],  # Cap for token budget
            "\n=== SAMPLE FILES ===",
        ]
        total_chars = 0
        for path, content in sorted(file_samples.items()):
            if total_chars > 12000:
                parts.append(f"\n[... {len(file_samples)} total files, truncated ...]")
                break
            parts.append(f"\n--- {path} ---")
            snippet = content[:2000]
            parts.append(snippet)
            total_chars += len(snippet)

        parts.append("\nAnalyze this repository and return the JSON object.")
        return "\n".join(parts)

    @staticmethod
    def _parse_response(raw_text: str) -> RepoPhilosophy:
        """Parse the LLM JSON response into a RepoPhilosophy."""
        import re
        philosophy = RepoPhilosophy(raw_response=raw_text)

        # Extract JSON from possible markdown fences
        json_str = raw_text
        m = re.search(r"```(?:json)?\s*\n?(\{.*?\})\s*```", raw_text, re.DOTALL)
        if m:
            json_str = m.group(1)
        else:
            m = re.search(r"\{.*\}", raw_text, re.DOTALL)
            if m:
                json_str = m.group(0)

        try:
            obj = json.loads(json_str)
            philosophy.architectural_pattern = obj.get("architectural_pattern", "")
            philosophy.primary_data_flow = obj.get("primary_data_flow", "")
            philosophy.configuration_strategy = obj.get("configuration_strategy", "")
            philosophy.error_handling_philosophy = obj.get("error_handling_philosophy", "")
            philosophy.entry_points = obj.get("entry_points", [])
            philosophy.domain_patterns = obj.get("domain_patterns", [])
            philosophy.execution_order = obj.get("execution_order", "")
        except json.JSONDecodeError:
            logger.warning("Failed to parse philosophy JSON, storing raw response")

        return philosophy
