"""入口点。捕获 PoE2 窗口 -> 检测标记颜色 -> 通过快捷键拾取 + 浮窗。

安全性：仅在游戏窗口处于焦点时进行点击/自动操作。未找到窗口时
（回退到显示器），点击被禁用。

模式（loot.mode）：hold（按住 pickup 时）、toggle（按 toggle 开/关）、single（每次按键点击一次）。
配置文件：--profile <name> 或快捷键 profile（循环切换）。自动药水/技能：automation 部分。

运行：
    python -m src.main                  # 工作模式 + 浮窗
    python -m src.main --profile mapping
    python -m src.main --no-overlay
    python -m src.main --calibrate      # 目标高亮窗口（无浮窗）
"""
import argparse
import threading
import time

import cv2

from .capture.screen import ScreenCapture
from .capture.window import GameWindow, monitor_region
from .config_manager import load_config
from .core.automation import Automation
from .core.hp_watcher import HPWatcher
from .core.loot_engine import LootEngine
from .core.loot_evaluator import RuleEvaluator, LLMEvaluator
from .core.pickup_logger import PickupLogger
from .core.profiles import ProfileManager
from .core.stats import StatsCollector
from .core.auto_calibrate import try_auto_calibrate
from .core.telegram_notify import TelegramNotifier
from .core.html_report import generate_html_report
from .input.keyboard import key_matches, parse_key, ComboTracker
from .input.mouse import Mouse
from .logger import get_logger
from .vision.color_detector import ColorDetector


class State:
    def __init__(self):
        self._lock = threading.Lock()
        self.auto_on = False
        self.pickup_held = False
        self.single_request = False
        self.pending_profile = None
        self.active_categories = None  # None = 全部，set = 仅指定的类别

    def toggle_auto(self):
        with self._lock:
            self.auto_on = not self.auto_on
            return self.auto_on

    def set_pickup(self, held):
        with self._lock:
            self.pickup_held = held

    def request_single(self):
        with self._lock:
            self.single_request = True

    def consume_single(self):
        with self._lock:
            if self.single_request:
                self.single_request = False
                return True
            return False

    def set_pending_profile(self, name):
        with self._lock:
            self.pending_profile = name

    def consume_pending_profile(self):
        with self._lock:
            name = self.pending_profile
            self.pending_profile = None
            return name

    def set_category_filter(self, categories):
        """设置类别过滤器（None = 全部）。"""
        with self._lock:
            self.active_categories = set(categories) if categories else None

    def get_active_categories(self):
        """获取当前激活的类别。"""
        with self._lock:
            return self.active_categories

    def snapshot(self):
        with self._lock:
            return self.auto_on, self.pickup_held


class Status:
    def __init__(self, **initial):
        self._lock = threading.Lock()
        self._data = dict(initial)

    def update(self, **kw):
        with self._lock:
            self._data.update(kw)

    def snapshot(self):
        with self._lock:
            return dict(self._data)


class Live:
    def __init__(self, det, mode, cat_map=None):
        self.lock = threading.Lock()
        self.det = det
        self.mode = mode
        self.cat_map = cat_map or {}


def detector_colors(cfg):
    f = cfg["filter"]
    colors = [list(f["marker_rgb"])]
    colors += [list(c) for c in f.get("extra_colors", []) or []]
    for c in f.get("category_colors", {}).values():
        if c and list(c) not in colors:
            colors.append(list(c))
    return colors


def build_detector(cfg):
    v = cfg["vision"]
    return ColorDetector(
        markers=detector_colors(cfg),
        hue_tol=v.get("hue_tolerance", 8),
        sat_min=v.get("sat_min", 120),
        val_min=v.get("val_min", 120),
        min_blob_area=v.get("min_blob_area", 12),
        close_px=v.get("close_px", 9),
    )


def category_for_pixel(hsv, tx, ty, cat_map, hue_tol, sat_min, val_min):
    """根据点击位置像素颜色确定物品类别。"""
    from .vision.color_detector import rgb_to_hsv_bounds
    if not (0 <= ty < hsv.shape[0] and 0 <= tx < hsv.shape[1]):
        return "?"
    px = hsv[ty, tx]
    for name, rgb in cat_map.items():
        for lo, hi in rgb_to_hsv_bounds(rgb, hue_tol, sat_min, val_min):
            if all(lo[i] <= px[i] <= hi[i] for i in range(3)):
                return name
    return "?"


