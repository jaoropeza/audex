import os
import re
import traceback
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, field_validator

router = APIRouter()

# Matches: [HH:MM:SS] optional [LABEL] optional [SPEAKER]  then the spoken text
_PREFIX_RE = re.compile(r"^(\[\d{2}:\d{2}:\d{2}\](?:\[[^\]]+\])*)\s*(.*)", re.DOTALL)


class TranslateRequest(BaseModel):
    lines: list[str]
    target_language: str = "English"

    @field_validator("lines")
    @classmethod
    def check_lines(cls, v):
        if not v:
            raise ValueError("lines must not be empty")
        if len(v) > 50:
            raise ValueError("At most 50 lines per request")
        return v


@router.post("/translate")
async def translate_lines(req: TranslateRequest):
    import anthropic  # lazy import — keeps server startup fast

    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        raise HTTPException(status_code=500, detail="ANTHROPIC_API_KEY not set")

    # Split prefix ([HH:MM:SS][LABEL]) from spoken text
    prefixes, contents = [], []
    for line in req.lines:
        m = _PREFIX_RE.match(line)
        if m:
            prefixes.append(m.group(1))
            contents.append(m.group(2).strip())
        else:
            prefixes.append("")
            contents.append(line)

    numbered = "\n".join(f"{i + 1}. {text}" for i, text in enumerate(contents))

    prompt = (
        f"Translate the following numbered transcript lines into {req.target_language}.\n"
        "Rules:\n"
        "- Return ONLY the numbered lines in the same format: \"1. translated text\"\n"
        "- Do NOT translate proper nouns, product names, or technical terms.\n"
        "- Preserve natural spoken-word flow; these are transcribed speech lines.\n"
        "- If a line is already in the target language, copy it unchanged.\n\n"
        f"{numbered}"
    )

    client = anthropic.Anthropic(api_key=api_key)
    try:
        response = client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=2048,
            messages=[{"role": "user", "content": prompt}],
        )
    except Exception as exc:
        traceback.print_exc()
        raise HTTPException(status_code=502, detail=f"Claude API error: {exc}")

    raw_lines = response.content[0].text.strip().splitlines()

    translated: list[str] = []
    for i, raw in enumerate(raw_lines):
        m = re.match(r"^\d+\.\s+(.*)", raw.strip())
        translated.append(m.group(1) if m else (contents[i] if i < len(contents) else ""))

    # Pad / trim to input length
    while len(translated) < len(req.lines):
        translated.append(contents[len(translated)] if len(translated) < len(contents) else "")
    translated = translated[: len(req.lines)]

    # Re-attach original prefixes
    result = [
        f"{p} {t}".strip() if p else t
        for p, t in zip(prefixes, translated)
    ]

    return {"translations": result}
