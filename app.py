"""动态分区分配可视化 Web 应用入口。"""

from __future__ import annotations

from http import HTTPStatus
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
import json
from pathlib import Path
import threading
from urllib.parse import urlparse

from simulation.engine import SimulationEngine, build_placeholder_state


BASE_DIR = Path(__file__).resolve().parent
STATIC_DIR = BASE_DIR / "static"
LOG_DIR = BASE_DIR / "logs"
HOST = "127.0.0.1"
PORT = 8000


class SimulationController:
    """管理仿真生命周期与后台调度线程。"""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._engine: SimulationEngine | None = None
        self._running = False
        self._paused = False
        self._stop_event = threading.Event()
        self._thread: threading.Thread | None = None

    def start(self, seed: int | None, interval_ms: int) -> dict[str, object]:
        self.stop()

        with self._lock:
            self._engine = SimulationEngine(log_dir=LOG_DIR, seed=seed, interval_ms=interval_ms)
            self._running = True
            self._paused = False
            self._stop_event = threading.Event()
            self._engine.step()
            self._thread = threading.Thread(target=self._run_loop, daemon=True)
            self._thread.start()
            return self._compose_state()

    def pause(self) -> dict[str, object]:
        thread_to_join: threading.Thread | None = None

        with self._lock:
            if self._engine is None:
                return build_placeholder_state()

            if self._thread is not None and self._running:
                self._running = False
                self._paused = True
                self._stop_event.set()
                thread_to_join = self._thread
                self._thread = None

        if thread_to_join is not None:
            thread_to_join.join(timeout=2)

        return self.get_state()

    def resume(self) -> dict[str, object]:
        with self._lock:
            if self._engine is None:
                return build_placeholder_state()

            if self._thread is not None and self._running:
                return self._compose_state()

            if not self._paused:
                return self._compose_state()

            self._running = True
            self._paused = False
            self._stop_event = threading.Event()
            self._thread = threading.Thread(target=self._run_loop, daemon=True)
            self._thread.start()
            return self._compose_state()

    def stop(self) -> dict[str, object]:
        thread_to_join: threading.Thread | None = None

        with self._lock:
            if self._thread is not None:
                self._running = False
                self._stop_event.set()
                thread_to_join = self._thread
                self._thread = None
            self._paused = False

        if thread_to_join is not None:
            thread_to_join.join(timeout=2)

        return self.get_state()

    def get_state(self) -> dict[str, object]:
        with self._lock:
            return self._compose_state()

    def _run_loop(self) -> None:
        while not self._stop_event.wait(self._current_interval_seconds()):
            with self._lock:
                if not self._running or self._engine is None:
                    break
                self._engine.step()

        with self._lock:
            self._running = False

    def _current_interval_seconds(self) -> float:
        with self._lock:
            if self._engine is None:
                return 0.7
            return self._engine.interval_ms / 1000

    def _compose_state(self) -> dict[str, object]:
        if self._engine is None:
            return build_placeholder_state()

        state = self._engine.serialize()
        state["running"] = self._running
        state["paused"] = self._paused
        return state


controller = SimulationController()


class AppRequestHandler(SimpleHTTPRequestHandler):
    """静态资源与 API 的统一请求处理器。"""

    extensions_map = {
        **SimpleHTTPRequestHandler.extensions_map,
        ".html": "text/html; charset=utf-8",
        ".css": "text/css; charset=utf-8",
        ".js": "application/javascript; charset=utf-8",
    }

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, directory=str(STATIC_DIR), **kwargs)

    def end_headers(self) -> None:
        self.send_header("Cache-Control", "no-store")
        super().end_headers()

    def do_GET(self) -> None:
        parsed = urlparse(self.path)

        if parsed.path == "/api/state":
            self._send_json(controller.get_state())
            return

        if parsed.path.startswith("/logs/"):
            self._serve_log_file(parsed.path.removeprefix("/logs/"))
            return

        if parsed.path == "/":
            self.path = "/index.html"

        super().do_GET()

    def do_POST(self) -> None:
        parsed = urlparse(self.path)
        content_length = int(self.headers.get("Content-Length", "0"))
        raw_body = self.rfile.read(content_length) if content_length else b"{}"
        payload = json.loads(raw_body.decode("utf-8") or "{}")

        if parsed.path == "/api/start":
            seed = payload.get("seed")
            interval_ms = int(payload.get("interval_ms", 700))
            state = controller.start(seed=seed if seed not in ("", None) else None, interval_ms=interval_ms)
            self._send_json(state, status=HTTPStatus.CREATED)
            return

        if parsed.path == "/api/stop":
            self._send_json(controller.stop())
            return

        if parsed.path == "/api/pause":
            self._send_json(controller.pause())
            return

        if parsed.path == "/api/resume":
            self._send_json(controller.resume())
            return

        self._send_json({"error": "Unknown API route."}, status=HTTPStatus.NOT_FOUND)

    def _serve_log_file(self, file_name: str) -> None:
        safe_name = Path(file_name).name
        target = (LOG_DIR / safe_name).resolve()
        if not target.exists() or LOG_DIR.resolve() not in target.parents:
            self.send_error(HTTPStatus.NOT_FOUND, "Log file not found.")
            return

        data = target.read_bytes()
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", "text/csv; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Content-Disposition", f'attachment; filename="{safe_name}"')
        self.end_headers()
        self.wfile.write(data)

    def _send_json(self, data: dict[str, object], status: HTTPStatus = HTTPStatus.OK) -> None:
        body = json.dumps(data, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, format: str, *args) -> None:
        """保持控制台输出简洁。"""


def main() -> None:
    LOG_DIR.mkdir(exist_ok=True)
    server = ThreadingHTTPServer((HOST, PORT), AppRequestHandler)
    print(f"Server running at http://{HOST}:{PORT}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
