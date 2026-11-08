"""本地演示服务：静态页面 + /api/search 实时调用采集流水线。"""

from __future__ import annotations

import json
import mimetypes
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import unquote, urlparse

from .build import ensure_page, ensure_sample
from .pipeline import OUT_DIR, run

MAX_BODY = 64 * 1024
SAMPLES: dict = {}
LOCK = threading.Lock()


class Handler(BaseHTTPRequestHandler):
    server_version = "PriceLens/1.0"

    def log_message(self, fmt: str, *args) -> None:   # 保持终端干净
        pass

    # ------------------------------------------------------------ 工具
    def _send(self, status: int, body: bytes, content_type: str) -> None:
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def _json(self, payload: dict, status: int = 200) -> None:
        body = json.dumps(payload, ensure_ascii=False, default=str).encode("utf-8")
        self._send(status, body, "application/json; charset=utf-8")

    # ------------------------------------------------------------ GET
    def do_GET(self) -> None:
        path = unquote(urlparse(self.path).path)

        if path in ("/", "/index.html"):
            page = ensure_page()
            self._send(200, page.read_bytes(), "text/html; charset=utf-8")
            return

        if path == "/api/health":
            self._json({"ok": True, "sample": bool(SAMPLES.get("data"))})
            return

        if path == "/api/sample":
            self._json(SAMPLES.get("data") or {})
            return

        if path.startswith("/out/"):
            target = (OUT_DIR / path[len("/out/"):]).resolve()
            if OUT_DIR.resolve() not in target.parents and target.parent != OUT_DIR.resolve():
                self._json({"error": "非法路径"}, 403)
                return
            if target.is_file():
                mime = mimetypes.guess_type(target.name)[0] or "application/octet-stream"
                if mime.startswith("text/") or mime in ("application/json",):
                    mime += "; charset=utf-8"
                self._send(200, target.read_bytes(), mime)
                return
            self._json({"error": "文件不存在"}, 404)
            return

        self._json({"error": "Not Found"}, 404)

    # ------------------------------------------------------------ POST
    def do_POST(self) -> None:
        if urlparse(self.path).path != "/api/search":
            self._json({"error": "Not Found"}, 404)
            return

        length = int(self.headers.get("Content-Length") or 0)
        if length <= 0 or length > MAX_BODY:
            self._json({"error": "请求体为空或过大"}, 400)
            return

        try:
            body = json.loads(self.rfile.read(length).decode("utf-8"))
        except (json.JSONDecodeError, UnicodeDecodeError):
            self._json({"error": "JSON 解析失败"}, 400)
            return

        keyword = str(body.get("keyword", "")).strip()[:40]
        if not keyword:
            self._json({"error": "请先输入关键词"}, 400)
            return

        platforms = body.get("platforms") or ["jd", "tb", "pdd"]
        platforms = tuple(p for p in platforms if p in ("jd", "tb", "pdd")) or ("jd", "tb", "pdd")
        limit = max(4, min(int(body.get("limit", 12) or 12), 30))
        source = body.get("source", "auto")
        if source not in ("auto", "live", "simulated"):
            source = "auto"

        try:
            with LOCK:
                payload = run(keyword=keyword, platforms=platforms, limit=limit, source=source)
        except Exception as exc:                      # 兜底，避免前端白屏
            self._json({"error": f"采集失败：{type(exc).__name__}: {exc}"}, 500)
            return

        self._json(payload)


def serve(host: str = "127.0.0.1", port: int = 8765) -> None:
    sample = ensure_sample()
    SAMPLES["data"] = sample
    ensure_page()

    httpd = ThreadingHTTPServer((host, port), Handler)
    print(f"PriceLens 演示服务已启动: http://{host}:{port}")
    print("按 Ctrl+C 停止。")
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\n已停止。")
    finally:
        httpd.server_close()
