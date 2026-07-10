from __future__ import annotations

import re

import httpx

from domain.entities import TranslationConfig
from domain.ports.translation_port import TranslationPort

_NUMBERED = re.compile(r"^\d+\.\s+(.*)", re.DOTALL)
_DEFAULT_URL = "http://localhost:11434"


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


class OllamaAdapter(TranslationPort):
    def __init__(self, config: TranslationConfig) -> None:
        self._config = config
        self._base_url = (config.api_url or _DEFAULT_URL).rstrip("/")

    async def translate(self, texts: list[str], target_language: str) -> list[str]:
        async with httpx.AsyncClient(timeout=60.0) as client:
            resp = await client.post(
                f"{self._base_url}/api/chat",
                json={
                    "model": self._config.model,
                    "stream": False,
                    "messages": [
                        {"role": "user", "content": _build_prompt(texts, target_language)}
                    ],
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
                # Accept partial match (e.g. "translategemma:4b" in "translategemma:4b")
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
