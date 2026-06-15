"""Эмуляция ввода для PoE2 через win32api.

Отправляет нажатия клавиш напрямую в окно игры.
Работает с любым типом контроллера (DualSense, Xbox и т.д.)
"""
import json
import logging
import time
from pathlib import Path

_log = logging.getLogger("autoloot.gamepad")

try:
    import win32api
    import win32con
    import win32gui
    HAS_WIN32 = True
except ImportError:
    HAS_WIN32 = False

MAPPING_FILE = Path(__file__).resolve().parents[2] / "config" / "gamepad" / "mapping.json"

# PoE2 keyboard shortcuts (works even in controller mode)
POE2_KEYS = {
    "pickup": 0x20,       # Space
    "hp_flask": 0x31,     # 1
    "mana_flask": 0x32,   # 2
    "dodge": 0x1B,        # Escape
    "skill_1": 0x51,      # Q
    "skill_2": 0x57,      # W
    "skill_3": 0x45,      # E
    "skill_4": 0x52,      # R
}


class GamepadEmulator:
    """Отправка нажатий в окно PoE2 через win32api."""

    def __init__(self):
        self.enabled = False
        self._mapping = self._load_mapping()
        self._hwnd = None

        if HAS_WIN32:
            self.enabled = True
            _log.info("Input emulator: win32api active")

    def _load_mapping(self):
        if MAPPING_FILE.exists():
            try:
                with open(MAPPING_FILE, encoding="utf-8") as f:
                    data = json.load(f)
                _log.info("Mapping loaded: %s", data.get("name", "unknown"))
                return data.get("buttons", {})
            except Exception:
                pass
        return {}

    def _find_game_window(self):
        """Find PoE2 window handle."""
        if self._hwnd and win32gui.IsWindow(self._hwnd):
            return self._hwnd

        def callback(hwnd, _):
            if win32gui.IsWindowVisible(hwnd):
                title = win32gui.GetWindowText(hwnd)
                if "path of exile" in title.lower():
                    self._hwnd = hwnd
                    return False
            return True

        win32gui.EnumWindows(callback, None)
        return self._hwnd

    def _send_key(self, vk_code, duration=0.03):
        """Send key press to game window."""
        hwnd = self._find_game_window()
        if not hwnd:
            return

        try:
            win32api.PostMessage(hwnd, win32con.WM_KEYDOWN, vk_code, 0)
            time.sleep(duration)
            win32api.PostMessage(hwnd, win32con.WM_KEYUP, vk_code, 0)
        except Exception as e:
            _log.debug("Key send error: %s", e)

    def press(self, action, duration=0.03):
        """Press button by action name."""
        if not self.enabled:
            return

        vk = POE2_KEYS.get(action)
        if vk is not None:
            self._send_key(vk, duration)

    def pickup(self):
        self.press("pickup", duration=0.03)

    def use_hp_flask(self):
        self.press("hp_flask", duration=0.05)

    def use_mana_flask(self):
        self.press("mana_flask", duration=0.05)

    def dodge(self):
        self.press("dodge", duration=0.03)

    def skill(self, slot):
        self.press(f"skill_{slot}", duration=0.03)

    def reset(self):
        pass
