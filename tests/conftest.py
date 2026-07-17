import pytest
import application.db_service as _db_svc_module


@pytest.fixture(scope="function", autouse=False)
def tmp_db(monkeypatch, tmp_path):
    """Redirect SQLite DB and transcripts dir to a temp directory for isolation."""
    db_path     = tmp_path / "test.db"
    transcripts = tmp_path / "transcripts"
    transcripts.mkdir()
    monkeypatch.setenv("STT_DB_PATH",         str(db_path))
    monkeypatch.setenv("STT_TRANSCRIPTS_DIR", str(transcripts))
    # Prevent startup_index from creating an auto-admin during tests
    monkeypatch.setattr(_db_svc_module, "startup_index", lambda: None)
    from adapters.db.sqlite_adapter import init_db
    init_db()
    yield tmp_path


@pytest.fixture(scope="function")
def client(tmp_db):
    from web_server import app
    from fastapi.testclient import TestClient
    with TestClient(app) as c:
        yield c


@pytest.fixture
def admin_token(client):
    res = client.post(
        "/api/auth/register",
        json={"username": "admin", "password": "Admin1234!", "email": "admin@test.com"},
    )
    assert res.status_code == 200, res.text
    return res.json()["access_token"]


@pytest.fixture
def auth_headers(admin_token):
    return {"Authorization": f"Bearer {admin_token}"}


@pytest.fixture
def user_headers(user_token):
    return {"Authorization": f"Bearer {user_token}"}


@pytest.fixture
def user_token(client, admin_token):
    admin_h = {"Authorization": f"Bearer {admin_token}"}
    r = client.post(
        "/api/admin/users",
        json={"username": "alice", "password": "Alice1234!", "email": "alice@test.com", "role": "user"},
        headers=admin_h,
    )
    assert r.status_code == 200, r.text
    res = client.post(
        "/api/auth/login",
        json={"username": "alice", "password": "Alice1234!"},
    )
    assert res.status_code == 200, res.text
    return res.json()["access_token"]
