"""Детекция уровня ХП по цвету орба в левом нижнем углу экрана.

Берёт вертикальный центральный срез региона орба и измеряет какая
доля пикселей заполнена "HP-красным". Орб заполняется снизу вверх,
поэтому доля красных пикселей ≈ текущий % ХП.
"""
import cv2
import numpy as np

# PoE2 HP орб: глубокий красный (HSV H~0-12, высокая S, средняя V)
_HP_LOW = np.array([0, 90, 40], dtype=np.uint8)
_HP_HIGH = np.array([12, 255, 220], dtype=np.uint8)

# Второй диапазон для красного (H wrap: 168-179)
_HP_LOW2 = np.array([168, 90, 40], dtype=np.uint8)
_HP_HIGH2 = np.array([179, 255, 220], dtype=np.uint8)

_DEFAULT_REGION = {"x": 0.01, "y": 0.84, "w": 0.10, "h": 0.15}


def detect_hp_ratio(frame_bgr, region=None):
    """Возвращает приблизительный % ХП (0.0 = мёртв, 1.0 = полный).

    region: dict(x, y, w, h) — доли от размера кадра (0..1).
    При ошибке возвращает 1.0 (считаем ХП полным, не спамим фласку).
    """
    if region is None:
        region = _DEFAULT_REGION

    fh, fw = frame_bgr.shape[:2]
    x1 = max(0, int(region["x"] * fw))
    y1 = max(0, int(region["y"] * fh))
    x2 = min(fw, int((region["x"] + region["w"]) * fw))
    y2 = min(fh, int((region["y"] + region["h"]) * fh))

    crop = frame_bgr[y1:y2, x1:x2]
    if crop.size == 0:
        return 1.0

    hsv = cv2.cvtColor(crop, cv2.COLOR_BGR2HSV)
    mask = cv2.inRange(hsv, _HP_LOW, _HP_HIGH)
    mask2 = cv2.inRange(hsv, _HP_LOW2, _HP_HIGH2)
    mask = cv2.bitwise_or(mask, mask2)

    # центральный вертикальный срез (1/5 ширины)
    cw = crop.shape[1]
    sw = max(2, cw // 5)
    cx = cw // 2
    strip = mask[:, max(0, cx - sw // 2): cx + sw // 2 + 1]

    filled = int(cv2.countNonZero(strip))
    total = int(strip.size)
    return filled / max(total, 1)
