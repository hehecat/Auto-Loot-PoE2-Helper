"""自动校准：启动时自动检测过滤器颜色。

扫描屏幕画面，查找 NeverSink 过滤器的特征颜色，
无需手动校准即可设置 HSV 阈值。
"""
import logging
import time

import cv2
import numpy as np

_log = logging.getLogger("autoloot.calibrate")

# NeverSink PoE2 过滤器的特征颜色（R、G、B）
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
    """估算帧上有多少 rgb 颜色像素。"""
    h_center, s_center, v_center = _rgb_to_hsv(rgb)
    lo = np.array([max(0, h_center - hue_tol), sat_min, val_min], dtype=np.uint8)
    hi = np.array([min(179, h_center + hue_tol), 255, 255], dtype=np.uint8)
    mask = cv2.inRange(hsv_frame, lo, hi)
    return cv2.countNonZero(mask)


def auto_detect_colors(frame_bgr, min_pixels=50):
    """自动检测帧上可见的过滤器颜色。

    返回 dict {category: [R, G, B]} 用于检测到的颜色。
    """
    if frame_bgr is None or frame_bgr.size == 0:
        return {}

    hsv = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2HSV)
    detected = {}

    for name, rgb in NEVERSINK_COLORS.items():
        score = _score_color_region(hsv, rgb, hue_tol=10, sat_min=80, val_min=80)
        if score >= min_pixels:
            detected[name] = list(rgb)
            _log.debug("颜色 '%s' 已检测到: %d 像素", name, score)

    return detected


def auto_calibrate_hsv_ranges(detected_colors, hue_tol=8, sat_min=100, val_min=100):
    """为检测到的颜色计算最佳 HSV 阈值。

    返回 {category: {"marker_rgb": [R,G,B], "hue_tolerance": N, ...}}
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
    """尝试通过多帧自动校准。

    返回 detected_colors dict，如果失败则返回空 dict。
    """
    _log.info("自动校准: 正在扫描 %d 帧...", attempts)
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
        _log.info("自动校准: 检测到颜色 %s", list(all_colors.keys()))
    else:
        _log.warning("自动校准: 未检测到颜色。请使用手动校准。")

    return all_colors
