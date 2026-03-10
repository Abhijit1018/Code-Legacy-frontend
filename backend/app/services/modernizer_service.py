"""
ModernizerService — thin service layer that adapts `CodeGenerator`
from legacy_modernizer into the FastAPI response schemas.
"""

from __future__ import annotations

import os
import logging

from legacy_modernizer.transformation.code_generator import CodeGenerator
from legacy_modernizer.transformation.result_formatter import ResultFormatter

from backend.app.schemas.responses import (
    ModernizationResponse,
    StatsResponse,
    ResultsResponse,
    LLMInfoResponse,
)

logger = logging.getLogger(__name__)


class ModernizerService:
    """
    Service consumed by the API routes.

    Reads API keys from environment variables (loaded via python-dotenv
    in main.py) and delegates to `CodeGenerator`.
    """

    def __init__(self):
        self._scaledown_key = os.getenv("SCALEDOWN_API_KEY", "")
        self._openrouter_key = os.getenv("OPENROUTER_API_KEY", "")

    # ------------------------------------------------------------------
    # Public methods
    # ------------------------------------------------------------------

    def analyze_repo(
        self,
        repo_url: str,
        branch: str = "main",
        target_language: str = "python",
        compression_rate: float = 0.5,
        llm_model: str = "deepseek/deepseek-chat-v3-0324",
        temperature: float = 0.2,
        max_tokens: int = 4096,
        remove_comments: bool = True,
        remove_tests: bool = True,
        github_token: str = "",
        additional_instructions: str = "",
    ) -> ModernizationResponse:
        gen = self._make_generator(
            compression_rate=compression_rate,
            llm_model=llm_model,
            temperature=temperature,
            max_tokens=max_tokens,
            remove_comments=remove_comments,
            remove_tests=remove_tests,
        )
        result = gen.analyze_repo(
            repo_url, branch=branch, target_language=target_language,
            github_token=github_token, additional_instructions=additional_instructions,
        )
        return self._to_response(result)

    def convert_repo(
        self,
        repo_url: str,
        branch: str = "main",
        target_language: str = "python",
        compression_rate: float = 0.5,
        llm_model: str = "deepseek/deepseek-chat-v3-0324",
        temperature: float = 0.2,
        max_tokens: int = 4096,
        remove_comments: bool = True,
        remove_tests: bool = True,
        github_token: str = "",
        additional_instructions: str = "",
    ) -> ModernizationResponse:
        gen = self._make_generator(
            compression_rate=compression_rate,
            llm_model=llm_model,
            temperature=temperature,
            max_tokens=max_tokens,
            remove_comments=remove_comments,
            remove_tests=remove_tests,
        )
        result = gen.analyze_repo(
            repo_url, branch=branch, target_language=target_language,
            github_token=github_token, additional_instructions=additional_instructions,
        )
        return self._to_response(result)

    def analyze_snippet(
        self,
        code: str,
        language: str = "cobol",
        target_language: str = "python",
        llm_model: str = "deepseek/deepseek-chat-v3-0324",
        temperature: float = 0.2,
        max_tokens: int = 4096,
        compression_rate: float = 0.5,
        additional_instructions: str = "",
    ) -> ModernizationResponse:
        gen = self._make_generator(
            compression_rate=compression_rate,
            llm_model=llm_model,
            temperature=temperature,
            max_tokens=max_tokens,
        )
        result = gen.analyze_code_snippet(
            code, language=language, target_language=target_language,
            additional_instructions=additional_instructions,
        )
        return self._to_response(result)

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _make_generator(
        self,
        compression_rate: float = 0.5,
        llm_model: str = "deepseek/deepseek-chat-v3-0324",
        temperature: float = 0.2,
        max_tokens: int = 4096,
        remove_comments: bool = True,
        remove_tests: bool = True,
    ) -> CodeGenerator:
        return CodeGenerator(
            scaledown_api_key=self._scaledown_key,
            openrouter_api_key=self._openrouter_key,
            compression_rate=compression_rate,
            llm_model=llm_model,
            temperature=temperature,
            max_tokens=max_tokens,
            remove_comments=remove_comments,
            remove_tests=remove_tests,
        )

    @staticmethod
    def _to_response(result) -> ModernizationResponse:
        d = ResultFormatter.to_dict(result)
        return ModernizationResponse(
            repo_url=d["repo_url"],
            stats=StatsResponse(**d["stats"]),
            results=ResultsResponse(**d["results"]),
            llm=LLMInfoResponse(**d["llm"]),
        )
