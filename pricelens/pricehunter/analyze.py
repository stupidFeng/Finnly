"""分析层：同款归组、性价比评分、异常标记、推荐与图表数据。"""

from __future__ import annotations

import datetime
import math
import statistics
from typing import Any

from .adapters import PLATFORM_COLORS, PLATFORM_NAMES
from .trend import ensure_history, trend_metrics

WEIGHTS = {"price": 0.45, "sales": 0.30, "rating": 0.25}


def _percentile(values: list[float], value: float) -> float:
    if not values:
        return 0.5
    lower = sum(1 for item in values if item < value)
    equal = sum(1 for item in values if item == value)
    return (lower + 0.5 * equal) / len(values)


def _assign_groups(products: list[dict[str, Any]]) -> list[dict[str, Any]]:
    buckets: dict[str, list[dict[str, Any]]] = {}
    for item in products:
        key = item["group_key"] or f"solo::{item['id']}"
        buckets.setdefault(key, []).append(item)

    groups: list[dict[str, Any]] = []
    for key, items in buckets.items():
        items.sort(key=lambda row: row["price"])
        cheapest = items[0]
        prices = [row["price"] for row in items]
        platforms = sorted({row["platform"] for row in items})
        group_id = f"G{len(groups) + 1:02d}"
        for row in items:
            row["group_id"] = group_id

        representative = min(items, key=lambda row: len(row["title_clean"]))
        groups.append({
            "id": group_id,
            "key": key,
            "title": representative["title_clean"][:46],
            "brand": representative["brand"],
            "model": representative["model"],
            "count": len(items),
            "platform_count": len(platforms),
            "platforms": platforms,
            "min_price": round(min(prices), 2),
            "max_price": round(max(prices), 2),
            "avg_price": round(sum(prices) / len(prices), 2),
            "spread_pct": round((max(prices) - min(prices)) / min(prices) * 100, 1) if min(prices) else 0,
            "cheapest_id": cheapest["id"],
            "cheapest_platform": cheapest["platform"],
            "items": [
                {
                    "id": row["id"],
                    "platform": row["platform"],
                    "platform_name": row["platform_name"],
                    "price": row["price"],
                    "sales": row["sales"],
                    "rating": row["rating"],
                    "shop": row["shop"],
                    "url": row["url"],
                }
                for row in items
            ],
        })

    groups.sort(key=lambda group: group["min_price"])
    remap = {group["id"]: f"G{index:02d}" for index, group in enumerate(groups, start=1)}
    for group in groups:
        group["id"] = remap[group["id"]]
    for item in products:
        item["group_id"] = remap[item["group_id"]]
    return groups


def _score(products: list[dict[str, Any]]) -> None:
    prices = [item["price"] for item in products]
    log_sales = [math.log1p(item["sales"]) for item in products]
    ratings = [item["rating"] for item in products if item["rating"]]

    for item in products:
        price_score = 1 - _percentile(prices, item["price"])
        sales_score = _percentile(log_sales, math.log1p(item["sales"]))
        rating_score = _percentile(ratings, item["rating"]) if item["rating"] else 0.5
        item["score_detail"] = {
            "price": round(price_score * 100, 1),
            "sales": round(sales_score * 100, 1),
            "rating": round(rating_score * 100, 1),
        }
        item["value_index"] = round(
            100 * (
                WEIGHTS["price"] * price_score
                + WEIGHTS["sales"] * sales_score
                + WEIGHTS["rating"] * rating_score
            ),
            1,
        )


def _flag_outliers(products: list[dict[str, Any]], groups: list[dict[str, Any]]) -> None:
    for group in groups:
        items = [item for item in products if item["group_id"] == group["id"]]
        if len(items) < 3:
            continue
        median = statistics.median(item["price"] for item in items)
        deviations = [abs(item["price"] - median) for item in items]
        mad = statistics.median(deviations) or 1.0
        for item in items:
            if item["price"] < median * 0.6 and abs(item["price"] - median) / mad > 4:
                item["flags"].append("价格异常，疑似引流款")
        if len({item["platform"] for item in items}) == 1:
            group["note"] = "仅单平台有货"


