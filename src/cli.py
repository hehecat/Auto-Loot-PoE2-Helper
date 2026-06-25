"""Auto Loot PoE2 Helper CLI 管理器。

通过命令行管理：
    python -m src.cli stats          # 显示今日统计数据
    python -m src.cli profiles       # 配置文件列表
    python -m src.cli patch          # 应用过滤器补丁
    python -m src.cli unpatch        # 撤销过滤器补丁
    python -m src.cli check          # 检查补丁状态
    python -m src.cli calibrate      # 启动校准
    python -m src.cli validate       # 验证配置
"""
import argparse
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def cmd_stats(args):
    """显示统计数据。"""
    from pathlib import Path
    import csv

    debug_dir = Path("_debug")
    if not debug_dir.exists():
        print("没有数据。请至少运行一次会话。")
        return

    csv_files = sorted(debug_dir.glob("session_*.csv"), reverse=True)
    if not csv_files:
        print("没有会话 CSV 文件。")
        return

    target = csv_files[0] if args.last else None
    if args.date:
        target = debug_dir / f"session_{args.date}.csv"
        if not target.exists():
            print(f"日期 {args.date} 的文件未找到。")
            return

    print(f"文件: {target.name}")
    print()

    total = 0
    by_cat = {}
    with open(target, encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            total += 1
            cat = row.get("category", "?")
            by_cat[cat] = by_cat.get(cat, 0) + 1

    print(f"总计拾取: {total}")
    print()
    for cat, count in sorted(by_cat.items(), key=lambda x: -x[1]):
        pct = count / total * 100 if total else 0
        print(f"  {cat:15s} {count:5d} ({pct:.0f}%)")


def cmd_profiles(args):
    """列出配置文件。"""
    from src.core.profiles import ProfileManager

    pm = ProfileManager()
    print("可用配置:")
    for name in pm.names:
        marker = " <-- 当前" if name == pm.current() else ""
        print(f"  {name}{marker}")


def cmd_patch(args):
    """修补过滤器。"""
    from src.config_manager import load_config
    from src.core.filter_patcher import patch
    from src.logger import get_logger

    cfg = load_config(args.config)
    log = get_logger(cfg)
    from pathlib import Path
    path = Path(cfg["filter"]["path"])
    if not path.exists():
        print(f"过滤器文件未找到: {path}")
        return
    ok = patch(path, cfg["filter"]["marker_rgb"],
               cfg["filter"]["categories"], log,
               cfg["filter"].get("category_colors"))
    print("成功" if ok else "失败")


def cmd_unpatch(args):
    """回滚过滤器。"""
    from src.config_manager import load_config
    from src.core.filter_patcher import unpatch
    from src.logger import get_logger

    cfg = load_config(args.config)
    log = get_logger(cfg)
    from pathlib import Path
    path = Path(cfg["filter"]["path"])
    unpatch(path, log)


def cmd_check(args):
    """检查补丁状态。"""
    from src.config_manager import load_config
    from src.core.filter_patcher import check
    from src.logger import get_logger

    cfg = load_config(args.config)
    log = get_logger(cfg)
    from pathlib import Path
    path = Path(cfg["filter"]["path"])
    if not path.exists():
        print(f"过滤器文件未找到: {path}")
        return
    check(path, cfg["filter"]["marker_rgb"], log)


def cmd_validate(args):
    """验证配置。"""
    from src.config_manager import load_config
    from src.config_validator import validate

    cfg = load_config(args.config)
    warnings = validate(cfg)
    if warnings:
        print("警告:")
        for w in warnings:
            print(f"  - {w}")
    else:
        print("配置有效。")


def cmd_gui(args):
    """启动 GUI。"""
    from src.ui.app import run_gui
    run_gui()


def main():
    parser = argparse.ArgumentParser(
        description="自动拾取 PoE2 助手 — CLI 管理工具",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    sub = parser.add_subparsers(dest="command")

    p_stats = sub.add_parser("stats", help="今日统计")
    p_stats.add_argument("--last", action="store_true", help="最近一次会话")
    p_stats.add_argument("--date", help="指定日期 (YYYYMMDD)")

    sub.add_parser("profiles", help="配置列表")

    p_patch = sub.add_parser("patch", help="给过滤器打补丁")
    p_patch.add_argument("--config", help="配置文件路径")

    p_unpatch = sub.add_parser("unpatch", help="回滚过滤器")
    p_unpatch.add_argument("--config", help="配置文件路径")

    p_check = sub.add_parser("check", help="检查补丁状态")
    p_check.add_argument("--config", help="配置文件路径")

    p_validate = sub.add_parser("validate", help="验证配置")
    p_validate.add_argument("--config", help="配置文件路径")

    sub.add_parser("gui", help="启动 GUI")

    args = parser.parse_args()

    cmds = {
        "stats": cmd_stats,
        "profiles": cmd_profiles,
        "patch": cmd_patch,
        "unpatch": cmd_unpatch,
        "check": cmd_check,
        "validate": cmd_validate,
        "gui": cmd_gui,
    }

    if args.command in cmds:
        cmds[args.command](args)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
