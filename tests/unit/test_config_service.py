import pytest
import json
from application.config_service import ConfigService
from domain.entities import AppSettings, TranslationProvider


@pytest.fixture(autouse=True)
def _setup(tmp_db):
    pass


def test_global_config_returns_defaults():
    svc = ConfigService()
    cfg = svc.get()
    assert isinstance(cfg, AppSettings)
    assert cfg.stt.model == "large-v3"


def test_per_user_config_falls_back_to_global(tmp_db):
    # Insert a user manually via UserAdapter
    from adapters.db.user_adapter import UserAdapter
    from application.auth_service import AuthService
    ua  = UserAdapter()
    hpw = AuthService().hash_password("pw")
    user = ua.create_user("test_cfg_user", hpw, role="user")

    # No per-user settings yet → should return global defaults
    svc = ConfigService(user.id)
    cfg = svc.get()
    assert cfg.stt.model == "large-v3"


def test_per_user_config_saves_and_loads(tmp_db):
    from adapters.db.user_adapter import UserAdapter
    from application.auth_service import AuthService
    ua   = UserAdapter()
    hpw  = AuthService().hash_password("pw")
    user = ua.create_user("cfg_save_user", hpw, role="user")

    svc = ConfigService(user.id)
    orig = svc.get()
    orig.translation.model = "gpt-4o"
    svc.save(orig)

    # Re-load
    svc2 = ConfigService(user.id)
    cfg2 = svc2.get()
    assert cfg2.translation.model == "gpt-4o"


def test_reset_clears_per_user_settings(tmp_db):
    from adapters.db.user_adapter import UserAdapter
    from application.auth_service import AuthService
    ua   = UserAdapter()
    hpw  = AuthService().hash_password("pw")
    user = ua.create_user("cfg_reset_user", hpw, role="user")

    svc = ConfigService(user.id)
    orig = svc.get()
    orig.stt.model = "tiny"
    svc.save(orig)
    assert ConfigService(user.id).get().stt.model == "tiny"

    svc.reset()
    assert ConfigService(user.id).get().stt.model == "large-v3"
