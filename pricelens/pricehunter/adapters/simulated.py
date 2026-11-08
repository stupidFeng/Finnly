"""模拟数据源：在无网络 / 反爬拦截时提供结构真实、可用于演示的采集结果。

- 价格 / 销量 / 评分按平台特性生成（拼多多最低、京东自营偏高、淘宝居中）
- 90 天价格历史带促销窗口，用于趋势图与「是否好价」判断
- 固定种子：同一关键词多次运行结果稳定，便于演示与回归
"""

from __future__ import annotations

import hashlib
import math
import random
import zlib
from datetime import date, timedelta

from ..models import RawProduct
from .base import BaseAdapter

PLATFORMS = ("jd", "tb", "pdd")

PLATFORM_META = {
    "jd": {"name": "京东", "color": "#ef4444"},
    "tb": {"name": "淘宝", "color": "#f59e0b"},
    "pdd": {"name": "拼多多", "color": "#f472b6"},
}

# (品牌, 型号, 规格, 基准价)
CATALOGS: dict[str, list[tuple[str, str, str, float]]] = {
    "机械键盘": [
        ("Keychron", "K8 Pro", "87键 蓝牙双模 热插拔 Gasket", 499),
        ("Keychron", "Q1 Pro", "75键 全铝 CNC 旋钮", 1299),
        ("Logitech", "G913", "TKL 无线 矮轴 RGB", 1299),
        ("Logitech", "K845", "104键 有线 机械", 399),
        ("Razer", "黑寡妇 V4 X", "104键 绿轴 RGB", 799),
        ("达尔优", "A87 Pro", "87键 三模 热插拔", 299),
        ("CHERRY", "MX3.0S", "108键 有线 樱桃轴", 499),
        ("珂芝", "K75", "75键 三模 客制化", 299),
        ("黑爵", "AKP815", "75键 三模 屏显", 399),
        ("狼蛛", "F87", "87键 三模 热插拔", 199),
        ("RK", "R87", "87键 有线 侧刻", 129),
        ("贱驴", "R2", "75键 三模 铝坨坨", 269),
        ("CORSAIR", "K70 RGB", "104键 有线 银轴", 999),
        ("杜伽", "K320", "87键 有线 白光", 599),
        ("瓦尔基里", "VK87", "87键 三模 电竞", 299),
    ],
    "无线耳机": [
        ("Apple", "AirPods Pro 2", "入耳式 主动降噪", 1899),
        ("Sony", "WF-1000XM5", "入耳式 降噪", 1899),
        ("HUAWEI", "FreeBuds Pro 3", "入耳式 星闪", 1499),
        ("Xiaomi", "Buds 5 Pro", "入耳式 双单元", 699),
        ("漫步者", "NeoBuds Pro 2", "入耳式 圈铁", 699),
        ("soundcore", "Liberty 4 NC", "入耳式 降噪", 499),
        ("OPPO", "Enco X3", "入耳式 丹拿调音", 999),
        ("vivo", "TWS 4", "入耳式 Hi-Fi", 499),
        ("Baseus", "M2s", "半入耳 蓝牙5.4", 249),
        ("QCY", "HT05", "入耳式 降噪", 199),
        ("Samsung", "Buds3 Pro", "入耳式 降噪", 1299),
        ("JBL", "TUNE Beam", "入耳式 长续航", 599),
    ],
    "空气炸锅": [
        ("美的", "KZ30E201", "3L 家用 可视", 199),
        ("苏泊尔", "KD35D71", "3.5L 免翻面", 269),
        ("九阳", "KL35-N71", "3.5L 蒸汽", 259),
        ("Xiaomi", "米家空气炸锅", "3.5L 智能", 199),
        ("Philips", "HD9252", "4.1L 旋风", 699),
        ("利仁", "KZ-J3001", "3L 机械", 179),
        ("Panasonic", "NF-HC150", "4L 双层", 599),
        ("BRUNO", "BZK-KZ03", "3.5L 复古", 499),
    ],
}

CATEGORY_ALIASES = [
    ("机械键盘", "机械键盘"),
    ("键盘", "机械键盘"),
    ("耳机", "无线耳机"),
    ("耳塞", "无线耳机"),
    ("airpods", "无线耳机"),
    ("空气炸锅", "空气炸锅"),
    ("炸锅", "空气炸锅"),
]

GENERIC_BRANDS = ["Aurora", "NOVA", "Lumi", "Kasa", "Zeno", "Orbit", "Mii", "Halo", "Veva"]
GENERIC_SPECS = ["标准版", "升级款", "Pro 版", "2026 新款", "旗舰款", "轻享版", "套装版"]


def _seed(*parts: str, platform: str = "") -> int:
    raw = "|".join(parts) + "|" + platform
    return zlib.crc32(raw.encode("utf-8"))


