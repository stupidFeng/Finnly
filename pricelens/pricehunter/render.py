"""静态 HTML 报告生成：纯 Python 输出内联 SVG 图表，零外部依赖、可离线打开。"""

from __future__ import annotations

import html
import json
import math
from typing import Any

CSS = """
:root{
  --bg:#0a0d12;--panel:#10151d;--panel2:#151b26;--line:#1f2836;
  --text:#e6edf3;--muted:#8b98ab;--accent:#34d399;--amber:#fbbf24;--rose:#fb7185;
}
*{box-sizing:border-box;margin:0;padding:0}
body{background:var(--bg);color:var(--text);font-family:-apple-system,BlinkMacSystemFont,"Segoe UI","PingFang SC","Hiragino Sans GB","Microsoft YaHei",sans-serif;
  line-height:1.6;padding:40px 32px 72px;background-image:radial-gradient(900px 420px at 12% -10%,rgba(52,211,153,.10),transparent 60%),radial-gradient(700px 380px at 100% 0,rgba(251,191,36,.07),transparent 60%);}
.wrap{max-width:1180px;margin:0 auto}
.num{font-family:ui-monospace,SFMono-Regular,Menlo,Consolas,monospace;font-variant-numeric:tabular-nums}
.brand{display:flex;align-items:center;gap:10px;font-size:13px;letter-spacing:.18em;color:var(--muted);text-transform:uppercase}
.dot{width:8px;height:8px;border-radius:50%;background:var(--accent);box-shadow:0 0 12px var(--accent)}
h1{font-size:38px;letter-spacing:-.02em;margin:14px 0 8px;font-weight:650}
.sub{color:var(--muted);font-size:13px}
.chips{display:flex;flex-wrap:wrap;gap:10px;margin-top:22px}
.chip{background:var(--panel);border:1px solid var(--line);border-radius:10px;padding:10px 14px;min-width:118px}
.chip span{display:block;font-size:11px;color:var(--muted);letter-spacing:.06em}
.chip b{font-size:19px;font-weight:600}
section{margin-top:44px}
h2{font-size:14px;letter-spacing:.16em;color:var(--muted);text-transform:uppercase;font-weight:600;display:flex;align-items:center;gap:10px}
h2:after{content:"";flex:1;height:1px;background:linear-gradient(90deg,var(--line),transparent)}
.panel{background:linear-gradient(180deg,var(--panel2),var(--panel));border:1px solid var(--line);border-radius:16px;padding:18px 20px;margin-top:16px;overflow:hidden}
.recs{display:grid;grid-template-columns:repeat(auto-fit,minmax(240px,1fr));gap:14px;margin-top:16px}
.rec{background:linear-gradient(180deg,var(--panel2),var(--panel));border:1px solid var(--line);border-radius:14px;padding:16px}
.rec .tag{display:inline-block;font-size:11px;padding:2px 8px;border-radius:999px;border:1px solid rgba(52,211,153,.35);color:var(--accent);margin-bottom:10px}
.rec h3{font-size:15px;font-weight:600;margin-bottom:6px;line-height:1.4}
.rec .price{font-size:22px;font-weight:700;color:var(--accent);margin:8px 0}
.rec p{font-size:12.5px;color:var(--muted);line-height:1.65}
table{width:100%;border-collapse:collapse;font-size:13px;margin-top:14px}
th,td{padding:9px 10px;text-align:left;border-bottom:1px solid var(--line);vertical-align:middle}
th{font-size:11px;color:var(--muted);letter-spacing:.08em;text-transform:uppercase;font-weight:600}
tbody tr:hover{background:rgba(255,255,255,.025)}
td.title{max-width:420px}
.mono{color:var(--muted);font-size:11.5px}
.pill{display:inline-block;padding:1px 8px;border-radius:999px;font-size:11px;border:1px solid}
.p-jd{color:#ef4444;border-color:rgba(239,68,68,.35);background:rgba(239,68,68,.08)}
.p-tb{color:#f59e0b;border-color:rgba(245,158,11,.35);background:rgba(245,158,11,.08)}
.p-pdd{color:#f472b6;border-color:rgba(244,114,182,.35);background:rgba(244,114,182,.08)}
.tag{display:inline-block;font-size:10.5px;padding:1px 6px;border-radius:5px;background:rgba(52,211,153,.10);color:#6ee7b7;margin-right:4px}
.tag.warn{background:rgba(251,113,133,.12);color:#fda4af}
.bar{height:5px;border-radius:3px;background:rgba(255,255,255,.08);overflow:hidden;margin-top:5px;width:78px}
.bar i{display:block;height:100%;background:linear-gradient(90deg,#34d399,#a7f3d0)}
a{color:inherit;text-decoration:none;border-bottom:1px dashed rgba(255,255,255,.18)}
a:hover{color:var(--accent);border-color:var(--accent)}
.groups{display:grid;grid-template-columns:repeat(auto-fit,minmax(330px,1fr));gap:14px;margin-top:16px}
.group{background:linear-gradient(180deg,var(--panel2),var(--panel));border:1px solid var(--line);border-radius:14px;padding:15px}
.group h4{font-size:13.5px;font-weight:600;margin-bottom:2px}
.grow{display:flex;align-items:center;justify-content:space-between;padding:7px 0;border-bottom:1px dashed rgba(255,255,255,.06);font-size:12.5px}
.grow:last-child{border-bottom:none}
.grow.best .gp{color:var(--accent);font-weight:700}
.geo{color:var(--muted);font-size:11.5px}
pre{background:#0b1016;border:1px solid var(--line);border-radius:12px;padding:14px;font-size:11.5px;color:#9fb3c8;overflow:auto;max-height:280px;margin-top:12px;line-height:1.6}
.note{font-size:12px;color:var(--muted);margin-top:10px;line-height:1.75}
footer{margin-top:56px;padding-top:18px;border-top:1px solid var(--line);color:#5b6879;font-size:11.5px;display:flex;justify-content:space-between;flex-wrap:wrap;gap:8px}
@media(max-width:720px){body{padding:24px 16px 48px}h1{font-size:28px}td.title{max-width:220px}}
"""

