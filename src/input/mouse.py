"""鼠标控制：游戏玩家风格 — 直接快速移动到目标。

光标沿直线以恒定的高速飞行 — 就像高 DPI 玩家的移动方式。
中间点产生可见轨迹（不是瞬移），但移动保持干脆利落。
最终 — 精确到达目标。
"""
import math
import random
import time

from pynput.mouse import Button, Controller

_SPEED_PPS = 2500   # 移动速度，像素/秒（约 400 DPI * 快速移动）
_MIN_STEPS = 3      # 最少中间帧数（始终有可见移动）


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

        # 步数：最少 3 步，每 60px 增加一步。
        # 2500px/s 速度下每 60px 一步 — 可见移动约 8ms/步。
        n = max(_MIN_STEPS, int(dist / 60))
        speed = random.uniform(_SPEED_PPS * 0.9, _SPEED_PPS * 1.1)
        duration = dist / speed
        step_sleep = duration / n

        for i in range(1, n + 1):
            t = i / n
            if i < n:
                # 中间点：微小横向噪声（看起来生动）
                noise = math.sin(t * math.pi) * random.uniform(0, 1.0)
                if dist > 0:
                    px = -(ty - sy) / dist * noise
                    py = (tx - sx) / dist * noise
                else:
                    px = py = 0
                self._m.position = (int(sx + (tx - sx) * t + px),
                                    int(sy + (ty - sy) * t + py))
            else:
                # 最终 — 精确到达目标，无噪声
                self._m.position = (tx, ty)
            time.sleep(step_sleep)
