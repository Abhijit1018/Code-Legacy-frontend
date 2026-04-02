"""
CodeGenerator — end-to-end orchestrator that drives the full
ingestion → analysis → context → compression → LLM pipeline.

Phase 2 rewrite: topological ordering, contextual prompts,
post-translation validation with retry.
"""

from __future__ import annotations

import re as _re
import time
import logging
from pathlib import Path
from dataclasses import dataclass, field

from legacy_modernizer.ingestion import RepoCloner, FileScanner
from legacy_modernizer.ingestion.file_scanner import ScanResult
from legacy_modernizer.analysis import ASTParser, DependencyGraph, DeadCodeFilter
from legacy_modernizer.analysis.ast_parser import ParseResult, FunctionInfo
from legacy_modernizer.analysis.repo_analyzer import RepoAnalyzer, RepoAnalysis
from legacy_modernizer.context import ContextBuilder, ScaledownBridge
from legacy_modernizer.context.context_builder import BuiltContext
from legacy_modernizer.context.scaledown_bridge import CompressionResult
from legacy_modernizer.llm import OpenRouterClient, PromptTemplates
from legacy_modernizer.llm.openrouter_client import LLMResponse
from legacy_modernizer.transformation.validator import (
    TranslationValidator,
    FileValidationResult,
)

logger = logging.getLogger(__name__)

MAX_VALIDATION_RETRIES = 2


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
    validation: FileValidationResult | None = None


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

    # Phase 1 outputs
    repo_philosophy: dict = field(default_factory=dict)
    dependency_graph_json: dict = field(default_factory=dict)
    file_mapping: dict[str, str] = field(default_factory=dict)

    # Phase 2 outputs
    validation_results: list[FileValidationResult] = field(default_factory=list)

    # Phase 3 outputs (populated later)
    workflow_files: list = field(default_factory=list)