def _tag(products: list[dict[str, Any]], groups: list[dict[str, Any]]) -> None:
    by_id = {item["id"]: item for item in products}
    top_sales = max(products, key=lambda item: item["sales"])["id"] if products else None

    for group in groups:
        items = sorted((by_id[row["id"]] for row in group["items"]), key=lambda item: item["price"])
        median = statistics.median(item["price"] for item in items)
        for item in items:
            if item["id"] == group["cheapest_id"] and group["platform_count"] > 1:
                item["tags"].append("同款最低价")
            if item["price"] <= median * 0.92 and group["count"] > 2:
                item["tags"].append("价格下探")
        best = max(items, key=lambda item: item["value_index"])
        if group["count"] > 1:
            best["tags"].append("同款性价比第一")

    for item in products:
        if item["id"] == top_sales:
            item["tags"].append("销量王")
        if item["rating"] and item["rating"] >= 4.9:
            item["tags"].append("口碑之选")
        if item["coupon"]:
            item["tags"].append("领券立减")
        if item["list_price"] and item["list_price"] > item["price"] * 1.08:
            item["tags"].append("折扣明显")

    for item in products:
        seen: list[str] = []
        for tag in item["tags"]:
            if tag not in seen:
                seen.append(tag)
        item["tags"] = seen[:3]


def _recommend(products: list[dict[str, Any]]) -> list[dict[str, Any]]:
    if not products:
        return []

    valid = [item for item in products if "价格异常，疑似引流款" not in item["flags"]]
    median_sales = statistics.median(item["sales"] for item in products)

    def pick(candidates: list[dict[str, Any]], key, *, exclude: set[str]) -> dict[str, Any] | None:
        for item in sorted(candidates, key=key, reverse=True):
            if item["id"] not in exclude:
                return item
        return None

    plans = [
        {
            "type": "sales",
            "label": "销量之选",
            "candidates": products,
            "key": lambda item: item["sales"],
            "reason": lambda item: (
                f"近 30 天销量 {item['sales']:,} 件，为同批最高，"
                f"市场验证充分，踩坑概率低。"
            ),
        },
        {
            "type": "value",
            "label": "性价比首选",
            "candidates": valid or products,
            "key": lambda item: item["value_index"],
            "reason": lambda item: (
                f"综合评分 {item['value_index']}（价格分 {item['score_detail']['price']}、"
                f"销量分 {item['score_detail']['sales']}、口碑分 {item['score_detail']['rating']}），"
                f"在同批商品中价格与销量最均衡。"
            ),
        },
        {
            "type": "budget",
            "label": "预算优选",
            "candidates": [item for item in products if item["sales"] >= median_sales] or products,
            "key": lambda item: -item["price"],
            "reason": lambda item: (
                f"到手价 ¥{item['price']:.2f}，是销量达标商品中的最低价，"
                f"较中位价低 {max(0, 100 - item['price'] / statistics.median(p['price'] for p in products) * 100):.0f}%。"
            ),
        },
        {
            "type": "quality",
            "label": "品质之选",
            "candidates": [item for item in products if item["rating"]] or products,
            "key": lambda item: (item["rating"] or 0) * 1000 + item["sales"] / 1e6,
            "reason": lambda item: (
                f"店铺评分 {item['rating']:.1f}，销量 {item['sales']:,} 件，"
                f"售后与口碑表现最好，适合看重长期体验的用户。"
            ),
        },
    ]

    chosen: set[str] = set()
    output: list[dict[str, Any]] = []
    for plan in plans:
        item = pick(plan["candidates"], plan["key"], exclude=chosen)
        if item is None:
            continue
        chosen.add(item["id"])
        output.append({
            "type": plan["type"],
            "label": plan["label"],
            "product_id": item["id"],
            "title": item["title_clean"][:40],
            "platform": item["platform"],
            "platform_name": item["platform_name"],
            "price": item["price"],
            "sales": item["sales"],
            "rating": item["rating"],
            "url": item["url"],
            "reason": plan["reason"](item),
        })
    order = {"value": 0, "budget": 1, "sales": 2, "quality": 3}
    output.sort(key=lambda rec: order.get(rec["type"], 9))
    return output


