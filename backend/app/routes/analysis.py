"""
analysis.py — API routes for repository analysis and conversion.

Endpoints:
    POST /api/analyze-repo   — analyse a GitHub repo and return modern code
    POST /api/convert-repo   — alias with explicit target-language support
    POST /api/analyze-snippet — analyse a raw code snippet
"""

from fastapi import APIRouter, HTTPException
import logging

from backend.app.schemas.requests import (
    AnalyzeRepoRequest,
    ConvertRepoRequest,
    AnalyzeSnippetRequest,
)
from backend.app.schemas.responses import ModernizationResponse, HealthResponse
from backend.app.services.modernizer_service import ModernizerService

logger = logging.getLogger(__name__)
router = APIRouter()

# Singleton service instance
_service = ModernizerService()


@router.post("/analyze-repo", response_model=ModernizationResponse)
async def analyze_repo(req: AnalyzeRepoRequest):
    """
    Clone a GitHub repository, analyse its legacy code, compress context
    via Scaledown, and generate modern Python/Go equivalents via an LLM.
    """
    try:
        result = _service.analyze_repo(
            repo_url=req.repo_url,
            branch=req.branch,
            target_language=req.target_language,
            compression_rate=req.compression_rate,
            llm_model=req.llm_model,
            temperature=req.temperature,
            max_tokens=req.max_tokens,
            remove_comments=req.remove_comments,
            remove_tests=req.remove_tests,
            github_token=req.github_token,
            additional_instructions=req.additional_instructions,
        )
        return result
    except Exception as exc:
        logger.exception("analyze-repo failed")
        raise HTTPException(status_code=500, detail=str(exc))


@router.post("/convert-repo", response_model=ModernizationResponse)
async def convert_repo(req: ConvertRepoRequest):
    """
    Same as analyze-repo but allows specifying a target language and
    compression rate.
    """
    try:
        result = _service.convert_repo(
            repo_url=req.repo_url,
            branch=req.branch,
            target_language=req.target_language,
            compression_rate=req.compression_rate,
            llm_model=req.llm_model,
            temperature=req.temperature,
            max_tokens=req.max_tokens,
            remove_comments=req.remove_comments,
            remove_tests=req.remove_tests,
            github_token=req.github_token,
            additional_instructions=req.additional_instructions,
        )
        return result
    except Exception as exc:
        logger.exception("convert-repo failed")
        raise HTTPException(status_code=500, detail=str(exc))


@router.post("/analyze-snippet", response_model=ModernizationResponse)
async def analyze_snippet(req: AnalyzeSnippetRequest):
    """Analyse a raw code snippet without cloning a repository."""
    try:
        result = _service.analyze_snippet(
            code=req.code,
            language=req.language,
            target_language=req.target_language,
            llm_model=req.llm_model,
            temperature=req.temperature,
            max_tokens=req.max_tokens,
            compression_rate=req.compression_rate,
            additional_instructions=req.additional_instructions,
        )
        return result
    except Exception as exc:
        logger.exception("analyze-snippet failed")
        raise HTTPException(status_code=500, detail=str(exc))
