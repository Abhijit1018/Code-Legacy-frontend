"""
ScaledownBridge — thin adapter between the legacy-modernizer pipeline
and the core Scaledown library.

This module imports Scaledown as a library (never modifies it) and
exposes a simple `compress()` interface.
"""

from __future__ import annotations

import os
import logging
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class CompressionResult:
    """Wrapper around Scaledown compression output."""
    compressed_text: str
    original_tokens: int
    compressed_tokens: int
    compression_ratio: float
    savings_percent: float


class ScaledownBridge:
    """
    Bridge to the Scaledown compression pipeline.

    Uses `ScaleDownCompressor` from the `scaledown` package.
    """

    def __init__(
        self,
        api_key: str | None = None,
        target_model: str = "gpt-4",
        rate: float = 0.5,
    ):
        """
        Args:
            api_key:      Scaledown API key.  Falls back to $SCALEDOWN_API_KEY.
            target_model: Model name passed to Scaledown for token counting.
            rate:         Compression rate (0.0–1.0). Lower = more compression.
        """
        self.api_key = api_key or os.getenv("SCALEDOWN_API_KEY", "")
        self.target_model = target_model
        self.rate = rate

    def compress(self, context: str, prompt: str = "Analyze this legacy code") -> CompressionResult:
        """
        Compress *context* via the Scaledown API and return a
        `CompressionResult`.

        Args:
            context: The raw code context to compress.
            prompt:  A guiding prompt passed alongside the context.
                     The Scaledown API requires both context and prompt.
        """
        if not self.api_key:
            raise ValueError(
                "Scaledown API key missing. Set SCALEDOWN_API_KEY in your "
                ".env file or pass api_key to the constructor."
            )

        # Import scaledown at call-time so the rest of legacy_modernizer
        # can be used even when scaledown extras aren't installed.
        from scaledown.compressor import ScaleDownCompressor  # type: ignore
        from scaledown.exceptions import AuthenticationError, APIError  # type: ignore

        compressor = ScaleDownCompressor(
            target_model=self.target_model,
            rate=self.rate,
            api_key=self.api_key,
        )

        try:
            # ScaleDownCompressor.compress() requires both context AND prompt
            result = compressor.compress(context=context, prompt=prompt)
        except AuthenticationError:
            raise ValueError(
                "Scaledown API key is invalid. Please check SCALEDOWN_API_KEY "
                "in your .env file."
            )
        except APIError as exc:
            raise RuntimeError(f"Scaledown API request failed: {exc}")

        original_tokens, compressed_tokens = result.tokens
        ratio = result.compression_ratio
        savings = result.savings_percent

        logger.info(
            "Scaledown compression: %d → %d tokens (%.1f%% saved)",
            original_tokens, compressed_tokens, savings,
        )

        return CompressionResult(
            compressed_text=result.content,
            original_tokens=original_tokens,
            compressed_tokens=compressed_tokens,
            compression_ratio=ratio,
            savings_percent=savings,
        )
