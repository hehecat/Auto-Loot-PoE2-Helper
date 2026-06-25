"""收集并显示会话期间的拾取统计数据。

收集每次拾取的数据，计算汇总并输出仪表盘到控制台或文件。
"""
import csv
import time
from collections import defaultdict
from pathlib import Path

_DEBUG_DIR = Path(__file__).resolve().parents[2] / "_debug"


class SessionStats:
    """当前会话的统计信息。"""

    def __init__(self):
        self.start_time = time.time()
        self.picks = []  # [(timestamp, category, x, y)]
        self.by_category = defaultdict(int)
        self.by_minute = defaultdict(int)
        self.total = 0

    def record(self, category, x=0, y=0):
        """记录一次拾取。"""
        now = time.time()
        self.picks.append((now, category, x, y))
        self.by_category[category] += 1
        minute_key = int((now - self.start_time) / 60)
        self.by_minute[minute_key] += 1
        self.total += 1

    @property
    def elapsed(self):
        """已用时间（秒）。"""
        return time.time() - self.start_time

    @property
    def picks_per_minute(self):
        """平均拾取速度（每分钟物品数）。"""
        minutes = self.elapsed / 60
        if minutes < 0.1:
            return 0
        return self.total / minutes

    def summary(self):
        """简要汇总。"""
        lines = [
            f"=== 会话: {self._fmt_time(self.elapsed)} ===",
            f"总计拾取: {self.total}",
            f"速度: {self.picks_per_minute:.1f} 件/分钟",
            "",
            "按分类:",
        ]
        for cat, count in sorted(self.by_category.items(), key=lambda x: -x[1]):
            pct = count / self.total * 100 if self.total else 0
            lines.append(f"  {cat:15s} {count:5d} ({pct:.0f}%)")
        return "\n".join(lines)

    def save_csv(self, path=None):
        """将详细日志保存为 CSV。"""
        if path is None:
            _DEBUG_DIR.mkdir(parents=True, exist_ok=True)
            date_str = time.strftime("%Y%m%d_%H%M%S")
            path = _DEBUG_DIR / f"session_{date_str}.csv"

        with open(path, "w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow(["time", "elapsed_s", "category", "x", "y"])
            for ts, cat, x, y in self.picks:
                writer.writerow([
                    time.strftime("%H:%M:%S", time.localtime(ts)),
                    f"{ts - self.start_time:.1f}",
                    cat, x, y,
                ])
        return path

    def _fmt_time(self, seconds):
        h = int(seconds // 3600)
        m = int((seconds % 3600) // 60)
        s = int(seconds % 60)
        if h > 0:
            return f"{h}时{m}分{s}秒"
        elif m > 0:
            return f"{m}分{s}秒"
        return f"{s}秒"


class StatsCollector:
    """全局统计收集器（单例）。"""
    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._session = None
        return cls._instance

    def start_session(self):
        self._session = SessionStats()
        return self._session

    @property
    def session(self):
        if self._session is None:
            self.start_session()
        return self._session

    def record(self, category, x=0, y=0):
        self.session.record(category, x, y)

    def end_session(self):
        """结束会话并保存 CSV。"""
        if self._session and self._session.total > 0:
            path = self._session.save_csv()
            return self._session.summary(), path
        return "会话无数据。", None
