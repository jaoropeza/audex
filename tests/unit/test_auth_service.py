from datetime import datetime
from application.auth_service import AuthService
from domain.entities import User, UserRole


def make_user(**kwargs) -> User:
    defaults = dict(
        id=1, username="alice", email=None, hashed_pw="x",
        role=UserRole.USER, is_active=True, settings_json=None,
        created_at=datetime.utcnow().isoformat(),
    )
    defaults.update(kwargs)
    return User(**defaults)


def test_hash_and_verify():
    svc = AuthService()
    h = svc.hash_password("secret")
    assert svc.verify_password("secret", h)
    assert not svc.verify_password("wrong", h)


def test_token_roundtrip():
    svc   = AuthService()
    user  = make_user()
    token = svc.create_token(user)
    payload = svc.decode_token(token)
    assert payload["sub"]  == "1"
    assert payload["role"] == "user"


def test_admin_token_role():
    svc   = AuthService()
    user  = make_user(id=2, role=UserRole.ADMIN)
    token = svc.create_token(user)
    payload = svc.decode_token(token)
    assert payload["role"] == "admin"


def test_invalid_token_raises():
    import pytest
    from jose import JWTError
    svc = AuthService()
    with pytest.raises(JWTError):
        svc.decode_token("not.a.valid.token")
