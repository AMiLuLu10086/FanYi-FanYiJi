"""
server.py — 本地网页服务
=========================
只用 Python 标准库（http.server），不引入 Web 框架。

启动：
    .venv\\Scripts\\python.exe server.py
然后浏览器打开 http://127.0.0.1:8000

接口一览：
    POST /api/runs                  {text, rounds}  新建任务，返回 run_id
    GET  /api/runs/<id>                             读任务状态（网页每秒轮询一次）
    GET  /api/runs/<id>?fmt=md                      导出 Markdown 全过程
    POST /api/runs/<id>/stop                        请求停止
    GET  /api/runs                                  历史运行列表
    GET  /api/status                                模型加载状态
    GET  /  /app.js  /style.css                     前端静态文件
"""
from __future__ import annotations

import json
import threading
import time
import traceback
import urllib.parse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import config  # 先 import config：它负责设好 HF_ENDPOINT / HF_HOME

import pipeline      # noqa: E402
import store         # noqa: E402
import translator    # noqa: E402

# 同时只允许一个任务在跑：两个任务会各自把模型读进内存，得不偿失
_task_lock = threading.Lock()
_active_run_id: str | None = None


# ─────────────────────────── 后台跑任务 ───────────────────────────

def _run_in_background(run: store.Run) -> None:
    global _active_run_id
    try:
        def on_step(step: dict) -> None:
            run.steps.append(step)

        result = pipeline.run(
            text=run.text,
            rounds=run.rounds,
            on_step=on_step,
            abort=run.stop_event,
        )
        run.final_zh = result["final_zh"]
        run.total_ms = result["total_ms"]
        run.status = "stopped" if result["stopped"] else "done"
    except translator.ModelUnavailable as exc:
        run.status = "error"
        run.error = str(exc)
    except MemoryError:
        run.status = "error"
        run.error = "内存不足，无法加载模型。请关闭其他占内存的程序后重试。"
    except Exception as exc:  # 兜底：不让服务进程崩掉
        run.status = "error"
        run.error = f"运行出错：{exc}"
        traceback.print_exc()
    finally:
        run.finished_at = time.time()
        try:
            store.save(run)
        except OSError as exc:
            print(f"[警告] 保存运行记录失败：{exc}")
        with _task_lock:
            _active_run_id = None


# ─────────────────────────── HTTP ───────────────────────────

