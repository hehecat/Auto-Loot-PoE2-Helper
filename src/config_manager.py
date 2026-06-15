"""Загрузка конфига: default.yaml + опциональный профиль (глубокий мердж)."""
import copy
import os

import yaml

DEFAULT_PATH = os.path.normpath(
    os.path.join(os.path.dirname(__file__), "..", "config", "default.yaml")
)


def _deep_merge(base, override):
    out = copy.deepcopy(base)
    for key, val in (override or {}).items():
        if isinstance(val, dict) and isinstance(out.get(key), dict):
            out[key] = _deep_merge(out[key], val)
        else:
            out[key] = val
    return out


def load_config(profile_path=None):
    with open(DEFAULT_PATH, encoding="utf-8") as f:
        cfg = yaml.safe_load(f)
    if profile_path:
        with open(profile_path, encoding="utf-8") as f:
            cfg = _deep_merge(cfg, yaml.safe_load(f) or {})
    return cfg
