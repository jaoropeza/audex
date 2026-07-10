from __future__ import annotations

import re

import httpx

from domain.entities import TranslationConfig
from domain.ports.translation_port import TranslationPort

_NUMBERED = re.compile(r"^\d+\.\s+(.*)", re.DOTALL)
_DEFAULT_URL = "http://localhost:11434"

# ISO 639 codes for the languages shown in the UI
_LANG_CODES: dict[str, str] = {
    "English": "en",
    "Spanish": "es",
    "French": "fr",
    "German": "de",
    "Portuguese": "pt",
    "Italian": "it",
    "Japanese": "ja",
    "Chinese": "zh-Hans",
    "Arabic": "ar",
    "Russian": "ru",
    "Korean": "ko",
    "Dutch": "nl",
    "Polish": "pl",
}


def _build_prompt(
    texts: list[str],
    target_language: str,
    source_language: str = "auto",
    prompt_template: str | None = None,
) -> str:
    numbered = "\n".join(f"{i + 1}. {t}" for i, t in enumerate(texts))
    tgt_code = _LANG_CODES.get(target_language, "")
    src_code = _LANG_CODES.get(source_language, "")

    if prompt_template:
        tgt_spec  = f"{target_language} ({tgt_code})" if tgt_code else target_language
        src_spec  = (
            f"{source_language} ({src_code})" if src_code
            else ("the source language" if source_language in ("auto", "Auto") else source_language)
        )
        try:
            return prompt_template.format(
                source_lang=src_spec,
                target_lang=tgt_spec,
                source_code=src_code or "auto",
                target_code=tgt_code,
                texts=numbered,
            )
        except (KeyError, ValueError):
            pass  # fall through to default

    # ── translategemma-style default prompt ──────────────────────────────────
    tgt_spec = f"{target_language} ({tgt_code})" if tgt_code else target_language

    if source_language in ("auto", "Auto"):
        instruction = (
            f"You are a professional translator. "
            f"Your goal is to accurately convey the meaning and nuances of the original text "
            f"while adhering to {tgt_spec} grammar, vocabulary, and cultural sensitivities. "
            f"Produce only the {tgt_spec} translation of each numbered line, "
            f"keeping the exact same numbered format (1. 2. 3. etc). "
            f"Do not add explanations, commentary, or extra text. "
            f"Please translate the following text into {tgt_spec}:"
        )
    else:
        src_spec = f"{source_language} ({src_code})" if src_code else source_language
        instruction = (
            f"You are a professional {src_spec} to {tgt_spec} translator. "
            f"Your goal is to accurately convey the meaning and nuances of the original {source_language} text "
            f"while adhering to {tgt_spec} grammar, vocabulary, and cultural sensitivities. "
            f"Produce only the {tgt_spec} translation of each numbered line, "
            f"keeping the exact same numbered format (1. 2. 3. etc). "
            f"Do not add explanations, commentary, or extra text. "
            f"Please translate the following {source_language} text into {tgt_spec}:"
        )

    # Two blank lines before the text — required by translategemma
    return f"{instruction}\n\n\n{numbered}"


def _parse_response(raw: str, original: list[str]) -> list[str]:
    result: list[str] = []
    for i, line in enumerate(raw.strip().splitlines()):
        m = _NUMBERED.match(line.strip())
        result.append(m.group(1) if m else (original[i] if i < len(original) else ""))
    while len(result) < len(original):
        result.append(original[len(result)])
    return result[: len(original)]


class OllamaAdapter(TranslationPort):
    def __init__(self, config: TranslationConfig) -> None:
        self._config = config
        self._base_url = (config.api_url or _DEFAULT_URL).rstrip("/")

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
        async with httpx.AsyncClient(timeout=120.0) as client:
            resp = await client.post(
                f"{self._base_url}/api/chat",
                json={
                    "model": self._config.model,
                    "stream": False,
                    "messages": [{"role": "user", "content": prompt}],
                },
            )
            resp.raise_for_status()
            content = resp.json()["message"]["content"]
            return _parse_response(content, texts)

    async def health_check(self) -> dict:
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                resp = await client.get(f"{self._base_url}/api/tags")
                resp.raise_for_status()
                models = [m["name"] for m in resp.json().get("models", [])]
                model_name = self._config.model
                found = any(model_name in m or m in model_name for m in models)
                if not found:
                    available = ", ".join(models) or "none pulled"
                    return {
                        "ok": False,
                        "detail": (
                            f"Model '{model_name}' not found in Ollama. "
                            f"Available: {available}. "
                            f"Run: ollama pull {model_name}"
                        ),
                    }
                return {"ok": True, "detail": f"Ollama running — model {model_name} ready"}
        except httpx.ConnectError:
            return {"ok": False, "detail": f"Cannot connect to Ollama at {self._base_url}"}
        except Exception as exc:
            return {"ok": False, "detail": str(exc)}
