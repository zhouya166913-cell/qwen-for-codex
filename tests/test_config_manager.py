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
        self.strict_secret_reader = mock.patch(
            "scripts.lib.config_manager.read_secret_for_update", return_value=None
        )
        self.read_secret_for_update = self.strict_secret_reader.start()
        self.addCleanup(self.strict_secret_reader.stop)
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
        self.assertNotIn("model_reasoning_effort", parsed)
        self.assertEqual(parsed["desktop"]["appearanceTheme"], "dark")
        self.assertIn(config_manager.PROVIDER_ID, parsed["model_providers"])
        catalog_path = Path(parsed["model_catalog_json"])
        self.assertTrue(catalog_path.exists())
        self.assertIn("model-catalog-direct-", catalog_path.name)

        state = json.loads(
            (self.home / "qwen-for-codex" / "state.json").read_text(encoding="utf-8")
        )
        self.assertEqual(state["schema"], 2)
        self.assertEqual(state["mode"], config_manager.MODE_DIRECT)

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
        expected = {
            "qwen-model-catalog.json": {
                "qwen3.8-max",
                "qwen3.8-flash",
                "qwen3.7-plus",
                "qwen3.7-flash",
            },
            "aggregate-model-catalog.json": {
                "qwen3.8-max",
                "qwen3.8-flash",
                "qwen3.7-plus",
                "qwen3.7-flash",
                "deepseek-v4.1-flash",
                "deepseek-v4-pro",
                "glm-5.3",
                "glm-5.2",
            },
        }
        for filename, expected_slugs in expected.items():
            with self.subTest(filename=filename):
                data = json.loads(
                    (PROJECT_ROOT / "assets" / filename).read_text(encoding="utf-8")
                )
                slugs = [model["slug"] for model in data["models"]]
                self.assertEqual(set(slugs), expected_slugs)
                self.assertEqual(len(slugs), len(set(slugs)))
                self.assertTrue(all(model["visibility"] == "list" for model in data["models"]))

    @mock.patch("scripts.lib.config_manager.store_secret", return_value="test_store")
    def test_switch_modes_then_uninstall_restores_original_config(
        self, _store: mock.Mock
    ) -> None:
        for mode in (
            config_manager.MODE_DIRECT,
            config_manager.MODE_AGGREGATE,
            config_manager.MODE_DIRECT,
        ):
            config_manager.install(
                home=self.home,
                source_root=PROJECT_ROOT,
                api_key="sk-test-value",
                base_url=config_manager.PUBLIC_ENDPOINTS["beijing"],
                model="qwen3.8-max",
                mode=mode,
            )
            state = json.loads(
                (self.home / "qwen-for-codex" / "state.json").read_text(encoding="utf-8")
            )
            parsed = tomllib.loads((self.home / "config.toml").read_text(encoding="utf-8"))
            catalog = json.loads(
                Path(parsed["model_catalog_json"]).read_text(encoding="utf-8")
            )
            self.assertEqual(state["schema"], 2)
            self.assertEqual(state["mode"], mode)
            self.assertIn(f"model-catalog-{mode}-", Path(parsed["model_catalog_json"]).name)
            self.assertEqual(len(catalog["models"]), 4 if mode == config_manager.MODE_DIRECT else 8)

        with mock.patch("scripts.lib.config_manager.delete_secret"):
            result = config_manager.uninstall(self.home)

        self.assertTrue(result["changed"])
        self.assertEqual(
            tomllib.loads((self.home / "config.toml").read_text(encoding="utf-8")),
            tomllib.loads(self.original),
        )

    @mock.patch("scripts.lib.config_manager.store_secret")
    @mock.patch("scripts.lib.config_manager._backup")
    def test_invalid_mode_is_rejected_before_backup_or_credential_write(
        self, backup: mock.Mock, store: mock.Mock
    ) -> None:
        before = (self.home / "config.toml").read_bytes()

        with self.assertRaises(config_manager.ConfigError):
            config_manager.install(
                home=self.home,
                source_root=PROJECT_ROOT,
                api_key="sk-test-value",
                base_url=config_manager.PUBLIC_ENDPOINTS["beijing"],
                model="qwen3.8-max",
                mode="not-a-mode",
            )

        self.assertEqual((self.home / "config.toml").read_bytes(), before)
        backup.assert_not_called()
        store.assert_not_called()

    @mock.patch("scripts.lib.config_manager.read_secret", return_value="")
    @mock.patch("scripts.lib.config_manager._codex_version", return_value="codex-test")
    def test_status_exposes_catalog_summaries_and_migrates_legacy_mode(
        self, _version: mock.Mock, _read: mock.Mock
    ) -> None:
        target_dir = self.home / "qwen-for-codex"
        target_dir.mkdir()
        (target_dir / "state.json").write_text(
            json.dumps(
                {
                    "schema": 1,
                    "model": "qwen3.8-max",
                    "base_url": config_manager.PUBLIC_ENDPOINTS["beijing"],
                }
            ),
            encoding="utf-8",
        )
        (self.home / "config.toml").write_text(
            f"{config_manager.DEFAULTS_BEGIN}\n{config_manager.DEFAULTS_END}\n"
            f"{config_manager.PROVIDER_BEGIN}\n{config_manager.PROVIDER_END}\n",
            encoding="utf-8",
        )

        result = config_manager.status(self.home, PROJECT_ROOT)

        self.assertTrue(result["installed"])
        self.assertEqual(result["mode"], config_manager.MODE_DIRECT)
        self.assertEqual(set(result["catalogs"]), {"direct", "aggregate"})
        self.assertEqual(len(result["catalogs"]["direct"]["models"]), 4)
        self.assertEqual(len(result["catalogs"]["aggregate"]["models"]), 8)
        for summary in result["catalogs"].values():
            self.assertEqual(summary["default_model"], "qwen3.8-max")
            self.assertTrue(summary["label"])
            self.assertTrue(
                all(set(model) == {"slug", "display_name", "description"} for model in summary["models"])
            )

    @mock.patch("scripts.lib.config_manager.read_secret", return_value="")
    @mock.patch("scripts.lib.config_manager._codex_version", return_value="codex-test")
    def test_status_ignores_non_object_state(
        self, _version: mock.Mock, _read: mock.Mock
    ) -> None:
        target_dir = self.home / "qwen-for-codex"
        target_dir.mkdir()
        (target_dir / "state.json").write_text("[]", encoding="utf-8")

        result = config_manager.status(self.home, PROJECT_ROOT)

        self.assertFalse(result["installed"])
        self.assertEqual(result["mode"], config_manager.MODE_DIRECT)
        self.assertIsNone(result["model"])

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

    @mock.patch("scripts.lib.config_manager.delete_secret")
    @mock.patch("scripts.lib.config_manager.store_secret")
    def test_switch_store_failure_keeps_active_direct_install(
        self, store: mock.Mock, delete: mock.Mock
    ) -> None:
        store.return_value = "test_store"
        config_manager.install(
            home=self.home,
            source_root=PROJECT_ROOT,
            api_key="sk-direct-value",
            base_url=config_manager.PUBLIC_ENDPOINTS["beijing"],
            mode=config_manager.MODE_DIRECT,
        )
        config_before = (self.home / "config.toml").read_bytes()
        state_path = self.home / "qwen-for-codex" / "state.json"
        state_before = state_path.read_bytes()
        parsed_before = tomllib.loads(config_before.decode("utf-8"))
        catalog_before = Path(parsed_before["model_catalog_json"]).read_bytes()
        store.side_effect = RuntimeError("credential write failed")

        with self.assertRaisesRegex(RuntimeError, "credential write failed"):
            config_manager.install(
                home=self.home,
                source_root=PROJECT_ROOT,
                api_key="sk-new-value",
                base_url=config_manager.PUBLIC_ENDPOINTS["beijing"],
                mode=config_manager.MODE_AGGREGATE,
            )

        self.assertEqual((self.home / "config.toml").read_bytes(), config_before)
        self.assertEqual(state_path.read_bytes(), state_before)
        self.assertEqual(Path(parsed_before["model_catalog_json"]).read_bytes(), catalog_before)
        delete.assert_called_once()

    @mock.patch("scripts.lib.config_manager.delete_secret")
    @mock.patch("scripts.lib.config_manager.store_secret", return_value="test_store")
    def test_first_install_state_failure_rolls_back_every_active_value(
        self, store: mock.Mock, delete: mock.Mock
    ) -> None:
        with mock.patch(
            "scripts.lib.config_manager._write_state", side_effect=OSError("state failed")
        ):
            with self.assertRaisesRegex(OSError, "state failed"):
                config_manager.install(
                    home=self.home,
                    source_root=PROJECT_ROOT,
                    api_key="sk-new-value",
                    base_url=config_manager.PUBLIC_ENDPOINTS["beijing"],
                    mode=config_manager.MODE_AGGREGATE,
                )

        self.assertEqual((self.home / "config.toml").read_text(encoding="utf-8"), self.original)
        self.assertFalse((self.home / "qwen-for-codex" / "state.json").exists())
        self.assertEqual(store.call_count, 1)
        delete.assert_called_once()

    @mock.patch("scripts.lib.config_manager.delete_secret")
    @mock.patch("scripts.lib.config_manager.store_secret", return_value="test_store")
    def test_switch_state_failure_restores_old_state_and_key(
        self, store: mock.Mock, _delete: mock.Mock
    ) -> None:
        config_manager.install(
            home=self.home,
            source_root=PROJECT_ROOT,
            api_key="sk-old-value",
            base_url=config_manager.PUBLIC_ENDPOINTS["beijing"],
            mode=config_manager.MODE_DIRECT,
        )
        config_before = (self.home / "config.toml").read_bytes()
        state_path = self.home / "qwen-for-codex" / "state.json"
        state_before = state_path.read_bytes()
        self.read_secret_for_update.return_value = "sk-old-value"

        with mock.patch(
            "scripts.lib.config_manager._write_state", side_effect=OSError("state failed")
        ):
            with self.assertRaisesRegex(OSError, "state failed"):
                config_manager.install(
                    home=self.home,
                    source_root=PROJECT_ROOT,
                    api_key="sk-new-value",
                    base_url=config_manager.PUBLIC_ENDPOINTS["beijing"],
                    mode=config_manager.MODE_AGGREGATE,
                )

        self.assertEqual((self.home / "config.toml").read_bytes(), config_before)
        self.assertEqual(state_path.read_bytes(), state_before)
        self.assertEqual(store.call_args_list[-1].args[0], "sk-old-value")

    @mock.patch("scripts.lib.config_manager.delete_secret")
    @mock.patch("scripts.lib.config_manager.store_secret", return_value="test_store")
    def test_uninstall_state_failure_restores_installed_config_and_key(
        self, store: mock.Mock, delete: mock.Mock
    ) -> None:
        config_manager.install(
            home=self.home,
            source_root=PROJECT_ROOT,
            api_key="sk-old-value",
            base_url=config_manager.PUBLIC_ENDPOINTS["beijing"],
        )
        config_before = (self.home / "config.toml").read_bytes()
        state_path = self.home / "qwen-for-codex" / "state.json"
        state_before = state_path.read_bytes()
        self.read_secret_for_update.return_value = "sk-old-value"

        with mock.patch(
            "scripts.lib.config_manager._write_state", side_effect=OSError("state failed")
        ):
            with self.assertRaisesRegex(OSError, "state failed"):
                config_manager.uninstall(self.home)

        self.assertEqual((self.home / "config.toml").read_bytes(), config_before)
        self.assertEqual(state_path.read_bytes(), state_before)
        delete.assert_called_once()
        self.assertEqual(store.call_args_list[-1].args[0], "sk-old-value")

    @mock.patch("scripts.lib.config_manager.store_secret")
    def test_cross_process_lock_rejects_overlapping_change(self, store: mock.Mock) -> None:
        config_before = (self.home / "config.toml").read_bytes()
        target_dir = config_manager.runtime_dir(self.home)

        with config_manager._operation_lock(target_dir):
            with self.assertRaises(config_manager.OperationBusyError):
                config_manager.install(
                    home=self.home,
                    source_root=PROJECT_ROOT,
                    api_key="sk-new-value",
                    base_url=config_manager.PUBLIC_ENDPOINTS["beijing"],
                )

        self.assertEqual((self.home / "config.toml").read_bytes(), config_before)
        store.assert_not_called()

    @mock.patch("scripts.lib.config_manager.store_secret", return_value="test_store")
    def test_managed_config_with_missing_or_corrupt_state_fails_closed(
        self, _store: mock.Mock
    ) -> None:
        config_manager.install(
            home=self.home,
            source_root=PROJECT_ROOT,
            api_key="sk-old-value",
            base_url=config_manager.PUBLIC_ENDPOINTS["beijing"],
        )
        config_before = (self.home / "config.toml").read_bytes()
        state_path = self.home / "qwen-for-codex" / "state.json"

        for state_content in (None, "{not-json"):
            with self.subTest(state_content=state_content):
                if state_content is None:
                    state_path.unlink(missing_ok=True)
                else:
                    state_path.write_text(state_content, encoding="utf-8")
                with self.assertRaises(config_manager.ConfigError):
                    config_manager.install(
                        home=self.home,
                        source_root=PROJECT_ROOT,
                        api_key="sk-new-value",
                        base_url=config_manager.PUBLIC_ENDPOINTS["beijing"],
                        mode=config_manager.MODE_AGGREGATE,
                    )
                self.assertEqual((self.home / "config.toml").read_bytes(), config_before)

    def test_array_table_model_key_is_not_treated_as_top_level(self) -> None:
        text = '[[profiles]]\nname = "demo"\nmodel = "nested-model"\n'
        cleaned, previous = config_manager._remove_top_level_keys(text)

        self.assertEqual(cleaned, text)
        self.assertEqual(previous, {})


if __name__ == "__main__":
    unittest.main()
