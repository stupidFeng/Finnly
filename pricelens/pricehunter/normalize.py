"""文本 / 价格 / 销量清洗与商品归一化、去重。"""

from __future__ import annotations

import hashlib
import re
import unicodedata
from typing import Any, Iterable

from .models import RawProduct

# ---------------------------------------------------------------- 基础解析

_PRICE_NUM = re.compile(r"\d+(?:\.\d+)?")
_SALES_NUM = re.compile(r"(\d+(?:\.\d+)?)\s*(万|w|W)?")

NOISE_PATTERNS = [
    r"【[^】]*】",
    r"\[[^\]]*\]",
    r"（[^）]*）",
    r"\([^)]*\)",
]

NOISE_WORDS = [
    "包邮", "顺丰", "官方正品", "正品保障", "正品保证", "正品险", "全国联保", "国行", "现货",
    "秒杀", "限时", "券后", "百亿补贴", "京东自营", "旗舰店", "自营", "新品", "送礼", "官方",
    "直营", "补贴", "特价", "清仓", "支持分期", "免息", "以旧换新", "官方授权", "正品", "精选",
    "hot", "new", "京东", "天猫", "淘宝", "拼多多",
]

# 常见品牌：别名 -> 规范名。用于同款归组，未命中的会退化为「首个拉丁词」。
BRANDS = {
    "keychron": "Keychron", "罗技": "Logitech", "logitech": "Logitech", "雷蛇": "Razer",
    "razer": "Razer", "达尔优": "达尔优", "樱桃": "CHERRY", "cherry": "CHERRY",
    "珂芝": "珂芝", "黑爵": "黑爵", "狼蛛": "狼蛛", "rk": "RK", "贱驴": "贱驴",
    "美商海盗船": "CORSAIR", "海盗船": "CORSAIR", "杜伽": "杜伽", "瓦尔基里": "瓦尔基里",
    "苹果": "Apple", "apple": "Apple", "airpods": "Apple", "索尼": "Sony", "sony": "Sony",
    "华为": "HUAWEI", "huawei": "HUAWEI", "小米": "Xiaomi", "xiaomi": "Xiaomi",
    "漫步者": "漫步者", "声阔": "soundcore", "soundcore": "soundcore", "oppo": "OPPO",
    "vivo": "vivo", "倍思": "Baseus", "baseus": "Baseus", "qcy": "QCY",
    "三星": "Samsung", "samsung": "Samsung", "jbl": "JBL", "美的": "美的",
    "苏泊尔": "苏泊尔", "九阳": "九阳", "飞利浦": "Philips", "philips": "Philips",
    "利仁": "利仁", "松下": "Panasonic", "panasonic": "Panasonic", "bruno": "BRUNO",
    "米家": "Xiaomi",
}

MODEL_PATTERN = re.compile(
    r"(?<![A-Za-z0-9])(?=[A-Za-z0-9.\-]*\d)[A-Za-z][A-Za-z0-9.\-]{1,12}(?![A-Za-z0-9])"
)
CAPACITY_PATTERN = re.compile(r"\d+(?:\.\d+)?\s*(?:L|ML|mAh|英寸|寸|键|W)\b", re.I)

STOP_TOKENS = {
    "pro", "max", "plus", "mini", "new", "the", "and", "for", "with", "gb", "tb",
}


def normalize_text(value: Any) -> str:
    """全角转半角、去零宽字符、压缩空白。"""
    if value is None:
        return ""
    text = unicodedata.normalize("NFKC", str(value))
    text = text.replace("\u200b", "").replace("\xa0", " ")
    return re.sub(r"\s+", " ", text).strip()


def parse_price(value: Any) -> float | None:
    """解析价格：支持 '￥1,299.00'、'1299-1599'、1299。区间取最低价。"""
    if value is None:
        return None
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return float(value) if value > 0 else None
    text = normalize_text(value).replace(",", "").replace("，", "")
    nums = [float(n) for n in _PRICE_NUM.findall(text)]
    if not nums:
        return None
    price = min(nums)
    return price if price > 0 else None


def parse_sales(value: Any) -> int:
    """解析销量：'2.3万+人付款' -> 23000。"""
    if value is None:
        return 0
    if isinstance(value, (int, float)):
        return max(0, int(value))
    text = normalize_text(value).replace(",", "").replace("，", "")
    match = _SALES_NUM.search(text)
    if not match:
        return 0
    num = float(match.group(1))
    if match.group(2):
        num *= 10000
    return max(0, int(round(num)))


def parse_rating(value: Any) -> float | None:
    """解析评分：支持 4.9 分制与 98% 好评率（按百分制折算五档）。"""
    if value is None:
        return None
    if isinstance(value, (int, float)):
        num = float(value)
    else:
        match = re.search(r"\d+(?:\.\d+)?", normalize_text(value))
        if not match:
            return None
        num = float(match.group(0))
    if 0 < num <= 5:
        return round(num, 2)
    if 5 < num <= 100:
        return round(num / 20, 2)
    return None


