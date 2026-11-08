"""数据模型：各平台适配器统一输出的原始商品记录。"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class RawProduct:
    """适配器采集到的未清洗记录。价格/销量/评分保持原始文本，清洗阶段统一解析。"""

    platform: str                      # jd / tb / pdd
    platform_name: str                 # 京东 / 淘宝 / 拼多多
    sku_id: str
    title: str
    price_raw: Any                     # 可能是 "￥1,299.00" / "1299-1599" / 1299.0
    sales_raw: Any = None              # 可能是 "2.3万+人付款" / 23000
    rating_raw: Any = None             # 可能是 4.9 / "98%好评"
    shop: str = ""
    url: str = ""
    coupon: str = ""
    list_price_raw: Any = None
    source: str = "live"               # live = 真实抓取, simulated = 模拟数据源
    history: list[tuple[str, float]] | None = None   # [(YYYY-MM-DD, price)]
    extra: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "platform": self.platform,
            "platform_name": self.platform_name,
            "sku_id": self.sku_id,
            "title": self.title,
            "price": self.price_raw,
            "sales": self.sales_raw,
            "rating": self.rating_raw,
            "shop": self.shop,
            "url": self.url,
            "coupon": self.coupon,
            "list_price": self.list_price_raw,
            "source": self.source,
        }
