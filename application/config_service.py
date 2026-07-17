from __future__ import annotations

import json
from pathlib import Path
from typing import Optional

from domain.entities import AppSettings

CONFIG_PATH = Path(__file__).parent.parent / "config" / "settings.json"


class ConfigService:
    """Load and persist AppSettings.

    When constructed with a user_id, per-user settings stored in the `users`
    table take precedence over the global config/settings.json file.
    When user_id is None, only the global file is used (admin/global context).
    """

    def __init__(self, user_id: Optional[int] = None):
        self._user_id = user_id

    # ── global helpers ────────────────────────────────────────────────────────

    def _load_global(self) -> AppSettings:
        if not CONFIG_PATH.exists():
            settings = AppSettings()
            self._save_global(settings)
            return settings
        try:
            with CONFIG_PATH.open(encoding="utf-8") as f:
                return AppSettings.from_dict(json.load(f))
        except Exception:
            return AppSettings()

    def _save_global(self, settings: AppSettings) -> None:
        CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
        with CONFIG_PATH.open("w", encoding="utf-8") as f:
            json.dump(settings.to_dict(), f, indent=2)

    # ── public API ────────────────────────────────────────────────────────────

    def get(self) -> AppSettings:
        global_cfg = self._load_global()
        if self._user_id is None:
            return global_cfg
        try:
            from adapters.db.user_adapter import UserAdapter
            user = UserAdapter().get_by_id(self._user_id)
            if user and user.settings_json:
                return AppSettings.from_dict(json.loads(user.settings_json))
        except Exception:
            pass
        return global_cfg

    def save(self, settings: AppSettings) -> None:
        if self._user_id is None:
            self._save_global(settings)
        else:
            try:
                from adapters.db.user_adapter import UserAdapter
                UserAdapter().set_user_settings(self._user_id, json.dumps(settings.to_dict()))
            except Exception:
                self._save_global(settings)

    def reset(self) -> AppSettings:
        """Reset to global defaults (removes per-user overrides if any)."""
        if self._user_id is not None:
            try:
                from adapters.db.user_adapter import UserAdapter
                UserAdapter().set_user_settings(self._user_id, None)
            except Exception:
                pass
        return self._load_global()
