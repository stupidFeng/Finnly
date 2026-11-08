"""采集流水线编排：采集 → 清洗 → 去重 → 分析 → 落盘。"""

from __future__ import annotations

import csv
import json
import re
import time
from pathlib import Path
from typing import Any

from .adapters import ALL_PLATFORMS, collect
from .analyze import analyze
from .normalize import dedupe, normalize
from .render import render_report

ROOT = Path(__file__).resolve().parent.parent
OUT_DIR = ROOT / "out"


def _safe_name(keyword: str) -> str:
    return re.sub(r"[^\w\u4e00-\u9fff-]+", "_", keyword).strip("_") or "query"


def run(
    keyword: str,
    platforms: tuple[str, ...] = ALL_PLATFORMS,
    limit: int = 12,
    source: str = "auto",
    out_dir: Path | None = None,
    write: bool = True,
) -> dict[str, Any]:
    started = time.perf_counter()
    out_dir = Path(out_dir) if out_dir else OUT_DIR

    raw_rows, logs = collect(keyword, platforms=platforms, limit=limit, source=source)

    normalized: list[dict[str, Any]] = []
    invalid = 0
    for row in raw_rows:
        product = normalize(row)
        if product is None:
            invalid += 1
        else:
            normalized.append(product)

    products, drop_stats = dedupe(normalized)
    drop_stats["invalid"] = invalid

    payload = analyze(
        keyword,
        products,
        raw_count=len(raw_rows),
        drop_stats=drop_stats,
        logs=logs,
    )
    payload["source"] = source
    payload["platforms_requested"] = list(platforms)
    payload["raw_sample"] = [row.to_dict() for row in raw_rows[:6]]
    payload["normalized_sample"] = [
        {
            "id": item["id"],
            "platform": item["platform"],
            "title_clean": item["title_clean"],
            "price": item["price"],
            "sales": item["sales"],
            "rating": item["rating"],
            "brand": item["brand"],
            "model": item["model"],
            "group_id": item["group_id"],
        }
        for item in products[:6]
    ]

    artifacts: dict[str, str] = {}
    payload["elapsed_ms"] = round((time.perf_counter() - started) * 1000)

    if write and products:
        out_dir.mkdir(parents=True, exist_ok=True)
        stamp = time.strftime("%Y%m%d_%H%M%S")
        base = f"{_safe_name(keyword)}_{stamp}"
        payload_dir = out_dir.name if out_dir.name else "out"
        artifacts = {
            "json": f"{payload_dir}/{base}.json",
            "csv": f"{payload_dir}/{base}.csv",
            "html": f"{payload_dir}/{base}.html",
        }
        payload["artifacts"] = artifacts
        payload["report_url"] = f"/{artifacts['html']}"

        json_path = out_dir / f"{base}.json"
        json_path.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8"
        )

        csv_path = out_dir / f"{base}.csv"
        with csv_path.open("w", encoding="utf-8-sig", newline="") as handle:
            writer = csv.writer(handle)
            writer.writerow(["排名", "平台", "商品", "品牌", "型号", "价格", "销量", "店铺评分",
                             "性价比指数", "店铺", "标签", "链接"])
            for index, item in enumerate(payload["products"], start=1):
                writer.writerow([
                    index, item["platform_name"], item["title"], item["brand"], item["model"],
                    item["price"], item["sales"], item["rating"] or "",
                    item["value_index"], item["shop"], " / ".join(item["tags"]), item["url"],
                ])

        html_path = out_dir / f"{base}.html"
        html_path.write_text(render_report(payload), encoding="utf-8")

    payload["artifacts"] = artifacts
    logs.append({
        "text": f"全流程耗时 {payload['elapsed_ms']} ms，产出 {len(artifacts)} 个文件",
        "level": "ok",
    })
    payload["logs"] = logs
    return payload
