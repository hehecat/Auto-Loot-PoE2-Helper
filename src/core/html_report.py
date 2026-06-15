"""Генерация HTML-отчёта статистики сессии.

Создаёт красивый HTML-файл с графиками и таблицами
после завершения сессии подбора.
"""
import json
import time
from pathlib import Path
from collections import defaultdict

_DEBUG_DIR = Path(__file__).resolve().parents[2] / "_debug"


def _fmt_time(seconds):
    h = int(seconds // 3600)
    m = int((seconds % 3600) // 60)
    s = int(seconds % 60)
    if h > 0:
        return f"{h}ч {m}мин {s}сек"
    elif m > 0:
        return f"{m}мин {s}сек"
    return f"{s}сек"


def generate_html_report(session_stats, output_path=None):
    """Создать HTML-отчёт из SessionStats.

    Возвращает путь к файлу.
    """
    if output_path is None:
        _DEBUG_DIR.mkdir(parents=True, exist_ok=True)
        date_str = time.strftime("%Y%m%d_%H%M%S")
        output_path = _DEBUG_DIR / f"report_{date_str}.html"

    total = session_stats.total
    elapsed = session_stats.elapsed
    ppm = session_stats.picks_per_minute

    cat_data = []
    for cat, count in sorted(session_stats.by_category.items(), key=lambda x: -x[1]):
        pct = count / total * 100 if total else 0
        cat_data.append({"name": cat, "count": count, "pct": round(pct, 1)})

    minute_data = []
    for minute in sorted(session_stats.by_minute.keys()):
        minute_data.append({"minute": minute, "count": session_stats.by_minute[minute]})

    html = f"""<!DOCTYPE html>
<html lang="ru">
<head>
<meta charset="UTF-8">
<title>Auto Loot — Отчёт сессии</title>
<style>
body {{ font-family: 'Segoe UI', Tahoma, sans-serif; background: #1a1a2e; color: #e0e0e0; margin: 40px; }}
h1 {{ color: #00ff88; border-bottom: 2px solid #00ff88; padding-bottom: 10px; }}
.stats {{ display: grid; grid-template-columns: repeat(4, 1fr); gap: 20px; margin: 20px 0; }}
.stat {{ background: #16213e; padding: 20px; border-radius: 10px; text-align: center; }}
.stat-value {{ font-size: 2em; color: #00ff88; font-weight: bold; }}
.stat-label {{ color: #9fb3c8; margin-top: 5px; }}
table {{ width: 100%; border-collapse: collapse; margin: 20px 0; }}
th {{ background: #16213e; padding: 12px; text-align: left; border-bottom: 2px solid #00ff88; }}
td {{ padding: 10px 12px; border-bottom: 1px solid #2a2a4a; }}
tr:hover {{ background: #16213e; }}
.bar {{ height: 20px; background: #00ff88; border-radius: 4px; display: inline-block; min-width: 4px; }}
.chart {{ background: #16213e; padding: 20px; border-radius: 10px; margin: 20px 0; }}
.footer {{ color: #555; margin-top: 40px; text-align: center; font-size: 0.9em; }}
</style>
</head>
<body>
<h1>Auto Loot PoE2 Helper — Отчёт сессии</h1>

<div class="stats">
  <div class="stat">
    <div class="stat-value">{total}</div>
    <div class="stat-label">Всего подобрано</div>
  </div>
  <div class="stat">
    <div class="stat-value">{_fmt_time(elapsed)}</div>
    <div class="stat-label">Длительность</div>
  </div>
  <div class="stat">
    <div class="stat-value">{ppm:.1f}</div>
    <div class="stat-label">Предм/мин</div>
  </div>
  <div class="stat">
    <div class="stat-value">{len(cat_data)}</div>
    <div class="stat-label">Категорий</div>
  </div>
</div>

<h2>По категориям</h2>
<table>
<tr><th>Категория</th><th>Количество</th><th>Доля</th><th></th></tr>
"""

    for cat in cat_data:
        bar_width = max(4, int(cat["pct"] * 3))
        html += f"""<tr>
  <td>{cat['name']}</td>
  <td>{cat['count']}</td>
  <td>{cat['pct']}%</td>
  <td><div class="bar" style="width:{bar_width}px"></div></td>
</tr>
"""

    html += "</table>"

    if minute_data:
        max_count = max(d["count"] for d in minute_data)
        html += """
<h2>Активность по минутам</h2>
<div class="chart" style="display:flex; align-items:flex-end; height:200px; gap:2px;">
"""
        for d in minute_data:
            bar_h = int(d["count"] / max(max_count, 1) * 180)
            html += f'<div style="flex:1; background:#00ff88; height:{bar_h}px; border-radius:2px;" title="мин {d["minute"]}: {d["count"]}"></div>\n'
        html += "</div>\n"

    html += f"""
<div class="footer">
  Auto Loot PoE2 Helper — {time.strftime("%Y-%m-%d %H:%M:%S")}
</div>
</body>
</html>"""

    output_path = Path(output_path)
    output_path.write_text(html, encoding="utf-8")
    return str(output_path)
