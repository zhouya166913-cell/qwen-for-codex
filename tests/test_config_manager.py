from __future__ import annotations

import json
import tempfile
import tomllib
import unittest
from pathlib import Path
from unittest import mock

from scripts.lib import config_manager


PROJECT_ROOT = Path(__file__).resolve().parents[1]


class ConfigManagerTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.home = Path(self.temp.name) / ".codex"
        self.home.mkdir()
        self.original = (
            'personality = "pragmatic"\n'
            'model = "gpt-6-sol"\n'
            'model_reasoning_effort = "medium"\n\n'
            '[desktop]\n'
            'appearanceTheme = "dark"\n'
        )
        (self.home / "config.toml").write_text(self.original, encoding="utf-8")

    def tearDown(self) -> None:
        self.temp.cleanup()

    @mock.patch("scripts.lib.config_manager.store_secret", return_value="test_store")
    def test_install_is_valid_and_does_not_write_key(self, _store: mock.Mock) -> None:
        key = "sk-test-secret-that-must-not-appear"
        result = config_manager.install(
            home=self.home,
            source_root=PROJECT_ROOT,
            api_key=key,
            base_url=config_manager.PUBLIC_ENDPOINTS["beijing"],
            model="qwen3.8-max",
        )
        text = (self.home / "config.toml").read_text(encoding="utf-8")
        parsed = tomllib.loads(text)
        self.assertTrue(result["installed"])
        self.assertNotIn(key, text)
        self.assertEqual(parsed["model"], "qwen3.8-max")
        self.assertEqual(parsed["model_provider"], config_manager.PROVIDER_ID)
        self.assertEqual(parsed["desktop"]["appearanceTheme"], "dark")
        self.assertIn(config_manager.PROVIDER_ID, parsed["model_providers"])
        self.assertTrue((self.home / "qwen-for-codex" / "model-catalog.json").exists())

    @mock.patch("scripts.lib.config_manager.store_secret", return_value="test_store")
    def test_reinstall_is_idempotent(self, _store: mock.Mock) -> None:
        for _ in range(2):
            config_manager.install(
                home=self.home,
                source_root=PROJECT_ROOT,
                api_key="sk-test-value",
                base_url=config_manager.PUBLIC_ENDPOINTS["beijing"],
                model="qwen3.8-max",
            )
        text = (self.home / "config.toml").read_text(encoding="utf-8")
        self.assertEqual(text.count(config_manager.DEFAULTS_BEGIN), 1)
        self.assertEqual(text.count(config_manager.PROVIDER_BEGIN), 1)
        tomllib.loads(text)

    @mock.patch("scripts.lib.config_manager.delete_secret")
    @mock.patch("scripts.lib.config_manager.store_secret", return_value="test_store")
    def test_uninstall_restores_previous_model_and_keeps_later_changes(
        self, _store: mock.Mock, _delete: mock.Mock
    ) -> None:
        config_manager.install(
            home=self.home,
            source_root=PROJECT_ROOT,
            api_key="sk-test-value",
            base_url=config_manager.PUBLIC_ENDPOINTS["beijing"],
            model="qwen3.8-max",
        )
        config_path = self.home / "config.toml"
        config_path.write_text(
            config_path.read_text(encoding="utf-8") + '\n[features]\nmemories = false\n',
            encoding="utf-8",
        )
        result = config_manager.uninstall(self.home)
        text = config_path.read_text(encoding="utf-8")
        parsed = tomllib.loads(text)
        self.assertTrue(result["changed"])
        self.assertEqual(parsed["model"], "gpt-6-sol")
        self.assertEqual(parsed["model_reasoning_effort"], "medium")
        self.assertFalse(parsed["features"]["memories"])
        self.assertNotIn(config_manager.DEFAULTS_BEGIN, text)
        self.assertNotIn(config_manager.PROVIDER_ID, parsed.get("model_providers", {}))

    def test_build_base_url_rejects_invalid_workspace(self) -> None:
        with self.assertRaises(config_manager.ConfigError):
            config_manager.build_base_url("beijing", "bad workspace!")

    @mock.patch("scripts.lib.config_manager.delete_secret")
    def test_uninstall_without_markers_never_changes_user_config(
        self, _delete: mock.Mock
    ) -> None:
        state_dir = self.home / "qwen-for-codex"
        state_dir.mkdir()
        (state_dir / "state.json").write_text(
            json.dumps({"previous_top_level": {"model": 'model = "stale-model"'}}),
            encoding="utf-8",
        )

        result = config_manager.uninstall(self.home)

        self.assertFalse(result["changed"])
        self.assertEqual((self.home / "config.toml").read_text(encoding="utf-8"), self.original)
        _delete.assert_called_once()

    def test_catalog_has_unique_picker_models(self) -> None:
        data = json.loads((PROJECT_ROOT / "assets" / "qwen-model-catalog.json").read_text(encoding="utf-8"))
        slugs = [model["slug"] for model in data["models"]]
        self.assertGreaterEqual(len(slugs), 4)
        self.assertEqual(len(slugs), len(set(slugs)))
        self.assertTrue(all(model["visibility"] == "list" for model in data["models"]))

    @mock.patch("scripts.lib.config_manager.getpass.getuser", return_value="mac-user")
    @mock.patch("scripts.lib.config_manager.platform.system", return_value="Darwin")
    @mock.patch("scripts.lib.config_manager.store_secret", return_value="macos_keychain")
    def test_macos_uses_native_keychain_command(
        self, _store: mock.Mock, _system: mock.Mock, _user: mock.Mock
    ) -> None:
        config_manager.install(
            home=self.home,
            source_root=PROJECT_ROOT,
            api_key="sk-test-value",
            base_url=config_manager.PUBLIC_ENDPOINTS["beijing"],
            model="qwen3.8-max",
        )
        parsed = tomllib.loads((self.home / "config.toml").read_text(encoding="utf-8"))
        auth = parsed["model_providers"][config_manager.PROVIDER_ID]["auth"]
        self.assertEqual(auth["command"], "/usr/bin/security")
        self.assertIn("mac-user", auth["args"])
        self.assertIn("QwenForCodex-DashScope", auth["args"])


if __name__ == "__main__":
    unittest.main()
