"""适配器注册表 + 采集调度（真实抓取失败时按策略降级）。"""

from __future__ import annotations

import time
from typing import Any

from ..models import RawProduct
from .base import AdapterError, BaseAdapter
from .jd import JDAdapter
from .pdd import PDDAdapter
from .simulated import PLATFORM_META, SimulatedAdapter
from .taobao import TaobaoAdapter

LIVE_ADAPTERS: dict[str, type[BaseAdapter]] = {
    "jd": JDAdapter,
    "tb": TaobaoAdapter,
    "pdd": PDDAdapter,
}

PLATFORM_NAMES = {key: meta["name"] for key, meta in PLATFORM_META.items()}
PLATFORM_COLORS = {key: meta["color"] for key, meta in PLATFORM_META.items()}
ALL_PLATFORMS = tuple(PLATFORM_META.keys())


def _log(logs: list[dict[str, Any]], text: str, level: str = "info") -> None:
    logs.append({"text": text, "level": level})


def collect(
    keyword: str,
    platforms: tuple[str, ...] = ALL_PLATFORMS,
    limit: int = 12,
    source: str = "auto",
) -> tuple[list[RawProduct], list[dict[str, Any]]]:
    """按平台并发/顺序采集。source: auto（真实优先，失败降级）| live | simulated。"""
    logs: list[dict[str, Any]] = []
    results: list[RawProduct] = []

    for platform in platforms:
        if platform not in PLATFORM_META:
            _log(logs, f"未知平台 {platform}，已跳过", "warn")
            continue

        name = PLATFORM_NAMES[platform]
        started = time.perf_counter()
        if source in ("auto", "live"):
            _log(logs, f"[{name}] 尝试真实抓取：search?keyword={keyword}")
            try:
                rows = LIVE_ADAPTERS[platform]().search(keyword, limit)
                results.extend(rows)
                cost = (time.perf_counter() - started) * 1000
                _log(logs, f"[{name}] 抓取成功 {len(rows)} 条（{cost:.0f} ms）", "ok")
                continue
            except AdapterError as exc:
                if source == "live":
                    _log(logs, f"[{name}] 抓取失败：{exc}", "error")
                    continue
                _log(logs, f"[{name}] 抓取失败：{exc} → 降级为模拟数据源", "warn")

        rows = SimulatedAdapter(platform).search(keyword, limit)
        results.extend(rows)
        cost = (time.perf_counter() - started) * 1000
        _log(logs, f"[{name}] 模拟数据源返回 {len(rows)} 条（{cost:.0f} ms）", "ok")

    return results, logs
