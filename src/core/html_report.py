"""生成会话统计的 HTML 报告。

在拾取会话结束后创建包含图表和表格的精美 HTML 文件。
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
        return f"{h}时{m}分{s}秒"
    elif m > 0:
        return f"{m}分{s}秒"
    return f"{s}秒"


def generate_html_report(session_stats, output_path=None):
    """从 SessionStats 创建 HTML 报告。

    返回文件路径。
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
<html lang="zh">
<head>
<meta charset="UTF-8">
<title>自动拾取 — 会话报告</title>
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
<h1>自动拾取 PoE2 助手 — 会话报告</h1>

<div class="stats">
  <div class="stat">
    <div class="stat-value">{total}</div>
    <div class="stat-label">总计拾取</div>
  </div>
  <div class="stat">
    <div class="stat-value">{_fmt_time(elapsed)}</div>
    <div class="stat-label">持续时间</div>
  </div>
  <div class="stat">
    <div class="stat-value">{ppm:.1f}</div>
    <div class="stat-label">件/分钟</div>
  </div>
  <div class="stat">
    <div class="stat-value">{len(cat_data)}</div>
    <div class="stat-label">分类数</div>
  </div>
</div>

<h2>按分类</h2>
<table>
<tr><th>分类</th><th>数量</th><th>占比</th><th></th></tr>
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
<h2>每分钟活动</h2>
<div class="chart" style="display:flex; align-items:flex-end; height:200px; gap:2px;">
"""
        for d in minute_data:
            bar_h = int(d["count"] / max(max_count, 1) * 180)
            html += f'<div style="flex:1; background:#00ff88; height:{bar_h}px; border-radius:2px;" title="第{d["minute"]}分钟: {d["count"]}"></div>\n'
        html += "</div>\n"

    html += f"""
<div class="footer">
  自动拾取 PoE2 助手 — {time.strftime("%Y-%m-%d %H:%M:%S")}
</div>
</body>
</html>"""

    output_path = Path(output_path)
    output_path.write_text(html, encoding="utf-8")
    return str(output_path)
