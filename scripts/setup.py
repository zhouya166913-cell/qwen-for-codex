#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import secrets
import subprocess
import sys
import tempfile
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
import webbrowser
from http import HTTPStatus
from http.cookies import CookieError, SimpleCookie
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any


SCRIPT_DIR = Path(__file__).resolve().parent
SOURCE_ROOT = SCRIPT_DIR.parent
sys.path.insert(0, str(SCRIPT_DIR))

from lib.config_manager import (  # noqa: E402
    PUBLIC_ENDPOINTS,
    ConfigError,
    codex_home,
    install,
    runtime_dir,
    status,
    uninstall,
)


DEFAULT_BASE_URL = PUBLIC_ENDPOINTS["beijing"]
DEFAULT_MODEL = "qwen3.8-max"
VERSION = "0.1.0"
MAX_BODY = 64 * 1024
SERVER_LIFETIME_SECONDS = 20 * 60


class SetupError(RuntimeError):
    pass


def _safe_message(value: str, secret: str = "") -> str:
    message = value.replace(secret, "<已隐藏>") if secret else value
    return " ".join(message.split())[:360]


def validate_api_key(api_key: str, timeout: int = 45) -> dict[str, Any]:
    key = api_key.strip()
    if len(key) < 8:
        raise SetupError("这个 API Key 看起来不完整，请重新复制后再试。")
    payload = json.dumps(
        {
            "model": DEFAULT_MODEL,
            "input": "Reply with exactly: OK",
            "reasoning": {"effort": "none"},
            "max_output_tokens": 16,
            "stream": False,
        }
    ).encode("utf-8")
    request = urllib.request.Request(
        f"{DEFAULT_BASE_URL}/responses",
        data=payload,
        method="POST",
        headers={
            "Authorization": f"Bearer {key}",
            "Content-Type": "application/json",
            "Accept": "application/json",
            "User-Agent": f"qwen-for-codex/{VERSION}",
        },
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            raw = response.read(1024 * 1024)
            if response.status != HTTPStatus.OK:
                raise SetupError("阿里云返回了异常状态，请稍后重试。")
            data = json.loads(raw.decode("utf-8")) if raw else {}
            return {"ok": True, "response_id": data.get("id")}
    except urllib.error.HTTPError as exc:
        body = exc.read(64 * 1024).decode("utf-8", errors="replace")
        if exc.code in (401, 403):
            raise SetupError("API Key 无效或没有模型调用权限，请检查后重试。") from exc
        if exc.code == 429:
            raise SetupError("阿里云当前限流或账户额度不足，请稍后重试或检查百炼余额。") from exc
        detail = _safe_message(body, key)
        raise SetupError(f"阿里云连接失败（{exc.code}）。{detail}") from exc
    except urllib.error.URLError as exc:
        raise SetupError("无法连接阿里云百炼，请检查网络后重试。") from exc
    except TimeoutError as exc:
        raise SetupError("连接阿里云超时，请检查网络后重试。") from exc
    except json.JSONDecodeError as exc:
        raise SetupError("阿里云返回了无法识别的数据，请稍后重试。") from exc


class SetupServer(ThreadingHTTPServer):
    daemon_threads = True

    def __init__(self, address, handler, *, token: str, home: Path):
        super().__init__(address, handler)
        self.session_token = token
        self.codex_home = home
        self.source_root = SOURCE_ROOT
        self.started_at = time.monotonic()
        self.last_activity = time.monotonic()


class SetupHandler(BaseHTTPRequestHandler):
    server: SetupServer
    server_version = f"QwenForCodexSetup/{VERSION}"

    def log_message(self, format: str, *args: object) -> None:
        safe_args = tuple("<redacted>" if "sk-" in str(arg) else arg for arg in args)
        super().log_message(format, *safe_args)

    def _security_headers(self, content_type: str) -> None:
        self.send_header("Content-Type", content_type)
        self.send_header("Cache-Control", "no-store, max-age=0")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("X-Frame-Options", "DENY")
        self.send_header("Referrer-Policy", "no-referrer")
        self.send_header("Permissions-Policy", "camera=(), microphone=(), geolocation=()")
        self.send_header(
            "Content-Security-Policy",
            "default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self'; "
            "connect-src 'self'; base-uri 'none'; form-action 'self'; frame-ancestors 'none'",
        )

    def _send_json(self, status_code: int, payload: dict[str, Any]) -> None:
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status_code)
        self._security_headers("application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _send_file(
        self, path: Path, content_type: str, extra_headers: dict[str, str] | None = None
    ) -> None:
        if not path.is_file():
            self.send_error(HTTPStatus.NOT_FOUND)
            return
        body = path.read_bytes()
        self.send_response(HTTPStatus.OK)
        self._security_headers(content_type)
        for name, value in (extra_headers or {}).items():
            self.send_header(name, value)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _session_cookie_token(self) -> str:
        try:
            cookies = SimpleCookie(self.headers.get("Cookie", ""))
            morsel = cookies.get("qwen_setup")
            return morsel.value if morsel else ""
        except CookieError:
            return ""

    def _authorized(self) -> bool:
        header_token = self.headers.get("X-Qwen-Setup-Token", "")
        cookie_token = self._session_cookie_token()
        return secrets.compare_digest(header_token, self.server.session_token) or secrets.compare_digest(
            cookie_token, self.server.session_token
        )

    def _valid_local_request(self) -> bool:
        host = self.headers.get("Host", "")
        if not (host.startswith("127.0.0.1:") or host.startswith("localhost:")):
            return False
        origin = self.headers.get("Origin")
        return not origin or origin.startswith("http://127.0.0.1:") or origin.startswith("http://localhost:")

    def _read_json(self) -> dict[str, Any]:
        try:
            length = int(self.headers.get("Content-Length", "0"))
        except ValueError as exc:
            raise SetupError("请求格式错误") from exc
        if length <= 0 or length > MAX_BODY:
            raise SetupError("请求内容大小异常")
        try:
            return json.loads(self.rfile.read(length).decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise SetupError("请求格式错误") from exc

    def do_GET(self) -> None:
        self.server.last_activity = time.monotonic()
        parsed = urllib.parse.urlsplit(self.path)
        ui_dir = self.server.source_root / "assets" / "setup"
        if parsed.path == "/":
            token = urllib.parse.parse_qs(parsed.query).get("token", [""])[0]
            token_is_valid = secrets.compare_digest(token, self.server.session_token)
            if not token_is_valid and not self._authorized():
                self.send_error(HTTPStatus.FORBIDDEN)
                return
            headers = None
            if token_is_valid:
                headers = {
                    "Set-Cookie": (
                        f"qwen_setup={self.server.session_token}; Path=/; HttpOnly; "
                        "SameSite=Strict; Max-Age=1200"
                    )
                }
            self._send_file(ui_dir / "index.html", "text/html; charset=utf-8", headers)
        elif parsed.path == "/styles.css":
            self._send_file(ui_dir / "styles.css", "text/css; charset=utf-8")
        elif parsed.path == "/app.js":
            self._send_file(ui_dir / "app.js", "text/javascript; charset=utf-8")
        elif parsed.path == "/favicon.ico":
            self.send_response(HTTPStatus.NO_CONTENT)
            self._security_headers("image/x-icon")
            self.end_headers()
        elif parsed.path == "/api/status":
            if not self._authorized():
                self._send_json(HTTPStatus.FORBIDDEN, {"ok": False, "message": "页面已失效，请重新打开设置。"})
                return
            self._send_json(HTTPStatus.OK, {"ok": True, **status(self.server.codex_home)})
        else:
            self.send_error(HTTPStatus.NOT_FOUND)

    def do_POST(self) -> None:
        self.server.last_activity = time.monotonic()
        if not self._valid_local_request() or not self._authorized():
            self._send_json(HTTPStatus.FORBIDDEN, {"ok": False, "message": "页面已失效，请重新打开设置。"})
            return
        try:
            if self.path == "/api/install":
                payload = self._read_json()
                api_key = str(payload.get("api_key", "")).strip()
                validate_api_key(api_key)
                result = install(
                    home=self.server.codex_home,
                    source_root=self.server.source_root,
                    api_key=api_key,
                    base_url=DEFAULT_BASE_URL,
                    model=DEFAULT_MODEL,
                )
                self._send_json(HTTPStatus.OK, {"ok": True, **result})
                threading.Timer(120, self.server.shutdown).start()
            elif self.path == "/api/uninstall":
                result = uninstall(self.server.codex_home)
                self._send_json(HTTPStatus.OK, {"ok": True, **result})
            else:
                self._send_json(HTTPStatus.NOT_FOUND, {"ok": False, "message": "请求不存在"})
        except (SetupError, ConfigError) as exc:
            self._send_json(HTTPStatus.BAD_REQUEST, {"ok": False, "message": _safe_message(str(exc))})
        except Exception:
            self._send_json(
                HTTPStatus.INTERNAL_SERVER_ERROR,
                {"ok": False, "message": "安装没有完成，原配置未被替换。请重新打开设置后再试。"},
            )


def serve(home: Path, ready_file: Path | None = None) -> int:
    token = secrets.token_urlsafe(32)
    server = SetupServer(("127.0.0.1", 0), SetupHandler, token=token, home=home)
    host, port = server.server_address
    url = f"http://{host}:{port}/?token={urllib.parse.quote(token)}"
    if ready_file:
        ready_file.parent.mkdir(parents=True, exist_ok=True)
        ready_file.write_text(url, encoding="utf-8")
    else:
        print(url, flush=True)

    def watchdog() -> None:
        while True:
            time.sleep(10)
            if time.monotonic() - server.last_activity > SERVER_LIFETIME_SECONDS:
                server.shutdown()
                return

    threading.Thread(target=watchdog, daemon=True).start()
    try:
        server.serve_forever(poll_interval=0.25)
    finally:
        server.server_close()
    return 0


def launch_detached(home: Path, no_open: bool = False) -> int:
    target_dir = runtime_dir(home)
    target_dir.mkdir(parents=True, exist_ok=True)
    handle, ready_name = tempfile.mkstemp(prefix="qwen-setup-", suffix=".ready", dir=target_dir)
    os.close(handle)
    ready_path = Path(ready_name)
    ready_path.unlink(missing_ok=True)
    log_path = target_dir / "setup-server.log"
    command = [
        sys.executable,
        str(Path(__file__).resolve()),
        "--serve",
        "--codex-home",
        str(home),
        "--ready-file",
        str(ready_path),
    ]
    kwargs: dict[str, Any] = {"stdin": subprocess.DEVNULL, "cwd": str(SOURCE_ROOT)}
    if os.name == "nt":
        kwargs["creationflags"] = subprocess.CREATE_NEW_PROCESS_GROUP | subprocess.DETACHED_PROCESS
    else:
        kwargs["start_new_session"] = True
    with log_path.open("a", encoding="utf-8") as log:
        kwargs["stdout"] = log
        kwargs["stderr"] = log
        process = subprocess.Popen(command, **kwargs)
    deadline = time.monotonic() + 8
    url = ""
    while time.monotonic() < deadline:
        if ready_path.exists():
            url = ready_path.read_text(encoding="utf-8").strip()
            break
        if process.poll() is not None:
            break
        time.sleep(0.1)
    ready_path.unlink(missing_ok=True)
    if not url:
        print(f"设置页启动失败，请查看：{log_path}", file=sys.stderr)
        return 1
    if not no_open:
        webbrowser.open(url, new=2)
    print("Qwen for Codex 设置页已打开。")
    print(url)
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Qwen for Codex 本地设置程序")
    parser.add_argument("--open", action="store_true", help="在浏览器打开设置页（默认行为）")
    parser.add_argument("--no-open", action="store_true", help="只打印设置页地址")
    parser.add_argument("--serve", action="store_true", help=argparse.SUPPRESS)
    parser.add_argument("--ready-file", type=Path, help=argparse.SUPPRESS)
    parser.add_argument("--status", action="store_true", help="只检查安装状态")
    parser.add_argument("--uninstall", action="store_true", help="移除本工具管理的配置")
    parser.add_argument("--codex-home", help="测试或高级场景使用的 Codex 目录")
    args = parser.parse_args()
    home = codex_home(args.codex_home)
    if args.status:
        print(json.dumps(status(home), ensure_ascii=False, indent=2))
        return 0
    if args.uninstall:
        print(json.dumps(uninstall(home), ensure_ascii=False, indent=2))
        return 0
    if args.serve:
        return serve(home, args.ready_file)
    return launch_detached(home, no_open=args.no_open)


if __name__ == "__main__":
    raise SystemExit(main())
