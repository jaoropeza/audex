from __future__ import annotations

import os
import re

from domain.entities import TranslationConfig
from domain.ports.translation_port import TranslationPort

_NUMBERED = re.compile(r"^\d+\.\s+(.*)", re.DOTALL)


def _build_prompt(
    texts: list[str],
    target_language: str,
    source_language: str = "auto",
    prompt_template: str | None = None,
) -> str:
    numbered = "\n".join(f"{i + 1}. {t}" for i, t in enumerate(texts))
    if prompt_template:
        try:
            return prompt_template.format(
                source_lang=source_language if source_language != "auto" else "the source language",
                target_lang=target_language,
                source_code=source_language,
                target_code=target_language,
                texts=numbered,
            )
        except (KeyError, ValueError):
            pass
    src_clause = f"from {source_language} " if source_language not in ("auto", "Auto") else ""
    return (
        f"Translate the following numbered transcript lines {src_clause}into {target_language}.\n"
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


class AnthropicAdapter(TranslationPort):
    def __init__(self, config: TranslationConfig) -> None:
        self._config = config

    def _client(self):
        import anthropic  # lazy — keeps server startup fast
        key = self._config.api_key or os.environ.get("ANTHROPIC_API_KEY", "")
        return anthropic.Anthropic(api_key=key)

    async def translate(
        self,
        texts: list[str],
        target_language: str,
        source_language: str = "auto",
        prompt_template: str | None = None,
    ) -> list[str]:
        prompt = _build_prompt(
            texts, target_language,
            source_language=source_language,
            prompt_template=prompt_template or self._config.prompt_template,
        )
        client = self._client()
        response = client.messages.create(
            model=self._config.model,
            max_tokens=2048,
            messages=[{"role": "user", "content": prompt}],
        )
        return _parse_response(response.content[0].text, texts)

    async def health_check(self) -> dict:
        try:
            client = self._client()
            # Minimal call to verify the key + model are valid
            client.messages.create(
                model=self._config.model,
                max_tokens=5,
                messages=[{"role": "user", "content": "hi"}],
            )
            return {"ok": True, "detail": f"Connected — model {self._config.model}"}
        except Exception as exc:
            return {"ok": False, "detail": str(exc)}
