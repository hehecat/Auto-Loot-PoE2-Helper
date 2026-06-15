"""Прозрачный click-through оверлей со статусом поверх игры (tkinter + win32).

GUI обязан жить в главном потоке. Цикл захвата запускается отдельным потоком,
а оверлей читает статус через переданный snapshot-колбэк.
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
        self._make_click_through()
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
            f"quit    : {s.get('quit_key', 'F12')}"
        )
        stats = s.get("stats", {})
        _labels = [("currency", "cur"), ("fragments", "frag"), ("gems", "gem"), ("waystones", "way")]
        stat_parts = [f"{short}:{stats[k]}" for k, short in _labels if stats.get(k)]
        if stat_parts:
            text += "\n" + "  ".join(stat_parts)
        if not s.get("clicks_enabled", True):
            text += "\n[!] окно PoE2 не найдено — клики off"
        elif not s.get("foreground", True):
            text += "\n[~] PoE2 не активна — клики на паузе"
        self.label.config(text=text, fg="#00ff88" if active else "#9fb3c8")
        self.root.after(self.poll_ms, self._tick)
