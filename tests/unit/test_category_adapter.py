import pytest
from adapters.db.category_adapter import CategoryAdapter
from adapters.db.sqlite_adapter import _connect


@pytest.fixture(autouse=True)
def _setup(tmp_db):
    pass


def _make_user(username: str) -> int:
    from datetime import datetime
    with _connect() as con:
        cur = con.execute(
            "INSERT INTO users (username, hashed_pw, role, is_active, created_at) VALUES (?,?,?,1,?)",
            (username, "hashed", "user", datetime.utcnow().isoformat()),
        )
        return cur.lastrowid


def test_create_and_get():
    ca  = CategoryAdapter()
    uid = _make_user("cat_user1")
    cat = ca.create(uid, "Work", color="#3b82f6", description="Work stuff")
    assert cat.id > 0
    assert cat.name == "Work"
    assert cat.color == "#3b82f6"
    fetched = ca.get(cat.id, uid)
    assert fetched is not None
    assert fetched.name == "Work"


def test_list_categories():
    ca  = CategoryAdapter()
    uid = _make_user("cat_list")
    ca.create(uid, "A")
    ca.create(uid, "B")
    cats = ca.list(uid)
    names = [c.name for c in cats]
    assert "A" in names and "B" in names


def test_update_category():
    ca  = CategoryAdapter()
    uid = _make_user("cat_upd")
    cat = ca.create(uid, "Old", color="#000")
    updated = ca.update(cat.id, uid, name="New", color="#fff")
    assert updated.name == "New"
    assert updated.color == "#fff"


def test_delete_category():
    ca  = CategoryAdapter()
    uid = _make_user("cat_del")
    cat = ca.create(uid, "ToDelete")
    assert ca.delete(cat.id, uid)
    assert ca.get(cat.id, uid) is None


def test_user_isolation():
    ca   = CategoryAdapter()
    uid1 = _make_user("cat_iso1")
    uid2 = _make_user("cat_iso2")
    ca.create(uid1, "Private")
    assert all(c.name != "Private" for c in ca.list(uid2))


def test_get_foreign_category_returns_none():
    ca   = CategoryAdapter()
    uid1 = _make_user("cat_fgn1")
    uid2 = _make_user("cat_fgn2")
    cat = ca.create(uid1, "Mine")
    assert ca.get(cat.id, uid2) is None


def test_update_foreign_category_returns_none():
    ca   = CategoryAdapter()
    uid1 = _make_user("cat_fgu1")
    uid2 = _make_user("cat_fgu2")
    cat = ca.create(uid1, "X")
    assert ca.update(cat.id, uid2, name="Hacked") is None


def test_delete_foreign_category_returns_false():
    ca   = CategoryAdapter()
    uid1 = _make_user("cat_fgd1")
    uid2 = _make_user("cat_fgd2")
    cat = ca.create(uid1, "Y")
    assert not ca.delete(cat.id, uid2)


def test_transcript_categories_link():
    from adapters.db.sqlite_adapter import SQLiteAdapter
    db  = SQLiteAdapter()
    ca  = CategoryAdapter()
    uid = _make_user("cat_link")
    tid = db.upsert_transcript("link.txt", user_id=uid, content="x", line_count=1)
    cat = ca.create(uid, "Linked")
    ca.set_transcript_categories(tid, uid, [cat.id])
    linked = ca.get_transcript_categories(tid, uid)
    assert any(c.id == cat.id for c in linked)
