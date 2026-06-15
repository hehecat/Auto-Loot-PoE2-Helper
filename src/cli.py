"""CLI менеджер Auto Loot PoE2 Helper.

Управление через командную строку:
    python -m src.cli stats          # показать статистику за сегодня
    python -m src.cli profiles       # список профилей
    python -m src.cli patch          # патчить фильтр
    python -m src.cli unpatch        # откатить фильтр
    python -m src.cli check          # проверить статус патча
    python -m src.cli calibrate      # запустить калибровку
    python -m src.cli validate       # валидировать конфиг
"""
import argparse
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def cmd_stats(args):
    """Показать статистику."""
    from pathlib import Path
    import csv

    debug_dir = Path("_debug")
    if not debug_dir.exists():
        print("Нет данных. Запусти хотя бы одну сессию.")
        return

    csv_files = sorted(debug_dir.glob("session_*.csv"), reverse=True)
    if not csv_files:
        print("Нет CSV-файлов сессий.")
        return

    target = csv_files[0] if args.last else None
    if args.date:
        target = debug_dir / f"session_{args.date}.csv"
        if not target.exists():
            print(f"Файл для даты {args.date} не найден.")
            return

    print(f"Файл: {target.name}")
    print()

    total = 0
    by_cat = {}
    with open(target, encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            total += 1
            cat = row.get("category", "?")
            by_cat[cat] = by_cat.get(cat, 0) + 1

    print(f"Всего подобрано: {total}")
    print()
    for cat, count in sorted(by_cat.items(), key=lambda x: -x[1]):
        pct = count / total * 100 if total else 0
        print(f"  {cat:15s} {count:5d} ({pct:.0f}%)")


def cmd_profiles(args):
    """Список профилей."""
    from src.core.profiles import ProfileManager

    pm = ProfileManager()
    print("Доступные профили:")
    for name in pm.names:
        marker = " <-- текущий" if name == pm.current() else ""
        print(f"  {name}{marker}")


def cmd_patch(args):
    """Патчить фильтр."""
    from src.config_manager import load_config
    from src.core.filter_patcher import patch
    from src.logger import get_logger

    cfg = load_config(args.config)
    log = get_logger(cfg)
    from pathlib import Path
    path = Path(cfg["filter"]["path"])
    if not path.exists():
        print(f"Файл фильтра не найден: {path}")
        return
    ok = patch(path, cfg["filter"]["marker_rgb"],
               cfg["filter"]["categories"], log,
               cfg["filter"].get("category_colors"))
    print("OK" if ok else "ОШИБКА")


def cmd_unpatch(args):
    """Откатить фильтр."""
    from src.config_manager import load_config
    from src.core.filter_patcher import unpatch
    from src.logger import get_logger

    cfg = load_config(args.config)
    log = get_logger(cfg)
    from pathlib import Path
    path = Path(cfg["filter"]["path"])
    unpatch(path, log)


def cmd_check(args):
    """Проверить статус патча."""
    from src.config_manager import load_config
    from src.core.filter_patcher import check
    from src.logger import get_logger

    cfg = load_config(args.config)
    log = get_logger(cfg)
    from pathlib import Path
    path = Path(cfg["filter"]["path"])
    if not path.exists():
        print(f"Файл фильтра не найден: {path}")
        return
    check(path, cfg["filter"]["marker_rgb"], log)


def cmd_validate(args):
    """Валидировать конфиг."""
    from src.config_manager import load_config
    from src.config_validator import validate

    cfg = load_config(args.config)
    warnings = validate(cfg)
    if warnings:
        print("Предупреждения:")
        for w in warnings:
            print(f"  - {w}")
    else:
        print("Конфиг валиден.")


def main():
    parser = argparse.ArgumentParser(
        description="Auto Loot PoE2 Helper — CLI менеджер",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    sub = parser.add_subparsers(dest="command")

    p_stats = sub.add_parser("stats", help="статистика за сегодня")
    p_stats.add_argument("--last", action="store_true", help="последняя сессия")
    p_stats.add_argument("--date", help="конкретная дата (YYYYMMDD)")

    sub.add_parser("profiles", help="список профилей")

    p_patch = sub.add_parser("patch", help="патчить фильтр")
    p_patch.add_argument("--config", help="путь к конфигу")

    p_unpatch = sub.add_parser("unpatch", help="откатить фильтр")
    p_unpatch.add_argument("--config", help="путь к конфигу")

    p_check = sub.add_parser("check", help="проверить статус патча")
    p_check.add_argument("--config", help="путь к конфигу")

    p_validate = sub.add_parser("validate", help="валидировать конфиг")
    p_validate.add_argument("--config", help="путь к конфигу")

    args = parser.parse_args()

    cmds = {
        "stats": cmd_stats,
        "profiles": cmd_profiles,
        "patch": cmd_patch,
        "unpatch": cmd_unpatch,
        "check": cmd_check,
        "validate": cmd_validate,
    }

    if args.command in cmds:
        cmds[args.command](args)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
