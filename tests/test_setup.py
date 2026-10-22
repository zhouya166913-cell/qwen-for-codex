from __future__ import annotations

import io
import http.client
import json
import tempfile
import threading
import unittest
from contextlib import redirect_stderr
from pathlib import Path
from unittest import mock

from scripts import setup


class _Response:
    status = 200

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return False

    def read(self, _limit: int) -> bytes:
        return json.dumps({"id": "resp_test", "output": []}).encode("utf-8")


class SetupTests(unittest.TestCase):
    @mock.patch("scripts.setup.urllib.request.urlopen", return_value=_Response())
    def test_validate_key_uses_responses_api_without_leaking_key(self, mocked: mock.Mock) -> None:
        secret = "sk-test-secret"
        result = setup.validate_api_key(secret)
        request = mocked.call_args.args[0]
        self.assertTrue(result["ok"])
        self.assertTrue(request.full_url.endswith("/responses"))
        self.assertNotIn(secret, request.data.decode("utf-8"))

    @mock.patch("scripts.setup.urllib.request.urlopen")
    def test_auth_error_is_plain_language(self, mocked: mock.Mock) -> None:
        mocked.side_effect = setup.urllib.error.HTTPError(
            url="https://example.invalid/responses",
            code=401,
            msg="Unauthorized",
            hdrs=None,
            fp=io.BytesIO(b'{"error":"invalid"}'),
        )
        with self.assertRaisesRegex(setup.SetupError, "API Key 无效"):
            setup.validate_api_key("sk-test-secret")

    @mock.patch("scripts.setup.threading.Timer")
    @mock.patch("scripts.setup.install")
    @mock.patch("scripts.setup.validate_api_key", return_value={"ok": True})
    def test_install_endpoint_passes_selected_mode(
        self, _validate: mock.Mock, install: mock.Mock, _timer: mock.Mock
    ) -> None:
        install.return_value = {
            "installed": True,
            "mode": "aggregate",
            "model": "qwen3.8-max",
        }
        with tempfile.TemporaryDirectory() as temporary:
            server = setup.SetupServer(
                ("127.0.0.1", 0),
                setup.SetupHandler,
                token="test-token",
                home=Path(temporary) / ".codex",
            )
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            try:
                connection = http.client.HTTPConnection(*server.server_address, timeout=5)
                body = json.dumps(
                    {"api_key": "sk-test-secret", "mode": "aggregate"}
                ).encode("utf-8")
                connection.request(
                    "POST",
                    "/api/install",
                    body=body,
                    headers={
                        "Content-Type": "application/json",
                        "Content-Length": str(len(body)),
                        "Cookie": "qwen_setup=test-token",
                        "Origin": f"http://127.0.0.1:{server.server_address[1]}",
                    },
                )
                response = connection.getresponse()
                payload = json.loads(response.read().decode("utf-8"))
                connection.close()
            finally:
                server.shutdown()
                server.server_close()
                thread.join(timeout=5)

        self.assertEqual(response.status, 200)
        self.assertTrue(payload["ok"])
        self.assertEqual(install.call_args.kwargs["mode"], "aggregate")

    @mock.patch("scripts.setup.install")
    @mock.patch("scripts.setup.validate_api_key")
    def test_install_endpoint_rejects_invalid_mode_before_key_validation(
        self, validate: mock.Mock, install: mock.Mock
    ) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            server = setup.SetupServer(
                ("127.0.0.1", 0),
                setup.SetupHandler,
                token="test-token",
                home=Path(temporary) / ".codex",
            )
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            try:
                connection = http.client.HTTPConnection(*server.server_address, timeout=5)
                body = json.dumps(
                    {"api_key": "sk-test-secret", "mode": "unknown"}
                ).encode("utf-8")
                connection.request(
                    "POST",
                    "/api/install",
                    body=body,
                    headers={
                        "Content-Type": "application/json",
                        "Content-Length": str(len(body)),
                        "Cookie": "qwen_setup=test-token",
                        "Origin": f"http://127.0.0.1:{server.server_address[1]}",
                    },
                )
                response = connection.getresponse()
                payload = json.loads(response.read().decode("utf-8"))
                connection.close()
            finally:
                server.shutdown()
                server.server_close()
                thread.join(timeout=5)

        self.assertEqual(response.status, 400)
        self.assertFalse(payload["ok"])
        self.assertIn("接入方式无效", payload["message"])
        validate.assert_not_called()
        install.assert_not_called()

    @mock.patch("scripts.setup.install")
    @mock.patch("scripts.setup.validate_api_key")
    def test_overlapping_mutation_returns_conflict_without_running(
        self, validate: mock.Mock, install: mock.Mock
    ) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            server = setup.SetupServer(
                ("127.0.0.1", 0),
                setup.SetupHandler,
                token="test-token",
                home=Path(temporary) / ".codex",
            )
            server.mutation_lock.acquire()
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            try:
                connection = http.client.HTTPConnection(*server.server_address, timeout=5)
                body = json.dumps(
                    {"api_key": "sk-test-secret", "mode": "aggregate"}
                ).encode("utf-8")
                connection.request(
                    "POST",
                    "/api/install",
                    body=body,
                    headers={
                        "Content-Type": "application/json",
                        "Content-Length": str(len(body)),
                        "Cookie": "qwen_setup=test-token",
                        "Origin": f"http://127.0.0.1:{server.server_address[1]}",
                    },
                )
                response = connection.getresponse()
                payload = json.loads(response.read().decode("utf-8"))
                connection.close()
            finally:
                server.mutation_lock.release()
                server.shutdown()
                server.server_close()
                thread.join(timeout=5)

        self.assertEqual(response.status, 409)
        self.assertFalse(payload["ok"])
        self.assertIn("另一个配置操作", payload["message"])
        validate.assert_not_called()
        install.assert_not_called()

    @mock.patch("scripts.setup.install")
    @mock.patch("scripts.setup.validate_api_key", return_value={"ok": True})
    def test_credential_store_error_is_actionable(
        self, _validate: mock.Mock, install: mock.Mock
    ) -> None:
        install.side_effect = setup.CredentialError("Windows 凭据管理器写入失败（错误 5）")
        with tempfile.TemporaryDirectory() as temporary:
            server = setup.SetupServer(
                ("127.0.0.1", 0),
                setup.SetupHandler,
                token="test-token",
                home=Path(temporary) / ".codex",
            )
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            try:
                connection = http.client.HTTPConnection(*server.server_address, timeout=5)
                body = json.dumps(
                    {"api_key": "sk-test-secret", "mode": "aggregate"}
                ).encode("utf-8")
                connection.request(
                    "POST",
                    "/api/install",
                    body=body,
                    headers={
                        "Content-Type": "application/json",
                        "Content-Length": str(len(body)),
                        "Cookie": "qwen_setup=test-token",
                        "Origin": f"http://127.0.0.1:{server.server_address[1]}",
                    },
                )
                response = connection.getresponse()
                payload = json.loads(response.read().decode("utf-8"))
                connection.close()
            finally:
                server.shutdown()
                server.server_close()
                thread.join(timeout=5)

        self.assertEqual(response.status, 500)
        self.assertFalse(payload["ok"])
        self.assertIn("系统凭据库", payload["message"])
        self.assertIn("解锁", payload["message"])

    def test_access_log_redacts_setup_token(self) -> None:
        token = "session-token-must-not-enter-log"
        with tempfile.TemporaryDirectory() as temporary:
            server = setup.SetupServer(
                ("127.0.0.1", 0),
                setup.SetupHandler,
                token=token,
                home=Path(temporary) / ".codex",
            )
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            captured = io.StringIO()
            with redirect_stderr(captured):
                thread.start()
                try:
                    connection = http.client.HTTPConnection(*server.server_address, timeout=5)
                    connection.request("GET", f"/?token={token}")
                    response = connection.getresponse()
                    response.read()
                    connection.close()
                finally:
                    server.shutdown()
                    server.server_close()
                    thread.join(timeout=5)

        log = captured.getvalue()
        self.assertEqual(response.status, 200)
        self.assertNotIn(token, log)
        self.assertIn("token=<redacted>", log)

    @mock.patch("scripts.setup.status", side_effect=RuntimeError("broken state"))
    def test_status_failure_still_returns_safe_json(self, _status: mock.Mock) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            server = setup.SetupServer(
                ("127.0.0.1", 0),
                setup.SetupHandler,
                token="test-token",
                home=Path(temporary) / ".codex",
            )
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            try:
                connection = http.client.HTTPConnection(*server.server_address, timeout=5)
                connection.request(
                    "GET",
                    "/api/status",
                    headers={"Cookie": "qwen_setup=test-token"},
                )
                response = connection.getresponse()
                payload = json.loads(response.read().decode("utf-8"))
                connection.close()
            finally:
                server.shutdown()
                server.server_close()
                thread.join(timeout=5)

        self.assertEqual(response.status, 500)
        self.assertFalse(payload["ok"])
        self.assertIn("无法读取", payload["message"])


if __name__ == "__main__":
    unittest.main()
