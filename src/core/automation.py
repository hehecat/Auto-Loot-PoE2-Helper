"""可选自动按键：按计时器按下按键（药水/技能）。

默认关闭（automation.enabled=false）。仅在主开关激活（快捷键 toggle）
且（如设置）游戏窗口处于焦点时触发。
"""
import threading
import time

from pynput.keyboard import Controller

from ..input.keyboard import parse_key


class Automation(threading.Thread):
    def __init__(self, auto_cfg, is_active_fn, stop_event, log):
        super().__init__(daemon=True)
        self.enabled = bool(auto_cfg.get("enabled", False))
        self.only_fg = bool(auto_cfg.get("only_when_foreground", True))
        self.actions = [a for a in auto_cfg.get("actions", []) if a.get("enabled")]
        self.is_active_fn = is_active_fn  # -> (master_on: bool, foreground: bool)
        self.stop_event = stop_event
        self.log = log
        self._kb = Controller()
        self._next = {}

    def _press(self, key):
        k = parse_key(key)
        self._kb.press(k)
        self._kb.release(k)

    def run(self):
        if not self.enabled or not self.actions:
            return
        self.log.info("自动自动化已激活: %s",
                      ", ".join(f"{a['name']}({a['key']}/{a['interval_ms']}ms)" for a in self.actions))
        now = time.perf_counter()
        for a in self.actions:
            self._next[a["name"]] = now + a["interval_ms"] / 1000.0

        while not self.stop_event.is_set():
            master_on, foreground = self.is_active_fn()
            if master_on and (foreground or not self.only_fg):
                t = time.perf_counter()
                for a in self.actions:
                    if t >= self._next[a["name"]]:
                        self._press(a["key"])
                        self._next[a["name"]] = t + a["interval_ms"] / 1000.0
            self.stop_event.wait(timeout=0.05)
