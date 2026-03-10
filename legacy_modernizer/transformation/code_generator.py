"""
CodeGenerator — end-to-end orchestrator that drives the full
ingestion → analysis → context → compression → LLM pipeline.
"""

from __future__ import annotations

import logging
from pathlib import Path
from dataclasses import dataclass, field

from legacy_modernizer.ingestion import RepoCloner, FileScanner
from legacy_modernizer.ingestion.file_scanner import ScanResult
from legacy_modernizer.analysis import ASTParser, DependencyGraph, DeadCodeFilter
from legacy_modernizer.analysis.ast_parser import ParseResult, FunctionInfo
from legacy_modernizer.context import ContextBuilder, ScaledownBridge
from legacy_modernizer.context.context_builder import BuiltContext
from legacy_modernizer.context.scaledown_bridge import CompressionResult
from legacy_modernizer.llm import OpenRouterClient, PromptTemplates
from legacy_modernizer.llm.openrouter_client import LLMResponse

logger = logging.getLogger(__name__)


@dataclass
class FileConversionResult:
    """Result of converting a single legacy file."""
    file_path: str = ""
    program_id: str = ""
    python_code: str = ""
    go_code: str = ""
    summary: str = ""
    documentation: str = ""
    original_code: str = ""
    error: str = ""


@dataclass
class ModernizationResult:
    """Full result of a modernisation run."""
    # Provenance
    repo_url: str = ""
    files_scanned: int = 0
    functions_found: int = 0
    languages_detected: list[str] = field(default_factory=list)

    # Context stats
    context_chars: int = 0
    compressed_chars: int = 0
    compression_savings_percent: float = 0.0

    # LLM output
    summary: str = ""
    dependency_explanation: str = ""
    python_code: str = ""
    go_code: str = ""
    original_code: dict[str, str] = field(default_factory=dict)
    documentation: str = ""
    model_used: str = ""
    tokens_used: int = 0

    # Per-file results
    per_file_results: list[FileConversionResult] = field(default_factory=list)


