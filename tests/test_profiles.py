from src.core.profiles import ProfileManager


def test_real_profiles_present():
    pm = ProfileManager()
    assert "default" in pm.names
    assert "mapping" in pm.names and "bossing" in pm.names
    assert pm.load("mapping")["loot"]["pickup_radius_px"] == 600
    assert pm.load("bossing")["loot"]["mode"] == "single"


def test_custom_dir_and_underscore_ignored(tmp_path):
    d = tmp_path / "profiles"
    d.mkdir()
    (d / "aaa.yaml").write_text("loot:\n  pickup_radius_px: 999\n", encoding="utf-8")
    (d / "_tmpl.yaml").write_text("x: 1\n", encoding="utf-8")
    pm = ProfileManager(d)
    assert pm.names == ["default", "aaa"]  # подчёркивание игнорируется
    cfg = pm.load("aaa")
    assert cfg["loot"]["pickup_radius_px"] == 999
    assert cfg["game"]["window_title"] == "Path of Exile 2"  # мердж с default


def test_cycle_wraps():
    pm = ProfileManager()
    start = pm.current()
    seen = [pm.next() for _ in pm.names]
    assert seen[-1] == start