def strip_noise(title: str) -> str:
    text = normalize_text(title)
    for pattern in NOISE_PATTERNS:
        text = re.sub(pattern, " ", text)
    for word in NOISE_WORDS:
        text = re.sub(re.escape(word), " ", text, flags=re.IGNORECASE)
    text = re.sub(r"[|/·•]+", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def detect_brand(title: str) -> str:
    lower = title.lower()
    for alias, brand in BRANDS.items():
        if alias in lower:
            return brand
    latin = re.search(r"[A-Za-z][A-Za-z0-9]{1,14}", title)
    return latin.group(0).upper() if latin else ""


def detect_model(clean_title: str, brand: str) -> str:
    text = clean_title
    if brand:
        text = re.sub(re.escape(brand), " ", text, flags=re.IGNORECASE)

    for match in MODEL_PATTERN.finditer(text):
        token = match.group(0).strip(".-")
        if len(token) >= 2 and re.search(r"\d", token):
            return token.upper()

    capacity = CAPACITY_PATTERN.search(text)
    if capacity:
        return capacity.group(0).replace(" ", "").upper()

    words = [
        word for word in re.findall(r"[A-Za-z][A-Za-z0-9]{1,14}|\d{1,4}", text)
        if word.lower() not in STOP_TOKENS
    ]
    if words:
        parts = words[:2]
        if len(words) > 2 and words[2].isdigit() and len(words[2]) <= 2:
            parts.append(words[2])
        return " ".join(parts).upper()

    cjk = [part for part in text.split(" ") if re.search(r"[\u4e00-\u9fff]", part)]
    return cjk[0][:6] if cjk else ""


def tokenize(text: str) -> list[str]:
    """拉丁词 + 中文二元组，用于同款相似度计算。"""
    tokens: list[str] = []
    for word in re.findall(r"[A-Za-z0-9.\-]+", text.lower()):
        word = word.strip(".-")
        if len(word) >= 2 and word not in STOP_TOKENS:
            tokens.append(word)
    cjk = re.sub(r"[^\u4e00-\u9fff]", "", text)
    tokens.extend(cjk[i:i + 2] for i in range(len(cjk) - 1))
    return tokens


def jaccard(a: Iterable[str], b: Iterable[str]) -> float:
    sa, sb = set(a), set(b)
    if not sa or not sb:
        return 0.0
    return len(sa & sb) / len(sa | sb)


def make_id(platform: str, sku_id: str, title: str) -> str:
    if sku_id:
        return f"{platform}-{sku_id}"
    digest = hashlib.md5(f"{platform}|{title}".encode("utf-8")).hexdigest()[:10]
    return f"{platform}-{digest}"


# ---------------------------------------------------------------- 归一化

def normalize(raw: RawProduct) -> dict[str, Any] | None:
    """把原始记录转换为统一结构；价格非法直接丢弃。"""
    price = parse_price(raw.price_raw)
    if price is None:
        return None
    title = normalize_text(raw.title)
    clean = strip_noise(title)
    brand = detect_brand(clean or title)
    model = detect_model(clean or title, brand)
    list_price = parse_price(raw.list_price_raw)
    if list_price is not None and list_price <= price:
        list_price = None

    signature = tokenize(clean or title)
    group_key = f"{brand}|{model}" if brand and model else ""

    return {
        "id": make_id(raw.platform, raw.sku_id, title),
        "sku_id": raw.sku_id,
        "platform": raw.platform,
        "platform_name": raw.platform_name,
        "title": title,
        "title_clean": clean or title,
        "brand": brand,
        "model": model,
        "group_key": group_key,
        "price": round(price, 2),
        "list_price": round(list_price, 2) if list_price else None,
        "sales": parse_sales(raw.sales_raw),
        "rating": parse_rating(raw.rating_raw),
        "shop": normalize_text(raw.shop),
        "url": raw.url,
        "coupon": normalize_text(raw.coupon),
        "source": raw.source,
        "signature": signature,
        "history": [[d, round(float(p), 2)] for d, p in (raw.history or [])],
        "history_source": "observed" if raw.history else "estimated",
        "group_id": "",
        "value_index": 0.0,
        "tags": [],
        "flags": [],
    }


def dedupe(products: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], dict[str, int]]:
    """三重去重：平台内 SKU -> 平台内同款同价 -> 完全重复标题。"""
    stats = {"invalid": 0, "sku_dup": 0, "near_dup": 0}

    seen_sku: set[str] = set()
    seen_exact: set[tuple] = set()
    stage1: list[dict[str, Any]] = []
    for item in products:
        if item["id"] in seen_sku:
            stats["sku_dup"] += 1
            continue
        seen_sku.add(item["id"])
        stage1.append(item)

    stage2: list[dict[str, Any]] = []
    for item in stage1:
        key = (item["platform"], item["brand"], item["model"], round(item["price"], 2))
        if key in seen_exact and (item["brand"] or item["model"]):
            stats["near_dup"] += 1
            continue
        seen_exact.add(key)
        stage2.append(item)

    final: list[dict[str, Any]] = []
    for item in stage2:
        duplicate = None
        for kept in final:
            if kept["platform"] != item["platform"]:
                continue
            if (kept["brand"], kept["model"]) != (item["brand"], item["model"]):
                continue
            if abs(kept["price"] - item["price"]) / max(kept["price"], 1) > 0.02:
                continue
            if jaccard(kept["signature"], item["signature"]) < 0.7:
                continue
            duplicate = kept
            break
        if duplicate is None:
            final.append(item)
        else:
            stats["near_dup"] += 1
            if item["sales"] > duplicate["sales"]:
                final[final.index(duplicate)] = item

    return final, stats
