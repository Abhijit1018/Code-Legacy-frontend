"""
OpenRouterClient — send optimised context to an LLM via OpenRouter
and return structured modernisation results.
"""

from __future__ import annotations

import os
import json
import logging
from dataclasses import dataclass, field

import requests

logger = logging.getLogger(__name__)

OPENROUTER_CHAT_URL = "https://openrouter.ai/api/v1/chat/completions"


@dataclass
class LLMResponse:
    """Structured result returned by the LLM."""
    summary: str = ""
    dependency_explanation: str = ""
    python_code: str = ""
    go_code: str = ""
    documentation: str = ""
    raw_text: str = ""
    model_used: str = ""
    tokens_used: int = 0


class OpenRouterClient:
    """
    Thin wrapper around the OpenRouter chat-completions API.

    Environment variable: OPENROUTER_API_KEY
    """

    DEFAULT_MODEL = "deepseek/deepseek-chat-v3-0324"

    def __init__(
        self,
        api_key: str | None = None,
        model: str | None = None,
        temperature: float = 0.2,
        max_tokens: int = 8192,
    ):
        self.api_key = api_key or os.getenv("OPENROUTER_API_KEY", "")
        self.model = model or self.DEFAULT_MODEL
        self.temperature = temperature
        self.max_tokens = max_tokens

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def generate(self, system_prompt: str, user_prompt: str) -> LLMResponse:
        """
        Send a chat-completion request and return an `LLMResponse`.

        The system prompt instructs the model to reply with a JSON object
        containing the five expected fields.  If the model does not return
        valid JSON we fall back to storing the raw text.
        """
        if not self.api_key:
            raise ValueError(
                "OPENROUTER_API_KEY is not set. "
                "Set it in your .env file or pass api_key to the constructor."
            )

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
            "HTTP-Referer": "https://github.com/scaledown-team/scaledown",
            "X-Title": "Legacy Modernizer",
        }

        payload = {
            "model": self.model,
            "temperature": self.temperature,
            "max_tokens": self.max_tokens,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
        }

        logger.info("Calling OpenRouter model=%s", self.model)

        try:
            resp = requests.post(
                OPENROUTER_CHAT_URL,
                headers=headers,
                json=payload,
                timeout=120,
            )
        except requests.exceptions.ConnectionError:
            raise RuntimeError("OpenRouter API is unreachable. Check your network.")
        except requests.exceptions.Timeout:
            raise RuntimeError("OpenRouter request timed out (120s). Try a smaller context.")

        # Handle HTTP errors with clear messages
        if resp.status_code == 401:
            raise ValueError(
                "OpenRouter API key is invalid. Please check OPENROUTER_API_KEY "
                "in your .env file."
            )
        if resp.status_code == 429:
            raise RuntimeError(
                "OpenRouter rate limit exceeded. Please wait and try again."
            )
        if resp.status_code >= 400:
            detail = resp.text[:300]
            raise RuntimeError(
                f"OpenRouter request failed (HTTP {resp.status_code}): {detail}"
            )

        data = resp.json()

        # Check for API-level errors (OpenRouter may return 200 with an error body)
        if "error" in data:
            err_msg = data["error"].get("message", str(data["error"]))
            raise RuntimeError(f"OpenRouter error: {err_msg}")

        raw_text = (
            data.get("choices", [{}])[0]
            .get("message", {})
            .get("content", "")
        )

        tokens_used = data.get("usage", {}).get("total_tokens", 0)

        return self._parse_response(raw_text, tokens_used)

    # ------------------------------------------------------------------
    # Response parsing
    # ------------------------------------------------------------------

    def _parse_response(self, raw_text: str, tokens_used: int) -> LLMResponse:
        """
        Attempt to parse the LLM output as JSON with the expected fields.
        Falls back to raw-text storage.
        """
        response = LLMResponse(
            raw_text=raw_text,
            model_used=self.model,
            tokens_used=tokens_used,
        )

        # Try to extract JSON from the response (model may wrap it in markdown)
        json_str = self._extract_json(raw_text)
        if json_str:
            try:
                obj = json.loads(json_str)
                response.summary = obj.get("summary", "")
                response.dependency_explanation = obj.get("dependency_explanation", "")
                response.python_code = obj.get("python_code", "")
                response.go_code = obj.get("go_code", "")
                response.documentation = obj.get("documentation", "")
                return response
            except json.JSONDecodeError:
                logger.warning("LLM returned invalid JSON, attempting partial recovery.")
                import re
                
                # Salvage python_code if JSON is truncated
                py_match = re.search(r'"python_code"\s*:\s*"((?:[^"\\]|\\.)*)', json_str)
                if py_match:
                    response.python_code = py_match.group(1).encode('utf-8').decode('unicode_escape')
                
                sum_match = re.search(r'"summary"\s*:\s*"((?:[^"\\]|\\.)*)', json_str)
                if sum_match:
                    response.summary = sum_match.group(1).encode('utf-8').decode('unicode_escape')
                    
                dep_match = re.search(r'"dependency_explanation"\s*:\s*"((?:[^"\\]|\\.)*)', json_str)
                if dep_match:
                    response.dependency_explanation = dep_match.group(1).encode('utf-8').decode('unicode_escape')
                    
                return response

        # Fallback: treat entire response as the summary
        response.summary = raw_text
        return response

    @staticmethod
    def _extract_json(text: str) -> str | None:
        """Extract the first JSON object from *text* (handles ```json fences)."""
        # Try fenced code block first
        import re
        m = re.search(r"```(?:json)?\s*\n?(\{.*?\})\s*```", text, re.DOTALL)
        if m:
            return m.group(1)
        # Try bare JSON
        m = re.search(r"\{.*\}", text, re.DOTALL)
        if m:
            return m.group(0)
        return None
