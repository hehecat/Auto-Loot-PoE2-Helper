"""Детекция цвета(ов)-маркера: HSV-маски вокруг заданных RGB -> центры пятен (цели).

Поддерживает один цвет ([r,g,b]) или несколько ([[r,g,b], ...]) — маски объединяются.
"""
from __future__ import annotations

from typing import List, Tuple, Optional

import cv2
import numpy as np
from numpy.typing import NDArray


def rgb_to_hsv_bounds(
    marker_rgb: List[int], hue_tol: int = 8, sat_min: int = 120, val_min: int = 120
) -> List[Tuple[NDArray[np.uint8], NDArray[np.uint8]]]:
    """RGB маркера -> список (low, high) границ в HSV.

    Красный HSV оборачивается: H=0 и H=172-179 — оба красный.
    Для красных оттенков возвращает два диапазона (wrap-around).
    """
    r, g, b = marker_rgb
    px = np.uint8([[[b, g, r]]])  # OpenCV ждёт BGR
    h = int(cv2.cvtColor(px, cv2.COLOR_BGR2HSV)[0][0][0])
    lo = h - hue_tol
    hi = h + hue_tol
    if lo < 0:
        return [
            (np.array([0, sat_min, val_min], dtype=np.uint8),
             np.array([hi, 255, 255], dtype=np.uint8)),
            (np.array([179 + lo, sat_min, val_min], dtype=np.uint8),
             np.array([179, 255, 255], dtype=np.uint8)),
        ]
    if hi > 179:
        return [
            (np.array([lo, sat_min, val_min], dtype=np.uint8),
             np.array([179, 255, 255], dtype=np.uint8)),
            (np.array([0, sat_min, val_min], dtype=np.uint8),
             np.array([hi - 179, 255, 255], dtype=np.uint8)),
        ]
    return [(np.array([lo, sat_min, val_min], dtype=np.uint8),
             np.array([hi, 255, 255], dtype=np.uint8))]


def normalize_colors(markers: list) -> List[List[int]]:
    """[r,g,b] -> [[r,g,b]]; [[r,g,b],...] остаётся списком."""
    if not markers:
        return []
    if isinstance(markers[0], (list, tuple)):
        return [list(c) for c in markers]
    return [list(markers)]


class ColorDetector:
    """Детектор цветовых маркеров на кадре через HSV-маски."""

    def __init__(
        self,
        markers: list,
        hue_tol: int = 8,
        sat_min: int = 120,
        val_min: int = 120,
        min_blob_area: int = 12,
        close_px: int = 9,
    ) -> None:
        self.colors: List[List[int]] = normalize_colors(markers)
        self.bounds: List[List[Tuple[NDArray, NDArray]]] = [
            rgb_to_hsv_bounds(c, hue_tol, sat_min, val_min) for c in self.colors
        ]
        self.min_blob_area: int = min_blob_area
        self._open_kernel: NDArray = np.ones((3, 3), np.uint8)
        self._close_kernel: Optional[NDArray] = (
            np.ones((close_px, close_px), np.uint8) if close_px > 0 else None
        )

    @property
    def low(self) -> NDArray:
        """Границы первого диапазона первого цвета (для совместимости)."""
        return self.bounds[0][0][0]

    @property
    def high(self) -> NDArray:
        """Верхняя граница первого диапазона первого цвета."""
        return self.bounds[0][0][1]

    def detect(
        self, frame_bgr: NDArray
    ) -> Tuple[List[Tuple[int, int, float]], NDArray]:
        """Возвращает (points, mask), где points = [(cx, cy, area), ...] по убыванию площади."""
        hsv = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2HSV)
        mask: Optional[NDArray] = None
        for ranges in self.bounds:
            for low, high in ranges:
                m = cv2.inRange(hsv, low, high)
                mask = m if mask is None else cv2.bitwise_or(mask, m)
        if mask is None:
            mask = np.zeros(frame_bgr.shape[:2], dtype=np.uint8)
        if self._close_kernel is not None:
            mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, self._close_kernel)
        mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, self._open_kernel)

        contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        points: List[Tuple[int, int, float]] = []
        for c in contours:
            area = cv2.contourArea(c)
            if area < self.min_blob_area:
                continue
            mom = cv2.moments(c)
            if mom["m00"] == 0:
                continue
            cx = int(mom["m10"] / mom["m00"])
            cy = int(mom["m01"] / mom["m00"])
            points.append((cx, cy, area))

        points.sort(key=lambda p: p[2], reverse=True)
        return points, mask
