"""京东搜索页适配器（搜索列表 + 价格接口 p.3.cn）。"""

from __future__ import annotations

import re
import urllib.parse

from ..models import RawProduct
from .base import AdapterError, BaseAdapter, http_get, http_get_json

ITEM_BLOCK = re.compile(r'<li[^>]+class="gl-item".*?</li>', re.S)
SKU = re.compile(r'data-sku="(\d+)"')
TITLE = re.compile(r'<div class="p-name[^"]*">.*?<em>(.*?)</em>', re.S)
SHOP = re.compile(r'<div class="p-shop"[^>]*>.*?<a[^>]*>(.*?)</a>', re.S)
COMMIT = re.compile(r'<div class="p-commit"[^>]*>.*?<a[^>]*>(.*?)</a>', re.S)
TAG = re.compile(r"<[^>]+>")


def _clean(html: str) -> str:
    return re.sub(r"\s+", " ", TAG.sub("", html)).strip()


class JDAdapter(BaseAdapter):
    key = "jd"
    name = "京东"
    color = "#ef4444"

    def search(self, keyword: str, limit: int = 12) -> list[RawProduct]:
        params = urllib.parse.urlencode({"keyword": keyword, "enc": "utf-8", "page": 1})
        url = f"https://search.jd.com/Search?{params}"
        html = http_get(url, referer="https://www.jd.com/")

        blocks = ITEM_BLOCK.findall(html)
        if not blocks:
            if "验证" in html or "login" in html.lower():
                raise AdapterError("触发京东安全验证，需要人工 Cookie")
            raise AdapterError("未解析到商品列表（页面结构可能已变更）")

        items: list[dict] = []
        for block in blocks[: limit * 2]:
            sku_match = SKU.search(block)
            title_match = TITLE.search(block)
            if not (sku_match and title_match):
                continue
            items.append({
                "sku": sku_match.group(1),
                "title": _clean(title_match.group(1)),
                "shop": _clean(SHOP.search(block).group(1)) if SHOP.search(block) else "京东商家",
                "sales": _clean(COMMIT.search(block).group(1)) if COMMIT.search(block) else "",
            })
            if len(items) >= limit:
                break

        if not items:
            raise AdapterError("商品条目解析失败")

        prices: dict[str, float] = {}
        sku_ids = ",".join(f"J_{item['sku']}" for item in items)
        try:
            payload = http_get_json(
                f"https://p.3.cn/prices/mgets?skuIds={sku_ids}&type=1",
                referer=url,
            )
            for row in payload:
                prices[str(row.get("id", "")).replace("J_", "")] = float(row.get("p", 0) or 0)
        except Exception:
            prices = {}

        results: list[RawProduct] = []
        for item in items:
            price = prices.get(item["sku"])
            if not price:
                continue
            results.append(RawProduct(
                platform=self.key,
                platform_name=self.name,
                sku_id=item["sku"],
                title=item["title"],
                price_raw=price,
                sales_raw=item["sales"],
                rating_raw=None,
                shop=item["shop"],
                url=f"https://item.jd.com/{item['sku']}.html",
                source="live",
            ))
        if not results:
            raise AdapterError("价格接口未返回有效数据")
        return results