def compute_priorities(points, hsv, cat_map, priority_cfg, hue_tol, sat_min, val_min):
    """返回帧中各点的 {(cx,cy): priority_int}。数值越小越重要。"""
    if not cat_map or not priority_cfg:
        return {}
    from .vision.color_detector import rgb_to_hsv_bounds
    h, w = hsv.shape[:2]
    result = {}
    for cx, cy, _area in points:
        if not (0 <= cy < h and 0 <= cx < w):
            continue
        px = hsv[cy, cx]
        cat = "?"
        for name, rgb in cat_map.items():
            for lo, hi in rgb_to_hsv_bounds(rgb, hue_tol, sat_min, val_min):
                if all(lo[i] <= px[i] <= hi[i] for i in range(3)):
                    cat = name
                    break
            if cat != "?":
                break
        result[(cx, cy)] = priority_cfg.get(cat, 99)
    return result


def run_loop(args, cfg, log, stop_event, status, win, region, clicks_enabled,
             cap, engine, live, apply_profile, hp_watcher=None, state=None, telegram=None):
    target_fps = max(1, cfg["capture"].get("target_fps", 30))
    frame_budget = 1.0 / target_fps
    last_log = 0.0
    picked = 0
    stats = {}   # {category: count} — 会话期间各类别的计数器
    vp = cfg.get("vision", {})
    loot_cfg = cfg.get("loot", {})
    priority_cfg = loot_cfg.get("category_priority", {})
    pickup_log = PickupLogger(enabled=cfg.get("logging", {}).get("csv_pickup", True))
    stats_collector = StatsCollector()
    stats_collector.start_session()

    if cap._double_buffer:
        cap.start_buffer(region, target_fps)

    try:
        while not stop_event.is_set():
            t0 = time.perf_counter()

            pending = state.consume_pending_profile() if state else None
            if pending:
                apply_profile(pending)

            frame = cap.grab(region)
            if frame is None:
                time.sleep(frame_budget)
                continue

            with live.lock:
                det, mode, cat_map = live.det, live.mode, live.cat_map

            roi = engine.get_roi(frame.shape)
            if roi:
                x1, y1, x2, y2 = roi
                detect_frame = frame[y1:y2, x1:x2]
                roi_offset = (x1, y1)
            else:
                detect_frame = frame
                roi_offset = (0, 0)

            points, mask = det.detect(detect_frame)
            if roi:
                points = [(x + roi_offset[0], y + roi_offset[1], a) for x, y, a in points]

            in_radius = engine.targets_in_radius(points, frame.shape)

            auto_on, pickup_held = state.snapshot() if state else (False, False)
            active_categories = state.get_active_categories() if state else None

            if active_categories and in_radius:
                hue_tol = vp.get("hue_tolerance", 8)
                sat_min = vp.get("sat_min", 120)
                val_min = vp.get("val_min", 120)
                hsv_check = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)
                filtered = []
                for p in in_radius:
                    cat = category_for_pixel(hsv_check, p[0], p[1], cat_map,
                                             hue_tol, sat_min, val_min)
                    if cat in active_categories:
                        filtered.append(p)
                in_radius = filtered
            active = (
                (mode == "hold" and pickup_held)
                or (mode in ("toggle", "lazy") and auto_on)
                or (mode == "single" and state.consume_single())
            )

            foreground = win.is_foreground()
            if active and clicks_enabled and foreground:
                hue_tol = vp.get("hue_tolerance", 8)
                sat_min = vp.get("sat_min", 120)
                val_min = vp.get("val_min", 120)
                hsv_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV) if cat_map else None
                priorities = (
                    compute_priorities(in_radius, hsv_frame, cat_map, priority_cfg,
                                       hue_tol, sat_min, val_min)
                    if cat_map and priority_cfg else None
                )
                if mode == "lazy":
                    mx, my = engine.mouse.position()
                    ref = (mx - region["left"], my - region["top"])
                    result = engine.pick_at(points, ref, engine.lazy_radius, priorities)
                else:
                    result = engine.pick_once(points, frame.shape, priorities) if in_radius else None
                if result:
                    tx, ty = result
                    picked += 1
                    cat = "?"
                    if cat_map:
                        if hsv_frame is None:
                            hsv_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)
                        cat = category_for_pixel(hsv_frame, tx, ty, cat_map,
                                                  hue_tol, sat_min, val_min)
                        log.info("已拾取 %s: (%d,%d)", cat, tx, ty)
                    else:
                        log.info("已拾取: (%d,%d)", tx, ty)
                    stats[cat] = stats.get(cat, 0) + 1
                    pickup_log.log(cat, tx, ty,
                                   region["left"] + tx, region["top"] + ty)
                    stats_collector.record(cat, region["left"] + tx, region["top"] + ty)
                    if telegram:
                        telegram.notify(cat, x=region["left"] + tx, y=region["top"] + ty)

            if hp_watcher:
                hp_watcher.check(frame, foreground)

            status.update(targets=len(points), in_radius=len(in_radius),
                          active=bool(active), picked=picked, auto=auto_on,
                          foreground=foreground,
                          stats=dict(stats),
                          active_cat=", ".join(sorted(active_categories)) if active_categories else "all",
                          session_stats=f"{stats_collector.session.total} 件 ({stats_collector.session.picks_per_minute:.0f}/分钟)",
                          hp=round(hp_watcher.hp_ratio * 100) if hp_watcher else None)

            now = time.perf_counter()
            if now - last_log >= 5.0:
                log.info("目标: %d (范围内 %d), 已拾取: %d", len(points), len(in_radius), picked)
                last_log = now

            if args.calibrate:
                vis = frame.copy()
                c = engine.center(frame.shape)
                cv2.circle(vis, c, engine.radius, (255, 255, 255), 1)
                cv2.drawMarker(vis, c, (255, 255, 255), cv2.MARKER_CROSS, 14, 1)
                rset = {(x, y) for (x, y, _a) in in_radius}
                for (cx, cy, _a) in points:
                    color = (0, 255, 0) if (cx, cy) in rset else (0, 0, 255)
                    cv2.circle(vis, (cx, cy), 8, color, 2)
                cv2.imshow("自动拾取 — 检测", vis)
                cv2.imshow("自动拾取 — 遮罩", mask)
                key = cv2.waitKey(1) & 0xFF
                if key == ord("q"):
                    stop_event.set()
                elif key == ord("s"):
                    import os; os.makedirs("_debug", exist_ok=True)
                    ts = time.strftime("%H%M%S")
                    cv2.imwrite(f"_debug/_calib_frame_{ts}.png", frame)
                    cv2.imwrite(f"_debug/_calib_mask_{ts}.png", mask)

            elapsed = time.perf_counter() - t0
            if elapsed < frame_budget:
                time.sleep(frame_budget - elapsed)
    except KeyboardInterrupt:
        log.info("已中断 (Ctrl+C)。")
        stop_event.set()
    finally:
        pickup_log.close()
        if cap._double_buffer:
            cap.stop_buffer()
        if args.calibrate:
            cv2.destroyAllWindows()


