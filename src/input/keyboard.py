"""辅助工具：将配置中的字符串快捷键解析为 pynput 对象并进行比较。

支持组合键："ctrl+space"、"alt+f8"、"shift+q" 等。
"""
from pynput import keyboard


def parse_key(spec):
    """'f8' -> Key.f8, 'space' -> Key.space, 'q' -> KeyCode('q'), 'ctrl+space' -> (Key.ctrl_l, Key.space)."""
    s = str(spec).lower()
    if "+" in s:
        parts = [parse_key(p.strip()) for p in s.split("+")]
        return tuple(parts)
    special = getattr(keyboard.Key, s, None)
    if special is not None:
        return special
    return keyboard.KeyCode.from_char(s)


def _is_modifier(key):
    """如果按键是修饰键（ctrl、alt、shift、win）则返回 True。"""
    return key in (
        keyboard.Key.ctrl_l, keyboard.Key.ctrl_r,
        keyboard.Key.alt_l, keyboard.Key.alt_r,
        keyboard.Key.shift, keyboard.Key.shift_r,
        keyboard.Key.cmd, keyboard.Key.cmd_r,
    )


class ComboTracker:
    """跟踪按下的修饰键以验证组合键。"""

    def __init__(self):
        self._pressed = set()

    def on_press(self, key):
        self._pressed.add(key)

    def on_release(self, key):
        self._pressed.discard(key)

    def check(self, combo):
        """检查组合键中的所有按键是否同时按下。"""
        if not isinstance(combo, tuple):
            return False
        return all(k in self._pressed for k in combo)


def key_matches(event_key, target):
    """检查 listener 中的按键（Key/KeyCode）是否与解析后的 target 匹配。"""
    if isinstance(target, tuple):
        return False
    if isinstance(target, keyboard.Key):
        return event_key == target
    return getattr(event_key, "char", None) == getattr(target, "char", None)
