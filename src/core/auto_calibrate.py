"""Автокалибровка: автоматическое определение цветов фильтра при старте.

Сканирует кадр экрана, ищет характерные цвета NeverSink фильтра
и настраивает HSV-пороги без ручной калибровки.
"""
import logging
import time

import cv2
import numpy as np

_log = logging.getLogger("autoloot.calibrate")

# Характерные цвета NeverSink PoE2 фильтра (R, G, B)
NEVERSINK_COLORS = {
    "currency_orange": (255, 120, 0),
    "currency_gold": (255, 199, 0),
    "fragments_purple": (180, 0, 255),
    "waystones_cyan": (50, 200, 255),
    "uniques_green": (0, 255, 0),
    "gems_red": (255, 40, 40),
    "marker_pink": (255, 0, 200),
}


def _rgb_to_hsv(rgb):
    """RGB -> HSV (OpenCV format)."""
    r, g, b = rgb
    px = np.uint8([[[b, g, r]]])
    return cv2.cvtColor(px, cv2.COLOR_BGR2HSV)[0][0]


def _score_color_region(hsv_frame, rgb, hue_tol=8, sat_min=80, val_min=80):
    """Оценить сколько пикселей цвета rgb на кадре."""
    h_center, s_center, v_center = _rgb_to_hsv(rgb)
    lo = np.array([max(0, h_center - hue_tol), sat_min, val_min], dtype=np.uint8)
    hi = np.array([min(179, h_center + hue_tol), 255, 255], dtype=np.uint8)
    mask = cv2.inRange(hsv_frame, lo, hi)
    return cv2.countNonZero(mask)


def auto_detect_colors(frame_bgr, min_pixels=50):
    """Автоматически определить какие цвета фильтра видны на кадре.

    Возвращает dict {category: [R, G, B]} для обнаруженных цветов.
    """
    if frame_bgr is None or frame_bgr.size == 0:
        return {}

    hsv = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2HSV)
    detected = {}

    for name, rgb in NEVERSINK_COLORS.items():
        score = _score_color_region(hsv, rgb, hue_tol=10, sat_min=80, val_min=80)
        if score >= min_pixels:
            detected[name] = list(rgb)
            _log.debug("Цвет '%s' обнаружен: %d пикселей", name, score)

    return detected


def auto_calibrate_hsv_ranges(detected_colors, hue_tol=8, sat_min=100, val_min=100):
    """Вычислить оптимальные HSV-пороги для обнаруженных цветов.

    Возвращает {category: {"marker_rgb": [R,G,B], "hue_tolerance": N, ...}}
    """
    result = {}
    for name, rgb in detected_colors.items():
        h, s, v = _rgb_to_hsv(rgb)
        result[name] = {
            "marker_rgb": rgb,
            "hue_tolerance": hue_tol,
            "sat_min": max(50, s - 40),
            "val_min": max(50, v - 40),
        }
    return result


def try_auto_calibrate(capture, region, attempts=3, delay=0.5):
    """Попытаться автоматически откалиброваться по нескольким кадрам.

    Возвращает detected_colors dict или пустой dict если не удалось.
    """
    _log.info("Автокалибровка: сканирую %d кадров...", attempts)
    all_colors = {}

    for i in range(attempts):
        frame = capture.grab(region)
        if frame is None:
            time.sleep(delay)
            continue

        detected = auto_detect_colors(frame)
        for name, rgb in detected.items():
            if name not in all_colors:
                all_colors[name] = rgb

        time.sleep(delay)

    if all_colors:
        _log.info("Автокалибровка: обнаружены цвета %s", list(all_colors.keys()))
    else:
        _log.warning("Автокалибровка: цвета не обнаружены. Используй ручную калибровку.")

    return all_colors
