"""搜索游戏窗口及其几何信息（屏幕坐标中的客户区）。

支持多显示器：根据索引或名称选择显示器。
"""
import win32api
import win32gui


class GameWindow:
    def __init__(self, title_substr):
        self.title_substr = title_substr
        self.hwnd = None

    def find(self):
        matches = []

        def _cb(hwnd, _):
            if win32gui.IsWindowVisible(hwnd):
                title = win32gui.GetWindowText(hwnd)
                if title and self.title_substr.lower() in title.lower():
                    matches.append(hwnd)

        win32gui.EnumWindows(_cb, None)
        self.hwnd = matches[0] if matches else None
        return self.hwnd

    def get_region(self):
        """窗口客户区，以屏幕坐标的 dict(left, top, width, height) 格式返回。"""
        if not self.hwnd:
            return None
        left, top, right, bottom = win32gui.GetClientRect(self.hwnd)
        if right - left <= 0 or bottom - top <= 0:
            return None  # 窗口已最小化 — 无客户区
        sx, sy = win32gui.ClientToScreen(self.hwnd, (left, top))
        ex, ey = win32gui.ClientToScreen(self.hwnd, (right, bottom))
        return {"left": sx, "top": sy, "width": ex - sx, "height": ey - sy}

    def is_foreground(self):
        return self.hwnd is not None and win32gui.GetForegroundWindow() == self.hwnd

    @staticmethod
    def primary_region():
        """主显示器区域 — 当未找到游戏窗口时的回退方案。"""
        return {
            "left": 0,
            "top": 0,
            "width": win32api.GetSystemMetrics(0),
            "height": win32api.GetSystemMetrics(1),
        }


def list_monitors():
    """所有显示器列表：[{"index": 0, "left": 0, "top": 0, "width": 1920, "height": 1080, "primary": True}, ...]"""
    monitors = []

    def _callback(hMonitor, hdc, lprcMonitor, dwData):
        rc = lprcMonitor
        monitors.append({
            "index": len(monitors),
            "left": rc.left,
            "top": rc.top,
            "width": rc.right - rc.left,
            "height": rc.bottom - rc.top,
            "primary": rc.left == 0 and rc.top == 0,
        })

    try:
        win32api.EnumDisplayMonitors(None, None, _callback, 0)
    except Exception:
        pass

    if not monitors:
        monitors.append({
            "index": 0,
            "left": 0, "top": 0,
            "width": win32api.GetSystemMetrics(0),
            "height": win32api.GetSystemMetrics(1),
            "primary": True,
        })

    return monitors


def monitor_region(index=0):
    """根据索引获取指定显示器的区域。"""
    monitors = list_monitors()
    if 0 <= index < len(monitors):
        m = monitors[index]
        return {"left": m["left"], "top": m["top"],
                "width": m["width"], "height": m["height"]}
    return GameWindow.primary_region()
