"""Хелперы для разбора строковых хоткеев из конфига в объекты pynput и их сравнения."""
from pynput import keyboard


def parse_key(spec):
    """'f8' -> Key.f8, 'space' -> Key.space, 'q' -> KeyCode('q')."""
    s = str(spec).lower()
    special = getattr(keyboard.Key, s, None)
    if special is not None:
        return special
    return keyboard.KeyCode.from_char(s)


def key_matches(event_key, target):
    """Совпадает ли клавиша из listener (Key/KeyCode) с распарсенным target."""
    if isinstance(target, keyboard.Key):
        return event_key == target
    return getattr(event_key, "char", None) == getattr(target, "char", None)
