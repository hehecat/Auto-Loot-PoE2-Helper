"""DualSense -> 虚拟 Xbox 桥接。

通过 pygame 读取 DualSense，重定向到虚拟 Xbox。
按键映射通过 DS4Windows 配置。
"""
import logging

_log = logging.getLogger("autoloot.dualsense_bridge")

try:
    import vgamepad as vg
except ImportError:
    vg = None

try:
    import pygame
except ImportError:
    pygame = None

# DS -> Xbox mapping (matches PoE2 default controller layout)
# Cross=A, Circle=B, Square=X, Triangle=Y, L1=LB, L2=LT, R1=RB, R2=RT
DS_BUTTON_TO_XBOX = {
    0:  0x1000,   # Cross (X) -> A = Pickup
    1:  0x2000,   # Circle (O) -> B = Dodge
    2:  0x4000,   # Square [] -> X = Attack
    3:  0x8000,   # Triangle /\ -> Y = Skill 2
    4:  0x0100,   # L1 -> LB = Inventory
    5:  0x0200,   # R1 -> RB
    8:  0x0020,   # Share -> Back
    9:  0x0010,   # Options -> Start = Menu
    11: 0x0040,   # L3 -> Left Stick Click = Highlight
    12: 0x0080,   # R3 -> Right Stick Click = Weapon Set
    13: 0x0001,   # D-pad Up
    14: 0x0002,   # D-pad Down = Map
    15: 0x0004,   # D-pad Left
    16: 0x0008,   # D-pad Right = Portal
}

SKIP_BUTTONS = {10}  # PS button - opens browser


class DualSenseBridge:
    """Forwards DualSense input to virtual Xbox."""

    def __init__(self, virtual_gamepad):
        self._gp = virtual_gamepad
        self._thread = None
        self._stop = None
        self._ds_index = None

    def start(self):
        if not vg or not pygame:
            _log.warning("vgamepad or pygame not installed")
            return False

        pygame.init()
        pygame.joystick.init()

        self._ds_index = self._find_dualsense()
        if self._ds_index is None:
            _log.warning("DualSense not found in pygame")
            pygame.quit()
            return False

        js = pygame.joystick.Joystick(self._ds_index)
        js.init()
        _log.info("DualSense bridge started: %s", js.get_name())

        import threading
        self._stop = threading.Event()
        self._thread = threading.Thread(target=self._loop, daemon=True)
        self._thread.start()
        return True

    def stop(self):
        if self._stop:
            self._stop.set()
        if self._thread:
            self._thread.join(timeout=1.0)
            self._thread = None
        try:
            pygame.quit()
        except Exception:
            pass

    def _find_dualsense(self):
        for i in range(pygame.joystick.get_count()):
            js = pygame.joystick.Joystick(i)
            js.init()
            name = js.get_name().lower()
            if 'dualsense' in name or 'ps5' in name or 'wireless controller' in name:
                return i
        return None

    def _loop(self):
        prev_buttons = {}
        while not self._stop.is_set():
            try:
                pygame.event.pump()
                js = pygame.joystick.Joystick(self._ds_index)

                # Forward buttons
                for b in range(js.get_numbuttons()):
                    if b in SKIP_BUTTONS:
                        continue

                    pressed = bool(js.get_button(b))
                    was_pressed = prev_buttons.get(b, False)

                    if pressed != was_pressed:
                        xbox_mask = DS_BUTTON_TO_XBOX.get(b)
                        if xbox_mask:
                            if pressed:
                                self._gp.press_button(button=xbox_mask)
                            else:
                                self._gp.release_button(button=xbox_mask)

                    prev_buttons[b] = pressed

                # Forward sticks
                if js.get_numaxes() >= 2:
                    lx = int(js.get_axis(0) * 32767)
                    ly = int(js.get_axis(1) * -32767)
                    self._gp.left_joystick(x_value=lx, y_value=ly)

                if js.get_numaxes() >= 4:
                    rx = int(js.get_axis(2) * 32767)
                    ry = int(js.get_axis(3) * -32767)
                    self._gp.right_joystick(x_value=rx, y_value=ry)

                # Forward triggers
                if js.get_numaxes() >= 6:
                    l2 = int((js.get_axis(4) + 1) / 2 * 255)
                    r2 = int((js.get_axis(5) + 1) / 2 * 255)
                    self._gp.left_trigger(value=l2)
                    self._gp.right_trigger(value=r2)

                self._gp.update()

            except Exception as e:
                _log.debug("Bridge error: %s", e)

            self._stop.wait(0.016)  # ~60Hz
