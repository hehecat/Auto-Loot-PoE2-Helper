"""Прозрачный оверлей со статусом поверх игры (tkinter + win32).

GUI обязан жить в главном потоке. Цикл захвата запускается отдельным потоком,
а оверлей читает статус через переданный snapshot-колбэк.

Клик-сквозь по умолчанию. F10 — временно выключить click-through для drag.
"""
import tkinter as tk

TRANSPARENT_BG = "#010101"  # цвет-ключ прозрачности (Windows)


class Overlay:
    def __init__(self, snapshot_fn, stop_event, poll_ms=120, width=320, margin=(360, 40)):
        self.snapshot_fn = snapshot_fn
        self.stop_event = stop_event
        self.poll_ms = poll_ms
        self.width = width
        self.margin = margin
        self.root = None
        self.label = None
        self._click_through = True
        self._hwnd = None

    def run(self):
        self.root = tk.Tk()
        self.root.title("AutoLoot Overlay")
        self.root.overrideredirect(True)
        self.root.attributes("-topmost", True)
        self.root.attributes("-alpha", 0.85)
        self.root.config(bg=TRANSPARENT_BG)
        try:
            self.root.attributes("-transparentcolor", TRANSPARENT_BG)
        except tk.TclError:
            pass

        self.label = tk.Label(
            self.root, justify="left", anchor="nw",
            font=("Consolas", 12, "bold"),
            bg=TRANSPARENT_BG, fg="#00ffaa",
        )
        self.label.pack(padx=12, pady=10)

        self.root.update_idletasks()
        x = self.root.winfo_screenwidth() - self.margin[0]
        self.root.geometry(f"+{x}+{self.margin[1]}")
        self._hwnd = self._make_click_through()
        self._setup_drag()
        self.root.bind("<F10>", self._toggle_click_through)
        self.root.bind("<Button-3>", self._toggle_click_through)
        self._tick()
        self.root.mainloop()

    def _make_click_through(self):
        try:
            import win32con
            import win32gui

            hwnd = self.root.winfo_id()
            parent = win32gui.GetParent(hwnd)
            if parent:
                hwnd = parent
            ex = win32gui.GetWindowLong(hwnd, win32con.GWL_EXSTYLE)
            win32gui.SetWindowLong(
                hwnd, win32con.GWL_EXSTYLE,
                ex | win32con.WS_EX_LAYERED | win32con.WS_EX_TRANSPARENT | win32con.WS_EX_TOOLWINDOW,
            )
            return hwnd
        except Exception:  # noqa: BLE001
            return None  # без click-through оверлей всё равно показывается

    def _set_click_through(self, enabled):
        if not self._hwnd:
            return
        try:
            import win32con
            import win32gui
            ex = win32gui.GetWindowLong(self._hwnd, win32con.GWL_EXSTYLE)
            if enabled:
                ex |= win32con.WS_EX_TRANSPARENT
            else:
                ex &= ~win32con.WS_EX_TRANSPARENT
            win32gui.SetWindowLong(self._hwnd, win32con.GWL_EXSTYLE, ex)
            self._click_through = enabled
        except Exception:  # noqa: BLE001
            pass

    def _toggle_click_through(self, _event=None):
        self._set_click_through(not self._click_through)

    def _setup_drag(self):
        def on_press(event):
            if not self._click_through:
                self._drag_x = event.x_root - self.root.winfo_x()
                self._drag_y = event.y_root - self.root.winfo_y()

        def on_drag(event):
            if not self._click_through:
                x = event.x_root - self._drag_x
                y = event.y_root - self._drag_y
                self.root.geometry(f"+{x}+{y}")

        self.root.bind("<Button-1>", on_press)
        self.root.bind("<B1-Motion>", on_drag)

    def _make_click_through(self):
        try:
            import win32con
            import win32gui

            hwnd = self.root.winfo_id()
            parent = win32gui.GetParent(hwnd)
            if parent:
                hwnd = parent
            ex = win32gui.GetWindowLong(hwnd, win32con.GWL_EXSTYLE)
            win32gui.SetWindowLong(
                hwnd, win32con.GWL_EXSTYLE,
                ex | win32con.WS_EX_LAYERED | win32con.WS_EX_TRANSPARENT | win32con.WS_EX_TOOLWINDOW,
            )
        except Exception:  # noqa: BLE001
            pass  # без click-through оверлей всё равно показывается

    def _tick(self):
        if self.stop_event.is_set():
            self.root.destroy()
            return
        s = self.snapshot_fn()
        active = s.get("active")
        autom = "on" if s.get("automation") else "off"
        master = "ON" if s.get("auto") else "off"
        hp = s.get("hp")
        hp_str = f"  HP: {hp}%" if hp is not None else ""
        text = (
            f"AUTO LOOT  [{'ON' if active else 'idle'}]\n"
            f"mode    : {s.get('mode', '-')}\n"
            f"profile : {s.get('profile', 'default')}\n"
            f"targets : {s.get('targets', 0)}  (radius {s.get('in_radius', 0)})\n"
            f"picked  : {s.get('picked', 0)}{hp_str}\n"
            f"master  : {master}   automation: {autom}\n"
            f"cat     : {s.get('active_cat', 'all')}\n"
            f"quit    : {s.get('quit_key', 'F12')}  drag: F10/RMB"
        )
        stats = s.get("stats", {})
        _labels = [("currency", "cur"), ("fragments", "frag"), ("gems", "gem"), ("waystones", "way")]
        stat_parts = [f"{short}:{stats[k]}" for k, short in _labels if stats.get(k)]
        if stat_parts:
            text += "\n" + "  ".join(stat_parts)
        session_stats = s.get("session_stats")
        if session_stats:
            text += f"\nсессия: {session_stats}"
        if not s.get("clicks_enabled", True):
            text += "\n[!] окно PoE2 не найдено — клики off"
        elif not s.get("foreground", True):
            text += "\n[~] PoE2 не активна — клики на паузе"
        self.label.config(text=text, fg="#00ff88" if active else "#9fb3c8")
        self.root.after(self.poll_ms, self._tick)
