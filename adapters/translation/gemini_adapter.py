from __future__ import annotations

import os
import re

from domain.entities import TranslationConfig
from domain.ports.translation_port import TranslationPort

_NUMBERED = re.compile(r"^\d+\.\s+(.*)", re.DOTALL)


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


class GeminiAdapter(TranslationPort):
    def __init__(self, config: TranslationConfig) -> None:
        self._config = config

    def _configure(self):
        import google.generativeai as genai  # lazy import
        key = self._config.api_key or os.environ.get("GEMINI_API_KEY", "")
        genai.configure(api_key=key)
        return genai

    async def translate(self, texts: list[str], target_language: str) -> list[str]:
        import asyncio
        genai = self._configure()
        model = genai.GenerativeModel(self._config.model)

        def _run():
            response = model.generate_content(_build_prompt(texts, target_language))
            return response.text

        raw = await asyncio.get_event_loop().run_in_executor(None, _run)
        return _parse_response(raw, texts)

    async def health_check(self) -> dict:
        import asyncio
        try:
            genai = self._configure()

            def _list():
                return list(genai.list_models())

            models = await asyncio.get_event_loop().run_in_executor(None, _list)
            names = [m.name for m in models]
            target = self._config.model
            found = any(target in n or n.endswith(target) for n in names)
            if names and not found:
                return {
                    "ok": False,
                    "detail": f"Model '{target}' not found. Check model name (e.g. 'gemini-2.0-flash').",
                }
            return {"ok": True, "detail": f"Gemini API connected — model {target}"}
        except Exception as exc:
            return {"ok": False, "detail": str(exc)}
