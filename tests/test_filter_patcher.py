from src.core import filter_patcher as fp

SAMPLE = "\n".join([
    "# header",
    '# !! Waypoint c0.start : "Start - Override ALL rules" : "Gold"',
    "Show",
    '\tClass == "Gold"',
    "\tSetBackgroundColor 255 199 0 166",
    "Show",
    "\tClass Currency",
    "\tSetBackgroundColor 255 255 255 255",
    "",
]) + "\n"


def _mk(tmp_path):
    p = tmp_path / "t.filter"
    p.write_text(SAMPLE, encoding="utf-8")
    return p


def test_patch_inserts_block_after_waypoint(tmp_path, log):
    p = _mk(tmp_path)
    assert fp.patch(p, [0, 255, 255], ["currency", "fragments", "waystones"], log)
    lines, _ = fp._read(p)
    assert any("SetBackgroundColor 0 255 255 255" in ln for ln in lines)
    si = next(i for i, ln in enumerate(lines) if "c0.start" in ln)
    bi = next(i for i, ln in enumerate(lines) if fp.START_SENTINEL in ln)
    assert bi == si + 1
    assert p.with_suffix(p.suffix + ".bak").exists()


def test_patch_idempotent(tmp_path, log):
    p = _mk(tmp_path)
    fp.patch(p, [0, 255, 255], ["currency"], log)
    n1 = len(fp._read(p)[0])
    fp.patch(p, [0, 255, 255], ["currency"], log)
    n2 = len(fp._read(p)[0])
    assert n1 == n2


def test_unpatch_restores(tmp_path, log):
    p = _mk(tmp_path)
    n0 = len(fp._read(p)[0])
    fp.patch(p, [0, 255, 255], ["currency", "fragments", "waystones"], log)
    assert fp.unpatch(p, log)
    assert len(fp._read(p)[0]) == n0
    assert not fp.unpatch(p, log)  # больше нечего удалять


def test_collision_refuses(tmp_path, log):
    p = _mk(tmp_path)
    # цвет 255 199 0 уже используется в SAMPLE -> патч должен отказать
    assert fp.patch(p, [255, 199, 0], ["currency"], log) is False


def test_build_block_contains_categories():
    block = "\n".join(fp.build_block([1, 2, 3], ["currency", "waystones"]))
    assert "AUTOLOOT: currency" in block
    assert "AUTOLOOT: waystones" in block
    assert "SetBackgroundColor 1 2 3 255" in block
