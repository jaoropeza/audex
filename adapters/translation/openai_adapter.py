from __future__ import annotations

import os
import re

from domain.entities import TranslationConfig
from domain.ports.translation_port import TranslationPort

_NUMBERED = re.compile(r"^\d+\.\s+(.*)", re.DOTALL)


def _resolve_prompt(config, texts: list[str], target_language: str) -> str:
    if config.prompt_template:
        numbered = "\n".join(f"{i + 1}. {t}" for i, t in enumerate(texts))
        try:
            return config.prompt_template.format(texts=numbered, target_language=target_language)
        except (KeyError, ValueError):
            pass
    return _build_prompt(texts, target_language)


def _build_prompt(texts: list[str], target_language: str) -> str:
    numbered = "\n".join(f"{i + 1}. {t}" for i, t in enumerate(texts))
    return (
        f"Translate the following numbered transcript lines into {target_language}.\n"
        "Rules:\n"
        '- Return ONLY the numbered lines in the same format: "1. translated text"\n'
        "- Do NOT translate proper nouns, product names, or technical terms.\n"
        "- Preserve natural spoken-word flow; these are transcribed speech lines.\n"
        "- If a line is already in the target language, copy it unchanged.\n\n"
        f"{numbered}"
    )


def _parse_response(raw: str, original: list[str]) -> list[str]:
    result: list[str] = []
    for i, line in enumerate(raw.strip().splitlines()):
        m = _NUMBERED.match(line.strip())
        result.append(m.group(1) if m else (original[i] if i < len(original) else ""))
    while len(result) < len(original):
        result.append(original[len(result)])
    return result[: len(original)]


class OpenAIAdapter(TranslationPort):
    """
    Works with any OpenAI-compatible endpoint:
    - OpenAI (default)
    - LM Studio, vLLM, NVIDIA NIM chat (set api_url)
    - Google Gemini via OpenAI-compatible mode (set api_url to Google's endpoint)
    """

    def __init__(self, config: TranslationConfig) -> None:
        self._config = config

    def _client(self):
        from openai import AsyncOpenAI  # lazy import
        key = self._config.api_key or os.environ.get("OPENAI_API_KEY", "none")
        kwargs: dict = {"api_key": key}
        if self._config.api_url:
            kwargs["base_url"] = self._config.api_url
        return AsyncOpenAI(**kwargs)

    async def translate(self, texts: list[str], target_language: str) -> list[str]:
        client = self._client()
        response = await client.chat.completions.create(
            model=self._config.model,
            messages=[{"role": "user", "content": _resolve_prompt(self._config, texts, target_language)}],
            temperature=0.2,
        )
        raw = response.choices[0].message.content or ""
        return _parse_response(raw, texts)

    async def health_check(self) -> dict:
        try:
            client = self._client()
            models = await client.models.list()
            ids = [m.id for m in models.data]
            found = self._config.model in ids or any(self._config.model in i for i in ids)
            if ids and not found:
                return {
                    "ok": False,
                    "detail": f"Model '{self._config.model}' not found. Available: {', '.join(ids[:5])}",
                }
            return {"ok": True, "detail": f"Connected — model {self._config.model}"}
        except Exception as exc:
            return {"ok": False, "detail": str(exc)}
