"""将拾取记录记录到 CSV 文件以进行统计分析。

格式：timestamp、category、x、y、screen_x、screen_y
文件：_debug/pickup_log_<date>.csv（每天一个文件）
"""
import csv
import os
import time
from pathlib import Path

_LOG_DIR = Path(__file__).resolve().parents[2] / "_debug"


class PickupLogger:
    def __init__(self, enabled=True):
        self.enabled = enabled
        self._file = None
        self._writer = None
        self._date = None

    def log(self, category, x, y, screen_x=0, screen_y=0):
        if not self.enabled:
            return
        today = time.strftime("%Y-%m-%d")
        if self._date != today:
            self._open(today)

        try:
            self._writer.writerow([
                time.strftime("%H:%M:%S"),
                category, x, y, screen_x, screen_y,
            ])
            self._file.flush()
        except Exception:
            pass

    def _open(self, date_str):
        if self._file:
            try:
                self._file.close()
            except Exception:
                pass
        _LOG_DIR.mkdir(parents=True, exist_ok=True)
        path = _LOG_DIR / f"pickup_log_{date_str}.csv"
        is_new = not path.exists()
        self._file = open(path, "a", newline="", encoding="utf-8")
        self._writer = csv.writer(self._file)
        if is_new:
            self._writer.writerow(["time", "category", "x", "y", "screen_x", "screen_y"])
        self._date = date_str

    def close(self):
        if self._file:
            try:
                self._file.close()
            except Exception:
                pass
            self._file = None
