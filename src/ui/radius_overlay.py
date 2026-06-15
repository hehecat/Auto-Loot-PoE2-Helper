"""Прозрачный оверлей с кругом радиуса подбора поверх игры.

Отображает круг радиуса, точку центра персонажа и все обнаруженные цели.
"""
from __future__ import annotations

import threading

try:
    import tkinter as tk
    from tkinter import font as tkfont
    HAS_TK = True
except ImportError:
    HAS_TK = False


class RadiusOverlay:
    """Прозрачный оверлей с кругом радиуса и метками целей."""

    def __init__(self, stop_event, get_state_fn):
        self.stop_event = stop_event
        self.get_state = get_state_fn
        self._root = None
        self._canvas = None
        self._radius = 250
        self._dragging = False
        self._drag_start_r = 0
        self._drag_start_y = 0

    def run(self):
        if not HAS_TK:
            return

        self._root = tk.Tk()
        self._root.title("Radius")
        self._root.overrideredirect(True)
        self._root.attributes("-topmost", True)
        self._root.attributes("-alpha", 0.5)
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

    def _update(self):
        if self.stop_event.is_set():
            self._root.destroy()
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

        color = "#00ff88" if active else "#ff4444"

        self._canvas.create_oval(
            char_cx - r, char_cy - r, char_cx + r, char_cy + r,
            outline=color, width=2, dash=(6, 4))

        self._canvas.create_oval(
            char_cx - 6, char_cy - 6, char_cx + 6, char_cy + 6,
            fill=color, outline="")

        self._canvas.create_line(char_cx - 15, char_cy, char_cx + 15, char_cy, fill=color, width=1)
        self._canvas.create_line(char_cx, char_cy - 15, char_cx, char_cy + 15, fill=color, width=1)

        f = tkfont.Font(family="Consolas", size=11, weight="bold")
        self._canvas.create_text(
            char_cx, char_cy - r - 15,
            text=f"R={self._radius}px",
            fill=color, font=f)
        self._canvas.create_text(
            char_cx, char_cy + r + 15,
            text=f"targets:{targets} in:{in_radius}",
            fill=color, font=f)
        self._canvas.create_text(
            char_cx, char_cy + r + 30,
            text="drag=resize | scroll=adjust",
            fill="#888888", font=tkfont.Font(family="Consolas", size=9))

        self._root.after(100, self._update)

    def stop(self):
        if self._root:
            try:
                self._root.destroy()
            except Exception:
                pass
