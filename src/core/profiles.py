"""配置管理器：发现 config/profiles/*.yaml 并加载合并后的配置。

配置文件 'default' = 基础的 config/default.yaml，无覆盖。
其他配置文件 — config/profiles/<name>.yaml 文件（合并到 default 之上）。
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
        """按名称获取配置文件合并后的配置。"""
        if name == "default":
            return load_config(None)
        path = self.dir / f"{name}.yaml"
        return load_config(str(path) if path.exists() else None)
