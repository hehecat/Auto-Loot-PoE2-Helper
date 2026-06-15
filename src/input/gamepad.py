"""Эмуляция ввода для PoE2 через виртуальный Xbox контроллер.

Решает проблему: когда подключён реальный DualSense, PoE2 игнорирует
клавиатуру и виртуальные контроллеры. Решение:
1. Временно отключаем все HID-контроллеры
2. Создаём виртуальный Xbox через vgamepad
3. Игра видит только Xbox → принимаем ввод
4. При остановке восстанавливаем контроллеры

Для DualSense нужно также эмулировать Touchpad как мышь для наведения.
"""
import ctypes
import ctypes.wintypes as wintypes
import json
import logging
import os
import subprocess
import time
from pathlib import Path

_log = logging.getLogger("autoloot.gamepad")

try:
    import vgamepad as vg
    HAS_VGAMEPAD = True
except ImportError:
    HAS_VGAMEPAD = False
    _log.warning("vgamepad not installed. pip install vgamepad")

MAPPING_FILE = Path(__file__).resolve().parents[2] / "config" / "gamepad" / "mapping.json"

# XInput button masks
XINPUT_BUTTONS = {
    "dpad_up":    0x0001,
    "dpad_down":  0x0002,
    "dpad_left":  0x0004,
    "dpad_right": 0x0008,
    "start":      0x0010,
    "back":       0x0020,
    "left_stick": 0x0040,
    "right_stick":0x0080,
    "left_bumper":0x0100,
    "right_bumper":0x0200,
    "guide":      0x0400,
    "a":          0x1000,
    "b":          0x2000,
    "x":          0x4000,
    "y":          0x8000,
}

# PoE2 action -> Xbox button
ACTION_TO_XBOX = {
    "pickup":      "a",        # X/Cross -> A
    "hp_flask":    "x",        # Square -> X (SLT на DualSense = L1 на Xbox)
    "mana_flask":  "y",        # Triangle -> Y
    "dodge":       "b",        # Circle -> B
    "skill_1":     "left_bumper",   # L1 -> LB
    "skill_2":     "right_bumper",  # R1 -> RB
    "skill_3":     "dpad_up",
    "skill_4":     "dpad_down",
    "inventory":   "back",
    "map":         "start",
}


def _disable_hid_controllers():
    """Отключить все HID-контроллеры через Device Manager (devcon/disable)."""
    _log.info("Disabling HID controllers...")
    try:
        # Ищем все HID-устройства с Gamepad в имени
        result = subprocess.run(
            ["powershell", "-Command",
             "Get-PnpDevice -Class HIDClass | Where-Object {$_.FriendlyName -match 'Gamepad|DualSense|Xbox|Controller'} | "
             "Disable-PnpDevice -Confirm:$false"],
            capture_output=True, text=True, timeout=10
        )
        if result.returncode == 0:
            _log.info("HID controllers disabled")
            return True
        else:
            _log.warning("Could not disable HID: %s", result.stderr.strip())
            return False
    except Exception as e:
        _log.warning("HID disable failed: %s", e)
        return False


def _enable_hid_controllers():
    """Восстановить все HID-контроллеры."""
    _log.info("Enabling HID controllers...")
    try:
        subprocess.run(
            ["powershell", "-Command",
             "Get-PnpDevice -Class HIDClass | Where-Object {$_.FriendlyName -match 'Gamepad|DualSense|Xbox|Controller'} | "
             "Enable-PnpDevice -Confirm:$false"],
            capture_output=True, timeout=10
        )
        _log.info("HID controllers re-enabled")
    except Exception as e:
        _log.warning("HID enable failed: %s", e)


class GamepadEmulator:
    """Эмуляция Xbox контроллера через vgamepad."""

    def __init__(self):
        self.enabled = False
        self._gamepad = None
        self._mapping = self._load_mapping()
        self._controllers_disabled = False
        self._original_state = None

    def start(self):
        """Инициализация: отключаем реальные контроллеры, создаём виртуальный."""
        if not HAS_VGAMEPAD:
            _log.error("vgamepad not installed. pip install vgamepad")
            return False

        # Сохраняем состояние и отключаем реальные контроллеры
        self._controllers_disabled = _disable_hid_controllers()

        # Ждём чтобы ОС обработала отключение
        time.sleep(1.0)

        # Создаём виртуальный Xbox 360 контроллер
        self._gamepad = vg.VX360Gamepad()
        self.enabled = True
        _log.info("Virtual Xbox 360 gamepad created successfully")
        return True

    def stop(self):
        """Остановка: восстанавливаем реальные контроллеры."""
        if self._gamepad:
            try:
                self._gamepad.reset()
                self._gamepad.update()
            except Exception:
                pass
            self._gamepad = None

        self.enabled = False

        # Восстанавливаем реальные контроллеры
        if self._controllers_disabled:
            _enable_hid_controllers()
            self._controllers_disabled = False

        _log.info("Gamepad emulator stopped")

    def press_button(self, action, hold_ms=50):
        """Нажать кнопку по действию (pickup, hp_flask, etc)."""
        if not self.enabled or not self._gamepad:
            return False

        btn_name = ACTION_TO_XBOX.get(action)
        if not btn_name:
            _log.warning("Unknown action: %s", action)
            return False

        btn_mask = XINPUT_BUTTONS.get(btn_name)
        if not btn_mask:
            _log.warning("Unknown Xbox button: %s", btn_name)
            return False

        try:
            self._gamepad.press_button(button=btn_mask)
            self._gamepad.update()
            time.sleep(hold_ms / 1000.0)
            self._gamepad.release_button(button=btn_mask)
            self._gamepad.update()
            return True
        except Exception as e:
            _log.error("Button press failed: %s", e)
            return False

    def set_trigger(self, trigger, value):
        """Установить значение триггера (0-255). trigger: 'left' или 'right'."""
        if not self.enabled or not self._gamepad:
            return
        try:
            if trigger == "left":
                self._gamepad.left_trigger(value=value)
            else:
                self._gamepad.right_trigger(value=value)
            self._gamepad.update()
        except Exception as e:
            _log.error("Trigger set failed: %s", e)

    def set_stick(self, stick, x, y):
        """Установить стик (x, y: -32767..32767). stick: 'left' или 'right'."""
        if not self.enabled or not self._gamepad:
            return
        try:
            if stick == "left":
                self._gamepad.left_joystick(x_value=x, y_value=y)
            else:
                self._gamepad.right_joystick(x_value=x, y_value=y)
            self._gamepad.update()
        except Exception as e:
            _log.error("Stick set failed: %s", e)

    def _load_mapping(self):
        """Загрузить маппинг кнопок из калибровки."""
        if MAPPING_FILE.exists():
            try:
                with open(MAPPING_FILE, encoding="utf-8") as f:
                    data = json.load(f)
                _log.info("Gamepad mapping loaded: %s", data.get("controller", "unknown"))
                return data
            except Exception:
                pass
        return {}

    def get_button_id(self, action):
        """Получить ID кнопки DualSense по действию (из калибровки)."""
        return self._mapping.get("buttons", {}).get(action)

    # --- Совместимость со старым API ---
    def pickup(self):
        """Подобрать лут (нажать A/X)."""
        self.press_button("pickup", hold_ms=50)

    def use_hp_flask(self):
        """Использовать HP фласку (нажать L2/SLT)."""
        self.press_button("hp_flask", hold_ms=80)
