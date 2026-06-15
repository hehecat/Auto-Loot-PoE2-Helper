"""Впрыск override-блока + сканирование нативных цветов из NeverSink .filter.

Override-блок обёрнут sentinel-комментариями и идемпотентен: повторный патч
заменяет старый блок. Перед первым патчем создаётся бэкап `<filter>.bak`.

Сканирование цветов (--scan-colors) парсит Show-блоки по $type-> тегам и собирает
их SetBackgroundColor — для детекции без перекраски фильтра.

CLI:
    python -m src.core.filter_patcher --check         # коллизия цвета + статус патча
    python -m src.core.filter_patcher --patch         # впрыснуть/обновить блок
    python -m src.core.filter_patcher --unpatch       # удалить блок
    python -m src.core.filter_patcher --scan-colors   # собрать нативные цвета из фильтра
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

# category -> список условий (каждое -> отдельный Show-блок; внутри блока строки = AND)
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

# NeverSink $type-> теги для категорий (матчим по комментарию Show-блока)
_CAT_MATCHERS = {
    "currency": lambda c: "$type->currency" in c and "$type->currency->splinter" not in c,
    "fragments": lambda c: "$type->fragments" in c or "$type->currency->splinter" in c,
    "waystones": lambda c: "$type->waystones" in c,
    "uniques": lambda c: "$type->uniques" in c,
    "gems": lambda c: "$type->gems" in c,
}


def _is_show_hide(line):
    """True если строка начинает Show/Hide-блок (не закомментирована)."""
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
    """Множество (r, g, b) фоновых цветов, занятых в фильтре (вне управляемого блока)."""
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


def build_block(marker_rgb, categories, category_colors=None):
    category_colors = category_colors or {}
    out = [START_SENTINEL,
           "# Авто-собираемые категории перекрашены в цвета-маркеры. Не редактируй вручную."]
    for cat in categories:
        conditions = CATEGORY_CLASS.get(cat)
        if not conditions:
            continue
        r, g, b = category_colors.get(cat, marker_rgb)
        for cond in conditions:
            out += [
                f"Show # AUTOLOOT: {cat}",
                f"\t{cond}",
                "\tSetFontSize 40",
                "\tSetTextColor 0 0 0 255",
                "\tSetBorderColor 0 0 0 255",
                f"\tSetBackgroundColor {r} {g} {b} 255",
            ]
    out.append(END_SENTINEL)
    return out


def _strip_block(lines):
    """Удалить существующий управляемый блок (между sentinel включительно)."""
    try:
        s = next(i for i, ln in enumerate(lines) if ln.strip() == START_SENTINEL)
        e = next(i for i, ln in enumerate(lines) if ln.strip() == END_SENTINEL)
    except StopIteration:
        return lines, False
    if e < s:
        return lines, False
    return lines[:s] + lines[e + 1:], True


def _insertion_index(lines):
    """Индекс, куда вставить блок: сразу после waypoint c0.start (верх правил)."""
    for i, ln in enumerate(lines):
        if "Waypoint c0.start" in ln:
            return i + 1
    for i, ln in enumerate(lines):
        if "[[0100]] Gold" in ln and not ln.lstrip().startswith("# [["):
            return i
    # фолбэк: перед первым Show/Hide
    for i, ln in enumerate(lines):
        if re.match(r"^\s*(Show|Hide)\b", ln):
            return i
    return len(lines)


def patch(path: Path, marker_rgb, categories, log, category_colors=None):
    lines, newline = _read(path)

    all_colors = [tuple(marker_rgb)]
    if category_colors:
        all_colors += [tuple(c) for c in category_colors.values() if c]
    used = used_background_colors(lines)
    for c in all_colors:
        if c in used:
            log.error("Цвет %s уже используется в фильтре — будут ложные срабатывания. "
                      "Поменяй цвета в конфиге.", c)
            return False

    bak = path.with_suffix(path.suffix + ".bak")
    if not bak.exists():
        shutil.copy2(path, bak)
        log.info("Бэкап оригинала: %s", bak)

    lines, existed = _strip_block(lines)
    block = build_block(marker_rgb, categories, category_colors)
    idx = _insertion_index(lines)
    lines[idx:idx] = block
    _write(path, lines, newline)

    log.info("%s override-блок (%d категорий) с %d уникальными цветами в %s",
             "Обновлён" if existed else "Впрыснут", len(categories), len(set(all_colors)), path.name)
    log.info("В игре: Escape -> Options -> UI -> перевыбери фильтр, чтобы перезагрузить.")
    return True


def unpatch(path: Path, log):
    lines, newline = _read(path)
    lines, existed = _strip_block(lines)
    if not existed:
        log.info("Управляемый блок не найден — нечего удалять.")
        return False
    _write(path, lines, newline)
    log.info("Override-блок удалён из %s.", path.name)
    return True


def check(path: Path, marker_rgb, log):
    lines, _ = _read(path)
    _, patched = _strip_block(lines)
    collide = tuple(marker_rgb) in used_background_colors(lines)
    log.info("Файл: %s", path)
    log.info("Патч установлен: %s", "да" if patched else "нет")
    log.info("Маркер %s свободен: %s", tuple(marker_rgb), "НЕТ (коллизия!)" if collide else "да")


_EXCLUDED_COLORS = {(0, 0, 0), (255, 255, 255)}


def _is_low_contrast(r, g, b):
    """True если цвет слишком тёмный или слишком светлый — плохой сигнал для CV."""
    lum = 0.299 * r + 0.587 * g + 0.114 * b
    return lum < 30 or lum > 240


def extract_filter_colors(path: Path, categories):
    """Собрать SetBackgroundColor из Show-блоков NeverSink по $type-> тегам.

    Отфильтровывает слишком тёмные/светлые/чёрные/белые цвета — они либо от
    скрытых блоков, либо слишком частые (ложные срабатывания).
    Возвращает список [R, G, B] — нативные цвета фона для детекции.
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
    parser = argparse.ArgumentParser(description="NeverSink filter tool")
    g = parser.add_mutually_exclusive_group(required=True)
    g.add_argument("--patch", action="store_true")
    g.add_argument("--unpatch", action="store_true")
    g.add_argument("--check", action="store_true")
    g.add_argument("--scan-colors", action="store_true",
                   help="собрать SetBackgroundColor из Show-блоков по $type-> тегам")
    parser.add_argument("--config", default=None)
    args = parser.parse_args()

    cfg = load_config(args.config)
    log = get_logger(cfg)
    path = Path(cfg["filter"]["path"])
    marker = cfg["filter"]["marker_rgb"]

    if not path.exists():
        log.error("Файл фильтра не найден: %s", path)
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
        log.info("Найдено %d нативных цветов для категорий %s:",
                 len(colors), cfg["filter"]["categories"])
        for c in colors:
            log.info("  RGB %s", c)
        log.info("Добавь в extra_colors конфига:\n  extra_colors: %s", colors)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
