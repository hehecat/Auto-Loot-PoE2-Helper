"""Интерактивный мастер калибровки.

ЛКМ — задать основной цвет-маркер (берётся реальный RGB с экрана). Наведи курсор и нажми
'a' — добавить ещё один цвет (несколько цветов). 'x' — очистить доп. цвета.
Трекбары — допуск тона, мин. насыщенность/яркость, мин. площадь, радиус.
Центр персонажа: Shift+ЛКМ или клавиши i/j/k/l. 's' — сохранить профиль, 'q' — выход.

Запуск:
    python -m src.calibrate                 # из текущего default
    python -m src.calibrate --profile X     # стартовые значения из профиля X
    python -m src.calibrate --target name   # имя профиля для сохранения (по умолч. calibrated)
"""
import argparse
import json
from pathlib import Path

import cv2
import win32con
import win32gui
import yaml

from .capture.screen import ScreenCapture
from .capture.window import GameWindow
from .config_manager import load_config
from .core.profiles import PROFILES_DIR, ProfileManager
from .logger import get_logger
from .vision.color_detector import ColorDetector, rgb_to_hsv_bounds

WIN = "AutoLoot Calibrate"
MASK = "mask"
POS_FILE = Path(__file__).resolve().parents[1] / "config" / "_window_pos.json"
# раскладка по умолчанию (первый запуск, пока нет сохранённых позиций): рядом на осн. мониторе
DEFAULT_RECTS = {WIN: [40, 40, 1000, 640], MASK: [1060, 40, 660, 500]}


def _load_positions():
    try:
        return json.loads(POS_FILE.read_text(encoding="utf-8"))
    except Exception:  # noqa: BLE001
        return {}


def _save_positions(rects):
    try:
        POS_FILE.write_text(json.dumps(rects), encoding="utf-8")
    except Exception:  # noqa: BLE001
        pass


def _get_window_rect(title):
    hwnd = win32gui.FindWindow(None, title)
    if not hwnd:
        return None
    l, t, r, b = win32gui.GetWindowRect(hwnd)
    return [l, t, r - l, b - t]


def _apply_window_rect(title, rect):
    if not rect:
        return
    hwnd = win32gui.FindWindow(None, title)
    if not hwnd:
        return
    x, y, w, h = rect
    win32gui.SetWindowPos(hwnd, 0, int(x), int(y), int(w), int(h),
                          win32con.SWP_NOZORDER | win32con.SWP_NOACTIVATE)


def sample_rgb(frame_bgr, x, y):
    """RGB пикселя кадра по координатам окна (с клампом в границы)."""
    h, w = frame_bgr.shape[:2]
    x = max(0, min(w - 1, x))
    y = max(0, min(h - 1, y))
    b, g, r = frame_bgr[y, x]
    return [int(r), int(g), int(b)]


