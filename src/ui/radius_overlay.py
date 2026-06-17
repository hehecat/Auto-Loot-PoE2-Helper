"""Прозрачный оверлей с 3D-эллипсом радиуса подбора поверх игры.

Отображает эллипс (перспективная проекция круга на пол),
метки целей и информацию о статусе.
"""
from __future__ import annotations

import math
import threading

try:
    import tkinter as tk
    from tkinter import font as tkfont
    HAS_TK = True
except ImportError:
    HAS_TK = False


class RadiusOverlay:
    """Прозрачный оверлей с 3D-эллипсом радиуса и метками целей."""

    PERSPECTIVE = 0.55

    def __init__(self, stop_event, get_state_fn):
        self.stop_event = stop_event
        self.get_state = get_state_fn
        self._root = None
        self._canvas = None
        self._radius = 250
        self._dragging = False
        self._drag_start_r = 0
        self._drag_start_y = 0
        self._targets = []
        self._pulse = 0
        self._pulse_dir = 1

    def run(self):
        if not HAS_TK:
            return

        self._root = tk.Tk()
        self._root.title("Radius")
        self._root.overrideredirect(True)
        self._root.attributes("-topmost", True)
        self._root.attributes("-alpha", 0.6)
        self._root.config(bg="black")

        screen_w = self._root.winfo_screenwidth()
        screen_h = self._root.winfo_screenheight()
        self._screen_w = screen_w
        self._screen_h = screen_h
        size = max(screen_w, screen_h)
        self._size = size
        x = (screen_w - size) // 2
        y = (screen_h - size) // 2
        self._root.geometry(f"{size}x{size}+{x}+{y}")

        try:
            self._root.attributes("-transparentcolor", "black")
        except Exception:
            pass

        self._canvas = tk.Canvas(
            self._root, width=size, height=size,
            bg="black", highlightthickness=0)
        self._canvas.pack()

        self._cx = size // 2
        self._cy = size // 2

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

    def _draw_glow_ellipse(self, cx, cy, rx, ry, color, alpha_steps=5):
        for i in range(alpha_steps, 0, -1):
            factor = i / alpha_steps
            expand = 1.0 + (alpha_steps - i) * 0.06
            erx = int(rx * expand)
            ery = int(ry * expand)
            r, g, b = self._hex_to_rgb(color)
            fade = int(255 * factor * 0.3)
            c = f"#{min(255, r + fade):02x}{min(255, g + fade):02x}{min(255, b + fade):02x}"
            self._canvas.create_oval(
                cx - erx, cy - ery, cx + erx, cy + ery,
                outline=c, width=1, dash=(4, 4))

    def _draw_pulsing_ring(self, cx, cy, rx, ry, color):
        pulse = self._pulse
        expand = 1.0 + pulse * 0.08
        erx = int(rx * expand)
        ery = int(ry * expand)
        r, g, b = self._hex_to_rgb(color)
        brightness = int(100 + 155 * (1.0 - pulse))
        c = f"#{min(255, r + brightness // 4):02x}{min(255, g + brightness // 4):02x}{min(255, b + brightness // 4):02x}"
        self._canvas.create_oval(
            cx - erx, cy - ery, cx + erx, cy + ery,
            outline=c, width=1)

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

        self._canvas.delete("all")

        fw, fh = frame_size
        scale = self._size / max(fw, fh)

        char_cx = self._cx + int(center_offset[0] * scale)
        char_cy = self._cy + int(center_offset[1] * scale)
        r = int(self._radius * scale)
        ry = int(r * self.PERSPECTIVE)

        color = "#00ff88" if active else "#ff4444"

        self._pulse += 0.08 * self._pulse_dir
        if self._pulse >= 1.0:
            self._pulse_dir = -1
        elif self._pulse <= 0.0:
            self._pulse_dir = 1

        self._draw_glow_ellipse(char_cx, char_cy, r, ry, color)
        self._draw_pulsing_ring(char_cx, char_cy, r, ry, color)

        self._canvas.create_oval(
            char_cx - r, char_cy - ry, char_cx + r, char_cy + ry,
            outline=color, width=2)

        inner_rx = int(r * 0.35)
        inner_ry = int(ry * 0.35)
        self._canvas.create_oval(
            char_cx - inner_rx, char_cy - inner_ry,
            char_cx + inner_rx, char_cy + inner_ry,
            outline=color, width=1, dash=(3, 5))

        self._draw_crosshair(char_cx, char_cy, color)

        f_label = tkfont.Font(family="Consolas", size=11, weight="bold")
        self._canvas.create_text(
            char_cx, char_cy - ry - 18,
            text=f"R={self._radius}px",
            fill=color, font=f_label)

        self._canvas.create_text(
            char_cx, char_cy + ry + 18,
            text=f"{targets} targets | {in_radius} in range",
            fill=color, font=f_label)

        f_hint = tkfont.Font(family="Consolas", size=9)
        self._canvas.create_text(
            char_cx, char_cy + ry + 34,
            text="drag=resize | scroll=adjust",
            fill="#666666", font=f_hint)

        self._root.after(50, self._update)

    def _draw_crosshair(self, cx, cy, color):
        arm = 8
        gap = 4
        w = 1
        self._canvas.create_line(cx - arm - gap, cy, cx - gap, cy, fill=color, width=w)
        self._canvas.create_line(cx + gap, cy, cx + arm + gap, cy, fill=color, width=w)
        self._canvas.create_line(cx, cy - arm - gap, cx, cy - gap, fill=color, width=w)
        self._canvas.create_line(cx, cy + gap, cx, cy + arm + gap, fill=color, width=w)

    @staticmethod
    def _hex_to_rgb(hex_color):
        hex_color = hex_color.lstrip("#")
        return tuple(int(hex_color[i:i+2], 16) for i in (0, 2, 4))

    def stop(self):
        if self._root:
            try:
                self._root.after(0, self._root.destroy)
            except Exception:
                pass
