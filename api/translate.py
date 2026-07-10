from __future__ import annotations

import re
import traceback

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, field_validator

from application.config_service import ConfigService
from application.translation_service import TranslationService

router = APIRouter()

# Matches: [HH:MM:SS] optional [LABEL] optional [SPEAKER]  then the spoken text
_PREFIX_RE = re.compile(r"^(\[\d{2}:\d{2}:\d{2}\](?:\[[^\]]+\])*)\s*(.*)", re.DOTALL)


class TranslateRequest(BaseModel):
    lines: list[str]
    target_language: str = "English"
    source_language: str = "auto"
    prompt_template: str | None = None

    @field_validator("lines")
    @classmethod
    def check_lines(cls, v):
        if not v:
            raise ValueError("lines must not be empty")
        return v


@router.post("/translate")
async def translate_lines(req: TranslateRequest):
    # Split [HH:MM:SS][LABEL] prefix from spoken text (API-layer concern)
    prefixes, contents = [], []
    for line in req.lines:
        m = _PREFIX_RE.match(line)
        if m:
            prefixes.append(m.group(1))
            contents.append(m.group(2).strip())
        else:
            prefixes.append("")
            contents.append(line)

    cfg = ConfigService().get()
    service = TranslationService(cfg.translation)

    try:
        translated = await service.translate(
            contents,
            req.target_language,
            source_language=req.source_language,
            prompt_template=req.prompt_template,
        )
    except Exception as exc:
        traceback.print_exc()
        raise HTTPException(status_code=502, detail=f"Translation error: {exc}")

    # Re-attach original prefixes
    result = [
        f"{p} {t}".strip() if p else t
        for p, t in zip(prefixes, translated)
    ]
    return {"translations": result}
