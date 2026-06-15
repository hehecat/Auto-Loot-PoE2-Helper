"""Эмуляция ввода для PoE2.

Использует pynput для реального нажатия клавиш.
Работает с любым типом контроллера (DualSense, Xbox и т.д.)
"""
import json
import logging
import time
from pathlib import Path

_log = logging.getLogger("autoloot.gamepad")

try:
    from pynput.keyboard import Controller, Key
    HAS_PYNPUT = True
except ImportError:
    HAS_PYNPUT = False

MAPPING_FILE = Path(__file__).resolve().parents[2] / "config" / "gamepad" / "mapping.json"

# PoE2 keyboard shortcuts (works even in controller mode)
POE2_KEYS = {
    "pickup": "space",
    "hp_flask": "1",
    "mana_flask": "2",
    "dodge": "escape",
    "skill_1": "q",
    "skill_2": "w",
    "skill_3": "e",
    "skill_4": "r",
}


class GamepadEmulator:
    """Отправка нажатий клавиш через pynput."""

    def __init__(self):
        self.enabled = False
        self._mapping = self._load_mapping()
        self._kb = None

        if HAS_PYNPUT:
            try:
                self._kb = Controller()
                self.enabled = True
                _log.info("Input emulator: pynput active")
            except Exception as e:
                _log.warning("pynput init failed: %s", e)
        else:
            _log.info("pynput not available")

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

    def _send_key(self, key_name, duration=0.03):
        """Send key press via pynput."""
        if not self._kb:
            return

        try:
            key_map = {
                "space": Key.space,
                "escape": Key.esc,
            }
            key = key_map.get(key_name) or key_name

            self._kb.press(key)
            time.sleep(duration)
            self._kb.release(key)
        except Exception as e:
            _log.debug("Key send error: %s", e)

    def press(self, action, duration=0.03):
        """Press button by action name."""
        if not self.enabled:
            return

        key_name = POE2_KEYS.get(action)
        if key_name:
            self._send_key(key_name, duration)

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