class CodeGenerator:
    """
    Orchestrates the entire legacy-modernisation pipeline:

        clone → scan → parse → dependency graph → dead-code filter
        → context build → Scaledown compress → LLM generate
    """

    def __init__(
        self,
        scaledown_api_key: str | None = None,
        openrouter_api_key: str | None = None,
        llm_model: str = "deepseek/deepseek-chat-v3-0324",
        compression_rate: float = 0.5,
        temperature: float = 0.2,
        max_tokens: int = 4096,
        remove_comments: bool = True,
        remove_tests: bool = True,
    ):
        self.cloner = RepoCloner()
        self.scanner = FileScanner()
        self.parser = ASTParser()
        self.dead_code_filter = DeadCodeFilter(
            remove_comments=remove_comments,
            remove_tests=remove_tests,
        )
        self.context_builder = ContextBuilder()
        self.scaledown = ScaledownBridge(
            api_key=scaledown_api_key,
            rate=compression_rate,
        )
        self.llm = OpenRouterClient(
            api_key=openrouter_api_key,
            model=llm_model,
            temperature=temperature,
            max_tokens=max_tokens,
        )

    # ------------------------------------------------------------------
    # Top-level entry points
    # ------------------------------------------------------------------

    def analyze_repo(self, repo_url: str, branch: str = "main", target_language: str = "python",
                     github_token: str = "", additional_instructions: str = "") -> ModernizationResult:
        """
        Full pipeline: clone → analyse → compress → LLM → result.
        """
        clone_url = repo_url
        if github_token and "github.com" in repo_url:
            # Inject token for private repo access: https://<token>@github.com/...
            clone_url = repo_url.replace("https://", f"https://{github_token}@")
        repo_path = self.cloner.clone(clone_url, branch=branch)
        try:
            return self._process(repo_url, repo_path, target_language=target_language,
                                 additional_instructions=additional_instructions)
        finally:
            self.cloner.cleanup(repo_path)

    def analyze_local(self, path: str | Path, additional_instructions: str = "") -> ModernizationResult:
        """Run the pipeline against an already-local directory."""
        return self._process("local", Path(path), additional_instructions=additional_instructions)

    def analyze_code_snippet(self, code: str, language: str = "python", target_language: str = "python",
                             additional_instructions: str = "") -> ModernizationResult:
        """Run the pipeline on a raw code snippet (skips clone/scan)."""
        context = self.context_builder.build_from_raw_files(
            {"snippet": code}, language=language,
        )
        result = self._compress_and_generate("snippet", context, target_language=target_language,
                                           additional_instructions=additional_instructions)
        result.original_code = {"snippet": code}
        return result

    # ------------------------------------------------------------------
    # Internal pipeline
    # ------------------------------------------------------------------

    def _process(self, repo_url: str, repo_path: Path, target_language: str = "python",
                 additional_instructions: str = "") -> ModernizationResult:
        import re as _re

        # 1. Scan files
        scan: ScanResult = self.scanner.scan(repo_path)
        logger.info("Scanned %d files", scan.total_files)

        # 2. Filter out test files and noise
        cleaned_files, filter_stats = self.dead_code_filter.filter_files(scan.files)
        logger.info(
            "After dead-code filter: %d files (skipped %d)",
            len(cleaned_files), filter_stats.files_skipped,
        )

        # 3. Populate original_code and prepare per-file data
        original_code: dict[str, str] = {}
        for sf in cleaned_files:
            try:
                original_code[sf.relative_path] = sf.read()
            except Exception:
                continue

        # 4. Process each file independently
        per_file_results: list[FileConversionResult] = []
        all_python_parts: list[str] = []
        all_go_parts: list[str] = []
        all_summaries: list[str] = []
        all_docs: list[str] = []
        total_tokens = 0
        model_used = ""

        for sf in cleaned_files:
            file_result = FileConversionResult(file_path=sf.relative_path)

            try:
                raw_source = sf.read()
                cleaned_source, _ = self.dead_code_filter.clean_source(raw_source, sf.language)

                # Extract PROGRAM-ID for naming
                prog_match = _re.search(r"PROGRAM-ID\.\s+([\w-]+)", raw_source, _re.IGNORECASE)
                file_result.program_id = prog_match.group(1) if prog_match else Path(sf.relative_path).stem
                file_result.original_code = raw_source

                # Build single-file context
                single_context = self.context_builder.build_from_raw_files(
                    {sf.relative_path: cleaned_source},
                    language=sf.language,
                )

                # Compress and generate for this single file
                single_result = self._compress_and_generate(
                    repo_url, single_context,
                    target_language=target_language,
                    additional_instructions=additional_instructions,
                )

                file_result.python_code = single_result.python_code
                file_result.go_code = single_result.go_code
                file_result.summary = single_result.summary
                file_result.documentation = single_result.documentation
                total_tokens += single_result.tokens_used
                model_used = single_result.model_used

                # Accumulate for combined output
                if single_result.python_code:
                    header = f"# === {file_result.program_id} (from {sf.relative_path}) ===\n"
                    all_python_parts.append(header + single_result.python_code)
                if single_result.go_code:
                    header = f"// === {file_result.program_id} (from {sf.relative_path}) ===\n"
                    all_go_parts.append(header + single_result.go_code)
                if single_result.summary:
                    all_summaries.append(f"**{file_result.program_id}**: {single_result.summary}")
                if single_result.documentation:
                    all_docs.append(single_result.documentation)

                logger.info("Successfully converted %s (%s)", sf.relative_path, file_result.program_id)

            except Exception as exc:
                file_result.error = str(exc)
                logger.error("Failed to convert %s: %s", sf.relative_path, exc)

            per_file_results.append(file_result)

        # 5. Build combined result
        result = ModernizationResult(repo_url=repo_url)
        result.files_scanned = scan.total_files
        result.functions_found = len(cleaned_files)
        result.languages_detected = list(scan.language_stats.keys())
        result.original_code = original_code
        result.per_file_results = per_file_results
        result.model_used = model_used
        result.tokens_used = total_tokens

        # Combined outputs
        result.summary = "\n\n".join(all_summaries) if all_summaries else "No programs detected."
        result.python_code = "\n\n\n".join(all_python_parts)
        result.go_code = "\n\n\n".join(all_go_parts)
        result.documentation = "\n\n---\n\n".join(all_docs)
        result.dependency_explanation = (
            f"Repository contains {len(per_file_results)} independent program(s). "
            f"Each was converted separately to preserve isolated program logic."
        )

        # Context stats (sum of all)
        result.context_chars = sum(len(fr.original_code) for fr in per_file_results)
        result.compressed_chars = result.context_chars  # raw context used
        result.compression_savings_percent = 0.0

        return result

    def _compress_and_generate(
        self, repo_url: str, context: BuiltContext, target_language: str = "python",
        additional_instructions: str = "",
    ) -> ModernizationResult:
        result = ModernizationResult(repo_url=repo_url)
        result.context_chars = len(context.text)

        # 5. Compress via Scaledown
        if result.context_chars < 50000:
            logger.info("Context is small enough (%d chars), skipping Scaledown compression to preserve logic", result.context_chars)
            llm_input = context.text
            result.compressed_chars = len(llm_input)
            result.compression_savings_percent = 0.0
        else:
            try:
                target_prompt = (
                    f"Convert this legacy code to modern {target_language.capitalize()}. "
                    f"Ensure the complete workflow logic, data divisions, and procedure logic are fully preserved."
                )
                if additional_instructions:
                    target_prompt += f" {additional_instructions}"
                compressed: CompressionResult = self.scaledown.compress(
                    context.text,
                    prompt=target_prompt
                )
                llm_input = compressed.compressed_text
                result.compressed_chars = len(llm_input)
                result.compression_savings_percent = compressed.savings_percent
            except Exception as exc:
                logger.warning("Scaledown compression failed (%s) — sending raw context", exc)
                llm_input = context.text
                result.compressed_chars = len(llm_input)

        # 6. Call LLM
        try:
            system = PromptTemplates.system_prompt(target_language)
            if additional_instructions:
                system += f"\n\nAdditional instructions from the user:\n{additional_instructions}"
            llm_resp: LLMResponse = self.llm.generate(
                system_prompt=system,
                user_prompt=PromptTemplates.analyze_prompt(llm_input, target_language),
            )
            result.summary = llm_resp.summary
            result.dependency_explanation = llm_resp.dependency_explanation
            result.python_code = llm_resp.python_code
            result.go_code = llm_resp.go_code
            result.documentation = llm_resp.documentation
            result.model_used = llm_resp.model_used
            result.tokens_used = llm_resp.tokens_used
        except Exception as exc:
            logger.error("LLM generation failed: %s", exc)
            result.summary = f"LLM generation failed: {exc}"

        return result
