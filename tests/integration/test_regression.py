"""
Regression tests: confirm every existing feature still works after auth was added.
One test per major pre-existing endpoint.
"""
import pytest


def test_list_transcripts_requires_auth(client):
    res = client.get("/api/transcripts")
    assert res.status_code == 401


def test_list_transcripts_with_auth(client, auth_headers):
    res = client.get("/api/transcripts", headers=auth_headers)
    assert res.status_code == 200
    assert isinstance(res.json()["files"], list)


def test_translate_requires_auth(client):
    res = client.post(
        "/api/translate",
        json={"lines": ["hello"], "target_language": "Spanish"},
    )
    assert res.status_code == 401


def test_config_get_with_auth(client, auth_headers):
    res = client.get("/api/config", headers=auth_headers)
    assert res.status_code == 200
    data = res.json()
    assert "stt" in data
    assert "translation" in data
    assert "summary" in data


def test_config_get_requires_auth(client):
    res = client.get("/api/config")
    assert res.status_code == 401


def test_recording_status_with_auth(client, auth_headers):
    res = client.get("/api/recording/status", headers=auth_headers)
    assert res.status_code == 200
    data = res.json()
    assert "running" in data


def test_recording_status_requires_auth(client):
    res = client.get("/api/recording/status")
    assert res.status_code == 401


def test_db_search_requires_auth(client):
    res = client.get("/api/db/search?q=hello")
    assert res.status_code == 401


def test_db_search_with_auth_no_results(client, auth_headers):
    res = client.get("/api/db/search?q=hello", headers=auth_headers)
    assert res.status_code == 200
    assert "results" in res.json()


def test_admin_stats_requires_admin(client, user_token):
    res = client.get(
        "/api/admin/stats",
        headers={"Authorization": f"Bearer {user_token}"},
    )
    assert res.status_code == 403


def test_admin_stats_with_admin(client, auth_headers):
    res = client.get("/api/admin/stats", headers=auth_headers)
    assert res.status_code == 200
    data = res.json()
    assert "total_users" in data
    assert "total_transcripts" in data


def test_categories_requires_auth(client):
    res = client.get("/api/categories")
    assert res.status_code == 401


def test_categories_crud(client, auth_headers):
    res = client.post(
        "/api/categories",
        json={"name": "Work", "color": "#3b82f6"},
        headers=auth_headers,
    )
    assert res.status_code == 200
    cat = res.json()
    assert cat["name"] == "Work"

    res2 = client.get("/api/categories", headers=auth_headers)
    assert any(c["name"] == "Work" for c in res2.json())

    res3 = client.delete(f"/api/categories/{cat['id']}", headers=auth_headers)
    assert res3.status_code == 200


def test_categories_user_isolated(client, auth_headers, user_token):
    client.post(
        "/api/categories",
        json={"name": "AdminOnly", "color": "#f00"},
        headers=auth_headers,
    )
    res = client.get(
        "/api/categories",
        headers={"Authorization": f"Bearer {user_token}"},
    )
    assert all(c["name"] != "AdminOnly" for c in res.json())


def test_transcript_content_user_isolated(client, auth_headers, user_token, tmp_db):
    """Admin uploads a transcript; regular user should NOT see it."""
    from adapters.db.sqlite_adapter import SQLiteAdapter
    from adapters.db.user_adapter import UserAdapter
    ua   = UserAdapter()
    admin = ua.get_by_username("admin")
    db   = SQLiteAdapter()
    db.upsert_transcript("admin_only.txt", user_id=admin.id, content="secret", line_count=1)

    res_admin = client.get("/api/transcripts", headers=auth_headers)
    files_admin = [f["name"] for f in res_admin.json()["files"]]
    assert "admin_only.txt" in files_admin

    res_user = client.get(
        "/api/transcripts",
        headers={"Authorization": f"Bearer {user_token}"},
    )
    files_user = [f["name"] for f in res_user.json()["files"]]
    assert "admin_only.txt" not in files_user
