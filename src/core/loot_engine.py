"""Логика подбора: клик по ближайшей цели в радиусе с кулдауном.

dedup_ms=0 (по умолчанию) => «прилипание»: программа долбит по ближайшей цели,
пока персонаж до неё не дойдёт и не поднимет (иначе перс мечется между предметами).
dedup_ms>0 включает анти-дабл-клик (не кликать недавно кликнутую точку).
"""
import math
import time


class LootEngine:
    def __init__(self, mouse, region, center_offset, radius, cooldown_ms, log,
                 dedup_px=24, dedup_ms=0):
        self.mouse = mouse
        self.region = region
        self.center_offset = center_offset
        self.radius = radius
        self.cooldown = cooldown_ms / 1000.0
        self.log = log
        self.dedup_px = dedup_px
        self.dedup_ms = dedup_ms / 1000.0
        self._last_click_t = 0.0
        self._recent = []  # [(x, y, t)] в координатах кадра

    def center(self, frame_shape):
        h, w = frame_shape[:2]
        return (w // 2 + self.center_offset[0], h // 2 + self.center_offset[1])

    def _in_radius(self, p, c):
        return math.hypot(p[0] - c[0], p[1] - c[1]) <= self.radius

    def _recently_clicked(self, p, now):
        self._recent = [(x, y, t) for (x, y, t) in self._recent if now - t < self.dedup_ms]
        return any(math.hypot(p[0] - x, p[1] - y) <= self.dedup_px for (x, y, _t) in self._recent)

    def targets_in_radius(self, points, frame_shape):
        c = self.center(frame_shape)
        return [p for p in points if self._in_radius(p, c)]

    def pick_once(self, points, frame_shape, priorities=None):
        """Кликнуть по наиболее приоритетной цели в радиусе подбора."""
        return self.pick_at(points, self.center(frame_shape), self.radius, priorities)

    def pick_at(self, points, ref, radius, priorities=None):
        """Кликнуть по наиболее приоритетной цели в пределах radius.

        ref и points — в координатах кадра.
        priorities — dict {(cx, cy): int}, меньше = важнее. None = сортировка по дистанции.
        Возвращает (tx, ty) если кликнули, иначе None.
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
        sx = self.region["left"] + tx
        sy = self.region["top"] + ty

        self.mouse.move_click(sx, sy)
        self._last_click_t = now
        self._recent.append((tx, ty, now))
        return (tx, ty)