class CodeGenerator:
    """
    Orchestrates the entire legacy-modernisation pipeline:

        clone → scan → repo analysis → topological translate
        → validate → retry → result
    """

    def __init__(
        self,
        scaledown_api_key: str | None = None,
        openrouter_api_key: str | None = None,
        llm_model: str = "nvidia/nemotron-3-super-120b-a12b:free",
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
        self.validator = TranslationValidator()
        self._remove_comments = remove_comments
        self._remove_tests = remove_tests

    # ------------------------------------------------------------------
    # Helper: LLM callable for RepoAnalyzer
    # ------------------------------------------------------------------

    def _llm_fn(self, system_prompt: str, user_prompt: str) -> str:
        """Wrapper matching the callable signature RepoAnalyzer expects."""
        resp: LLMResponse = self.llm.generate(
            system_prompt=system_prompt,
            user_prompt=user_prompt,
        )
        return resp.raw_text if hasattr(resp, 'raw_text') else resp.summary

    # ------------------------------------------------------------------
    # Top-level entry points
    # ------------------------------------------------------------------

    def analyze_repo(self, repo_url: str, branch: str = "main", target_language: str = "python",
                     github_token: str = "", additional_instructions: str = "") -> ModernizationResult:  # type: ignore[return]
        """
        Full pipeline: clone → analyse → compress → LLM → result.
        """
        clone_url = repo_url
        if github_token and "github.com" in repo_url:
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
    # Internal pipeline (Phase 2 rewrite)
    # ------------------------------------------------------------------

    def _process(self, repo_url: str, repo_path: Path, target_language: str = "python",
                 additional_instructions: str = "") -> ModernizationResult:
        # 1. Scan files
        scan: ScanResult = self.scanner.scan(repo_path)
        logger.info("Scanned %d files", scan.total_files)

        # 2. Run Phase 1 analysis (NEW)
        analyzer = RepoAnalyzer(
            llm_fn=self._llm_fn,
            remove_comments=self._remove_comments,
            remove_tests=self._remove_tests,
        )
        analysis: RepoAnalysis = analyzer.analyze(scan)

        # 3. Populate original_code
        original_code: dict[str, str] = {}
        for sf in analysis.source_files:
            try:
                original_code[sf.relative_path] = sf.read()
            except Exception:
                continue

        # 4. Translate in topological order (NEW)
        per_file_results: list[FileConversionResult] = []
        all_python_parts: list[str] = []
        all_go_parts: list[str] = []
        all_summaries: list[str] = []
        all_docs: list[str] = []
        all_validations: list[FileValidationResult] = []
        total_tokens = 0
        model_used = ""

        # Track already-translated code for contextual prompts
        translated_code: dict[str, str] = {}

        # Get philosophy and symbol table text for prompts
        philosophy_text = ""
        symbol_table_text = ""
        if analysis.philosophy:
            philosophy_text = analysis.philosophy.render_for_prompt()
        if analysis.symbol_table:
            symbol_table_text = analysis.symbol_table.render_for_prompt()

        # File mapping: old path → new path
        file_mapping: dict[str, str] = {}

        for file_path in analysis.translation_order:
            # Phase 6: Stagger requests for free tiers
            time.sleep(1)
            
            # Find the source file and content
            source_code = analysis.file_contents.get(file_path, "")
            if not source_code:
                continue

            file_result = FileConversionResult(file_path=str(file_path))

            try:
                # Get original raw source for display
                file_result.original_code = original_code.get(str(file_path), "") or source_code

                # Extract PROGRAM-ID for naming
                prog_match = _re.search(
                    r"PROGRAM-ID\.\s+([\w-]+)", file_result.original_code, _re.IGNORECASE,
                )
                file_result.program_id = (
                    prog_match.group(1) if prog_match else Path(str(file_path)).stem
                )

                # Get dependencies that have already been translated
                dep_files = []
                if analysis.file_dependency_graph:
                    dep_files = analysis.file_dependency_graph.get_dependencies(file_path)
                translated_deps = {
                    dep: translated_code[dep]  # type: ignore[index]
                    for dep in dep_files
                    if dep in translated_code  # type: ignore[operator]
                }

                # Build contextual prompt (Phase 2.2 — NEW)
                relevant_files = [file_path] + dep_files
                symbol_subset = ""
                if analysis.symbol_table:
                    symbol_subset = analysis.symbol_table.render_for_prompt(relevant_files)

                user_prompt = PromptTemplates.contextual_translate_prompt(
                    source_code=source_code,
                    file_path=file_path,
                    target_language=target_language,
                    philosophy_text=philosophy_text,
                    symbol_table_text=symbol_subset or symbol_table_text,
                    translated_deps=translated_deps,
                    additional_instructions=additional_instructions,
                )

                # Call LLM
                system = PromptTemplates.system_prompt(target_language)
                if additional_instructions:
                    system += f"\n\nAdditional instructions from the user:\n{additional_instructions}"

                llm_resp: LLMResponse = self.llm.generate(  # type: ignore[attr-defined]
                    system_prompt=system,
                    user_prompt=user_prompt,
                )

                file_result.python_code = llm_resp.python_code
                file_result.go_code = llm_resp.go_code
                file_result.summary = llm_resp.summary
                file_result.documentation = llm_resp.documentation
                total_tokens += llm_resp.tokens_used  # type: ignore[operator]
                model_used = llm_resp.model_used

                # Phase 2.3 — Post-translation validation with retry (NEW)
                generated_code = (
                    llm_resp.python_code if target_language == "python"
                    else llm_resp.go_code
                )
                if generated_code:
                    validation = self.validator.validate(  # type: ignore[attr-defined]
                        generated_code, target_language, file_path,
                    )

                    # Retry loop
                    retry_count = 0
                    while not validation.passed and retry_count < MAX_VALIDATION_RETRIES:
                        retry_count += 1
                        logger.info(
                            "Validation failed for %s (retry %d/%d)",
                            file_path, retry_count, MAX_VALIDATION_RETRIES,
                        )
                        fix_prompt = self.validator.build_fix_prompt(  # type: ignore[attr-defined]
                            generated_code, validation,
                        )
                        fix_resp = self.llm.generate(  # type: ignore[attr-defined]
                            system_prompt=system,
                            user_prompt=fix_prompt,
                        )
                        # Extract the fixed code
                        fixed_code = (
                            fix_resp.python_code if target_language == "python"
                            else fix_resp.go_code
                        )
                        if not fixed_code:
                            # Model returned raw code instead of JSON
                            fixed_code = fix_resp.raw_text if hasattr(fix_resp, 'raw_text') else ""
                        if fixed_code:
                            generated_code = fixed_code
                            if target_language == "python":
                                file_result.python_code = fixed_code
                            else:
                                file_result.go_code = fixed_code
                            total_tokens += fix_resp.tokens_used
                        validation = self.validator.validate(
                            generated_code, target_language, file_path,
                        )
                        validation.retry_count = retry_count

                    file_result.validation = validation
                    all_validations.append(validation)

                # Track translated code for subsequent files
                translated_output = file_result.python_code or file_result.go_code
                if translated_output:
                    translated_code[str(file_path)] = translated_output

                # Generate new file path
                ext = ".py" if target_language == "python" else ".go"
                new_name = file_result.program_id.lower().replace("-", "_") + ext
                file_mapping[str(file_path)] = new_name

                # Accumulate for combined output
                if file_result.python_code:
                    header = f"# === {file_result.program_id} (from {file_path}) ===\n"
                    all_python_parts.append(header + file_result.python_code)
                if file_result.go_code:
                    header = f"// === {file_result.program_id} (from {file_path}) ===\n"
                    all_go_parts.append(header + file_result.go_code)
                if file_result.summary:
                    all_summaries.append(f"**{file_result.program_id}**: {file_result.summary}")
                if file_result.documentation:
                    all_docs.append(file_result.documentation)

                logger.info(
                    "Translated %s (%s) — validation: %s",
                    file_path, file_result.program_id,
                    "PASSED" if (file_result.validation and file_result.validation.passed) else "FAILED/SKIPPED",
                )

            except Exception as exc:
                file_result.error = str(exc)
                logger.error("Failed to convert %s: %s", file_path, exc)

            per_file_results.append(file_result)

        # 5. Build combined result
        result = ModernizationResult(repo_url=repo_url)
        result.files_scanned = scan.total_files
        result.functions_found = len(analysis.source_files)
        result.languages_detected = list(scan.language_stats.keys())
        result.original_code = original_code
        result.per_file_results = per_file_results
        result.model_used = model_used
        result.tokens_used = total_tokens

        # Phase 1 outputs
        if analysis.philosophy:
            result.repo_philosophy = analysis.philosophy.to_dict()
        if analysis.file_dependency_graph:
            result.dependency_graph_json = analysis.file_dependency_graph.to_adjacency_json()
        result.file_mapping = file_mapping

        # Phase 2 outputs
        result.validation_results = all_validations

        # Combined outputs
        if all_summaries:
            result.summary = "\n\n".join(all_summaries)
        elif scan.total_files == 0:
            result.summary = (
                "No supported source files were detected in the repository. "
                "Supported extensions include .cbl/.cob, .java, .py, .go, .c/.cpp, and .f90."
            )
        elif per_file_results and not (all_python_parts or all_go_parts):
            first_error = next((fr.error for fr in per_file_results if fr.error), "Unknown error")
            result.summary = (
                f"Detected {len(per_file_results)} source file(s), but conversion failed for all files. "
                f"First error: {first_error}"
            )
        else:
            result.summary = "No programs detected."

        result.python_code = "\n\n\n".join(all_python_parts)
        result.go_code = "\n\n\n".join(all_go_parts)
        result.documentation = "\n\n---\n\n".join(all_docs)

        # Dependency explanation from philosophy
        dep_parts = []
        if analysis.philosophy and analysis.philosophy.primary_data_flow:
            dep_parts.append(f"Data flow: {analysis.philosophy.primary_data_flow}")
        if analysis.file_dependency_graph:
            dep_parts.append(
                f"Dependency graph: {analysis.file_dependency_graph.file_count} files, "
                f"{analysis.file_dependency_graph.edge_count} cross-file relationships."
            )
        dep_parts.append(
            f"Translation order: {len(analysis.translation_order)} files "
            f"processed in topological (leaf-first) order."
        )
        passed = sum(1 for v in all_validations if v.passed)
        dep_parts.append(f"Validation: {passed}/{len(all_validations)} files passed.")
        result.dependency_explanation = " | ".join(dep_parts)

        # Context stats
        result.context_chars = sum(len(c) for c in analysis.file_contents.values())
        result.compressed_chars = result.context_chars
        result.compression_savings_percent = 0.0

        return result

    def _compress_and_generate(
        self, repo_url: str, context: BuiltContext, target_language: str = "python",
        additional_instructions: str = "",
    ) -> ModernizationResult:
        """Compress context and generate via LLM (used for snippets)."""
        result = ModernizationResult(repo_url=repo_url)
        result.context_chars = len(context.text)

        # Compress via Scaledown
        if result.context_chars < 50000:
            logger.info(
                "Context is small enough (%d chars), skipping Scaledown",
                result.context_chars,
            )
            llm_input = context.text
            result.compressed_chars = len(llm_input)
            result.compression_savings_percent = 0.0
        else:
            try:
                target_prompt = (
                    f"Convert this legacy code to modern {target_language.capitalize()}. "
                    f"Ensure the complete workflow logic is fully preserved."
                )
                if additional_instructions:
                    target_prompt += f" {additional_instructions}"
                compressed: CompressionResult = self.scaledown.compress(
                    context.text, prompt=target_prompt,
                )
                llm_input = compressed.compressed_text
                result.compressed_chars = len(llm_input)
                result.compression_savings_percent = compressed.savings_percent
            except Exception as exc:
                logger.warning("Scaledown failed (%s) — sending raw context", exc)
                llm_input = context.text
                result.compressed_chars = len(llm_input)

        # Call LLM
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
