from __future__ import annotations

import os
import re
import secrets
import shutil
from pathlib import Path
from typing import Optional

_TRANSCRIPT_RE = re.compile(r'.+_\d{8}_\d{6}(\.txt|\.wav)$')

from adapters.db.sqlite_adapter import SQLiteAdapter, _connect, init_db
from adapters.db.chroma_adapter import ChromaAdapter

PROJECT_DIR     = Path(__file__).parent.parent
_default_td     = PROJECT_DIR / "transcripts"
TRANSCRIPTS_DIR = Path(os.environ.get("STT_TRANSCRIPTS_DIR", str(_default_td)))

_sqlite = SQLiteAdapter()
_chroma = ChromaAdapter()


def _ensure_admin_user() -> Optional[int]:
    """Create a default admin user if the users table is empty. Returns the admin user id."""
    from adapters.db.user_adapter import UserAdapter
    from application.auth_service import AuthService
    ua = UserAdapter()
    if ua.count_users() > 0:
        # Return id of first admin found, or None
        for u in ua.list_users():
            if u.role.value == "admin":
                return u.id
        return ua.list_users()[0].id
    password = secrets.token_urlsafe(12)
    hashed   = AuthService().hash_password(password)
    user     = ua.create_user("admin", hashed, role="admin", email=None)
    print(f"\n[STT] *** First-run setup: admin user created ***")
    print(f"[STT]     Username : admin")
    print(f"[STT]     Password : {password}")
    print(f"[STT]     Change this password via the Admin panel after first login.\n")
    return user.id


def _backfill_user_ids(admin_id: int) -> None:
    """Assign legacy (NULL user_id) records to the admin user."""
    with _connect() as con:
        con.execute(
            "UPDATE transcriptions SET user_id=? WHERE user_id IS NULL", (admin_id,)
        )
        con.execute(
            "UPDATE summaries SET user_id=? WHERE user_id IS NULL", (admin_id,)
        )
        con.execute(
            "UPDATE transcript_tags SET user_id=? WHERE user_id IS NULL", (admin_id,)
        )


def _backfill_content(admin_id: int) -> None:
    """Populate content column for rows that were inserted without content."""
    with _connect() as con:
        missing = con.execute(
            "SELECT id, filename, user_id FROM transcriptions WHERE content IS NULL"
        ).fetchall()

    for row in missing:
        uid      = row["user_id"] or admin_id
        fname    = row["filename"]
        # Look in user subdir first, then shared transcripts/, then project root
        for base in (TRANSCRIPTS_DIR / str(uid), TRANSCRIPTS_DIR, PROJECT_DIR):
            p = base / fname
            if p.exists():
                try:
                    content = p.read_text(encoding="utf-8", errors="ignore")
                    lines   = [ln.rstrip() for ln in content.splitlines() if ln.strip()]
                    _sqlite.upsert_transcript(fname, user_id=uid,
                                              content=content, line_count=len(lines))
                except OSError:
                    pass
                break


def startup_index() -> None:
    TRANSCRIPTS_DIR.mkdir(parents=True, exist_ok=True)
    init_db()

    # Migrate legacy transcript/audio files from project root
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

    # Ensure at least one admin user exists; get their id for backfill
    admin_id = _ensure_admin_user()

    # Index un-indexed top-level transcripts directly under the admin user.
    # Using admin_id (not None) makes upsert idempotent on every restart:
    # ON CONFLICT(user_id, filename) DO UPDATE is safe; NULL→admin_id backfill
    # would collide with an already-backfilled row on the second startup.
    for path in sorted(TRANSCRIPTS_DIR.glob("*.txt")):
        if path.name.endswith("_summary.txt"):
            continue
        try:
            content = path.read_text(encoding="utf-8", errors="ignore")
            lines   = [ln.rstrip() for ln in content.splitlines() if ln.strip()]
        except OSError:
            continue
        _sqlite.upsert_transcript(path.name, user_id=admin_id, content=content, line_count=len(lines))
        try:
            _chroma.index(path.name, lines)
        except RuntimeError:
            pass

    # Backfill: assign NULL user_ids to admin, populate missing content
    _backfill_user_ids(admin_id)
    _backfill_content(admin_id)


class DBService:
    def index(
        self,
        filename: str,
        lines: list[str],
        user_id: Optional[int] = None,
        embedding_config=None,  # Optional[EmbeddingConfig]
    ) -> None:
        init_db()
        content = "\n".join(lines)
        _sqlite.upsert_transcript(filename, user_id=user_id, content=content, line_count=len(lines))
        try:
            _chroma.index(filename, lines, user_id=user_id, config=embedding_config)
        except RuntimeError:
            pass

    def get_content(self, filename: str, user_id: Optional[int] = None) -> Optional[str]:
        return _sqlite.get_transcript_content(filename, user_id=user_id)

    def semantic_search(
        self,
        query: str,
        n_results: int = 5,
        user_id: Optional[int] = None,
    ) -> list[dict]:
        return _chroma.search(query, n_results, user_id=user_id)

    def save_summary(
        self,
        filename: str,
        summary_text: str,
        user_id: Optional[int] = None,
        provider: Optional[str] = None,
        model: Optional[str] = None,
        prompt_used: Optional[str] = None,
    ) -> None:
        _sqlite.save_summary(filename, summary_text, user_id=user_id,
                             provider=provider, model=model, prompt_used=prompt_used)

    def get_summary(self, filename: str, user_id: Optional[int] = None) -> Optional[dict]:
        return _sqlite.get_summary(filename, user_id=user_id)

    def list_transcriptions(self, user_id: Optional[int] = None) -> list[dict]:
        return _sqlite.list_transcriptions(user_id=user_id)

    def set_tags(self, filename: str, tags: list[str], user_id: Optional[int] = None) -> None:
        _sqlite.set_tags(filename, tags, user_id=user_id)

    def get_tags(self, filename: str, user_id: Optional[int] = None) -> list[str]:
        return _sqlite.get_tags(filename, user_id=user_id)

    def all_distinct_tags(self, user_id: Optional[int] = None) -> list[str]:
        return _sqlite.all_distinct_tags(user_id=user_id)
