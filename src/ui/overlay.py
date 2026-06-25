"""透明状态浮窗，显示在游戏上方（tkinter + win32）。

GUI 必须在主线程中运行。捕获循环在独立线程中启动，
浮窗通过传入的 snapshot 回调读取状态。

默认启用点击穿透。F10 — 临时禁用点击穿透以便拖拽。
"""
import tkinter as tk

TRANSPARENT_BG = "#010101"  # 透明色键 (Windows)


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
        self.root.title("自动拾取浮窗")
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
            return None  # 即使没有 click-through，浮窗仍然显示

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
            pass  # 即使没有 click-through，浮窗仍然显示

    def _tick(self):
        if self.stop_event.is_set():
            self.root.destroy()
            return
        s = self.snapshot_fn()
        active = s.get("active")
        autom = "开" if s.get("automation") else "关"
        master = "开" if s.get("auto") else "关"
        hp = s.get("hp")
        hp_str = f"  HP: {hp}%" if hp is not None else ""
        text = (
            f"自动拾取  [{'运行中' if active else '空闲'}]\n"
            f"模式   : {s.get('mode', '-')}\n"
            f"配置   : {s.get('profile', 'default')}\n"
            f"目标   : {s.get('targets', 0)}  (半径 {s.get('in_radius', 0)})\n"
            f"已拾取 : {s.get('picked', 0)}{hp_str}\n"
            f"总开关 : {master}   自动化: {autom}\n"
            f"分类   : {s.get('active_cat', 'all')}\n"
            f"退出   : {s.get('quit_key', 'F12')}  拖动: F10/右键"
        )
        stats = s.get("stats", {})
        _labels = [("currency", "cur"), ("fragments", "frag"), ("gems", "gem"), ("waystones", "way")]
        stat_parts = [f"{short}:{stats[k]}" for k, short in _labels if stats.get(k)]
        if stat_parts:
            text += "\n" + "  ".join(stat_parts)
        session_stats = s.get("session_stats")
        if session_stats:
            text += f"\n会话: {session_stats}"
        if not s.get("clicks_enabled", True):
            text += "\n[!] 未找到 PoE2 窗口 — 点击已关闭"
        elif not s.get("foreground", True):
            text += "\n[~] PoE2 未激活 — 点击已暂停"
        self.label.config(text=text, fg="#00ff88" if active else "#9fb3c8")
        self.root.after(self.poll_ms, self._tick)
