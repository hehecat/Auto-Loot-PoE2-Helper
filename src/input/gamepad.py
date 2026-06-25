"""通过虚拟 Xbox 控制器模拟 PoE2 输入。

解决问题：当连接了真实 DualSense 时，PoE2 会忽略虚拟控制器。
解决方案：
1. 通过 vgamepad 创建虚拟 Xbox
2. 心跳线程每 50ms 更新控制器
3. 停止时恢复控制器状态

按键映射通过 DS4Windows 配置。
"""
import ctypes
import ctypes.wintypes as wintypes
import logging
import os
import subprocess
import threading
import time

_log = logging.getLogger("autoloot.gamepad")

try:
    import vgamepad as vg
    HAS_VGAMEPAD = True
except ImportError:
    HAS_VGAMEPAD = False
    _log.warning("vgamepad not installed. pip install vgamepad")

# XInput button masks (TRIGGERS NOT HERE - handled separately)
XINPUT_BUTTONS = {
    "dpad_up":      0x0001,
    "dpad_down":    0x0002,
    "dpad_left":    0x0004,
    "dpad_right":   0x0008,
    "start":        0x0010,
    "back":         0x0020,
    "left_stick":   0x0040,
    "right_stick":  0x0080,
    "left_bumper":  0x0100,
    "right_bumper": 0x0200,
    "guide":        0x0400,
    "a":            0x1000,
    "b":            0x2000,
    "x":            0x4000,
    "y":            0x8000,
}

# Actions that use triggers instead of buttons
TRIGGER_ACTIONS = {
    "left_trigger":  "left",
    "right_trigger": "right",
}

# PoE2 action -> Xbox button (DEFAULT PoE2 controller layout)
ACTION_TO_XBOX = {
    "pickup":        "a",              # A (Cross) = 拾取物品
    "hp_flask":      "left_trigger",   # LT (L2) = HP 血瓶
    "mana_flask":    "right_trigger",  # RT (R2) = Mana 蓝瓶
    "attack":        "x",              # X (Square) = 攻击
    "dodge":         "b",              # B (Circle) = 闪避
    "skill_2":       "y",              # Y (Triangle) = 技能 2
    "inventory":     "left_bumper",    # LB (L1) = 背包
    "highlight":     "left_stick",     # L3 = 高亮物品
    "weapon_set":    "right_stick",    # R3 = 切换武器组
    "map":           "dpad_down",      # D-pad Down = 地图
    "menu":          "start",          # Start = 菜单
    "portal":        "dpad_right",     # D-pad Right = 传送门
}


def _is_admin():
    try:
        return bool(ctypes.windll.shell32.IsUserAnAdmin())
    except Exception:
        return False


def _disable_hid_powershell():
    """仅通过 PowerShell 禁用 DualSense（需要管理员权限）。"""
    try:
        result = subprocess.run(
            ["powershell", "-NoProfile", "-NonInteractive", "-Command",
             "chcp 65001 > $null; "
             "$devices = Get-PnpDevice | Where-Object {$_.InstanceId -like '*VID_054C*PID_0CE6*'}; "
             "if ($devices) { $devices | Disable-PnpDevice -Confirm:$false -ErrorAction Stop; "
             "Write-Output 'DualSense disabled' } else { Write-Output 'DualSense not found' }"],
            capture_output=True, timeout=15
        )
        out = (result.stdout or b'').decode('utf-8', errors='replace')
        err = (result.stderr or b'').decode('utf-8', errors='replace')
        _log.info("PowerShell: %s %s", out.strip(), err.strip()[:200])
        return 'disabled' in out.lower() or result.returncode == 0
    except Exception as e:
        _log.warning("PowerShell disable failed: %s", e)
        return False


def _enable_hid_powershell():
    """通过 PowerShell 启用 DualSense。"""
    try:
        subprocess.run(
            ["powershell", "-NoProfile", "-NonInteractive", "-Command",
             "chcp 65001 > $null; "
             "Get-PnpDevice | Where-Object {$_.InstanceId -like '*VID_054C*PID_0CE6*'} | "
             "Enable-PnpDevice -Confirm:$false -ErrorAction SilentlyContinue"],
            capture_output=True, timeout=15
        )
    except Exception as e:
        _log.warning("PowerShell enable failed: %s", e)


