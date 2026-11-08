"""平台适配器基类与公共 HTTP 工具。"""

from __future__ import annotations

import gzip
import json
import urllib.error
import urllib.request
from typing import Any

from ..models import RawProduct

DEFAULT_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/125.0 Safari/537.36"
    ),
    "Accept-Language": "zh-CN,zh;q=0.9",
    "Accept-Encoding": "gzip",
}


class AdapterError(RuntimeError):
    """抓取失败（反爬拦截、需要登录、接口变更等），由上层决定是否降级。"""


class BaseAdapter:
    key: str = ""
    name: str = ""
    color: str = ""

    def search(self, keyword: str, limit: int = 12) -> list[RawProduct]:
        raise NotImplementedError


def http_get(url: str, timeout: float = 8.0, referer: str | None = None) -> str:
    headers = dict(DEFAULT_HEADERS)
    if referer:
        headers["Referer"] = referer
    request = urllib.request.Request(url, headers=headers)
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            body = response.read()
            if response.headers.get("Content-Encoding") == "gzip":
                body = gzip.decompress(body)
            return body.decode("utf-8", "ignore")
    except urllib.error.HTTPError as exc:
        raise AdapterError(f"HTTP {exc.code}") from exc
    except Exception as exc:  # 网络不可达 / 超时 / TLS 等
        raise AdapterError(type(exc).__name__) from exc


def http_get_json(url: str, timeout: float = 8.0, referer: str | None = None) -> Any:
    text = http_get(url, timeout=timeout, referer=referer)
    text = text.strip()
    if text.startswith("(") or text.startswith("jsonp"):
        text = text[text.find("(") + 1: text.rfind(")")]
    return json.loads(text)