def _base_catalog(keyword: str) -> list[tuple[str, str, str, float]]:
    lowered = keyword.lower()
    for alias, category in CATEGORY_ALIASES:
        if alias in lowered:
            return CATALOGS[category]

    rng = random.Random(_seed(keyword, "generic"))
    rows: list[tuple[str, str, str, float]] = []
    for _ in range(11):
        brand = rng.choice(GENERIC_BRANDS)
        model = f"{rng.choice('SKXAZ')}{rng.randint(2, 99)}"
        if rng.random() < 0.4:
            model += " Pro"
        spec = rng.choice(GENERIC_SPECS)
        base = round(rng.uniform(69, 1299), 0) - 0.01
        rows.append((brand, model, spec, float(base)))
    return rows


def _price_factor(platform: str, rng: random.Random) -> float:
    if platform == "pdd":
        return rng.uniform(0.84, 0.97)
    if platform == "tb":
        return rng.uniform(0.93, 1.05)
    return rng.uniform(1.0, 1.08)


def _sales(platform: str, rng: random.Random) -> int:
    span = {"jd": (2.4, 4.6), "tb": (2.2, 4.5), "pdd": (3.0, 5.1)}[platform]
    return int(10 ** rng.uniform(*span))


def _make_history(rng: random.Random, price: float, days: int = 90) -> list[tuple[str, float]]:
    today = date.today()
    promos = [(20, 26, 0.88), (56, 62, 0.85), (78, 82, 0.93)]
    series: list[tuple[str, float]] = []
    for i in range(days):
        day = today - timedelta(days=days - 1 - i)
        factor = 1.0
        for start, end, discount in promos:
            if start <= i <= end:
                factor *= discount
        factor *= 1 + 0.012 * math.sin(i / 6.5) + rng.uniform(-0.008, 0.008)
        series.append((day.isoformat(), round(price * factor, 2)))
    series[-1] = (series[-1][0], round(price, 2))
    return series


class SimulatedAdapter(BaseAdapter):
    def __init__(self, platform: str):
        meta = PLATFORM_META[platform]
        self.key = platform
        self.name = meta["name"]
        self.color = meta["color"]

    def search(self, keyword: str, limit: int = 12) -> list[RawProduct]:
        rows = _base_catalog(keyword)
        results: list[RawProduct] = []

        for brand, model, spec, base in rows:
            rng = random.Random(_seed(keyword, brand, model, platform=self.key))
            available = rng.random() < (0.82 if self.key == "pdd" else 0.9)
            if not available:
                continue

            price = base * _price_factor(self.key, rng)
            price = round(price, 2) if price < 100 else round(price) - 0.01
            sales = _sales(self.key, rng)
            rating = round(rng.uniform(4.3, 5.0), 1)
            sku_no = 100000000 + (_seed(brand, model) % 89999999)

            decorations = {
                "jd": f"【官方旗舰】{brand} {model} {keyword} {spec} 京东自营",
                "tb": f"{brand} {model} {keyword} {spec} 官方正品 包邮",
                "pdd": f"{brand} {model} {keyword} {spec} 百亿补贴 正品保障",
            }
            coupons = ["", "", "满300减30", "满500减50", "满1000减100"]
            shops = {
                "jd": f"{brand}京东自营旗舰店" if rng.random() < 0.5 else f"{brand}官方旗舰店",
                "tb": f"{brand}官方旗舰店" if rng.random() < 0.6 else f"{brand}数码专营店",
                "pdd": f"{brand}官方旗舰店",
            }

            results.append(RawProduct(
                platform=self.key,
                platform_name=self.name,
                sku_id=str(sku_no),
                title=decorations[self.key],
                price_raw=price,
                list_price_raw=round(base * rng.uniform(1.15, 1.32), 2),
                sales_raw=f"{sales}人付款",
                rating_raw=rating,
                shop=shops[self.key],
                url={
                    "jd": f"https://item.jd.com/{sku_no}.html",
                    "tb": f"https://item.taobao.com/item.htm?id={600000000000 + sku_no}",
                    "pdd": f"https://mobile.yangkeduo.com/goods.html?goods_id={300000000000 + sku_no}",
                }[self.key],
                coupon=rng.choice(coupons),
                source="simulated",
                history=_make_history(rng, price),
            ))

        # 制造一条重复条目，用于验证「同平台同 SKU 去重」链路
        if results and len(results) > 2:
            clone = results[1]
            results.append(RawProduct(
                platform=clone.platform,
                platform_name=clone.platform_name,
                sku_id=clone.sku_id,
                title=clone.title + " 限时秒杀",
                price_raw=round(clone.price_raw * 0.99, 2),
                sales_raw=clone.sales_raw,
                rating_raw=clone.rating_raw,
                shop=clone.shop,
                url=clone.url,
                source="simulated",
                history=clone.history,
            ))

        return results[:limit + 1]
