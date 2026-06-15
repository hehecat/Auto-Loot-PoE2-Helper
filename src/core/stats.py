"""Сбор и отображение статистики подбора за сессию.

Собирает данные о каждом подборе, считает итоги и выводит дашборд
в консоль или в файл.
"""
import csv
import time
from collections import defaultdict
from pathlib import Path

_DEBUG_DIR = Path(__file__).resolve().parents[2] / "_debug"


class SessionStats:
    """Статистика текущей сессии."""

    def __init__(self):
        self.start_time = time.time()
        self.picks = []  # [(timestamp, category, x, y)]
        self.by_category = defaultdict(int)
        self.by_minute = defaultdict(int)
        self.total = 0

    def record(self, category, x=0, y=0):
        """Записать подбор."""
        now = time.time()
        self.picks.append((now, category, x, y))
        self.by_category[category] += 1
        minute_key = int((now - self.start_time) / 60)
        self.by_minute[minute_key] += 1
        self.total += 1

    @property
    def elapsed(self):
        """Прошедшее время в секундах."""
        return time.time() - self.start_time

    @property
    def picks_per_minute(self):
        """Средняя скорость подбора (предметов в минуту)."""
        minutes = self.elapsed / 60
        if minutes < 0.1:
            return 0
        return self.total / minutes

    def summary(self):
        """Краткая сводка."""
        lines = [
            f"=== Сессия: {self._fmt_time(self.elapsed)} ===",
            f"Всего подобрано: {self.total}",
            f"Скорость: {self.picks_per_minute:.1f} предм/мин",
            "",
            "По категориям:",
        ]
        for cat, count in sorted(self.by_category.items(), key=lambda x: -x[1]):
            pct = count / self.total * 100 if self.total else 0
            lines.append(f"  {cat:15s} {count:5d} ({pct:.0f}%)")
        return "\n".join(lines)

    def save_csv(self, path=None):
        """Сохранить детальный лог в CSV."""
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
            return f"{h}ч {m}мин {s}сек"
        elif m > 0:
            return f"{m}мин {s}сек"
        return f"{s}сек"


class StatsCollector:
    """Глобальный сборщик статистики (синглтон)."""
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
        """Завершить сессию и сохранить CSV."""
        if self._session and self._session.total > 0:
            path = self._session.save_csv()
            return self._session.summary(), path
        return "Нет данных за сессию.", None
