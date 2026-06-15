import numpy as np
from src.vision.hp_detector import detect_hp_ratio

REGION = {"x": 0.0, "y": 0.0, "w": 1.0, "h": 1.0}  # весь кадр


def _make_hp_frame(fill_ratio, width=100, height=200):
    """Синтетический кадр: нижние fill_ratio*height строк = HP-красный, верхние = чёрные."""
    frame = np.zeros((height, width, 3), dtype=np.uint8)
    filled_rows = int(height * fill_ratio)
    # HP-красный BGR: (30, 20, 180) — тёмно-красный
    frame[height - filled_rows:, :] = (30, 20, 180)
    return frame


def test_full_hp():
    frame = _make_hp_frame(1.0)
    ratio = detect_hp_ratio(frame, REGION)
    assert ratio > 0.85


def test_empty_hp():
    frame = _make_hp_frame(0.0)
    ratio = detect_hp_ratio(frame, REGION)
    assert ratio < 0.10


def test_half_hp():
    frame = _make_hp_frame(0.5)
    ratio = detect_hp_ratio(frame, REGION)
    assert 0.35 < ratio < 0.65


def test_bad_region_returns_full():
    frame = np.zeros((100, 100, 3), dtype=np.uint8)
    ratio = detect_hp_ratio(frame, {"x": 2.0, "y": 2.0, "w": 0.1, "h": 0.1})
    assert ratio == 1.0
