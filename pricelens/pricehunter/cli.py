"""命令行入口：search / serve / build-demo。"""

from __future__ import annotations

import argparse
import json
import sys
import unicodedata
import webbrowser
from pathlib import Path

from . import __version__
from .adapters import ALL_PLATFORMS
from .build import SAMPLE_FILE, build_page
from .pipeline import OUT_DIR, run


def _width(text: str) -> int:
    return sum(2 if unicodedata.east_asian_width(ch) in "WF" else 1 for ch in str(text))


def _clip(text: str, width: int) -> str:
    out = ""
    for ch in str(text):
        if _width(out) + _width(ch) > width:
            return out + "…"
        out += ch
    return out


def _pad(text: str, width: int) -> str:
    return text + " " * max(0, width - _width(text))


def print_table(payload: dict) -> None:
    stats = payload["stats"]
    print(f"\n关键词「{payload['keyword']}」 · 原始 {stats['raw']} 条 → 有效 {stats['unique']} 条 "
          f"· 去重 {stats['removed']} 条 · 同款 {stats['groups']} 组 "
          f"· 最低价 ¥{stats['min_price']:.2f} · 耗时 {payload['elapsed_ms']} ms\n")

    header = (f"{_pad('#', 4)}{_pad('平台', 7)}{_pad('商品', 40)}{_pad('价格', 11)}"
              f"{_pad('销量', 10)}{_pad('评分', 7)}{_pad('性价比', 8)}标签")
    print(header)
    print("─" * 108)
    for index, item in enumerate(payload["products"], start=1):
        price = f"¥{item['price']:,.2f}"
        sales = f"{item['sales']:,}"
        rating = f"{item['rating']:.1f}" if item["rating"] else "—"
        tags = " ".join(item["tags"][:2])
        print(
            f"{index:<4}{_pad(item['platform_name'], 7)}{_pad(_clip(item['title_clean'], 38), 40)}"
            f"{_pad(price, 11)}{_pad(sales, 10)}{_pad(rating, 7)}"
            f"{_pad(str(item['value_index']), 8)}{tags}"
        )

    if payload["recommendations"]:
        print("\n推荐：")
        for rec in payload["recommendations"]:
            print(f"  · {rec['label']}：{_clip(rec['title'], 34)} [{rec['platform_name']}] "
                  f"¥{rec['price']:.2f} — {rec['reason']}")

    if payload.get("artifacts"):
        print("\n产出文件：")
        for kind, path in payload["artifacts"].items():
            print(f"  {kind.upper():<5}{Path(path).resolve()}")


def cmd_search(args: argparse.Namespace) -> int:
    platforms = tuple(p.strip() for p in args.platforms.split(",") if p.strip())
    invalid = [p for p in platforms if p not in ALL_PLATFORMS]
    if invalid:
        print(f"未知平台：{', '.join(invalid)}（可选：{', '.join(ALL_PLATFORMS)}）", file=sys.stderr)
        return 2

    payload = run(
        keyword=args.keyword,
        platforms=platforms or ALL_PLATFORMS,
        limit=args.limit,
        source=args.source,
        out_dir=Path(args.out) if args.out else OUT_DIR,
        write=True,
    )

    if args.verbose:
        for line in payload["logs"]:
            print(f"[{line['level']:<5}] {line['text']}")

    if not payload["products"]:
        print("未采集到商品：真实抓取全部失败，且当前 --source 不允许降级。"
              "可改用 --source auto（默认）或 --source simulated 重试。", file=sys.stderr)
        return 1

    print_table(payload)

    if "json" in args.format:
        print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0


def cmd_serve(args: argparse.Namespace) -> int:
    from .server import serve

    if args.open:
        import threading
        threading.Timer(1.0, lambda: webbrowser.open(f"http://{args.host}:{args.port}")).start()
    serve(args.host, args.port)
    return 0


def cmd_build_demo(args: argparse.Namespace) -> int:
    sample = run(keyword=args.keyword, limit=args.limit, source="simulated")
    SAMPLE_FILE.write_text(json.dumps(sample, ensure_ascii=False, default=str), encoding="utf-8")
    page = build_page(sample)
    print(f"示例数据：{SAMPLE_FILE}")
    print(f"演示页面：{page}")
    print(f"示例报告：{sample.get('artifacts', {}).get('html', '—')}")
    print(f"\n启动交互演示：python -m pricehunter serve --open")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="pricehunter",
        description="PriceLens 价镜 —— 电商商品价格自动化采集与对比工具",
    )
    parser.add_argument("--version", action="version", version=f"PriceLens {__version__}")
    sub = parser.add_subparsers(dest="command", required=True)

    search = sub.add_parser("search", help="采集并分析指定关键词")
    search.add_argument("keyword", help="搜索关键词，如「机械键盘」")
    search.add_argument("--platforms", default="jd,tb,pdd", help="平台，逗号分隔：jd,tb,pdd")
    search.add_argument("--limit", type=int, default=12, help="单平台采集条数（默认 12）")
    search.add_argument("--source", choices=["auto", "live", "simulated"], default="auto",
                        help="auto=真实优先并降级；live=仅真实；simulated=仅模拟")
    search.add_argument("--out", default="", help="产物目录（默认 ./out）")
    search.add_argument("--format", default="table", help="终端输出：table 或 json（csv/html 总会写盘）")
    search.add_argument("-v", "--verbose", action="store_true", help="打印采集日志")
    search.set_defaults(func=cmd_search)

    serve_cmd = sub.add_parser("serve", help="启动本地交互演示网页")
    serve_cmd.add_argument("--host", default="127.0.0.1")
    serve_cmd.add_argument("--port", type=int, default=8765)
    serve_cmd.add_argument("--open", action="store_true", help="启动后自动打开浏览器")
    serve_cmd.set_defaults(func=cmd_serve)

    demo = sub.add_parser("build-demo", help="重建示例数据与演示页面")
    demo.add_argument("--keyword", default="机械键盘")
    demo.add_argument("--limit", type=int, default=12)
    demo.set_defaults(func=cmd_build_demo)

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        return args.func(args)
    except KeyboardInterrupt:
        return 130


if __name__ == "__main__":
    raise SystemExit(main())
