import pytest


def test_list_users_as_admin(client, auth_headers):
    res = client.get("/api/admin/users", headers=auth_headers)
    assert res.status_code == 200
    users = res.json()
    assert len(users) >= 1
    assert users[0]["username"] == "admin"


def test_list_users_as_regular_user_forbidden(client, user_token):
    res = client.get(
        "/api/admin/users",
        headers={"Authorization": f"Bearer {user_token}"},
    )
    assert res.status_code == 403


def test_create_user_as_admin(client, auth_headers):
    res = client.post(
        "/api/admin/users",
        json={"username": "newuser", "password": "Newuser1!", "role": "user"},
        headers=auth_headers,
    )
    assert res.status_code == 200
    data = res.json()
    assert data["username"] == "newuser"
    assert data["role"] == "user"


def test_create_duplicate_user(client, auth_headers):
    client.post(
        "/api/admin/users",
        json={"username": "dup", "password": "Dup12345!", "role": "user"},
        headers=auth_headers,
    )
    res = client.post(
        "/api/admin/users",
        json={"username": "dup", "password": "Dup12345!", "role": "user"},
        headers=auth_headers,
    )
    assert res.status_code == 409


def test_update_user_role(client, auth_headers, user_token):
    # Get alice's user id
    users = client.get("/api/admin/users", headers=auth_headers).json()
    alice = next(u for u in users if u["username"] == "alice")
    res = client.put(
        f"/api/admin/users/{alice['id']}",
        json={"role": "admin"},
        headers=auth_headers,
    )
    assert res.status_code == 200
    assert res.json()["role"] == "admin"


def test_deactivate_user(client, auth_headers, user_token):
    users = client.get("/api/admin/users", headers=auth_headers).json()
    alice = next(u for u in users if u["username"] == "alice")
    res = client.put(
        f"/api/admin/users/{alice['id']}",
        json={"is_active": False},
        headers=auth_headers,
    )
    assert res.status_code == 200
    assert res.json()["is_active"] is False

    # Alice should no longer be able to log in
    login_res = client.post(
        "/api/auth/login",
        json={"username": "alice", "password": "Alice1234!"},
    )
    assert login_res.status_code == 401


def test_stats_shows_counts(client, auth_headers, user_token):
    res = client.get("/api/admin/stats", headers=auth_headers)
    assert res.status_code == 200
    data = res.json()
    assert data["total_users"] >= 2   # admin + alice
    assert "db_size_bytes" in data


def test_global_settings_get(client, auth_headers):
    res = client.get("/api/admin/global-settings", headers=auth_headers)
    assert res.status_code == 200
    assert "stt" in res.json()
