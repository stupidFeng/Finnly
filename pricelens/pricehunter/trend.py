"""价格趋势：缺失历史的确定性补全 + 趋势指标计算。"""

from __future__ import annotations

import hashlib
import math
import random
from datetime import date, timedelta


def synthesize_history(key: str, price: float, days: int = 90) -> list[list]:
    """为没有真实历史价的商品生成可复现的参考曲线（明确标记为 estimated）。"""
    seed = int(hashlib.md5(key.encode("utf-8")).hexdigest()[:12], 16)
    rng = random.Random(seed)
    today = date.today()
    promos = [(18, 24, 0.9), (52, 58, 0.87), (75, 79, 0.94)]
    series: list[list] = []
    for i in range(days):
        day = today - timedelta(days=days - 1 - i)
        factor = 1.0
        for start, end, discount in promos:
            if start <= i <= end:
                factor *= discount
        factor *= 1 + 0.01 * math.sin(i / 7) + rng.uniform(-0.006, 0.006)
        series.append([day.isoformat(), round(price * factor, 2)])
    series[-1][1] = round(price, 2)
    return series


def ensure_history(product: dict) -> None:
    if not product.get("history"):
        product["history"] = synthesize_history(product["id"], product["price"])
        product["history_source"] = "estimated"


def trend_metrics(product: dict) -> dict:
    history = product["history"]
    prices = [point[1] for point in history]
    current = prices[-1]
    low = min(prices)
    high = max(prices)
    avg30 = sum(prices[-30:]) / max(len(prices[-30:]), 1)
    base = prices[-31] if len(prices) > 30 else prices[0]
    change = (current - base) / base * 100 if base else 0.0
    vs_low = (current - low) / low * 100 if low else 0.0

    if current <= low * 1.01:
        signal = "历史低价"
    elif current <= avg30 * 0.97:
        signal = "好价"
    elif current <= avg30 * 1.03:
        signal = "正常"
    else:
        signal = "偏高"

    return {
        "current": round(current, 2),
        "low": round(low, 2),
        "high": round(high, 2),
        "avg30": round(avg30, 2),
        "change_30d": round(change, 2),
        "vs_low": round(vs_low, 2),
        "signal": signal,
    }
