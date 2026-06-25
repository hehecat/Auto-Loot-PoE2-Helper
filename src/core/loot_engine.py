"""拾取逻辑：在半径范围内点击最近的目标，并有冷却时间。

dedup_ms=0（默认）=>「粘滞」模式：程序持续点击最近的目标，直到角色走到并拾取
（否则角色会在物品之间来回跑）。
dedup_ms>0 启用防双击（不点击刚点击过的位置）。
"""
from __future__ import annotations

import math
import time
from typing import Dict, List, Optional, Tuple

from ..input.mouse import Mouse


class LootEngine:
    """战利品拾取引擎：优先级、防双击、防卡住、ROI。"""

    def __init__(
        self,
        mouse,
        region,
        center_offset,
        radius,
        cooldown_ms,
        log,
        dedup_px=24,
        dedup_ms=0,
        stuck_timeout_s=5.0,
        roi_margin_px=100,
        gamepad=None,
    ) -> None:
        self.mouse = mouse
        self.region = region
        self.center_offset = center_offset
        self.radius = radius
        self.cooldown = cooldown_ms / 1000.0
        self.log = log
        self.dedup_px = dedup_px
        self.dedup_ms = dedup_ms / 1000.0
        self._last_click_t = 0.0
        self._recent = []
        self._stuck_timeout = stuck_timeout_s
        self._stuck_target = None
        self._stuck_start = 0.0
        self.roi_margin = roi_margin_px
        self.gamepad = gamepad

    def center(self, frame_shape: Tuple[int, ...]) -> Tuple[int, int]:
        """角色在帧坐标中的中心位置。"""
        h, w = frame_shape[:2]
        return (w // 2 + self.center_offset[0], h // 2 + self.center_offset[1])

    def get_roi(self, frame_shape: Tuple[int, ...]) -> Optional[Tuple[int, int, int, int]]:
        """返回角色周围的 ROI (x1, y1, x2, y2) 或 None。"""
        h, w = frame_shape[:2]
        cx, cy = self.center(frame_shape)
        r = self.radius + self.roi_margin
        x1 = max(0, cx - r)
        y1 = max(0, cy - r)
        x2 = min(w, cx + r)
        y2 = min(h, cy + r)
        if x2 - x1 >= w and y2 - y1 >= h:
            return None
        return (x1, y1, x2, y2)

    def _in_radius(self, p: Tuple[int, int], c: Tuple[int, int]) -> bool:
        return math.hypot(p[0] - c[0], p[1] - c[1]) <= self.radius

    def _recently_clicked(self, p: Tuple[int, int], now: float) -> bool:
        if self.dedup_ms <= 0:
            return False
        self._recent = [(x, y, t) for (x, y, t) in self._recent if now - t < self.dedup_ms]
        return any(math.hypot(p[0] - x, p[1] - y) <= self.dedup_px for (x, y, _t) in self._recent)

    def targets_in_radius(
        self, points: List[Tuple[int, int, float]], frame_shape: Tuple[int, ...]
    ) -> List[Tuple[int, int, float]]:
        """筛选拾取半径内的目标。"""
        c = self.center(frame_shape)
        return [p for p in points if self._in_radius(p, c)]

    def pick_once(
        self,
        points: List[Tuple[int, int, float]],
        frame_shape: Tuple[int, ...],
        priorities: Optional[Dict[Tuple[int, int], int]] = None,
    ) -> Optional[Tuple[int, int]]:
        """点击拾取半径内优先级最高的目标。"""
        return self.pick_at(points, self.center(frame_shape), self.radius, priorities)

    def pick_at(
        self,
        points: List[Tuple[int, int, float]],
        ref: Tuple[int, int],
        radius: int,
        priorities: Optional[Dict[Tuple[int, int], int]] = None,
    ) -> Optional[Tuple[int, int]]:
        """在 radius 范围内点击优先级最高的目标。

        ref 和 points — 使用帧坐标。
        priorities — dict {(cx, cy): int}，越小越重要。None = 按距离排序。
        如果点击了则返回 (tx, ty)，否则返回 None。
        """
        now = time.perf_counter()
        if now - self._last_click_t < self.cooldown:
            return None

        candidates = [
            p for p in points
            if math.hypot(p[0] - ref[0], p[1] - ref[1]) <= radius
            and not self._recently_clicked(p, now)
        ]
        if not candidates:
            return None

        if priorities:
            candidates.sort(key=lambda p: (
                priorities.get((p[0], p[1]), 99),
                math.hypot(p[0] - ref[0], p[1] - ref[1]),
            ))
        else:
            candidates.sort(key=lambda p: math.hypot(p[0] - ref[0], p[1] - ref[1]))
        tx, ty, _area = candidates[0]

        if self._stuck_target and math.hypot(tx - self._stuck_target[0],
                                             ty - self._stuck_target[1]) < self.dedup_px:
            if now - self._stuck_start > self._stuck_timeout:
                self._recent.append((tx, ty, now))
                self._stuck_target = None
                self.log.debug("防卡住: 跳过目标 (%d,%d) — 卡住超过 %.0f 秒",
                               tx, ty, self._stuck_timeout)
                return None
        else:
            self._stuck_target = (tx, ty)
            self._stuck_start = now

        sx = self.region["left"] + tx
        sy = self.region["top"] + ty

        if self.gamepad and self.gamepad.enabled:
            self.gamepad.pickup()
        else:
            self.mouse.move_click(sx, sy)
        self._last_click_t = now
        self._recent.append((tx, ty, now))
        return (tx, ty)