def save_calibration(path, colors, hue_tol, sat_min, val_min, min_area, radius, center_off, close_px=9):
    data = {
        "filter": {
            "marker_rgb": list(colors[0]),
            "extra_colors": [list(c) for c in colors[1:]],
        },
        "vision": {
            "hue_tolerance": int(hue_tol),
            "sat_min": int(sat_min),
            "val_min": int(val_min),
            "min_blob_area": int(min_area),
            "close_px": int(close_px),
        },
        "loot": {
            "pickup_radius_px": int(radius),
            "center_offset_xy": [int(center_off[0]), int(center_off[1])],
        },
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        f.write("# Сгенерировано мастером калибровки (python -m src.calibrate)\n")
        yaml.safe_dump(data, f, allow_unicode=True, sort_keys=False)
    return data


def _initial_colors(cfg):
    colors = [list(cfg["filter"]["marker_rgb"])]
    colors += [list(c) for c in cfg["filter"].get("extra_colors", []) or []]
    return colors


def main():
    parser = argparse.ArgumentParser(description="Auto Loot calibration wizard")
    parser.add_argument("--profile", default=None, help="стартовый профиль")
    parser.add_argument("--target", default="calibrated", help="имя профиля для сохранения")
    parser.add_argument("--config", default=None)
    args = parser.parse_args()

    pm = ProfileManager()
    if args.config:
        cfg = load_config(args.config)
    elif args.profile and args.profile in pm.names:
        cfg = pm.load(args.profile)
    else:
        cfg = load_config(None)
    log = get_logger(cfg)

    win = GameWindow(cfg["game"]["window_title"])
    region = win.get_region() if win.find() else GameWindow.primary_region()
    cap = ScreenCapture(cfg["capture"]["backend"])
    log.info("Калибровка: регион=%s, backend=%s", region, cap.backend)

    v = cfg["vision"]
    loot = cfg["loot"]
    shared = {
        "frame": None,
        "colors": _initial_colors(cfg),
        "center_off": list(loot.get("center_offset_xy", [0, 0])),
        "last_xy": (0, 0),
    }

    def on_mouse(event, x, y, flags, _param):
        if event == cv2.EVENT_MOUSEMOVE:
            shared["last_xy"] = (x, y)
            return
        frame = shared["frame"]
        if frame is None or event != cv2.EVENT_LBUTTONDOWN:
            return
        if flags & cv2.EVENT_FLAG_SHIFTKEY:
            h, w = frame.shape[:2]
            shared["center_off"] = [x - w // 2, y - h // 2]
            log.info("Центр -> offset %s", shared["center_off"])
        else:
            shared["colors"][0] = sample_rgb(frame, x, y)
            log.info("Основной цвет -> RGB %s", shared["colors"][0])

    cv2.namedWindow(WIN, cv2.WINDOW_NORMAL)
    cv2.namedWindow(MASK, cv2.WINDOW_NORMAL)
    cv2.setMouseCallback(WIN, on_mouse)
    noop = lambda _v: None
    cv2.createTrackbar("HueTol", WIN, int(v.get("hue_tolerance", 8)), 30, noop)
    cv2.createTrackbar("SatMin", WIN, int(v.get("sat_min", 120)), 255, noop)
    cv2.createTrackbar("ValMin", WIN, int(v.get("val_min", 120)), 255, noop)
    cv2.createTrackbar("MinArea", WIN, int(v.get("min_blob_area", 12)), 2000, noop)
    cv2.createTrackbar("ClosePx", WIN, int(v.get("close_px", 9)), 25, noop)
    cv2.createTrackbar("Radius", WIN, int(loot.get("pickup_radius_px", 450)), 1500, noop)

    target_path = PROFILES_DIR / f"{args.target}.yaml"
    log.info("ЛКМ=осн.цвет, a=+цвет(под курсором), x=очистить доп., d=debug, Shift+ЛКМ/ijkl=центр, s=сохр, q=выход")

    saved_pos = _load_positions()
    live_rects = dict(saved_pos)
    pos_restored = False

    while True:
        frame = cap.grab(region)
        if frame is None:
            if (cv2.waitKey(20) & 0xFF) == ord("q"):
                break
            continue
        shared["frame"] = frame

        # окно закрыли крестиком -> выходим без ошибки
        try:
            if cv2.getWindowProperty(WIN, cv2.WND_PROP_VISIBLE) < 1:
                break
        except cv2.error:
            break

        hue_tol = cv2.getTrackbarPos("HueTol", WIN)
        sat_min = cv2.getTrackbarPos("SatMin", WIN)
        val_min = cv2.getTrackbarPos("ValMin", WIN)
        min_area = cv2.getTrackbarPos("MinArea", WIN)
        close_px = cv2.getTrackbarPos("ClosePx", WIN)
        radius = cv2.getTrackbarPos("Radius", WIN)

        det = ColorDetector(shared["colors"], hue_tol, sat_min, val_min, min_area, close_px)
        points, mask = det.detect(frame)

        h, w = frame.shape[:2]
        cx = w // 2 + shared["center_off"][0]
        cy = h // 2 + shared["center_off"][1]

        vis = frame.copy()
        cv2.circle(vis, (cx, cy), radius, (255, 255, 255), 1)
        cv2.drawMarker(vis, (cx, cy), (255, 255, 255), cv2.MARKER_CROSS, 16, 1)
        n_in = 0
        for (px, py, _a) in points:
            inside = (px - cx) ** 2 + (py - cy) ** 2 <= radius * radius
            n_in += inside
            cv2.circle(vis, (px, py), 8, (0, 255, 0) if inside else (0, 0, 255), 2)

        lo, hi = rgb_to_hsv_bounds(shared["colors"][0], hue_tol, sat_min, val_min)[0]
        lines = [
            f"colors {shared['colors']}",
            f"primary HSV {lo.tolist()}..{hi.tolist()}",
            f"targets {len(points)}  in-radius {n_in}  radius {radius}",
            "LMB=color  a=+color  x=clear  d=debug-save  Shift+LMB/ijkl=center  s=save  q=quit",
        ]
        for i, t in enumerate(lines):
            y = 22 + i * 22
            cv2.putText(vis, t, (10, y), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 0, 0), 3, cv2.LINE_AA)
            cv2.putText(vis, t, (10, y), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 255), 1, cv2.LINE_AA)

        cv2.imshow(WIN, vis)
        cv2.imshow(MASK, mask)

        k = cv2.waitKey(1) & 0xFF

        # восстановить позиции окон один раз (после того как окна реально созданы)
        if not pos_restored:
            for t in (WIN, MASK):
                _apply_window_rect(t, saved_pos.get(t) or DEFAULT_RECTS.get(t))
            pos_restored = True
        for t in (WIN, MASK):
            rr = _get_window_rect(t)
            if rr:
                live_rects[t] = rr

        if k == ord("q"):
            break
        elif k == ord("s"):
            save_calibration(target_path, shared["colors"], hue_tol, sat_min, val_min,
                             min_area, radius, shared["center_off"], close_px)
            log.info("Сохранено в %s. Запуск: python -m src.main --profile %s", target_path, args.target)
        elif k == ord("a"):
            lx, ly = shared["last_xy"]
            c = sample_rgb(frame, lx, ly)
            shared["colors"].append(c)
            log.info("Добавлен цвет RGB %s (всего %d)", c, len(shared["colors"]))
        elif k == ord("d"):
            import os; os.makedirs("_debug", exist_ok=True)
            cv2.imwrite("_debug/_debug_frame.png", frame)
            cv2.imwrite("_debug/_debug_vis.png", vis)
            cv2.imwrite("_debug/_debug_mask.png", mask)
            log.info("Debug сохранён в _debug/ (целей: %d)", len(points))
        elif k == ord("x"):
            shared["colors"] = [shared["colors"][0]]
            log.info("Доп. цвета очищены.")
        elif k == ord("i"):
            shared["center_off"][1] -= 5
        elif k == ord("k"):
            shared["center_off"][1] += 5
        elif k == ord("j"):
            shared["center_off"][0] -= 5
        elif k == ord("l"):
            shared["center_off"][0] += 5

    _save_positions(live_rects)
    cv2.destroyAllWindows()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
