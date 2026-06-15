"""Управление мышью: геймерский стиль — прямой быстрый бросок к цели.

Курсор летит по прямой линии с постоянной высокой скоростью — так выглядит
движение геймера с высоким DPI. Промежуточные точки дают видимую траекторию
(не телепорт), но движение остаётся резким. Финал — точно на цели.
"""
import math
import random
import time

from pynput.mouse import Button, Controller

_SPEED_PPS = 2500   # скорость броска, пикселей/сек (примерно 400 DPI * быстрое движение)
_MIN_STEPS = 3      # минимум промежуточных кадров (всегда есть видимое движение)


class Mouse:
    def __init__(self, restore_pos=False, rand_delay_ms=(15, 30), human_move=True):
        self._m = Controller()
        self.restore_pos = restore_pos
        self.rand_delay_ms = rand_delay_ms
        self.human_move = human_move

    def position(self):
        return self._m.position

    def move_click(self, x, y, **_kwargs):
        prev = self._m.position
        if self.human_move:
            self._human_move(int(x), int(y))
        else:
            self._m.position = (int(x), int(y))
        delay = random.randint(*self.rand_delay_ms) / 1000.0
        time.sleep(delay)
        self._m.click(Button.left, 1)
        if self.restore_pos:
            self._m.position = prev

    def _human_move(self, tx, ty):
        sx, sy = self._m.position
        dist = math.hypot(tx - sx, ty - sy)

        if dist < 2:
            self._m.position = (tx, ty)
            return

        # Количество шагов: минимум 3, плюс по одному на каждые 60px.
        # При 2500px/s и шаге каждые 60px — видимое движение ~8ms на шаг.
        n = max(_MIN_STEPS, int(dist / 60))
        speed = random.uniform(_SPEED_PPS * 0.9, _SPEED_PPS * 1.1)
        duration = dist / speed
        step_sleep = duration / n

        for i in range(1, n + 1):
            t = i / n
            if i < n:
                # промежуточные точки: мелкий поперечный шум (выглядит живо)
                noise = math.sin(t * math.pi) * random.uniform(0, 1.0)
                if dist > 0:
                    px = -(ty - sy) / dist * noise
                    py = (tx - sx) / dist * noise
                else:
                    px = py = 0
                self._m.position = (int(sx + (tx - sx) * t + px),
                                    int(sy + (ty - sy) * t + py))
            else:
                # финал — точно на цели, без шума
                self._m.position = (tx, ty)
            time.sleep(step_sleep)
