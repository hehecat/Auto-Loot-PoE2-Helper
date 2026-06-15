"""Точка входа. Захват окна PoE2 -> детекция цвета-маркера -> подбор по хоткею + оверлей.

Безопасность: клики/автоматика только когда окно игры в фокусе. Без найденного окна
(фолбэк на монитор) клики отключены.

Режимы (loot.mode): hold (пока зажат pickup), toggle (вкл/выкл по toggle), single (клик за нажатие).
Профили: --profile <name> или хоткей profile (циклом). Авто-фласки/скиллы: секция automation.

Запуск:
    python -m src.main                  # рабочий режим + оверлей
    python -m src.main --profile mapping
    python -m src.main --no-overlay
    python -m src.main --calibrate      # окно подсветки целей (без оверлея)
"""
import argparse
import threading
import time

import cv2

from .capture.screen import ScreenCapture
from .capture.window import GameWindow
from .config_manager import load_config
from .core.automation import Automation
from .core.hp_watcher import HPWatcher
from .core.loot_engine import LootEngine
from .core.profiles import ProfileManager
from .input.keyboard import key_matches, parse_key
from .input.mouse import Mouse
from .logger import get_logger
from .vision.color_detector import ColorDetector


class State:
    auto_on = False
    pickup_held = False
    single_request = False
    pending_profile = None


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


def category_for_pixel(frame_bgr, tx, ty, cat_map, hue_tol, sat_min, val_min):
    """Определить категорию предмета по цвету пикселя в точке клика."""
    from .vision.color_detector import rgb_to_hsv_bounds
    hsv = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2HSV)
    if not (0 <= ty < frame_bgr.shape[0] and 0 <= tx < frame_bgr.shape[1]):
        return "?"
    px = hsv[ty, tx]
    for name, rgb in cat_map.items():
        for lo, hi in rgb_to_hsv_bounds(rgb, hue_tol, sat_min, val_min):
            if all(lo[i] <= px[i] <= hi[i] for i in range(3)):
                return name
    return "?"


