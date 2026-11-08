"""淘宝搜索适配器。

说明：淘宝搜索接口需要登录态 Cookie + 风控签名，未提供 Cookie 时会直接判定不可用，
由上层降级到模拟数据源（保持整条流水线可演示）。
"""

from __future__ import annotations

import json
import os
import re
import urllib.parse

from ..models import RawProduct
from .base import AdapterError, BaseAdapter, http_get


class TaobaoAdapter(BaseAdapter):
    key = "tb"
    name = "淘宝"
    color = "#f59e0b"

    def search(self, keyword: str, limit: int = 12) -> list[RawProduct]:
        cookie = os.environ.get("PRICEHUNTER_TAOBAO_COOKIE", "")
        if not cookie:
            raise AdapterError("未配置 PRICEHUNTER_TAOBAO_COOKIE，淘宝搜索需要登录态")

        params = urllib.parse.urlencode({"q": keyword, "s": 0})
        url = f"https://s.taobao.com/search?{params}"
        html = http_get(url, referer="https://www.taobao.com/")
        if "亲，请登录" in html or "login" in html.lower():
            raise AdapterError("登录态失效")

        match = re.search(r"g_page_config\s*=\s*(\{.*?\});", html, re.S)
        if not match:
            raise AdapterError("未找到 g_page_config，页面结构可能已变更")
        try:
            config = json.loads(match.group(1))
            auctions = config["mods"]["itemlist"]["data"]["auctions"]
        except Exception as exc:
            raise AdapterError("搜索 JSON 结构解析失败") from exc

        results: list[RawProduct] = []
        for item in auctions[:limit]:
            price = item.get("view_price") or item.get("price")
            if not price:
                continue
            results.append(RawProduct(
                platform=self.key,
                platform_name=self.name,
                sku_id=str(item.get("nid", "")),
                title=item.get("raw_title") or item.get("title", ""),
                price_raw=price,
                sales_raw=item.get("view_sales", ""),
                rating_raw=None,
                shop=item.get("nick", ""),
                url=f"https://item.taobao.com/item.htm?id={item.get('nid', '')}",
                source="live",
            ))
        if not results:
            raise AdapterError("搜索结果为空")
        return results
