from pynput import keyboard as kb

from src.input.keyboard import key_matches, parse_key


def test_parse_key():
    assert parse_key("f12") == kb.Key.f12
    assert parse_key("space") == kb.Key.space
    assert parse_key("q") == kb.KeyCode.from_char("q")


def test_key_matches():
    assert key_matches(kb.Key.f8, parse_key("f8"))
    assert not key_matches(kb.Key.f7, parse_key("f8"))
    assert key_matches(kb.KeyCode.from_char("a"), parse_key("a"))
    assert not key_matches(kb.KeyCode.from_char("a"), parse_key("b"))
