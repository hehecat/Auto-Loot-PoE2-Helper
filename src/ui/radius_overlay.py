"""Прозрачный оверлей: оранжевый прямоугольник-аура вокруг персонажа.

Простой прямоугольный контур с пульсацией от центра наружу.
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
    """Прозрачный оверлей: прямоугольник-аура с пульсацией."""

    def __init__(self, stop_event, get_state_fn):
        self.stop_event = stop_event
        self.get_state = get_state_fn
        self._root = None
        self._canvas = None
        self._radius = 250
        self._dragging = False
        self._drag_start_r = 0
        self._drag_start_y = 0
        self._pulse = 0.0
        self._start_time = time.perf_counter()

    def run(self):
        if not HAS_TK:
            return

        self._root = tk.Tk()
        self._root.title("Radius")
        self._root.overrideredirect(True)
        self._root.attributes("-topmost", True)
        self._root.attributes("-alpha", 0.6)
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

        self._canvas.bind("<Button-1>", self._on_press)
        self._canvas.bind("<B1-Motion>", self._on_drag)
        self._canvas.bind("<ButtonRelease-1>", self._on_release)
        self._canvas.bind("<MouseWheel>", self._on_scroll)

        self._update()
        self._root.mainloop()

    def _on_press(self, event):
        self._dragging = True
        self._drag_start_r = self._radius
        self._drag_start_y = event.y_root

    def _on_drag(self, event):
        if self._dragging:
            dy = self._drag_start_y - event.y_root
            self._radius = max(50, min(1500, self._drag_start_r + dy))

    def _on_release(self, event):
        self._dragging = False

    def _on_scroll(self, event):
        if event.delta > 0:
            self._radius = min(1500, self._radius + 10)
        else:
            self._radius = max(50, self._radius - 10)

    def _update(self):
        if self.stop_event.is_set():
            self._root.after(0, self._root.destroy)
            return

        state = self.get_state()
        self._radius = state.get("radius", self._radius)
        active = state.get("active", False)
        targets = state.get("targets", 0)
        in_radius = state.get("in_radius", 0)
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

        r = int(self._radius * sx)
        ry = int(r * 0.55)

        elapsed = time.perf_counter() - self._start_time
        self._pulse = (math.sin(elapsed * 2.5) + 1.0) / 2.0

        pulse_expand = 1.0 + self._pulse * 0.12
        pr = int(r * pulse_expand)
        pry = int(ry * pulse_expand)

        color = "#ff8800" if active else "#ff4444"

        self._canvas.create_rectangle(
            cx - pr, cy - pry, cx + pr, cy + pry,
            outline=color, width=2)

        inner_expand = 0.6 + self._pulse * 0.1
        ir = int(r * inner_expand)
        iry = int(ry * inner_expand)
        inner_color = "#cc6600" if active else "#cc3333"
        self._canvas.create_rectangle(
            cx - ir, cy - iry, cx + ir, cy + iry,
            outline=inner_color, width=1, dash=(4, 6))

        self._canvas.create_rectangle(
            cx - 4, cy - 4, cx + 4, cy + 4,
            fill=color, outline="")

        f = tkfont.Font(family="Consolas", size=11, weight="bold")
        self._canvas.create_text(
            cx, cy - pry - 14,
            text=f"R={self._radius}px",
            fill=color, font=f)

        self._canvas.create_text(
            cx, cy + pry + 14,
            text=f"{targets} targets | {in_radius} in range",
            fill=color, font=f)

        self._root.after(50, self._update)

    def stop(self):
        if self._root:
            try:
                self._root.after(0, self._root.destroy)
            except Exception:
                pass
