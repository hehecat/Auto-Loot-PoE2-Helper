"""透明浮窗：角色轮廓方框 + 状态。

方框勾勒角色位置，上方显示 AutoLoot_ON/OFF 标签。
"""
from __future__ import annotations

import math
import time
import threading

try:
    import tkinter as tk
    from tkinter import font as tkfont
    HAS_TK = True
except ImportError:
    HAS_TK = False


class RadiusOverlay:
    """透明浮窗：角色轮廓 + 状态。"""

    def __init__(self, stop_event, get_state_fn):
        self.stop_event = stop_event
        self.get_state = get_state_fn
        self._root = None
        self._canvas = None
        self._start_time = time.perf_counter()

    def run(self):
        if not HAS_TK:
            return

        self._root = tk.Tk()
        self._root.title("Radius")
        self._root.overrideredirect(True)
        self._root.attributes("-topmost", True)
        self._root.attributes("-alpha", 0.7)
        self._root.config(bg="black")

        sw = self._root.winfo_screenwidth()
        sh = self._root.winfo_screenheight()
        self._root.geometry(f"{sw}x{sh}+0+0")

        try:
            self._root.attributes("-transparentcolor", "black")
        except Exception:
            pass

        self._canvas = tk.Canvas(self._root, width=sw, height=sh, bg="black", highlightthickness=0)
        self._canvas.pack()

        self._update()
        self._root.mainloop()

    def _update(self):
        if self.stop_event.is_set():
            self._root.after(0, self._root.destroy)
            return

        state = self.get_state()
        active = state.get("active", False)
        center_offset = state.get("center_offset", [0, 0])
        frame_size = state.get("frame_size", [1920, 1080])
        win_region = state.get("window_region", None)

        self._canvas.delete("all")

        if win_region:
            wl = win_region.get("left", 0)
            wt = win_region.get("top", 0)
            ww = win_region.get("width", 1920)
            wh = win_region.get("height", 1080)
        else:
            wl, wt = 0, 0
            ww, wh = 1920, 1080

        fw, fh = frame_size
        sx = ww / fw
        sy = wh / fh

        cx = wl + ww // 2 + int(center_offset[0] * sx)
        cy = wt + wh // 2 + int(center_offset[1] * sy)

        elapsed = time.perf_counter() - self._start_time
        pulse = (math.sin(elapsed * 3.0) + 1.0) / 2.0

        size = 40
        half = size // 2

        color = "#ff8800" if active else "#555555"

        self._canvas.create_rectangle(
            cx - half, cy - half, cx + half, cy + half,
            outline=color, width=2)

        glow_alpha = 0.3 + pulse * 0.4
        r, g, b = 0xff, 0x88, 0x00
        gr = int(r * glow_alpha)
        gg = int(g * glow_alpha)
        gb = int(b * glow_alpha)
        glow_color = f"#{min(255, gr):02x}{min(255, gg):02x}{min(255, gb):02x}"

        if active:
            expand = int(pulse * 6)
            self._canvas.create_rectangle(
                cx - half - expand, cy - half - expand,
                cx + half + expand, cy + half + expand,
                outline=glow_color, width=1)

        f = tkfont.Font(family="Consolas", size=13, weight="bold")

        if active:
            label = "自动拾取 开"
            label_color = "#00ff88"
        else:
            label = "自动拾取 关"
            label_color = "#ff4444"

        self._canvas.create_text(
            cx, cy - half - 18,
            text=label, fill=label_color, font=f)

        self._root.after(50, self._update)

    def stop(self):
        if self._root:
            try:
                self._root.after(0, self._root.destroy)
            except Exception:
                pass
