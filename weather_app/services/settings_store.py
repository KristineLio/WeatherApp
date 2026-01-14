from __future__ import annotations

import json
import os
from pathlib import Path

from weather_app.domain.settings import Settings


def default_settings_path() -> Path:
    """
    Prefer user home (portable + works when installed):
      ~/.weather_app/settings.json  (Linux/macOS)
      C:\\Users\\You\\.weather_app\\settings.json (Windows)
    """
    home = Path.home()
    return home / ".weather_app" / "settings.json"


class SettingsStore:
    def __init__(self, path: Path | None = None):
        self.path = path or default_settings_path()

    def load(self) -> Settings:
        try:
            if not self.path.exists():
                return Settings()

            with self.path.open("r", encoding="utf-8") as f:
                data = json.load(f)
            return Settings.from_dict(data)

        except Exception:
            # Keep app resilient: bad JSON shouldn't crash the UI
            return Settings()

    def save(self, settings: Settings) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self.path.with_suffix(".tmp")

        with tmp.open("w", encoding="utf-8") as f:
            json.dump(settings.to_dict(), f, ensure_ascii=False, indent=2)

        os.replace(tmp, self.path)
