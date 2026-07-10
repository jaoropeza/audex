from __future__ import annotations

import re
import shutil
from pathlib import Path
from typing import Optional

# Only migrate files produced by _make_output_path: {prefix}_{YYYYMMDD}_{HHMMSS}.txt
_TRANSCRIPT_RE = re.compile(r'.+_\d{8}_\d{6}(\.txt|\.wav)$')

from adapters.db.sqlite_adapter import SQLiteAdapter, init_db
from adapters.db.chroma_adapter import ChromaAdapter

PROJECT_DIR     = Path(__file__).parent.parent
TRANSCRIPTS_DIR = PROJECT_DIR / "transcripts"

_sqlite = SQLiteAdapter()
_chroma = ChromaAdapter()


def startup_index() -> None:
    """
    On first startup:
    1. Ensure the transcripts/ folder exists.
    2. Migrate existing .txt files from the project root into transcripts/.
    3. Index all transcripts into SQLite + ChromaDB.
    """
    TRANSCRIPTS_DIR.mkdir(parents=True, exist_ok=True)
    init_db()

    # Migrate legacy transcript/audio files from project root.
    # Only touch files that match the timestamped naming pattern to avoid
    # accidentally moving config files like requirements.txt.
    for path in list(PROJECT_DIR.iterdir()):
        if not path.is_file():
            continue
        if not _TRANSCRIPT_RE.match(path.name):
            continue
        dest = TRANSCRIPTS_DIR / path.name
        if not dest.exists():
            shutil.move(str(path), str(dest))
        else:
            path.unlink(missing_ok=True)

    # Index all transcripts in transcripts/
    for path in sorted(TRANSCRIPTS_DIR.glob("*.txt")):
        if path.name.endswith("_summary.txt"):
            continue
        lines: list[str] = []
        try:
            with open(path, "r", encoding="utf-8", errors="ignore") as f:
                lines = [line.rstrip() for line in f if line.strip()]
        except OSError:
            pass
        _sqlite.upsert_transcript(path.name, len(lines))
        try:
            _chroma.index(path.name, lines)
        except RuntimeError:
            pass


class DBService:
    def index(self, filename: str, lines: list[str]) -> None:
        init_db()
        _sqlite.upsert_transcript(filename, len(lines))
        try:
            _chroma.index(filename, lines)
        except RuntimeError:
            pass

    def semantic_search(self, query: str, n_results: int = 5) -> list[dict]:
        return _chroma.search(query, n_results)

    def save_summary(
        self,
        filename: str,
        summary_text: str,
        provider: Optional[str] = None,
        model: Optional[str] = None,
        prompt_used: Optional[str] = None,
    ) -> None:
        _sqlite.save_summary(filename, summary_text, provider, model, prompt_used)

    def get_summary(self, filename: str) -> Optional[dict]:
        return _sqlite.get_summary(filename)

    def list_transcriptions(self) -> list[dict]:
        return _sqlite.list_transcriptions()

    def set_tags(self, filename: str, tags: list[str]) -> None:
        _sqlite.set_tags(filename, tags)

    def get_tags(self, filename: str) -> list[str]:
        return _sqlite.get_tags(filename)

    def all_distinct_tags(self) -> list[str]:
        return _sqlite.all_distinct_tags()