def main():
    parser = argparse.ArgumentParser(description="自动拾取 PoE 助手")
    parser.add_argument("--calibrate", action="store_true",
                        help="显示目标高亮窗口和 HSV 遮罩 (无浮窗)")
    parser.add_argument("--no-overlay", action="store_true", help="不显示浮窗")
    parser.add_argument("--gui", action="store_true", help="启动 GUI 而非控制台")
    parser.add_argument("--profile", default=None, help="启动配置名称 (config/profiles/<name>.yaml)")
    parser.add_argument("--config", default=None, help="自定义配置文件路径 (yaml)")
    args = parser.parse_args()

    if args.gui:
        from .ui.app import run_gui
        run_gui()
        return 0

    boot = load_config(args.config)
    log = get_logger(boot)
    log.info("=== 自动拾取 PoE 助手 ===")

    # --- 选择起始配置文件 ---
    pm = ProfileManager()
    start = args.profile or boot.get("profiles", {}).get("start") or "default"
    if start not in pm.names:
        log.warning("配置 '%s' 未找到，使用默认配置。可用: %s", start, ", ".join(pm.names))
        start = "default"
    pm.set_current(start)
    cfg = load_config(args.config) if args.config else pm.load(start)
    log.info("配置: %s | 启动: %s", ", ".join(pm.names), start)

    # --- 游戏窗口（回退到主显示器）---
    win = GameWindow(cfg["game"]["window_title"])
    region = None
    clicks_enabled = False
    if win.find():
        region = win.get_region()
        clicks_enabled = region is not None
        if region:
            log.info("已找到窗口: hwnd=%s, 区域=%s", win.hwnd, region)
        else:
            log.warning("已找到窗口 '%s'，但已最小化 — 等待恢复。",
                        cfg["game"]["window_title"])
    if not win.hwnd or region is None:
        monitor_idx = cfg.get("game", {}).get("monitor", 0)
        region = monitor_region(monitor_idx)
        clicks_enabled = False
        log.warning("窗口 '%s' 未找到/已最小化 — 显示器 #%s, 点击已禁用。",
                    cfg["game"]["window_title"], monitor_idx)

    cap = ScreenCapture(cfg["capture"]["backend"],
                        double_buffer=cfg["capture"].get("double_buffer", False))
    log.info("捕获: backend=%s, double_buffer=%s", cap.backend, cap._double_buffer)

    if cfg.get("vision", {}).get("auto_calibrate", False) and region:
        detected = try_auto_calibrate(cap, region)
        if detected:
            for name, rgb in detected.items():
                cat_name = name.split("_")[0]
                if cat_name not in cfg.get("filter", {}).get("category_colors", {}):
                    cfg.setdefault("filter", {}).setdefault("category_colors", {})[cat_name] = rgb
            log.info("自动校准: 已从画面应用颜色")

    loot = cfg["loot"]
    mouse = Mouse(
        rand_delay_ms=tuple(loot.get("randomize_delay_ms", [20, 70])),
        human_move=loot.get("human_mouse", True),
    )
    engine = LootEngine(
        mouse=mouse, region=region,
        center_offset=loot.get("center_offset_xy", [0, 0]),
        radius=loot["pickup_radius_px"],
        cooldown_ms=loot.get("click_cooldown_ms", 90),
        log=log,
        dedup_px=loot.get("dedup_px", 24),
        dedup_ms=loot.get("dedup_ms", 0),
        stuck_timeout_s=loot.get("stuck_timeout_s", 5.0),
        roi_margin_px=loot.get("roi_margin_px", 100),
    )
    engine.lazy_radius = loot.get("lazy_radius_px", 80)

    loot_eval_cfg = cfg.get("loot_eval", {})
    if loot_eval_cfg.get("llm_enabled") and loot_eval_cfg.get("llm_api_key"):
        evaluator = LLMEvaluator(
            api_key=loot_eval_cfg["llm_api_key"],
            model=loot_eval_cfg.get("llm_model", "gpt-4o-mini"),
            base_url=loot_eval_cfg.get("llm_base_url"),
        )
        log.info("拾取评估器: LLM (%s)", loot_eval_cfg.get("llm_model", "gpt-4o-mini"))
    else:
        evaluator = RuleEvaluator()
        log.info("拾取评估器: 规则")

    tg_cfg = cfg.get("telegram", {})
    telegram = TelegramNotifier(
        bot_token=tg_cfg.get("bot_token"),
        chat_id=tg_cfg.get("chat_id"),
        enabled=tg_cfg.get("enabled", False),
    )

    live = Live(det=build_detector(cfg), mode=loot.get("mode", "hold"),
                cat_map=cfg.get("filter", {}).get("category_colors", {}))
    log.info("检测颜色: %s (HSV 窗口: %d)", live.det.colors, len(live.det.bounds))
    log.warning("屏幕捕获仅在窗口化/窗口化全屏模式下工作 (非独占全屏)。")

    state = State()
    stop_event = threading.Event()
    status = Status(mode=live.mode, profile=start,
                    quit_key=str(cfg["hotkeys"]["quit"]).upper(),
                    clicks_enabled=clicks_enabled, targets=0, in_radius=0,
                    active=False, picked=0, auto=False,
                    automation=cfg.get("automation", {}).get("enabled", False))

    def apply_profile(name):
        pcfg = pm.load(name)
        new_det = build_detector(pcfg)
        ploot = pcfg["loot"]
        with live.lock:
            live.det = new_det
            live.mode = ploot.get("mode", "hold")
            live.cat_map = pcfg.get("filter", {}).get("category_colors", {})
            engine.radius = ploot["pickup_radius_px"]
            engine.lazy_radius = ploot.get("lazy_radius_px", 80)
            engine.cooldown = ploot.get("click_cooldown_ms", 90) / 1000.0
            engine.center_offset = ploot.get("center_offset_xy", [0, 0])
            engine.dedup_px = ploot.get("dedup_px", 24)
            engine.dedup_ms = ploot.get("dedup_ms", 0) / 1000.0
        status.update(profile=name, mode=live.mode)
        colors = [pcfg["filter"]["marker_rgb"]] + [c for c in pcfg["filter"].get("category_colors", {}).values() if c]
        log.info("配置 -> %s | 半径=%d 模式=%s 颜色=%d",
                 name, engine.radius, live.mode, len(colors))

    # --- 快捷键 ---
    k_quit = parse_key(cfg["hotkeys"]["quit"])
    k_toggle = parse_key(cfg["hotkeys"]["toggle"])
    k_pickup = parse_key(cfg["hotkeys"]["pickup"])
    k_profile = parse_key(cfg["hotkeys"].get("profile", "f7"))
    k_reload = parse_key(cfg["hotkeys"].get("reload", "f5"))
    k_settings = parse_key(cfg["hotkeys"].get("settings", "f6"))

    cat_hotkeys = {}
    for cat_name, key_spec in cfg.get("hotkeys", {}).get("category_hotkeys", {}).items():
        cat_hotkeys[parse_key(key_spec)] = cat_name

    def reload_config():
        nonlocal cfg
        try:
            new_cfg = load_config(args.config) if args.config else pm.load(pm.current())
            cfg = new_cfg
            vp_new = cfg.get("vision", {})
            loot_new = cfg.get("loot", {})
            with live.lock:
                live.det = build_detector(cfg)
                live.mode = loot_new.get("mode", "hold")
                live.cat_map = cfg.get("filter", {}).get("category_colors", {})
            engine.radius = loot_new["pickup_radius_px"]
            engine.lazy_radius = loot_new.get("lazy_radius_px", 80)
            engine.cooldown = loot_new.get("click_cooldown_ms", 90) / 1000.0
            engine.center_offset = loot_new.get("center_offset_xy", [0, 0])
            engine.dedup_px = loot_new.get("dedup_px", 24)
            engine.dedup_ms = loot_new.get("dedup_ms", 0) / 1000.0
            engine._stuck_timeout = loot_new.get("stuck_timeout_s", 5.0)
            log.info("配置已重载。模式=%s 半径=%d", live.mode, engine.radius)
        except Exception as e:
            log.warning("重载配置失败: %s", e)

    def open_settings():
        try:
            from .ui.settings_gui import SettingsGUI
            gui = SettingsGUI(on_apply=apply_settings)
            gui.open(cfg)
        except Exception as e:
            log.warning("设置界面打开失败: %s", e)

    def apply_settings(new_cfg):
        nonlocal cfg
        try:
            cfg_update = new_cfg
            from .config_manager import _deep_merge
            cfg = _deep_merge(cfg, cfg_update)
            vp_new = cfg.get("vision", {})
            loot_new = cfg.get("loot", {})
            with live.lock:
                live.det = build_detector(cfg)
                live.mode = loot_new.get("mode", "hold")
                live.cat_map = cfg.get("filter", {}).get("category_colors", {})
            engine.radius = loot_new["pickup_radius_px"]
            engine.lazy_radius = loot_new.get("lazy_radius_px", 80)
            engine.cooldown = loot_new.get("click_cooldown_ms", 90) / 1000.0
            engine.center_offset = loot_new.get("center_offset_xy", [0, 0])
            engine.dedup_px = loot_new.get("dedup_px", 24)
            engine.dedup_ms = loot_new.get("dedup_ms", 0) / 1000.0
            engine._stuck_timeout = loot_new.get("stuck_timeout_s", 5.0)
            engine.roi_margin = loot_new.get("roi_margin_px", 100)
            log.info("设置已应用: 模式=%s 半径=%d", live.mode, engine.radius)
        except Exception as e:
            log.warning("应用设置失败: %s", e)

    listener = None
    combo_tracker = ComboTracker()
    try:
        from pynput import keyboard

        def on_press(key):
            combo_tracker.on_press(key)
            if key_matches(key, k_quit):
                stop_event.set()
                return False
            if key_matches(key, k_toggle):
                is_on = state.toggle_auto()
                log.info("总开关 (开关/自动化): %s", "开启" if is_on else "关闭")
            if key_matches(key, k_profile):
                state.set_pending_profile(pm.next())
            if key_matches(key, k_reload):
                reload_config()
            if key_matches(key, k_settings):
                open_settings()
            if key in cat_hotkeys:
                cat = cat_hotkeys[key]
                state.set_category_filter([cat])
                log.info("分类: %s (仅此分类)", cat)
            if key_matches(key, k_pickup):
                state.set_pickup(True)
                if live.mode == "single":
                    state.request_single()

        def on_release(key):
            combo_tracker.on_release(key)
            if key in cat_hotkeys:
                state.set_category_filter(None)
                log.info("分类: 全部")
            if key_matches(key, k_pickup):
                state.set_pickup(False)

        listener = keyboard.Listener(on_press=on_press, on_release=on_release)
        listener.start()
        log.info("快捷键: 拾取=%s 开关=%s 配置=%s 重载=%s 退出=%s | 模式=%s",
                 cfg["hotkeys"]["pickup"], cfg["hotkeys"]["toggle"],
                 cfg["hotkeys"].get("profile", "f7"), cfg["hotkeys"].get("reload", "f5"),
                 cfg["hotkeys"]["quit"], live.mode)
    except Exception as e:
        log.warning("键盘监听不可用 (%s)。快捷键无法使用 — 仅通过 Ctrl+C / 浮窗控制。", e)
        status.update(hotkeys_disabled=True)

    # --- 自动按键 ---
    def auto_active():
        fg = win.is_foreground() if clicks_enabled else False
        return (state.auto_on, fg)

    automation = Automation(cfg.get("automation", {}), auto_active, stop_event, log)
    automation.start()

    hp_watcher = HPWatcher(cfg.get("hp_flask", {}), log)
    if hp_watcher.enabled:
        log.info("生命药剂: 按键=%s 阈值=%.0f%% 冷却=%.1f秒",
                 cfg["hp_flask"]["key"], hp_watcher.threshold * 100, hp_watcher.cooldown)

    use_overlay = cfg.get("overlay", {}).get("enabled", True) and not args.no_overlay and not args.calibrate
    log.info("启动。分类覆盖: %s%s",
             ", ".join(cfg["filter"]["categories"]), " | 浮窗: 开启" if use_overlay else "")

    loop_args = (args, cfg, log, stop_event, status, win, region, clicks_enabled,
                 cap, engine, live, apply_profile, hp_watcher, state, telegram)

    # --- 托盘图标 ---
    from .ui.tray import TrayIcon, HAS_TRAY
    tray = None
    if cfg.get("overlay", {}).get("tray_icon", True) and HAS_TRAY:
        tray = TrayIcon(
            state, stop_event,
            on_toggle=lambda: state.toggle_auto(),
            on_reload=reload_config,
            on_quit=lambda: stop_event.set(),
            on_settings=open_settings,
            profile_names=pm.names,
            on_profile=lambda name: state.set_pending_profile(name),
        )
        tray.start()

    if use_overlay:
        from .ui.overlay import Overlay
        worker = threading.Thread(target=run_loop, args=loop_args, daemon=True)
        worker.start()
        try:
            Overlay(status.snapshot, stop_event,
                    poll_ms=cfg.get("overlay", {}).get("poll_ms", 120)).run()
        except KeyboardInterrupt:
            log.info("已中断 (Ctrl+C)。")
        except Exception as e:
            log.warning("浮窗启动失败 (%s) — 无浮窗运行。", e)
            stop_event.wait()
        finally:
            stop_event.set()
            worker.join(timeout=2.0)
    else:
        run_loop(*loop_args)

    if listener:
        listener.stop()
    if tray:
        tray.stop()

    summary, csv_path = stats_collector.end_session()
    log.info(summary)
    if csv_path:
        log.info("详细日志: %s", csv_path)

    try:
        report_path = generate_html_report(stats_collector.session)
        log.info("HTML 报告: %s", report_path)
    except Exception as e:
        log.debug("HTML 报告未生成: %s", e)

    log.info("已停止。")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
