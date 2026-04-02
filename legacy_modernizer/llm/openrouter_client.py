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

    DEFAULT_MODEL = "nvidia/nemotron-3-super-120b-a12b:free"

    FALLBACK_MODELS = [
        "z-ai/glm-4.5-air:free",
        "meta-llama/llama-3.3-70b-instruct:free",
        "qwen/qwen-2.5-72b-instruct:free",
    ]

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

        # Handle HTTP errors with clear messages (Phase 6: Added retry for 429)
        import time
        max_retries = 3
        retry_delay = 2 # seconds
        models_to_try: list[str] = [self.model] + [m for m in self.FALLBACK_MODELS if m != self.model]
        current_model_idx: int = 0
        attempt: int = 0

        while attempt <= max_retries:
            # Update payload model for fallback
            payload["model"] = models_to_try[current_model_idx]

            try:
                # Add a timeout to prevent hanging forever
                resp = requests.post(
                    OPENROUTER_CHAT_URL, 
                    json=payload, 
                    headers=headers,
                    timeout=180
                )

                # Rate limit handling (HTTP 429)
                if resp.status_code == 429:
                    # Try the next fallback model first (doesn't consume an attempt delay)
                    if current_model_idx + 1 < len(models_to_try):
                        current_model_idx += 1
                        logger.warning(
                            "OpenRouter rate limit hit. Falling back to %s",
                            models_to_try[current_model_idx]
                        )
                        time.sleep(2)
                        continue
                    else:
                        if attempt < max_retries:
                            wait_time = retry_delay * (2 ** attempt)
                            logger.warning(
                                "All models ratelimited. OpenRouter 429. Retrying %d/%d in %ds...",
                                attempt + 1, max_retries, wait_time
                            )
                            current_model_idx = 0  # Reset to first model
                            time.sleep(wait_time)
                            attempt += 1
                            continue
                        else:
                            raise RuntimeError(f"OpenRouter rate limit exceeded after {max_retries} retries.")

                resp.raise_for_status() # This will raise for 4xx/5xx errors

                # If we get here, the request was successful (2xx)
                break
                
            except requests.exceptions.RequestException as e:
                # Authentication errors shouldn't be retried
                if hasattr(e, 'response') and e.response is not None and e.response.status_code == 401:
                    logger.error("OpenRouter authentication failed (401). Check API key.")
                    raise ValueError(
                        "OpenRouter API key is invalid. Please check OPENROUTER_API_KEY "
                        "in your .env file."
                    )
                if resp.status_code >= 400:
                    detail = resp.text[:300]
                    raise RuntimeError(
                        f"OpenRouter request failed (HTTP {resp.status_code}): {detail}"
                    )
                
                # If we get here, it's a 200 OK
                break
                
            except (requests.exceptions.ConnectionError, requests.exceptions.Timeout) as exc:
                if attempt < max_retries:
                    wait_time = retry_delay * (2 ** attempt)
                    logger.warning("Network error (%s). Retrying in %ds...", exc, wait_time)
                    time.sleep(wait_time)
                    continue
                else:
                    raise RuntimeError(f"OpenRouter API unreachable after {max_retries} retries: {exc}")

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
