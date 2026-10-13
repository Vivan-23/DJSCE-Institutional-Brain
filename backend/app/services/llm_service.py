"""
Centralized LLM client.

Wraps the chat-completion provider so RAG, the extraction engine, and the
Company PA all share one configurable client instead of each constructing their
own. Defaults to Groq (see ``settings.LLM_MODEL``); swap the provider here.
"""
import json
import re
import time
from typing import Any, Optional

import structlog

from app.core.config import settings

log = structlog.get_logger()

_RATE_LIMIT_RETRIES = 3  # provider 429s back off 2 s, 4 s, 8 s before giving up


class LLMService:
    def __init__(self) -> None:
        self.client = None
        self.model = settings.LLM_MODEL
        if settings.GROQ_API_KEY:
            try:
                import groq
                self.client = groq.Groq(api_key=settings.GROQ_API_KEY)
                log.info("LLM client initialized", model=self.model)
            except Exception as e:  # pragma: no cover - defensive init
                log.error("Failed to initialize LLM client", error=str(e))

    @property
    def is_available(self) -> bool:
        return self.client is not None

    def complete(
        self,
        system_prompt: str,
        user_prompt: str,
        *,
        max_tokens: int = 1024,
        temperature: float = 0.2,
    ) -> str:
        """Return the raw text completion. Raises if the LLM is unavailable."""
        if not self.client:
            raise RuntimeError("LLM client not configured (set GROQ_API_KEY).")
        for attempt in range(_RATE_LIMIT_RETRIES + 1):
            try:
                completion = self.client.chat.completions.create(
                    messages=[
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": user_prompt},
                    ],
                    model=self.model,
                    max_tokens=max_tokens,
                    temperature=temperature,
                )
                return completion.choices[0].message.content or ""
            except Exception as e:  # noqa: BLE001 - only rate limits are retried
                if "RateLimit" not in type(e).__name__ or attempt == _RATE_LIMIT_RETRIES:
                    raise
                wait = 2 ** (attempt + 1)
                log.warning("LLM rate-limited; retrying", wait_s=wait, attempt=attempt + 1)
                time.sleep(wait)
        raise RuntimeError("unreachable")

    def complete_json(
        self,
        system_prompt: str,
        user_prompt: str,
        *,
        max_tokens: int = 2048,
        temperature: float = 0.1,
        default: Optional[Any] = None,
    ) -> Any:
        """
        Ask for JSON and parse it robustly (tolerates ```json fences and prose
        around the payload). Returns ``default`` if nothing parseable comes back.
        """
        guard = (
            "\n\nRespond with ONLY valid JSON — no prose, no markdown fences."
        )
        try:
            raw = self.complete(
                system_prompt + guard,
                user_prompt,
                max_tokens=max_tokens,
                temperature=temperature,
            )
        except Exception as e:
            log.warning("LLM JSON completion failed", error=str(e))
            return default

        parsed = _extract_json(raw)
        if parsed is None:
            log.warning("Could not parse JSON from LLM output", sample=raw[:200])
            return default
        return parsed


def _extract_json(text: str) -> Optional[Any]:
    """Pull the first JSON object/array out of an LLM response."""
    if not text:
        return None
    text = text.strip()

    # Strip ```json ... ``` fences if present
    fence = re.search(r"```(?:json)?\s*(.+?)```", text, re.DOTALL)
    if fence:
        text = fence.group(1).strip()

    # Direct parse first
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass

    # Fall back to the first balanced {...} or [...] span
    for open_ch, close_ch in (("{", "}"), ("[", "]")):
        start = text.find(open_ch)
        end = text.rfind(close_ch)
        if start != -1 and end > start:
            try:
                return json.loads(text[start : end + 1])
            except json.JSONDecodeError:
                continue
    return None


llm_service = LLMService()
