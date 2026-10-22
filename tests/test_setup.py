from __future__ import annotations

import io
import json
import unittest
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


if __name__ == "__main__":
    unittest.main()
