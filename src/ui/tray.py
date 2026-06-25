"""系统托盘图标（pystray），包含主要控制功能。

托盘在独立线程（daemon）中创建。图标显示状态并提供右键菜单：
Toggle、Profile、Settings、Reload、Quit。
"""
import logging
import threading

_log = logging.getLogger("autoloot.tray")

try:
    from PIL import Image, ImageDraw
    import pystray
    HAS_TRAY = True
except ImportError:
    HAS_TRAY = False


def _make_icon(color="#00ff88"):
    """创建一个带有彩色圆圈的简单 16x16 图标。"""
    img = Image.new("RGBA", (16, 16), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    r, g, b = int(color[1:3], 16), int(color[3:5], 16), int(color[5:7], 16)
    draw.ellipse([2, 2, 13, 13], fill=(r, g, b, 255))
    return img


class TrayIcon:
    def __init__(self, state, stop_event, on_toggle, on_reload, on_quit,
                 on_settings=None, profile_names=None, on_profile=None):
        self.state = state
        self.stop_event = stop_event
        self.on_toggle = on_toggle
        self.on_reload = on_reload
        self.on_quit = on_quit
        self.on_settings = on_settings
        self.profile_names = profile_names or []
        self.on_profile = on_profile
        self._icon = None
        self._thread = None

    def start(self):
        if not HAS_TRAY:
            _log.debug("pystray/Pillow 未安装 — 系统托盘图标不可用。")
            return
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()

    def stop(self):
        if self._icon:
            try:
                self._icon.stop()
            except Exception:
                pass

    def _run(self):
        try:
            def _settings():
                if self.on_settings:
                    self.on_settings()

            menu = pystray.Menu(
                pystray.MenuItem("开关 (F8)", lambda: self.on_toggle(),
                                 default=True),
                pystray.MenuItem("设置 (F6)", _settings),
                pystray.MenuItem("重载 (F5)", lambda: self.on_reload()),
                pystray.Menu.SEPARATOR,
                *self._profile_items(),
                pystray.Menu.SEPARATOR,
                pystray.MenuItem("退出 (F12)", lambda: self.on_quit()),
            )
            self._icon = pystray.Icon(
                "AutoLoot", _make_icon(), "自动拾取 PoE 助手", menu
            )
            self._icon.run()
        except Exception as e:
            _log.debug("托盘图标启动失败: %s", e)

    def _profile_items(self):
        items = []
        for name in self.profile_names:
            items.append(
                pystray.MenuItem(
                    f"配置: {name}",
                    lambda n=name: self.on_profile(n) if self.on_profile else None,
                )
            )
        return items

    def update_status(self, active):
        if self._icon and HAS_TRAY:
            try:
                color = "#00ff88" if active else "#ff4444"
                self._icon.icon = _make_icon(color)
            except Exception:
                pass
