from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest import mock

from scripts.lib import credential_store


class CredentialStoreTests(unittest.TestCase):
    @mock.patch("scripts.lib.credential_store._store_windows")
    @mock.patch("scripts.lib.credential_store.platform.system", return_value="Windows")
    def test_windows_never_silently_falls_back_to_file(
        self, _system: mock.Mock, store_windows: mock.Mock
    ) -> None:
        store_windows.side_effect = credential_store.CredentialError("write failed")
        with tempfile.TemporaryDirectory() as temp:
            runtime_dir = Path(temp)
            with self.assertRaises(credential_store.CredentialError):
                credential_store.store_secret("sk-test-value", runtime_dir)
            self.assertFalse((runtime_dir / credential_store.FALLBACK_FILE).exists())


if __name__ == "__main__":
    unittest.main()
