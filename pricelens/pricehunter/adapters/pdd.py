"""拼多多适配器。

说明：拼多多没有公开的网页搜索接口，移动端 API 需要 anti-content 签名参数，
因此默认仅保留接口占位；接入方式为在环境变量中提供第三方合规数据服务，
或自行实现签名后替换 fetch()。当前实现会抛出 AdapterError 触发降级。
"""

from __future__ import annotations

import os

from ..models import RawProduct
from .base import AdapterError, BaseAdapter


class PDDAdapter(BaseAdapter):
    key = "pdd"
    name = "拼多多"
    color = "#f472b6"

    def search(self, keyword: str, limit: int = 12) -> list[RawProduct]:
        endpoint = os.environ.get("PRICEHUNTER_PDD_ENDPOINT", "")
        if not endpoint:
            raise AdapterError("拼多多无公开搜索接口（需要 anti-content 签名），未配置数据服务")
        raise AdapterError(f"已配置数据服务 {endpoint}，但当前版本未实现其协议适配")
