from __future__ import annotations

from pathlib import Path
from typing import Optional

from adapters.db.sqlite_adapter import SQLiteAdapter, init_db
from adapters.db.chroma_adapter import ChromaAdapter

_PROJECT_DIR = Path(__file__).parent.parent

_sqlite = SQLiteAdapter()
_chroma = ChromaAdapter()


def startup_index() -> None:
    """Scan existing .txt files on first startup and index into SQLite + ChromaDB."""
    init_db()
    for path in sorted(_PROJECT_DIR.glob("*.txt")):
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
            pass  # chromadb unavailable — skip silently


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
