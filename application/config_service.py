from __future__ import annotations

import json
from pathlib import Path

from domain.entities import AppSettings

CONFIG_PATH = Path(__file__).parent.parent / "config" / "settings.json"


class ConfigService:
    """Load and persist AppSettings to/from config/settings.json."""

    def get(self) -> AppSettings:
        if not CONFIG_PATH.exists():
            settings = AppSettings()
            self.save(settings)
            return settings
        try:
            with CONFIG_PATH.open(encoding="utf-8") as f:
                data = json.load(f)
            return AppSettings.from_dict(data)
        except Exception:
            return AppSettings()

    def save(self, settings: AppSettings) -> None:
        CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
        with CONFIG_PATH.open("w", encoding="utf-8") as f:
            json.dump(settings.to_dict(), f, indent=2)

    def reset(self) -> AppSettings:
        settings = AppSettings()
        self.save(settings)
        return settings
