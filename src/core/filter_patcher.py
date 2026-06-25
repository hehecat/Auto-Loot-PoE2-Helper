"""注入 override 块 + 扫描 NeverSink .filter 中的原生颜色。

Override 块用 sentinel 注释包裹，具有幂等性：再次修补会替换旧块。
首次修补前会创建备份 `<filter>.bak`。

颜色扫描（--scan-colors）根据 $type-> 标签解析 Show 块，收集其 SetBackgroundColor
 — 用于无需重新着色过滤器的检测。

CLI:
    python -m src.core.filter_patcher --check         # 颜色冲突 + 补丁状态
    python -m src.core.filter_patcher --patch         # 注入/更新块
    python -m src.core.filter_patcher --unpatch       # 删除块
    python -m src.core.filter_patcher --scan-colors   # 从过滤器收集原生颜色
    python -m src.core.filter_patcher --scan-colors --config path/to/profile.yaml
"""
import argparse
import re
import shutil
from pathlib import Path

from ..config_manager import load_config
from ..logger import get_logger

START_SENTINEL = "# >>> AUTOLOOT OVERRIDE START (managed by Auto Loot PoE Helper) >>>"
END_SENTINEL = "# <<< AUTOLOOT OVERRIDE END <<<"

# category -> 条件列表（每个 -> 单独的 Show 块；块内行为 AND）
CATEGORY_CLASS = {
    "currency": ['Class "Currency"'],
    "fragments": ['Class "Map Fragments" "Tablet"'],
    "waystones": ['Class "Waystones"'],
    "uniques": ["Rarity Unique"],
    "gems": [
        'Class "Skill Gems" "Support Gems"',
        'BaseType "Uncut Skill Gem" "Uncut Support Gem" "Uncut Spirit Gem"',
    ],
}

_BG_RE = re.compile(r"^\s*SetBackgroundColor\s+(\d+)\s+(\d+)\s+(\d+)", re.IGNORECASE)
_NS_VERSION_RE = re.compile(r'NeverSink\s+PoE2?\s+([\d.]+)', re.IGNORECASE)


def detect_neversink_version(path: Path):
    """根据过滤器注释确定 NeverSink 版本。"""
    lines, _ = _read(path)
    for ln in lines[:50]:
        m = _NS_VERSION_RE.search(ln)
        if m:
            return m.group(1)
    return None

# NeverSink $type-> 类别标签（根据 Show 块注释匹配）
_CAT_MATCHERS = {
    "currency": lambda c: "$type->currency" in c and "$type->currency->splinter" not in c,
    "fragments": lambda c: "$type->fragments" in c or "$type->currency->splinter" in c,
    "waystones": lambda c: "$type->waystones" in c,
    "uniques": lambda c: "$type->uniques" in c,
    "gems": lambda c: "$type->gems" in c,
}


def _is_show_hide(line):
    """如果行开始一个 Show/Hide 块（非注释行）则为 True。"""
    m = re.match(r'^\s*(Show|Hide)\b', line)
    if not m:
        return False
    return "#" not in line[: m.start(1)]


def _read(path: Path):
    text = path.read_bytes().decode("utf-8-sig")
    newline = "\r\n" if "\r\n" in text else "\n"
    lines = text.replace("\r\n", "\n").split("\n")
    return lines, newline


def _write(path: Path, lines, newline):
    path.write_text(newline.join(lines), encoding="utf-8", newline="")


def used_background_colors(lines):
    """过滤器中（管理块之外）已占用的背景颜色集合 (r, g, b)。"""
    colors = set()
    inside = False
    for ln in lines:
        if ln.strip() == START_SENTINEL:
            inside = True
        elif ln.strip() == END_SENTINEL:
            inside = False
        elif not inside:
            m = _BG_RE.match(ln)
            if m:
                colors.add((int(m.group(1)), int(m.group(2)), int(m.group(3))))
    return colors


