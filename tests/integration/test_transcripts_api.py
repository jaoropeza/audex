"""Integration tests for the transcripts API endpoints."""
import pytest


def _seed_transcript(client, auth_headers, filename="t1.txt", content="[00:00:01] Hello"):
    """Insert a transcript directly via the DB adapter and return it."""
    from adapters.db.user_adapter import UserAdapter
    from adapters.db.sqlite_adapter import SQLiteAdapter
    user = UserAdapter().get_by_username("admin")
    SQLiteAdapter().upsert_transcript(filename, user_id=user.id, content=content, line_count=1)
    return filename


def test_list_transcripts_empty(client, auth_headers):
    res = client.get("/api/transcripts", headers=auth_headers)
    assert res.status_code == 200
    assert res.json()["files"] == []


def test_list_transcripts_returns_seeded(client, auth_headers):
    _seed_transcript(client, auth_headers, "listed.txt")
    res = client.get("/api/transcripts", headers=auth_headers)
    assert res.status_code == 200
    names = [f["name"] for f in res.json()["files"]]
    assert "listed.txt" in names


def test_get_transcript_content(client, auth_headers):
    _seed_transcript(client, auth_headers, "read.txt", "[00:00:01] Test line")
    res = client.get("/api/transcripts/read.txt", headers=auth_headers)
    assert res.status_code == 200
    data = res.json()
    assert data["name"] == "read.txt"
    assert isinstance(data["lines"], list)
    assert len(data["lines"]) >= 1


def test_get_transcript_not_found(client, auth_headers):
    res = client.get("/api/transcripts/missing.txt", headers=auth_headers)
    assert res.status_code == 404


def test_get_transcript_invalid_name(client, auth_headers):
    res = client.get("/api/transcripts/../etc/passwd.txt", headers=auth_headers)
    assert res.status_code in (400, 404)


def test_delete_transcript(client, auth_headers):
    _seed_transcript(client, auth_headers, "del.txt")
    res = client.delete("/api/transcripts/del.txt", headers=auth_headers)
    assert res.status_code == 200
    res2 = client.get("/api/transcripts/del.txt", headers=auth_headers)
    assert res2.status_code == 404


def test_delete_nonexistent(client, auth_headers):
    res = client.delete("/api/transcripts/ghost.txt", headers=auth_headers)
    assert res.status_code == 404


def test_tags_set_and_get(client, auth_headers):
    _seed_transcript(client, auth_headers, "tags.txt")
    res = client.put(
        "/api/transcripts/tags.txt/tags",
        json={"tags": ["meeting", "important"]},
        headers=auth_headers,
    )
    assert res.status_code == 200
    res2 = client.get("/api/transcripts/tags.txt/tags", headers=auth_headers)
    assert res2.status_code == 200
    tags = res2.json()["tags"]
    assert "meeting" in tags and "important" in tags


def test_tags_requires_auth(client):
    res = client.get("/api/transcripts/x.txt/tags")
    assert res.status_code == 401


def test_transcript_requires_auth(client):
    res = client.get("/api/transcripts/x.txt")
    assert res.status_code == 401


def test_transcript_user_isolation(client, auth_headers, user_headers):
    _seed_transcript(client, auth_headers, "admin_secret.txt")
    res = client.get("/api/transcripts/admin_secret.txt", headers=user_headers)
    assert res.status_code == 404
