import numpy as np

from src.calibrate import _initial_colors, sample_rgb, save_calibration
from src.config_manager import load_config


def test_sample_rgb_and_clamp():
    f = np.zeros((20, 20, 3), np.uint8)
    f[5, 7] = (255, 255, 0)  # BGR cyan в (x=7, y=5)
    assert sample_rgb(f, 7, 5) == [0, 255, 255]
    assert sample_rgb(f, 999, 999) == [0, 0, 0]  # за границей -> кламп


def test_save_and_load_roundtrip(tmp_path):
    p = tmp_path / "cal.yaml"
    save_calibration(p, [[0, 255, 255], [180, 0, 255]], 9, 150, 140, 15, 500, [5, -10])
    cfg = load_config(str(p))
    assert cfg["filter"]["marker_rgb"] == [0, 255, 255]
    assert cfg["filter"]["extra_colors"] == [[180, 0, 255]]
    assert cfg["vision"]["hue_tolerance"] == 9
    assert cfg["loot"]["pickup_radius_px"] == 500
    assert cfg["loot"]["center_offset_xy"] == [5, -10]
    assert cfg["game"]["window_title"] == "Path of Exile 2"  # мердж с default


def test_initial_colors():
    base = load_config(None)
    marker = list(base["filter"]["marker_rgb"])
    assert _initial_colors(base) == [marker]
    base["filter"]["extra_colors"] = [[1, 2, 3]]
    assert _initial_colors(base) == [marker, [1, 2, 3]]