def analyze(
    keyword: str,
    products: list[dict[str, Any]],
    *,
    raw_count: int,
    drop_stats: dict[str, int],
    logs: list[dict[str, Any]],
) -> dict[str, Any]:
    for item in products:
        ensure_history(item)

    groups = _assign_groups(products)
    _score(products)
    _flag_outliers(products, groups)
    _tag(products, groups)

    for item in products:
        item["trend"] = trend_metrics(item)

    products.sort(key=lambda item: (item["price"], -item["value_index"]))

    platform_stats: list[dict[str, Any]] = []
    for key in ("jd", "tb", "pdd"):
        rows = [item for item in products if item["platform"] == key]
        if not rows:
            continue
        platform_stats.append({
            "key": key,
            "name": PLATFORM_NAMES[key],
            "color": PLATFORM_COLORS[key],
            "count": len(rows),
            "avg_price": round(sum(item["price"] for item in rows) / len(rows), 2),
            "min_price": round(min(item["price"] for item in rows), 2),
            "avg_sales": int(sum(item["sales"] for item in rows) / len(rows)),
            "avg_rating": round(
                sum(item["rating"] for item in rows if item["rating"])
                / max(1, sum(1 for item in rows if item["rating"])), 2,
            ),
        })

    prices = [item["price"] for item in products]
    top_value = sorted(products, key=lambda item: item["value_index"], reverse=True)
    trend_products: list[dict[str, Any]] = []
    seen_groups: set[str] = set()
    for item in top_value:
        if item["group_id"] in seen_groups:
            continue
        seen_groups.add(item["group_id"])
        trend_products.append(item)
        if len(trend_products) >= 5:
            break

    dates = [point[0] for point in trend_products[0]["history"]] if trend_products else []
    series = [
        {
            "id": item["id"],
            "name": f"{item['brand']} {item['model']}".strip() or item["title_clean"][:16],
            "title": item["title_clean"][:32],
            "platform": item["platform"],
            "platform_name": item["platform_name"],
            "color": PLATFORM_COLORS[item["platform"]],
            "values": [point[1] for point in item["history"]],
            **item["trend"],
        }
        for item in trend_products
    ]

    recommendations = _recommend(products)

    logs.append({"text": f"清洗完成：原始 {raw_count} 条，有效 {len(products)} 条", "level": "info"})
    logs.append({
        "text": (
            f"去重：SKU 重复 {drop_stats.get('sku_dup', 0)} 条、"
            f"近似重复 {drop_stats.get('near_dup', 0)} 条、"
            f"价格无效 {drop_stats.get('invalid', 0)} 条"
        ),
        "level": "info",
    })
    logs.append({"text": f"聚合出 {len(groups)} 个同款分组，覆盖 {len(platform_stats)} 个平台", "level": "info"})
    logs.append({"text": "性价比评分：价格 45% + 销量 30% + 评分 25%", "level": "info"})

    return {
        "keyword": keyword,
        "generated_at": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "stats": {
            "raw": raw_count,
            "unique": len(products),
            "removed": max(0, raw_count - len(products)),
            "groups": len(groups),
            "platforms": len(platform_stats),
            "min_price": round(min(prices), 2) if prices else 0,
            "max_price": round(max(prices), 2) if prices else 0,
            "median_price": round(statistics.median(prices), 2) if prices else 0,
            "avg_price": round(sum(prices) / len(prices), 2) if prices else 0,
            "total_sales": sum(item["sales"] for item in products),
            "best_value": round(max(item["value_index"] for item in products), 1) if products else 0,
        },
        "platform_stats": platform_stats,
        "products": products,
        "groups": groups,
        "trend": {"dates": dates, "series": series},
        "recommendations": recommendations,
    }