PALETTE = ["#34d399", "#60a5fa", "#fbbf24", "#f472b6", "#a78bfa", "#22d3ee"]

SOURCE_LABEL = {
    "auto": "自动（真实优先，失败降级）",
    "live": "真实抓取",
    "simulated": "模拟数据源",
}


def esc(value: Any) -> str:
    return html.escape(str(value))


def money(value: float) -> str:
    return f"¥{value:,.0f}" if value >= 100 else f"¥{value:,.2f}"


def _line_chart(dates: list[str], series: list[dict], width: int = 900, height: int = 320) -> str:
    if not dates or not series:
        return "<p class='note'>暂无趋势数据</p>"
    left, right, top, bottom = 60, 206, 18, 34
    plot_w, plot_h = width - left - right, height - top - bottom
    values = [v for item in series for v in item["values"]]
    low, high = min(values), max(values)
    pad = (high - low) * 0.1 or max(high * 0.05, 1)
    low, high = max(0.0, low - pad), high + pad
    n = len(dates)

    def px(i: int) -> float:
        return left + plot_w * i / max(n - 1, 1)

    def py(value: float) -> float:
        return top + plot_h * (1 - (value - low) / (high - low))

    parts = [f"<svg viewBox='0 0 {width} {height}' width='100%' role='img'>"]
    parts.append("<defs><linearGradient id='fade' x1='0' y1='0' x2='0' y2='1'>"
                 "<stop offset='0' stop-color='#34d399' stop-opacity='.18'/>"
                 "<stop offset='1' stop-color='#34d399' stop-opacity='0'/></linearGradient></defs>")

    for step in range(5):
        value = low + (high - low) * step / 4
        y = py(value)
        parts.append(f"<line x1='{left}' y1='{y:.1f}' x2='{left + plot_w}' y2='{y:.1f}' stroke='#1f2836' stroke-width='1'/>")
        parts.append(f"<text x='{left - 10}' y='{y + 4:.1f}' fill='#64748b' font-size='10' text-anchor='end' "
                     f"font-family='ui-monospace,monospace'>{value:,.0f}</text>")

    for index in (0, n // 3, n * 2 // 3, n - 1):
        if 0 <= index < n:
            parts.append(f"<text x='{px(index):.1f}' y='{height - 12}' fill='#64748b' font-size='10' "
                         f"text-anchor='middle' font-family='ui-monospace,monospace'>{dates[index][5:]}</text>")

    for order, item in enumerate(series):
        color = PALETTE[order % len(PALETTE)]
        points = " ".join(f"{px(i):.1f},{py(v):.1f}" for i, v in enumerate(item["values"]))
        parts.append(f"<polyline points='{points}' fill='none' stroke='{color}' stroke-width='2' "
                     f"stroke-linejoin='round' stroke-linecap='round' opacity='.92'/>")
        parts.append(f"<circle cx='{px(n - 1):.1f}' cy='{py(item['values'][-1]):.1f}' r='3.4' fill='{color}'/>")
        ly = 40 + order * 24
        parts.append(f"<rect x='{width - right + 14}' y='{ly - 8}' width='9' height='9' rx='2' fill='{color}'/>")
        label = esc(item["name"])[:11]
        parts.append(f"<text x='{width - right + 30}' y='{ly}' fill='#9fb3c8' font-size='10.5' "
                     f"font-family='ui-monospace,monospace'>{label} ¥{item['current']:,.0f}</text>")

    parts.append("</svg>")
    return "".join(parts)


def _platform_bars(stats: list[dict], width: int = 900, height: int = 218) -> str:
    if not stats:
        return ""
    left, top, bar_h, gap, right_col = 92, 20, 26, 32, 214
    usable = width - left - right_col
    max_price = max(item["avg_price"] for item in stats) or 1
    parts = [f"<svg viewBox='0 0 {width} {height}' width='100%' role='img'>"]
    for index, item in enumerate(stats):
        y = top + index * (bar_h + gap)
        w = usable * item["avg_price"] / max_price
        parts.append(f"<text x='{left - 14}' y='{y + bar_h * 0.7:.0f}' fill='#9fb3c8' font-size='12' "
                     f"text-anchor='end'>{esc(item['name'])}</text>")
        parts.append(f"<rect x='{left}' y='{y}' width='{usable}' height='{bar_h}' rx='7' fill='#141b26'/>")
        parts.append(f"<rect x='{left}' y='{y}' width='{max(w, 4):.1f}' height='{bar_h}' rx='7' "
                     f"fill='{item['color']}' opacity='.78'/>")
        parts.append(f"<text x='{left + usable + 16}' y='{y + 12:.0f}' fill='#e6edf3' font-size='13' "
                     f"font-family='ui-monospace,monospace'>{money(item['avg_price'])}</text>")
        parts.append(f"<text x='{left + usable + 16}' y='{y + 25:.0f}' fill='#64748b' font-size='10' "
                     f"font-family='ui-monospace,monospace'>{item['count']} 件 · 均销 {item['avg_sales']:,}</text>")
    parts.append("</svg>")
    return "".join(parts)


def _scatter(products: list[dict], width: int = 900, height: int = 300) -> str:
    if not products:
        return ""
    left, right, top, bottom = 62, 26, 18, 38
    plot_w, plot_h = width - left - right, height - top - bottom
    prices = [item["price"] for item in products]
    sales = [math.log10(item["sales"] + 10) for item in products]
    p_min, p_max = min(prices), max(prices)
    s_min, s_max = min(sales), max(sales)
    p_min, p_max = p_min - (p_max - p_min) * 0.06 - 1, p_max + (p_max - p_min) * 0.06 + 1
    s_max += 0.15

    colors = {"jd": "#ef4444", "tb": "#f59e0b", "pdd": "#f472b6"}
    parts = [f"<svg viewBox='0 0 {width} {height}' width='100%' role='img'>"]

    for step in range(5):
        price = p_min + (p_max - p_min) * step / 4
        x = left + plot_w * (price - p_min) / (p_max - p_min)
        parts.append(f"<line x1='{x:.1f}' y1='{top}' x2='{x:.1f}' y2='{top + plot_h}' stroke='#1f2836'/>")
        parts.append(f"<text x='{x:.1f}' y='{height - 14}' fill='#64748b' font-size='10' text-anchor='middle' "
                     f"font-family='ui-monospace,monospace'>{price:,.0f}</text>")
    for step in range(4):
        value = s_min + (s_max - s_min) * step / 3
        y = top + plot_h * (1 - (value - s_min) / (s_max - s_min))
        parts.append(f"<line x1='{left}' y1='{y:.1f}' x2='{left + plot_w}' y2='{y:.1f}' stroke='#1f2836'/>")
        parts.append(f"<text x='{left - 10}' y='{y + 4:.1f}' fill='#64748b' font-size='10' text-anchor='end' "
                     f"font-family='ui-monospace,monospace'>{10 ** value:,.0f}</text>")

    for item in products:
        x = left + plot_w * (item["price"] - p_min) / (p_max - p_min)
        value = math.log10(item["sales"] + 10)
        y = top + plot_h * (1 - (value - s_min) / (s_max - s_min))
        radius = 4 + (item["rating"] or 4.3) * 1.15
        color = colors.get(item["platform"], "#94a3b8")
        parts.append(f"<circle cx='{x:.1f}' cy='{y:.1f}' r='{radius:.1f}' fill='{color}' opacity='.34'/>"
                     f"<circle cx='{x:.1f}' cy='{y:.1f}' r='2.4' fill='{color}'/>")

    parts.append(f"<text x='{left + plot_w / 2}' y='{height - 1}' fill='#475569' font-size='10' "
                 f"text-anchor='middle'>价格 →</text>")
    parts.append("</svg>")
    return "".join(parts)


def render_report(payload: dict[str, Any]) -> str:
    stats = payload["stats"]
    products = payload["products"]
    groups = [group for group in payload["groups"] if group["count"] > 1][:8]
    recs = payload["recommendations"]
    raw_pre = esc(json.dumps(payload.get("raw_sample", [])[:3], ensure_ascii=False, indent=2))

    rec_html = "".join(
        f"<article class='rec'><span class='tag'>{esc(rec['label'])}</span>"
        f"<h3>{esc(rec['title'])}</h3>"
        f"<div class='mono'>[{esc(rec['platform_name'])}] {esc(rec['label'])} 推荐</div>"
        f"<div class='price num'>{money(rec['price'])}</div>"
        f"<p>{esc(rec['reason'])}</p></article>"
        for rec in recs
    )

    group_html = "".join(
        "<article class='group'>"
        f"<h4>{esc(group['title'])}</h4>"
        f"<div class='geo'>{esc(group['brand'])} {esc(group['model'])} · "
        f"{group['platform_count']} 平台 / {group['count']} 条报价 · 价差 {group['spread_pct']}%</div>"
        + "".join(
            f"<div class='grow{' best' if row['id'] == group['cheapest_id'] else ''}'>"
            f"<span><span class='pill p-{row['platform']}'>{esc(row['platform_name'])}</span> "
            f"<span class='geo'>{esc(row['shop'])[:16]}</span></span>"
            f"<span class='gp num'>{money(row['price'])}</span></div>"
            for row in group["items"]
        )
        + "</article>"
        for group in groups
    )

    rows: list[str] = []
    for index, item in enumerate(products, start=1):
        tags = "".join(f"<span class='tag{' warn' if '异常' in tag else ''}'>{esc(tag)}</span>" for tag in item["tags"])
        flags = "".join(f"<span class='tag warn'>{esc(flag)}</span>" for flag in item["flags"])
        rows.append(
            "<tr>"
            f"<td class='num mono'>{index:02d}</td>"
            f"<td><span class='pill p-{item['platform']}'>{esc(item['platform_name'])}</span></td>"
            f"<td class='title'><a href='{esc(item['url'])}' target='_blank' rel='noopener'>{esc(item['title_clean'][:52])}</a>"
            f"<div class='mono'>{esc(item['brand'])} {esc(item['model'])} · {esc(item['shop'])[:24]}</div></td>"
            f"<td class='num' style='font-size:15px;font-weight:600'>{money(item['price'])}</td>"
            f"<td class='num'>{item['sales']:,}</td>"
            f"<td class='num'>{item['rating'] if item['rating'] is not None else '—'}</td>"
            f"<td><span class='num'>{item['value_index']}</span><div class='bar'><i style='width:{item['value_index']}%'></i></div></td>"
            f"<td>{tags}{flags}</td>"
            "</tr>"
        )

    return f"""<!DOCTYPE html>
<html lang="zh-CN"><head><meta charset="utf-8"/>
<meta name="viewport" content="width=device-width,initial-scale=1"/>
<title>PriceLens 报告 · {esc(payload['keyword'])}</title>
<style>{CSS}</style></head>
<body><div class="wrap">
  <div class="brand"><span class="dot"></span>PriceLens 价镜 · 价格监测报告</div>
  <h1>「{esc(payload['keyword'])}」全网比价</h1>
  <div class="sub">采集时间 {esc(payload['generated_at'])} · 数据来源 {esc(SOURCE_LABEL.get(payload.get('source', 'auto'), payload.get('source', 'auto')))} ·
    商品 {stats['unique']} 条 · 去重 {stats['removed']} 条 · 耗时 {payload.get('elapsed_ms', 0)} ms</div>

  <div class="chips">
    <div class="chip"><span>最低价</span><b class="num" style="color:var(--accent)">{money(stats['min_price'])}</b></div>
    <div class="chip"><span>中位价</span><b class="num">{money(stats['median_price'])}</b></div>
    <div class="chip"><span>同款分组</span><b class="num">{stats['groups']}</b></div>
    <div class="chip"><span>覆盖平台</span><b class="num">{stats['platforms']}</b></div>
    <div class="chip"><span>总销量</span><b class="num">{stats['total_sales']:,}</b></div>
    <div class="chip"><span>最高性价比</span><b class="num" style="color:var(--amber)">{stats['best_value']}</b></div>
  </div>

  <section><h2>性价比推荐</h2><div class="recs">{rec_html}</div></section>

  <section><h2>价格趋势 · 近 90 天</h2>
    <div class="panel">{_line_chart(payload['trend']['dates'], payload['trend']['series'])}
      <p class="note">曲线取每个同款分组中性价比最高的报价；历史价格缺失时按商品价格走势模型补全（estimated）。</p>
    </div>
  </section>

  <section><h2>平台均价对比</h2><div class="panel">{_platform_bars(payload['platform_stats'])}</div></section>

  <section><h2>价格 × 销量分布</h2>
    <div class="panel">{_scatter(products)}
      <p class="note">横轴为价格，纵轴为销量（对数刻度），气泡大小对应店铺评分；左上区域通常意味着「低价高销」。</p>
    </div>
  </section>

  <section><h2>同款横向对比</h2><div class="groups">{group_html}</div></section>

  <section><h2>商品明细（按价格升序）</h2>
    <div class="panel" style="padding:6px 18px 14px">
      <table><thead><tr><th>#</th><th>平台</th><th>商品</th><th>价格</th><th>销量</th><th>评分</th>
      <th>性价比</th><th>标签</th></tr></thead><tbody>{''.join(rows)}</tbody></table>
    </div>
  </section>

  <section><h2>原始采集数据示例</h2>
    <div class="panel"><pre>{raw_pre}</pre>
      <p class="note">原始记录保留平台返回的文本形态，进入清洗层后再统一解析为数值型字段，便于复用与审计。</p>
    </div>
  </section>

  <footer><span>PriceLens 价镜 v1.0 · 仅供个人学习与价格监测</span>
    <span>CLI: python -m pricehunter search "{esc(payload['keyword'])}"</span></footer>
</div></body></html>"""
