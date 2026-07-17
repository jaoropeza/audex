import pytest


def test_bootstrap_status_empty_db(client):
    res = client.get("/api/auth/bootstrap-status")
    assert res.status_code == 200
    assert res.json()["needs_setup"] is True


def test_register_first_user(client):
    res = client.post(
        "/api/auth/register",
        json={"username": "admin", "password": "Admin1234!"},
    )
    assert res.status_code == 200
    data = res.json()
    assert "access_token" in data
    assert data["user"]["username"] == "admin"
    assert data["user"]["role"] == "admin"


def test_bootstrap_status_after_register(client, admin_token):
    res = client.get("/api/auth/bootstrap-status")
    assert res.json()["needs_setup"] is False


def test_register_second_user_blocked(client, admin_token):
    res = client.post(
        "/api/auth/register",
        json={"username": "other", "password": "Other1234!"},
    )
    assert res.status_code == 403


def test_login_correct(client, admin_token):
    res = client.post(
        "/api/auth/login",
        json={"username": "admin", "password": "Admin1234!"},
    )
    assert res.status_code == 200
    assert "access_token" in res.json()


def test_login_wrong_password(client, admin_token):
    res = client.post(
        "/api/auth/login",
        json={"username": "admin", "password": "wrong"},
    )
    assert res.status_code == 401


def test_login_unknown_user(client, admin_token):
    res = client.post(
        "/api/auth/login",
        json={"username": "nobody", "password": "pw"},
    )
    assert res.status_code == 401


def test_me_returns_user(client, auth_headers):
    res = client.get("/api/auth/me", headers=auth_headers)
    assert res.status_code == 200
    assert res.json()["username"] == "admin"


def test_me_without_token(client):
    res = client.get("/api/auth/me")
    assert res.status_code == 401