# 需要追加粉色标记的 Class 类型（仅修改 Show 块，不碰 Hide 块）
PATCH_CLASSES = [
    "Stackable Currency",
    "Currency",
    "Waystones",
    "Map Fragments",
    "Tablet",
    "Skill Gems",
    "Uncut Skill Gems",
    "Uncut Support Gems",
    "Uncut Spirit Gems",
    "Gems",
]

_PINK_BG = "SetBackgroundColor 255 0 200"


def _class_in_block(block_lines):
    """检查块中是否包含目标 Class 类型。"""
    for ln in block_lines:
        stripped = ln.strip()
        if stripped.startswith("Class "):
            for cls_name in PATCH_CLASSES:
                if cls_name in stripped:
                    return True
    return False


def _inject_pink_into_show_blocks(lines, marker_rgb, categories, log):
    """扫描所有 Show 块，给匹配目标 Class 的追加粉色背景。

    完全不修改 Hide 块，因此过滤器的隐藏逻辑保持不变。
    只在 Show 块中已有 SetBackgroundColor 的地方替换为粉色。
    """
    r, g, b = marker_rgb
    pink_directive = f"\tSetBackgroundColor {r} {g} {b}"

    result = []
    i = 0
    modified = 0
    while i < len(lines):
        stripped = lines[i].strip()
        if stripped.startswith("Show"):
            # 收集当前 Show 块的所有行
            block = [lines[i]]
            i += 1
            while i < len(lines):
                s = lines[i].strip()
                if s.startswith("Show") or s.startswith("Hide"):
                    break
                block.append(lines[i])
                i += 1

            if _class_in_block(block):
                # 在块末尾追加粉色背景（覆盖原有的 SetBackgroundColor）
                result.extend(block)
                result.append(pink_directive)
                modified += 1
            else:
                result.extend(block)
        elif stripped.startswith("Hide"):
            # Hide 块原封不动
            result.append(lines[i])
            i += 1
            while i < len(lines):
                s = lines[i].strip()
                if s.startswith("Show") or s.startswith("Hide"):
                    break
                result.append(lines[i])
                i += 1
        else:
            result.append(lines[i])
            i += 1

    log.info("已为 %d 个 Show 块追加粉色标记 (R=%d G=%d B=%d)", modified, r, g, b)
    return result


def _strip_block(lines):
    """移除旧格式的 sentinel 标记块（兼容之前版本）。"""
    try:
        s = next(i for i, ln in enumerate(lines) if ln.strip() == START_SENTINEL)
        e = next(i for i, ln in enumerate(lines) if ln.strip() == END_SENTINEL)
    except StopIteration:
        return lines, False
    if e < s:
        return lines, False
    return lines[:s] + lines[e + 1:], True


def patch(path: Path, marker_rgb, categories, log, category_colors=None):
    lines, newline = _read(path)

    bak = path.with_suffix(path.suffix + ".bak")
    if not bak.exists():
        shutil.copy2(path, bak)
        log.info("已备份原文件: %s", bak)

    # 先用旧方法移除之前注入的 sentinel 块（如果存在）
    lines, existed = _strip_block(lines)

    # 新方法：给现有 Show 块追加粉色
    patched = _inject_pink_into_show_blocks(lines, marker_rgb, categories, log)
    _write(path, patched, newline)

    log.info("已完成。游戏内: Escape -> 选项 -> UI -> 重新选择过滤器以重新加载。")
    return True


def unpatch(path: Path, log):
    lines, newline = _read(path)

    # 移除旧格式的 sentinel 块
    lines, existed_sentinel = _strip_block(lines)

    # 移除新格式注入的粉色行（SetBackgroundColor 255 0 200）
    new_lines = []
    removed_pink = 0
    for ln in lines:
        if ln.strip() == _PINK_BG:
            removed_pink += 1
            continue
        new_lines.append(ln)
    lines = new_lines

    if not existed_sentinel and removed_pink == 0:
        log.info("未找到补丁 — 无需删除。")
        return False

    _write(path, lines, newline)
    if removed_pink > 0:
        log.info("已从 %s 中移除 %d 行粉色标记。", path.name, removed_pink)
    if existed_sentinel:
        log.info("已从 %s 中移除旧的覆盖块。", path.name)
    return True


