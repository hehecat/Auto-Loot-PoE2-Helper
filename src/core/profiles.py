"""Менеджер профилей: обнаружение config/profiles/*.yaml и загрузка слитого конфига.

Профиль 'default' = базовый config/default.yaml без переопределений.
Остальные профили — файлы config/profiles/<name>.yaml (мерджатся поверх default).
"""
import os
from pathlib import Path

from ..config_manager import load_config

PROFILES_DIR = Path(__file__).resolve().parents[2] / "config" / "profiles"


class ProfileManager:
    def __init__(self, profiles_dir=PROFILES_DIR):
        self.dir = Path(profiles_dir)
        self.dir.mkdir(parents=True, exist_ok=True)
        self.names = ["default"] + sorted(
            p.stem for p in self.dir.glob("*.yaml") if not p.name.startswith("_")
        )
        self.idx = 0

    def set_current(self, name):
        if name in self.names:
            self.idx = self.names.index(name)

    def current(self):
        return self.names[self.idx]

    def next(self):
        self.idx = (self.idx + 1) % len(self.names)
        return self.current()

    def load(self, name):
        """Слитый конфиг для профиля по имени."""
        if name == "default":
            return load_config(None)
        path = self.dir / f"{name}.yaml"
        return load_config(str(path) if path.exists() else None)
