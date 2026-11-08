"""演示网页构建：把模板 + CSS + JS + 示例数据打包成单文件 index.html。"""

from __future__ import annotations

import json
from pathlib import Path

from .pipeline import run

WEB_DIR = Path(__file__).resolve().parent / "web"
SAMPLE_FILE = WEB_DIR / "sample.json"
INDEX_FILE = WEB_DIR / "index.html"


def build_page(sample: dict | None = None) -> Path:
    template = (WEB_DIR / "template.html").read_text(encoding="utf-8")
    css = (WEB_DIR / "app.css").read_text(encoding="utf-8")
    js = (WEB_DIR / "app.js").read_text(encoding="utf-8")
    data = sample if sample is not None else load_sample()

    page = (
        template
        .replace("/*__CSS__*/", css)
        .replace("//__JS__", js)
        .replace("__SAMPLE_JSON__", json.dumps(data, ensure_ascii=False, default=str))
    )
    INDEX_FILE.write_text(page, encoding="utf-8")
    return INDEX_FILE


def load_sample() -> dict:
    if SAMPLE_FILE.exists():
        try:
            return json.loads(SAMPLE_FILE.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            pass
    return {}


def ensure_sample(keyword: str = "机械键盘") -> dict:
    sample = load_sample()
    if sample.get("products"):
        return sample
    sample = run(keyword=keyword, limit=12, source="simulated")
    SAMPLE_FILE.write_text(json.dumps(sample, ensure_ascii=False, default=str), encoding="utf-8")
    return sample


def ensure_page() -> Path:
    if not INDEX_FILE.exists():
        ensure_sample()
        build_page()
    return INDEX_FILE