def check(path: Path, marker_rgb, log):
    lines, _ = _read(path)
    _, patched = _strip_block(lines)
    collide = tuple(marker_rgb) in used_background_colors(lines)
    ns_ver = detect_neversink_version(path)
    log.info("文件: %s", path)
    if ns_ver:
        log.info("NeverSink 版本: %s", ns_ver)
    log.info("补丁已安装: %s", "是" if patched else "否")
    log.info("标记颜色 %s 可用: %s", tuple(marker_rgb), "否 (冲突!)" if collide else "是")


_EXCLUDED_COLORS = {(0, 0, 0), (255, 255, 255)}


def _is_low_contrast(r, g, b):
    """如果颜色太暗或太亮 — CV 信号不良则为 True。"""
    lum = 0.299 * r + 0.587 * g + 0.114 * b
    return lum < 30 or lum > 240


def extract_filter_colors(path: Path, categories):
    """根据 $type-> 标签从 NeverSink Show 块收集 SetBackgroundColor。

    过滤掉太暗/太亮/黑色/白色的颜色 — 这些要么来自隐藏块，
    要么过于常见（误报）。
    返回 [R, G, B] 列表 — 用于检测的原生背景颜色。
    """
    lines, _newline = _read(path)
    colors = set()
    active_tags = set()

    for line in lines:
        stripped = line.strip()

        if not stripped or stripped.lstrip().startswith("#"):
            continue

        if _is_show_hide(line):
            active_tags = set()
            if stripped.startswith("Show"):
                comment = line[line.find("#"):] if "#" in line else ""
                for cat in categories:
                    if _CAT_MATCHERS.get(cat, lambda _: False)(comment):
                        active_tags.add(cat)
        elif active_tags:
            m = _BG_RE.match(stripped)
            if m:
                c = (int(m.group(1)), int(m.group(2)), int(m.group(3)))
                if c not in _EXCLUDED_COLORS and not _is_low_contrast(*c):
                    colors.add(c)

    return [list(c) for c in sorted(colors)]


def main():
    parser = argparse.ArgumentParser(description="NeverSink 过滤器工具")
    g = parser.add_mutually_exclusive_group(required=True)
    g.add_argument("--patch", action="store_true")
    g.add_argument("--unpatch", action="store_true")
    g.add_argument("--check", action="store_true")
    g.add_argument("--scan-colors", action="store_true",
                   help="从 Show 块中按 $type-> 标签收集 SetBackgroundColor")
    parser.add_argument("--config", default=None)
    args = parser.parse_args()

    cfg = load_config(args.config)
    log = get_logger(cfg)
    path = Path(cfg["filter"]["path"])
    marker = cfg["filter"]["marker_rgb"]

    if not path.exists():
        log.error("过滤器文件未找到: %s", path)
        return 1

    if args.check:
        check(path, marker, log)
    elif args.patch:
        cat_colors = cfg["filter"].get("category_colors", {})
        ok = patch(path, marker, cfg["filter"]["categories"], log, cat_colors)
        return 0 if ok else 1
    elif args.unpatch:
        unpatch(path, log)
    elif args.scan_colors:
        colors = extract_filter_colors(path, cfg["filter"]["categories"])
        log.info("找到 %d 个原生颜色用于分类 %s:",
                 len(colors), cfg["filter"]["categories"])
        for c in colors:
            log.info("  RGB %s", c)
        log.info("请添加到配置的 extra_colors 中:\n  extra_colors: %s", colors)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