def compute_priorities(points, frame_bgr, cat_map, priority_cfg, hue_tol, sat_min, val_min):
    """Вернуть {(cx,cy): priority_int} для точек в кадре. Меньше = важнее."""
    if not cat_map or not priority_cfg:
        return {}
    from .vision.color_detector import rgb_to_hsv_bounds
    hsv = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2HSV)
    h, w = frame_bgr.shape[:2]
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
             cap, engine, live, apply_profile, hp_watcher=None):
    target_fps = max(1, cfg["capture"].get("target_fps", 30))
    frame_budget = 1.0 / target_fps
    last_log = 0.0
    picked = 0
    stats = {}   # {category: count} — счётчик по категориям за сессию
    vp = cfg.get("vision", {})
    loot_cfg = cfg.get("loot", {})
    priority_cfg = loot_cfg.get("category_priority", {})

    try:
        while not stop_event.is_set():
            t0 = time.perf_counter()

            if State.pending_profile:
                name, State.pending_profile = State.pending_profile, None
                apply_profile(name)

            frame = cap.grab(region)
            if frame is None:
                time.sleep(frame_budget)
                continue

            with live.lock:
                det, mode, cat_map = live.det, live.mode, live.cat_map

            points, mask = det.detect(frame)
            in_radius = engine.targets_in_radius(points, frame.shape)

            active = (
                (mode == "hold" and State.pickup_held)
                or (mode in ("toggle", "lazy") and State.auto_on)
                or (mode == "single" and State.single_request)
            )
            if mode == "single":
                State.single_request = False

            foreground = win.is_foreground()
            if active and clicks_enabled and foreground:
                hue_tol = vp.get("hue_tolerance", 8)
                sat_min = vp.get("sat_min", 120)
                val_min = vp.get("val_min", 120)
                priorities = (
                    compute_priorities(in_radius, frame, cat_map, priority_cfg,
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
                        cat = category_for_pixel(frame, tx, ty, cat_map,
                                                  vp.get("hue_tolerance", 8),
                                                  vp.get("sat_min", 120),
                                                  vp.get("val_min", 120))
                        log.info("Подобрано %s: (%d,%d)", cat, tx, ty)
                    else:
                        log.info("Подобрано: (%d,%d)", tx, ty)
                    stats[cat] = stats.get(cat, 0) + 1

            if hp_watcher:
                hp_watcher.check(frame, foreground)

            status.update(targets=len(points), in_radius=len(in_radius),
                          active=bool(active), picked=picked, auto=State.auto_on,
                          foreground=foreground,
                          stats=dict(stats),
                          hp=round(hp_watcher.hp_ratio * 100) if hp_watcher else None)

            now = time.perf_counter()
            if now - last_log >= 5.0:
                log.info("Целей: %d (в радиусе %d), подобрано: %d", len(points), len(in_radius), picked)
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
                cv2.imshow("AutoLoot — detections", vis)
                cv2.imshow("AutoLoot — mask", mask)
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
        log.info("Прервано (Ctrl+C).")
        stop_event.set()
    finally:
        if args.calibrate:
            cv2.destroyAllWindows()


def main():
    parser = argparse.ArgumentParser(description="Auto Loot PoE Helper")
    parser.add_argument("--calibrate", action="store_true",
                        help="окно с подсветкой целей и HSV-маской (без оверлея)")
    parser.add_argument("--no-overlay", action="store_true", help="не показывать оверлей")
    parser.add_argument("--profile", default=None, help="имя стартового профиля (config/profiles/<name>.yaml)")
    parser.add_argument("--config", default=None, help="путь к произвольному конфигу (yaml)")
    args = parser.parse_args()

    boot = load_config(args.config)
    log = get_logger(boot)
    log.info("=== Auto Loot PoE Helper ===")

    # --- выбор стартового профиля ---
    pm = ProfileManager()
    start = args.profile or boot.get("profiles", {}).get("start") or "default"
    if start not in pm.names:
        log.warning("Профиль '%s' не найден, использую default. Доступны: %s", start, ", ".join(pm.names))
        start = "default"
    pm.set_current(start)
    cfg = load_config(args.config) if args.config else pm.load(start)
    log.info("Профили: %s | старт: %s", ", ".join(pm.names), start)

    # --- окно игры (с фолбэком на основной монитор) ---
    win = GameWindow(cfg["game"]["window_title"])
    if win.find():
        region = win.get_region()
        clicks_enabled = region is not None
        if region:
            log.info("Окно найдено: hwnd=%s, регион=%s", win.hwnd, region)
        else:
            log.warning("Окно '%s' найдено, но свёрнуто — жду разворачивания.",
                        cfg["game"]["window_title"])
    if not win.hwnd or region is None:
        region = GameWindow.primary_region()
        clicks_enabled = False
        log.warning("Окно '%s' не найдено/свёрнуто — монитор %s, КЛИКИ ОТКЛЮЧЕНЫ.",
                    cfg["game"]["window_title"], region)

    cap = ScreenCapture(cfg["capture"]["backend"])
    log.info("Захват: backend=%s", cap.backend)

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
        dedup_ms=loot.get("dedup_ms", 0),
    )
    engine.lazy_radius = loot.get("lazy_radius_px", 80)
    live = Live(det=build_detector(cfg), mode=loot.get("mode", "hold"),
                cat_map=cfg.get("filter", {}).get("category_colors", {}))
    log.info("Цвета детекции: %s (HSV-окон: %d)", live.det.colors, len(live.det.bounds))
    log.warning("Захват экрана работает только в режиме Windowed / Windowed Fullscreen "
                "(не Exclusive Fullscreen).")

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
        status.update(profile=name, mode=live.mode)
        colors = [pcfg["filter"]["marker_rgb"]] + [c for c in pcfg["filter"].get("category_colors", {}).values() if c]
        log.info("Профиль -> %s | radius=%d mode=%s colors=%d",
                 name, engine.radius, live.mode, len(colors))

    # --- хоткеи ---
    k_quit = parse_key(cfg["hotkeys"]["quit"])
    k_toggle = parse_key(cfg["hotkeys"]["toggle"])
    k_pickup = parse_key(cfg["hotkeys"]["pickup"])
    k_profile = parse_key(cfg["hotkeys"].get("profile", "f7"))

    def on_press(key):
        if key_matches(key, k_quit):
            stop_event.set()
            return False
        if key_matches(key, k_toggle):
            State.auto_on = not State.auto_on
            log.info("Мастер (toggle/автоматика): %s", "ВКЛ" if State.auto_on else "выкл")
        if key_matches(key, k_profile):
            State.pending_profile = pm.next()
        if key_matches(key, k_pickup):
            State.pickup_held = True
            if live.mode == "single":
                State.single_request = True

    def on_release(key):
        if key_matches(key, k_pickup):
            State.pickup_held = False

    listener = None
    try:
        from pynput import keyboard
        listener = keyboard.Listener(on_press=on_press, on_release=on_release)
        listener.start()
        log.info("Хоткеи: pickup=%s toggle=%s profile=%s quit=%s | режим=%s",
                 cfg["hotkeys"]["pickup"], cfg["hotkeys"]["toggle"],
                 cfg["hotkeys"].get("profile", "f7"), cfg["hotkeys"]["quit"], live.mode)
    except Exception as e:
        log.warning("Слушатель клавиатуры недоступен (%s). Выход — Ctrl+C.", e)

    # --- авто-автоматика ---
    def auto_active():
        fg = win.is_foreground() if clicks_enabled else False
        return (State.auto_on, fg)

    automation = Automation(cfg.get("automation", {}), auto_active, stop_event, log)
    automation.start()

    hp_watcher = HPWatcher(cfg.get("hp_flask", {}), log)
    if hp_watcher.enabled:
        log.info("HP фласка: клавиша=%s порог=%.0f%% кулдаун=%.1fс",
                 cfg["hp_flask"]["key"], hp_watcher.threshold * 100, hp_watcher.cooldown)

    use_overlay = cfg.get("overlay", {}).get("enabled", True) and not args.no_overlay and not args.calibrate
    log.info("Старт. Категории override: %s%s",
             ", ".join(cfg["filter"]["categories"]), " | оверлей: вкл" if use_overlay else "")

    loop_args = (args, cfg, log, stop_event, status, win, region, clicks_enabled,
                 cap, engine, live, apply_profile, hp_watcher)

    if use_overlay:
        from .ui.overlay import Overlay
        worker = threading.Thread(target=run_loop, args=loop_args, daemon=True)
        worker.start()
        try:
            Overlay(status.snapshot, stop_event,
                    poll_ms=cfg.get("overlay", {}).get("poll_ms", 120)).run()
        except KeyboardInterrupt:
            log.info("Прервано (Ctrl+C).")
        except Exception as e:
            log.warning("Оверлей не запустился (%s) — работаю без него.", e)
            stop_event.wait()
        finally:
            stop_event.set()
            worker.join(timeout=2.0)
    else:
        run_loop(*loop_args)

    if listener:
        listener.stop()
    log.info("Остановлено.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