class Handler(BaseHTTPRequestHandler):
    server_version = "TranslationLoop/1.0"

    # ── 小工具 ──
    def _send_json(self, payload: dict, status: int = 200) -> None:
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def _send_text(self, text: str, content_type: str, status: int = 200,
                   extra_headers: list[tuple[str, str]] | None = None) -> None:
        body = text.encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        for key, value in (extra_headers or []):
            self.send_header(key, value)
        self.end_headers()
        self.wfile.write(body)

    def _send_file(self, path: Path) -> None:
        if not path.is_file():
            self._send_json({"error": "文件不存在"}, 404)
            return
        content_type = {
            ".html": "text/html; charset=utf-8",
            ".js": "application/javascript; charset=utf-8",
            ".css": "text/css; charset=utf-8",
            ".svg": "image/svg+xml",
        }.get(path.suffix, "application/octet-stream")
        self._send_text(path.read_text(encoding="utf-8"), content_type)

    def _read_json_body(self) -> dict:
        length = int(self.headers.get("Content-Length") or 0)
        if length <= 0:
            return {}
        raw = self.rfile.read(length)
        try:
            data = json.loads(raw.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError):
            raise ValueError("请求内容不是合法的 JSON")
        if not isinstance(data, dict):
            raise ValueError("请求内容必须是 JSON 对象")
        return data

    def log_message(self, fmt: str, *args) -> None:  # 精简日志：只留一行
        if self.path.startswith("/api"):
            print(f"[{time.strftime('%H:%M:%S')}] {self.command} {self.path}")

    # ── 路由 ──
    def do_GET(self) -> None:  # noqa: N802
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path
        query = urllib.parse.parse_qs(parsed.query)

        if path == "/" or path == "/index.html":
            self._send_file(config.WEB_DIR / "index.html")
            return
        if path in ("/app.js", "/style.css"):
            self._send_file(config.WEB_DIR / path.lstrip("/"))
            return
        if path == "/api/status":
            self._send_json({
                "engine": translator.engine_status(),
                "models": {
                    "zh2en": config.MODEL_ZH2EN,
                    "en2zh": config.MODEL_EN2ZH,
                },
                "models_dir": str(config.MODELS_DIR),
                "default_rounds": config.DEFAULT_ROUNDS,
                "max_rounds": config.MAX_ROUNDS,
                "max_input_chars": config.MAX_INPUT_CHARS,
            })
            return
        if path == "/api/runs":
            self._send_json({"runs": store.recent()})
            return
        if path.startswith("/api/runs/"):
            run_id = path[len("/api/runs/"):].strip("/")
            run = store.get(run_id)
            if run is None:
                self._send_json({"error": f"找不到运行记录 {run_id}"}, 404)
                return
            data = run.to_dict()
            if query.get("fmt", [""])[0] == "md":
                markdown = store.to_markdown(data)
                self._send_text(
                    markdown,
                    "text/markdown; charset=utf-8",
                    extra_headers=[(
                        "Content-Disposition",
                        f'attachment; filename="translate-loop-{run_id}.md"',
                    )],
                )
                return
            self._send_json(data)
            return

        self._send_json({"error": f"未知路径 {path}"}, 404)

    def do_POST(self) -> None:  # noqa: N802
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path

        if path == "/api/runs":
            self._handle_create_run()
            return

        if path.startswith("/api/runs/") and path.endswith("/stop"):
            run_id = path[len("/api/runs/"):-len("/stop")].strip("/")
            run = store.get(run_id)
            if run is None:
                self._send_json({"error": f"找不到运行记录 {run_id}"}, 404)
                return
            run.stop_event.set()
            self._send_json({"ok": True, "id": run_id})
            return

        self._send_json({"error": f"未知路径 {path}"}, 404)

    def _handle_create_run(self) -> None:
        global _active_run_id
        try:
            body = self._read_json_body()
        except ValueError as exc:
            self._send_json({"error": str(exc)}, 400)
            return

        text = str(body.get("text") or "").strip()
        if not text:
            self._send_json({"error": "请先输入要翻译的中文"}, 400)
            return
        if len(text) > config.MAX_INPUT_CHARS:
            self._send_json({
                "error": f"文本太长了：{len(text)} 字，上限 {config.MAX_INPUT_CHARS} 字。"
                         f"机翻模型一次只能处理有限长度，超了会翻出乱码。",
            }, 400)
            return

        try:
            rounds = int(body.get("rounds", config.DEFAULT_ROUNDS))
        except (TypeError, ValueError):
            self._send_json({"error": "轮数必须是整数"}, 400)
            return
        if rounds < 1 or rounds > config.MAX_ROUNDS:
            self._send_json({
                "error": f"轮数需要在 1 到 {config.MAX_ROUNDS} 之间",
            }, 400)
            return

        with _task_lock:
            if _active_run_id is not None:
                current = store.get(_active_run_id)
                if current is not None and current.status == "running":
                    self._send_json({
                        "error": "已经有一个任务在跑了，请等它结束，或先点「停止」。",
                    }, 409)
                    return

            run = store.create(text, rounds)
            _active_run_id = run.id

        threading.Thread(
            target=_run_in_background, args=(run,), daemon=True
        ).start()

        self._send_json({"id": run.id, "rounds": rounds}, 201)


class Server(ThreadingHTTPServer):
    daemon_threads = True
    # 注意：这里故意【不】设 allow_reuse_address。
    # 在 Windows 上它对应 SO_REUSEADDR，会让第二个进程也能绑上同一个端口，
    # 于是一个端口上同时有多个服务在监听、请求被最旧的那个接走，
    # 排查起来非常费解（改完代码重启却看不到变化，就是这个原因）。
    # 关掉它以后，重复启动会直接报"端口被占用"，一眼就知道该先关掉旧的。


def main() -> int:
    config.MODELS_DIR.mkdir(parents=True, exist_ok=True)
    config.RUNS_DIR.mkdir(parents=True, exist_ok=True)

    print("=" * 62)
    print("  Round-Trip Amnesia（往返失忆症）")
    print("=" * 62)
    print(f"  模型目录：{config.MODELS_DIR}")
    print(f"  记录目录：{config.RUNS_DIR}")
    print(f"  模型下载源：{config.HF_ENDPOINT}")
    print(f"  默认轮数：{config.DEFAULT_ROUNDS}（页面可改，上限 {config.MAX_ROUNDS}）")
    print()
    print("  首次运行需要下载两个模型，共约 624MB，请耐心等待。")
    print(f"  打开浏览器访问：http://{config.HOST}:{config.PORT}")
    print("  按 Ctrl+C 结束服务")
    print("=" * 62)

    # 后台预热模型：这样第一次点「开始翻译」不用干等
    def warmup() -> None:
        try:
            translator.warmup()
            print("[模型] 两个模型都已加载完成，可以开始翻译了。")
        except Exception as exc:
            print(f"[模型] 预热失败：{exc}")
            print("[模型] 不影响使用，点「开始翻译」时会再试一次。")

    threading.Thread(target=warmup, daemon=True).start()

    server = Server((config.HOST, config.PORT), Handler)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n已停止。")
    finally:
        server.server_close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
