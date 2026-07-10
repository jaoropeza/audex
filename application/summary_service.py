from __future__ import annotations

import asyncio
import os
from typing import Optional

from domain.entities import SummaryConfig, SummaryProvider, TranslationConfig, TranslationProvider

_DEFAULT_PROMPT = (
    "You are a professional meeting assistant. "
    "Analyze the following conversation transcript and produce a structured summary "
    "in the SAME language as the transcript.\n\n"
    "TRANSCRIPT:\n{transcript}\n\n"
    "Write the summary using these sections exactly:\n\n"
    "## Overview\n"
    "2–3 sentences describing what was discussed.\n\n"
    "## Key Decisions & Agreements\n"
    "Bullet list of decisions or agreements reached. Write \"None identified\" if none.\n\n"
    "## Action Items\n"
    "Bullet list of concrete tasks, with the responsible person when mentioned. "
    "Write \"None identified\" if none.\n\n"
    "## Next Steps\n"
    "What should happen after this conversation ends. Write \"None identified\" if none.\n\n"
    "## Notable Points\n"
    "Any other important facts, context, risks, or follow-up items worth remembering."
)


class SummaryService:
    def __init__(self, config: SummaryConfig) -> None:
        self._config = config

    # ── Internal helpers ──────────────────────────────────────────────────────

    def _as_translation_config(self) -> TranslationConfig:
        return TranslationConfig(
            provider = TranslationProvider(self._config.provider.value),
            model    = self._config.model,
            api_url  = self._config.api_url,
            api_key  = self._config.api_key,
        )

    def _resolve_key(self, env_var: str) -> str:
        return self._config.api_key or os.environ.get(env_var, "")

    def _build_prompt(self, transcript_text: str, override_template: Optional[str]) -> str:
        template = override_template or self._config.prompt_template or _DEFAULT_PROMPT
        try:
            return template.format(transcript=transcript_text)
        except (KeyError, ValueError):
            return _DEFAULT_PROMPT.format(transcript=transcript_text)

    # ── Public API ────────────────────────────────────────────────────────────

    async def test(self) -> dict:
        try:
            from application.translation_service import TranslationService
            return await TranslationService(self._as_translation_config()).test()
        except Exception as exc:
            return {"ok": False, "detail": str(exc)}

    async def summarize(
        self,
        transcript_text: str,
        prompt_template: Optional[str] = None,
    ) -> str:
        prompt = self._build_prompt(transcript_text, prompt_template)
        provider = self._config.provider

        if provider == SummaryProvider.ANTHROPIC:
            return await self._call_anthropic(prompt)
        elif provider == SummaryProvider.OLLAMA:
            return await self._call_ollama(prompt)
        elif provider == SummaryProvider.OPENAI:
            return await self._call_openai(prompt)
        elif provider == SummaryProvider.GEMINI:
            return await self._call_gemini(prompt)
        else:
            raise ValueError(f"Unknown summary provider: {provider}")

    # ── Provider implementations ──────────────────────────────────────────────

    async def _call_anthropic(self, prompt: str) -> str:
        import anthropic  # type: ignore
        key = self._resolve_key("ANTHROPIC_API_KEY")
        client = anthropic.Anthropic(api_key=key)
        loop = asyncio.get_event_loop()
        response = await loop.run_in_executor(
            None,
            lambda: client.messages.create(
                model=self._config.model,
                max_tokens=2048,
                messages=[{"role": "user", "content": prompt}],
            ),
        )
        return response.content[0].text

    async def _call_ollama(self, prompt: str) -> str:
        import httpx  # type: ignore
        url = (self._config.api_url or "http://localhost:11434").rstrip("/")
        # Estimate tokens (≈ chars / 3.5) + 2048 for output headroom, rounded to
        # the next power of two, capped at 131072.
        estimated = int(len(prompt) / 3.5) + 2048
        p = 1
        while p < estimated:
            p <<= 1
        num_ctx = min(p, 131072)
        async with httpx.AsyncClient(timeout=300) as client:
            resp = await client.post(
                f"{url}/api/chat",
                json={
                    "model": self._config.model,
                    "messages": [{"role": "user", "content": prompt}],
                    "stream": False,
                    "options": {"num_ctx": num_ctx},
                },
            )
            resp.raise_for_status()
            return resp.json()["message"]["content"]

    async def _call_openai(self, prompt: str) -> str:
        import openai  # type: ignore
        key = self._resolve_key("OPENAI_API_KEY")
        client = openai.AsyncOpenAI(
            api_key=key,
            base_url=self._config.api_url or None,
        )
        response = await client.chat.completions.create(
            model=self._config.model,
            messages=[{"role": "user", "content": prompt}],
            max_tokens=2048,
        )
        return response.choices[0].message.content

    async def _call_gemini(self, prompt: str) -> str:
        import google.generativeai as genai  # type: ignore
        loop = asyncio.get_event_loop()
        key = self._resolve_key("GEMINI_API_KEY")
        genai.configure(api_key=key)
        model = genai.GenerativeModel(self._config.model)
        response = await loop.run_in_executor(None, model.generate_content, prompt)
        return response.text
