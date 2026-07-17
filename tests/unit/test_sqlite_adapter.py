import pytest
from adapters.db.sqlite_adapter import SQLiteAdapter, _connect, init_db


@pytest.fixture(autouse=True)
def _setup(tmp_db):
    pass  # tmp_db fixture already calls init_db


def _make_user(username: str, uid_hint: int = None) -> int:
    """Insert a bare-bones user row and return the assigned id."""
    from datetime import datetime
    with _connect() as con:
        cur = con.execute(
            "INSERT INTO users (username, hashed_pw, role, is_active, created_at) VALUES (?,?,?,1,?)",
            (username, "hashed", "user", datetime.utcnow().isoformat()),
        )
        return cur.lastrowid


def test_upsert_and_get_transcript():
    db  = SQLiteAdapter()
    uid = _make_user("u1")
    db.upsert_transcript("test.txt", user_id=uid, content="[00:00:01][SPK][Alice] Hello", line_count=1)
    row = db.get_transcript("test.txt", user_id=uid)
    assert row is not None
    assert row["content"] == "[00:00:01][SPK][Alice] Hello"
    assert row["line_count"] == 1


def test_user_isolation():
    db   = SQLiteAdapter()
    uid1 = _make_user("iso1")
    uid2 = _make_user("iso2")
    db.upsert_transcript("same.txt", user_id=uid1, content="user1 content", line_count=1)
    db.upsert_transcript("same.txt", user_id=uid2, content="user2 content", line_count=1)
    assert db.get_transcript_content("same.txt", user_id=uid1) == "user1 content"
    assert db.get_transcript_content("same.txt", user_id=uid2) == "user2 content"


def test_delete_transcript():
    db  = SQLiteAdapter()
    uid = _make_user("del1")
    db.upsert_transcript("del.txt", user_id=uid, content="bye", line_count=1)
    assert db.delete_transcript("del.txt", user_id=uid)
    assert db.get_transcript("del.txt", user_id=uid) is None


def test_tags_user_scoped():
    db   = SQLiteAdapter()
    uid1 = _make_user("tag1")
    uid2 = _make_user("tag2")
    db.upsert_transcript("tagged.txt", user_id=uid1, content="x", line_count=1)
    db.set_tags("tagged.txt", ["alpha", "beta"], user_id=uid1)
    assert set(db.get_tags("tagged.txt", user_id=uid1)) == {"alpha", "beta"}
    # Different user sees no tags
    assert db.get_tags("tagged.txt", user_id=uid2) == []


def test_list_transcriptions_user_scoped():
    db   = SQLiteAdapter()
    uid1 = _make_user("list1")
    uid2 = _make_user("list2")
    db.upsert_transcript("a.txt", user_id=uid1, content="", line_count=0)
    db.upsert_transcript("b.txt", user_id=uid2, content="", line_count=0)
    user1 = [r["filename"] for r in db.list_transcriptions(user_id=uid1)]
    user2 = [r["filename"] for r in db.list_transcriptions(user_id=uid2)]
    assert "a.txt" in user1 and "b.txt" not in user1
    assert "b.txt" in user2 and "a.txt" not in user2


def test_summary_save_and_get():
    db  = SQLiteAdapter()
    uid = _make_user("summ1")
    db.upsert_transcript("s.txt", user_id=uid, content="hello", line_count=1)
    db.save_summary("s.txt", "A summary.", user_id=uid, provider="anthropic", model="test")
    row = db.get_summary("s.txt", user_id=uid)
    assert row is not None
    assert row["summary_text"] == "A summary."


def test_count_transcriptions():
    db  = SQLiteAdapter()
    uid = _make_user("count1")
    before = db.count_transcriptions()
    db.upsert_transcript("c1.txt", user_id=uid, content="x", line_count=1)
    db.upsert_transcript("c2.txt", user_id=uid, content="y", line_count=1)
    assert db.count_transcriptions() == before + 2


def test_upsert_with_null_user_allowed():
    """NULL user_id should be allowed (legacy rows)."""
    db = SQLiteAdapter()
    db.upsert_transcript("legacy.txt", user_id=None, content="old content", line_count=1)
    row = db.get_transcript("legacy.txt", user_id=None)
    assert row is not None
    assert row["content"] == "old content"
