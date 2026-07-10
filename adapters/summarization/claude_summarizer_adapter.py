from __future__ import annotations

import os
from datetime import datetime
from typing import Optional

from domain.ports.summarization_port import SummarizationPort

_MODEL   = "claude-haiku-4-5-20251001"
_PROMPT  = """\
You are a professional meeting assistant. \
Analyze the following conversation transcript and produce a structured summary \
in the SAME language as the transcript.

TRANSCRIPT:
{transcript}

Write the summary using these sections exactly:

## Overview
2–3 sentences describing what was discussed.

## Key Decisions & Agreements
Bullet list of decisions or agreements reached. Write "None identified" if none.

## Action Items
Bullet list of concrete tasks, with the responsible person when mentioned. \
Write "None identified" if none.

## Next Steps
What should happen after this conversation ends. Write "None identified" if none.

## Notable Points
Any other important facts, context, risks, or follow-up items worth remembering.\
"""


class ClaudeSummarizerAdapter(SummarizationPort):
    def __init__(self, api_key: Optional[str] = None) -> None:
        self._api_key = api_key

    def summarize(self, transcript_path: str) -> None:
        try:
            import anthropic
        except ImportError:
            print("[ERROR] Summarization requires: pip install anthropic")
            return

        key = self._api_key or os.environ.get("ANTHROPIC_API_KEY")
        if not key:
            print("[ERROR] --summarize requires ANTHROPIC_API_KEY env var or --api-key.")
            return

        try:
            with open(transcript_path, encoding="utf-8") as f:
                transcript = f.read().strip()
        except FileNotFoundError:
            print(f"[WARN] Transcript file not found: {transcript_path}")
            return

        if not transcript:
            print("[INFO] Transcript is empty — skipping summary.")
            return
        if len(transcript.splitlines()) < 3:
            print("[INFO] Transcript too short for a meaningful summary.")
            return

        print("[INFO] Generating meeting summary...", flush=True)
        try:
            client   = anthropic.Anthropic(api_key=key)
            response = client.messages.create(
                model=_MODEL,
                max_tokens=1500,
                messages=[{"role": "user", "content": _PROMPT.format(transcript=transcript)}],
            )
            summary = response.content[0].text
        except Exception as exc:
            print(f"[ERROR] Summarization failed: {exc}")
            return

        summary_path = transcript_path.replace(".txt", "_summary.txt")
        with open(summary_path, "w", encoding="utf-8") as f:
            f.write("Transcript Summary\n")
            f.write(f"Source : {transcript_path}\n")
            f.write(f"Created: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
            f.write("=" * 60 + "\n\n")
            f.write(summary + "\n")

        sep = "=" * 60
        print(f"\n{sep}\n  MEETING SUMMARY\n{sep}")
        print(summary)
        print(sep)
        print(f"[INFO] Summary saved to: {summary_path}")
