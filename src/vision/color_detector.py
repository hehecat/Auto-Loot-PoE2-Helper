"""标记颜色检测：基于给定 RGB 的 HSV 掩码 -> 斑点中心（目标）。

支持单种颜色（[r,g,b]）或多种颜色（[[r,g,b], ...]）— 掩码会合并。
"""
from __future__ import annotations

from typing import List, Tuple, Optional

import cv2
import numpy as np
from numpy.typing import NDArray


def rgb_to_hsv_bounds(
    marker_rgb: List[int], hue_tol: int = 8, sat_min: int = 120, val_min: int = 120
) -> List[Tuple[NDArray[np.uint8], NDArray[np.uint8]]]:
    """标记 RGB -> HSV 中的 (low, high) 边界列表。

    红色 HSV 环绕处理：H=0 和 H=172-179 — 两者都是红色。
    对于红色色调，返回两个范围（环绕）。
    """
    r, g, b = marker_rgb
    px = np.uint8([[[b, g, r]]])  # OpenCV 需要 BGR
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
    """[r,g,b] -> [[r,g,b]]；[[r,g,b],...] 保持为列表。"""
    if not markers:
        return []
    if isinstance(markers[0], (list, tuple)):
        return [list(c) for c in markers]
    return [list(markers)]


class ColorDetector:
    """通过 HSV 掩码在帧上检测颜色标记。"""

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
        """第一个颜色的第一个范围的下界（用于兼容性）。"""
        return self.bounds[0][0][0]

    @property
    def high(self) -> NDArray:
        """第一个颜色的第一个范围的上界。"""
        return self.bounds[0][0][1]

    def detect(
        self, frame_bgr: NDArray
    ) -> Tuple[List[Tuple[int, int, float]], NDArray]:
        """返回 (points, mask)，其中 points = [(cx, cy, area), ...] 按面积降序排列。"""
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
