"""Integration tests for the categories API endpoints."""
import pytest


def test_list_categories_empty(client, auth_headers):
    res = client.get("/api/categories", headers=auth_headers)
    assert res.status_code == 200
    assert res.json() == []


def test_create_category(client, auth_headers):
    res = client.post(
        "/api/categories",
        json={"name": "Meeting", "color": "#3b82f6", "description": "Team meetings"},
        headers=auth_headers,
    )
    assert res.status_code == 200
    cat = res.json()
    assert cat["name"] == "Meeting"
    assert cat["color"] == "#3b82f6"
    assert cat["id"] > 0


def test_list_categories_after_create(client, auth_headers):
    client.post("/api/categories", json={"name": "Work", "color": "#0f0"}, headers=auth_headers)
    res = client.get("/api/categories", headers=auth_headers)
    assert any(c["name"] == "Work" for c in res.json())


def test_update_category(client, auth_headers):
    cat = client.post(
        "/api/categories",
        json={"name": "Old", "color": "#000"},
        headers=auth_headers,
    ).json()
    res = client.put(
        f"/api/categories/{cat['id']}",
        json={"name": "New", "color": "#fff"},
        headers=auth_headers,
    )
    assert res.status_code == 200
    assert res.json()["name"] == "New"
    assert res.json()["color"] == "#fff"


def test_delete_category(client, auth_headers):
    cat = client.post(
        "/api/categories",
        json={"name": "ToDelete", "color": "#f00"},
        headers=auth_headers,
    ).json()
    res = client.delete(f"/api/categories/{cat['id']}", headers=auth_headers)
    assert res.status_code == 200
    remaining = client.get("/api/categories", headers=auth_headers).json()
    assert all(c["id"] != cat["id"] for c in remaining)


def test_delete_nonexistent(client, auth_headers):
    res = client.delete("/api/categories/99999", headers=auth_headers)
    assert res.status_code == 404


def test_categories_require_auth(client):
    res = client.get("/api/categories")
    assert res.status_code == 401


def test_categories_user_isolated(client, auth_headers, user_headers):
    client.post(
        "/api/categories",
        json={"name": "AdminPrivate", "color": "#f00"},
        headers=auth_headers,
    )
    res = client.get("/api/categories", headers=user_headers)
    assert all(c["name"] != "AdminPrivate" for c in res.json())


def test_update_foreign_category_forbidden(client, auth_headers, user_headers):
    cat = client.post(
        "/api/categories",
        json={"name": "AdminCat", "color": "#000"},
        headers=auth_headers,
    ).json()
    res = client.put(
        f"/api/categories/{cat['id']}",
        json={"name": "Hacked"},
        headers=user_headers,
    )
    assert res.status_code == 404


def test_duplicate_name_same_user(client, auth_headers):
    client.post("/api/categories", json={"name": "Dup", "color": "#0f0"}, headers=auth_headers)
    res = client.post("/api/categories", json={"name": "Dup", "color": "#00f"}, headers=auth_headers)
    assert res.status_code in (400, 409)


def test_assign_categories_to_transcript(client, auth_headers):
    from adapters.db.user_adapter import UserAdapter
    from adapters.db.sqlite_adapter import SQLiteAdapter
    user = UserAdapter().get_by_username("admin")
    tid  = SQLiteAdapter().upsert_transcript("catlink.txt", user_id=user.id, content="x", line_count=1)

    cat = client.post(
        "/api/categories",
        json={"name": "Linked", "color": "#0f0"},
        headers=auth_headers,
    ).json()

    res = client.put(
        "/api/transcripts/catlink.txt/categories",
        json={"category_ids": [cat["id"]]},
        headers=auth_headers,
    )
    assert res.status_code == 200

    res2 = client.get("/api/transcripts/catlink.txt/categories", headers=auth_headers)
    assert res2.status_code == 200
    assert any(c["id"] == cat["id"] for c in res2.json())
