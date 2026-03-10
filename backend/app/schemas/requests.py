"""
Request schemas for the Legacy Modernizer API.
"""

from pydantic import BaseModel, Field


class AnalyzeRepoRequest(BaseModel):
    """Request body for POST /api/analyze-repo."""

    repo_url: str = Field(
        ...,
        description="GitHub repository URL (HTTPS).",
        examples=["https://github.com/owner/legacy-app"],
    )
    branch: str = Field(
        default="main",
        description="Branch to clone.",
    )
    target_language: str = Field(
        default="python",
        description="Target language for conversion (python or go).",
    )
    compression_rate: float = Field(
        default=0.5,
        ge=0.1,
        le=1.0,
        description="Scaledown compression rate (0.1 = aggressive, 1.0 = none).",
    )
    llm_model: str = Field(
        default="deepseek/deepseek-chat-v3-0324",
        description="LLM model to use via OpenRouter.",
    )
    temperature: float = Field(
        default=0.2,
        ge=0.0,
        le=2.0,
        description="LLM sampling temperature (0 = deterministic, higher = more creative).",
    )
    max_tokens: int = Field(
        default=4096,
        ge=256,
        le=32768,
        description="Maximum tokens in the LLM response.",
    )
    remove_comments: bool = Field(
        default=True,
        description="Strip comments from source code before analysis.",
    )
    remove_tests: bool = Field(
        default=True,
        description="Exclude test files from analysis.",
    )
    github_token: str = Field(
        default="",
        description="GitHub personal access token for private repositories.",
    )
    additional_instructions: str = Field(
        default="",
        description="Extra instructions for the LLM (e.g. coding style, framework preferences).",
    )


class ConvertRepoRequest(BaseModel):
    """Request body for POST /api/convert-repo."""

    repo_url: str = Field(
        ...,
        description="GitHub repository URL (HTTPS).",
    )
    branch: str = Field(default="main")
    target_language: str = Field(
        default="python",
        description="Target language for conversion (python or go).",
    )
    compression_rate: float = Field(
        default=0.5,
        ge=0.1,
        le=1.0,
        description="Scaledown compression rate (0.1 = aggressive, 1.0 = none).",
    )
    llm_model: str = Field(
        default="deepseek/deepseek-chat-v3-0324",
        description="LLM model to use via OpenRouter.",
    )
    temperature: float = Field(
        default=0.2,
        ge=0.0,
        le=2.0,
        description="LLM sampling temperature.",
    )
    max_tokens: int = Field(
        default=4096,
        ge=256,
        le=32768,
        description="Maximum tokens in the LLM response.",
    )
    remove_comments: bool = Field(
        default=True,
        description="Strip comments from source code before analysis.",
    )
    remove_tests: bool = Field(
        default=True,
        description="Exclude test files from analysis.",
    )
    github_token: str = Field(
        default="",
        description="GitHub personal access token for private repositories.",
    )
    additional_instructions: str = Field(
        default="",
        description="Extra instructions for the LLM.",
    )


class AnalyzeSnippetRequest(BaseModel):
    """Request body for POST /api/analyze-snippet."""

    code: str = Field(
        ...,
        description="Raw legacy source code to analyse.",
    )
    language: str = Field(
        default="cobol",
        description="Language of the code snippet.",
    )
    target_language: str = Field(
        default="python",
        description="Target language for conversion (python or go).",
    )
    llm_model: str = Field(
        default="deepseek/deepseek-chat-v3-0324",
        description="LLM model to use via OpenRouter.",
    )
    temperature: float = Field(
        default=0.2,
        ge=0.0,
        le=2.0,
        description="LLM sampling temperature.",
    )
    max_tokens: int = Field(
        default=4096,
        ge=256,
        le=32768,
        description="Maximum tokens in the LLM response.",
    )
    compression_rate: float = Field(
        default=0.5,
        ge=0.1,
        le=1.0,
        description="Scaledown compression rate.",
    )
    additional_instructions: str = Field(
        default="",
        description="Extra instructions for the LLM.",
    )