class GamepadEmulator:
    """通过 vgamepad 模拟 Xbox 控制器。"""

    def __init__(self):
        self.enabled = False
        self._gamepad = None
        self._controllers_disabled = False
        self._heartbeat_thread = None
        self._heartbeat_stop = threading.Event()
        self._lock = threading.Lock()
        self._bridge = None

    def start(self):
        """初始化：创建虚拟 Xbox。

        DualSense 不会被禁用 — 它继续用于手动控制。
        机器人通过虚拟 Xbox 发送命令（拾取、血瓶）。
        PoE2 接受来自两个控制器的输入。
        """
        if not HAS_VGAMEPAD:
            _log.error("vgamepad not installed. pip install vgamepad")
            return False

        # 恢复 DualSense（如果之前被禁用）
        _enable_hid_powershell()
        time.sleep(0.3)

        # 创建虚拟 Xbox 360 控制器
        self._gamepad = vg.VX360Gamepad()
        # reset + update 初始化控制器以支持 XInput
        self._gamepad.reset()
        self._gamepad.update()
        time.sleep(0.3)

        # 启动心跳线程以保持 SDL2 控制器活跃
        self._start_heartbeat()

        # 启动 DualSense → Virtual Xbox 桥接
        self._bridge = None
        try:
            from .dualsense_hid import DualSenseHIDReader
            self._bridge = DualSenseHIDReader(self._gamepad)
            if self._bridge.start():
                _log.info("DualSense HID reader ACTIVE (raw HID, like DS4Windows)")
            else:
                _log.info("DualSense HID not available")
                self._bridge = None
        except Exception as e:
            _log.info("DualSense HID skip: %s", e)

        self.enabled = True

        _log.info("Virtual Xbox 360 gamepad created")
        _log.info("DualSense → Xbox bridge: input forwarded via virtual Xbox")
        return True

    def stop(self):
        """停止。"""
        if self._bridge:
            try:
                self._bridge.stop()
            except Exception:
                pass
            self._bridge = None

        self._stop_heartbeat()

        if self._gamepad:
            try:
                self._gamepad.reset()
                self._gamepad.update()
            except Exception:
                pass
            self._gamepad = None

        self.enabled = False
        _log.info("Gamepad emulator stopped")

    def _start_heartbeat(self):
        self._heartbeat_stop.clear()
        self._heartbeat_thread = threading.Thread(target=self._heartbeat_loop, daemon=True)
        self._heartbeat_thread.start()

    def _stop_heartbeat(self):
        self._heartbeat_stop.set()
        if self._heartbeat_thread:
            self._heartbeat_thread.join(timeout=2.0)
            self._heartbeat_thread = None

    def _heartbeat_loop(self):
        while not self._heartbeat_stop.is_set():
            with self._lock:
                try:
                    if self._gamepad:
                        self._gamepad.update()
                except Exception:
                    pass
            self._heartbeat_stop.wait(0.05)  # 50ms = 20Hz

    def press_button(self, action, hold_ms=100):
        """根据动作按下按钮或扳机。"""
        if not self.enabled or not self._gamepad:
            return False

        btn_name = ACTION_TO_XBOX.get(action)
        if not btn_name:
            _log.warning("Unknown action: %s", action)
            return False

        # 检查扳机（L2/R2）
        trigger_side = TRIGGER_ACTIONS.get(btn_name)
        if trigger_side:
            try:
                with self._lock:
                    if trigger_side == "left":
                        self._gamepad.left_trigger(value=255)
                    else:
                        self._gamepad.right_trigger(value=255)
                    self._gamepad.update()
                time.sleep(hold_ms / 1000.0)
                with self._lock:
                    if trigger_side == "left":
                        self._gamepad.left_trigger(value=0)
                    else:
                        self._gamepad.right_trigger(value=0)
                    self._gamepad.update()
                return True
            except Exception as e:
                _log.error("Trigger press failed: %s", e)
                return False

        # 普通按钮
        btn_mask = XINPUT_BUTTONS.get(btn_name)
        if not btn_mask:
            _log.warning("Unknown Xbox button: %s", btn_name)
            return False

        try:
            with self._lock:
                self._gamepad.press_button(button=btn_mask)
                self._gamepad.update()
            time.sleep(hold_ms / 1000.0)
            with self._lock:
                self._gamepad.release_button(button=btn_mask)
                self._gamepad.update()
            return True
        except Exception as e:
            _log.error("Button press failed: %s", e)
            return False

    def set_trigger(self, trigger, value):
        """设置扳机值（0-255）。"""
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
        """设置摇杆（x, y: -32767..32767）。"""
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

    def get_button_id(self, action):
        """根据动作获取按钮 ID（来自 ACTION_TO_XBOX）。"""
        return ACTION_TO_XBOX.get(action)

    # --- 与旧 API 的兼容性 ---
    def pickup(self):
        """拾取物品（按下 A/Cross）。"""
        self.press_button("pickup", hold_ms=100)

    def use_hp_flask(self):
        """使用 HP 血瓶（按下 L2/LT）。"""
        self.press_button("hp_flask", hold_ms=100)
