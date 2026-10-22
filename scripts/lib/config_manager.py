from __future__ import annotations

import json
import getpass
import os
import platform
import re
import shutil
import subprocess
import tempfile
import time
import tomllib
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .credential_store import delete_secret, read_secret, store_secret


DEFAULTS_BEGIN = "# >>> qwen-for-codex defaults >>>"
DEFAULTS_END = "# <<< qwen-for-codex defaults <<<"
PROVIDER_BEGIN = "# >>> qwen-for-codex provider >>>"
PROVIDER_END = "# <<< qwen-for-codex provider <<<"
MANAGED_KEYS = ("model", "model_provider", "model_reasoning_effort", "model_catalog_json")
PROVIDER_ID = "qwen_model_studio"
VALID_MODELS = {
    "qwen3.8-max",
    "qwen3.8-flash",
    "qwen3.8-27b",
    "qwen3.7-plus",
    "qwen3.7-flash",
}
REGION_HOSTS = {
    "beijing": "cn-beijing.maas.aliyuncs.com",
    "singapore": "ap-southeast-1.maas.aliyuncs.com",
    "hongkong": "cn-hongkong.maas.aliyuncs.com",
    "virginia": "us-east-1.maas.aliyuncs.com",
    "frankfurt": "eu-central-1.maas.aliyuncs.com",
    "tokyo": "ap-northeast-1.maas.aliyuncs.com",
}
PUBLIC_ENDPOINTS = {
    "beijing": "https://dashscope.aliyuncs.com/compatible-mode/v1",
    "singapore": "https://dashscope-intl.aliyuncs.com/compatible-mode/v1",
}


class ConfigError(RuntimeError):
    pass


def codex_home(override: str | None = None) -> Path:
    if override:
        return Path(override).expanduser().resolve()
    configured = os.environ.get("CODEX_HOME")
    return Path(configured).expanduser().resolve() if configured else Path.home() / ".codex"


def runtime_dir(home: Path) -> Path:
    return home / "qwen-for-codex"


def build_base_url(region: str, workspace_id: str = "") -> str:
    if region not in REGION_HOSTS:
        raise ConfigError("不支持的百炼地域")
    workspace = workspace_id.strip()
    if workspace:
        if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_-]{2,63}", workspace):
            raise ConfigError("业务空间 ID 格式无效")
        return f"https://{workspace}.{REGION_HOSTS[region]}/compatible-mode/v1"
    if region not in PUBLIC_ENDPOINTS:
        raise ConfigError("该地域需要填写业务空间 ID")
    return PUBLIC_ENDPOINTS[region]


def _toml_string(value: str) -> str:
    return json.dumps(value, ensure_ascii=False)


def _atomic_write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    handle, temporary = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".tmp", dir=path.parent)
    temporary_path = Path(temporary)
    try:
        with os.fdopen(handle, "w", encoding="utf-8", newline="") as stream:
            stream.write(content)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary_path, path)
    finally:
        if temporary_path.exists():
            temporary_path.unlink()


def _strip_marked_block(text: str, begin: str, end: str) -> str:
    lines = text.splitlines(keepends=True)
    output: list[str] = []
    skipping = False
    found_begin = False
    for line in lines:
        if line.strip() == begin:
            if skipping:
                raise ConfigError("Codex 配置中的管理标记发生嵌套")
            skipping = True
            found_begin = True
            continue
        if line.strip() == end:
            if not skipping:
                raise ConfigError("Codex 配置中的结束标记没有对应开始标记")
            skipping = False
            continue
        if not skipping:
            output.append(line)
    if skipping:
        raise ConfigError("Codex 配置中的管理块没有结束标记")
    return "".join(output) if found_begin else text


def strip_managed_blocks(text: str) -> str:
    text = _strip_marked_block(text, DEFAULTS_BEGIN, DEFAULTS_END)
    return _strip_marked_block(text, PROVIDER_BEGIN, PROVIDER_END)


def _remove_top_level_keys(text: str) -> tuple[str, dict[str, str]]:
    lines = text.splitlines(keepends=True)
    output: list[str] = []
    previous: dict[str, str] = {}
    in_table = False
    pattern = re.compile(r"^\s*([A-Za-z0-9_-]+)\s*=")
    for line in lines:
        stripped = line.lstrip()
        if stripped.startswith("[") and not stripped.startswith("[["):
            in_table = True
        match = pattern.match(line)
        if not in_table and match and match.group(1) in MANAGED_KEYS:
            previous[match.group(1)] = line.rstrip("\r\n")
            continue
        output.append(line)
    return "".join(output), previous


def _restore_top_level(text: str, previous: dict[str, str]) -> str:
    if not previous:
        return text.lstrip("\r\n")
    ordered = [previous[key] for key in MANAGED_KEYS if key in previous]
    return "\n".join(ordered) + "\n\n" + text.lstrip("\r\n")


def _validate_toml(text: str) -> None:
    try:
        tomllib.loads(text or "")
    except tomllib.TOMLDecodeError as exc:
        raise ConfigError(f"Codex 配置不是有效 TOML：{exc}") from exc


def _backup(config_path: Path, target_dir: Path) -> Path:
    target_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    destination = target_dir / f"config-{stamp}.toml"
    counter = 1
    while destination.exists():
        destination = target_dir / f"config-{stamp}-{counter}.toml"
        counter += 1
    if config_path.exists():
        shutil.copy2(config_path, destination)
    else:
        destination.write_text("", encoding="utf-8")
    return destination


def _load_state(target_dir: Path) -> dict[str, Any]:
    path = target_dir / "state.json"
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}


def _write_state(target_dir: Path, state: dict[str, Any]) -> None:
    _atomic_write(target_dir / "state.json", json.dumps(state, ensure_ascii=False, indent=2) + "\n")


def _copy_runtime_files(source_root: Path, target_dir: Path) -> tuple[Path, str, list[str]]:
    target_dir.mkdir(parents=True, exist_ok=True)
    catalog_source = source_root / "assets" / "qwen-model-catalog.json"
    catalog_target = target_dir / "model-catalog.json"
    if not catalog_source.exists():
        raise ConfigError(f"安装资源缺失：{catalog_source.name}")
    shutil.copy2(catalog_source, catalog_target)

    system = platform.system()
    if system == "Windows":
        helper_source = source_root / "scripts" / "runtime" / "read_windows_credential.ps1"
        helper_target = target_dir / "read_windows_credential.ps1"
        if not helper_source.exists():
            raise ConfigError(f"安装资源缺失：{helper_source.name}")
        shutil.copy2(helper_source, helper_target)
        return (
            catalog_target,
            "powershell.exe",
            ["-NoProfile", "-NonInteractive", "-ExecutionPolicy", "Bypass", "-File", str(helper_target)],
        )
    if system == "Darwin":
        return (
            catalog_target,
            "/usr/bin/security",
            ["find-generic-password", "-a", getpass.getuser(), "-s", "QwenForCodex-DashScope", "-w"],
        )
    raise ConfigError("当前版本只支持 Windows 和 macOS")


def _config_blocks(
    base_url: str,
    model: str,
    catalog_path: Path,
    auth_command: str,
    auth_args: list[str],
) -> tuple[str, str]:
    defaults = "\n".join(
        [
            DEFAULTS_BEGIN,
            f"model = {_toml_string(model)}",
            f"model_provider = {_toml_string(PROVIDER_ID)}",
            'model_reasoning_effort = "xhigh"',
            f"model_catalog_json = {_toml_string(str(catalog_path))}",
            DEFAULTS_END,
        ]
    )
    provider = "\n".join(
        [
            PROVIDER_BEGIN,
            f"[model_providers.{PROVIDER_ID}]",
            'name = "Alibaba Cloud Model Studio · Qwen"',
            f"base_url = {_toml_string(base_url)}",
            'wire_api = "responses"',
            "supports_websockets = false",
            "",
            f"[model_providers.{PROVIDER_ID}.auth]",
            f"command = {_toml_string(auth_command)}",
            f"args = [{', '.join(_toml_string(value) for value in auth_args)}]",
            "timeout_ms = 5000",
            "refresh_interval_ms = 0",
            PROVIDER_END,
        ]
    )
    return defaults, provider


def install(
    *,
    home: Path,
    source_root: Path,
    api_key: str,
    base_url: str,
    model: str,
) -> dict[str, Any]:
    if model not in VALID_MODELS:
        raise ConfigError("不支持的默认模型")
    config_path = home / "config.toml"
    target_dir = runtime_dir(home)
    current = config_path.read_text(encoding="utf-8") if config_path.exists() else ""
    _validate_toml(current)
    state = _load_state(target_dir)
    had_managed = DEFAULTS_BEGIN in current or PROVIDER_BEGIN in current
    baseline = strip_managed_blocks(current)
    if had_managed and state.get("previous_top_level"):
        baseline = _restore_top_level(baseline, state["previous_top_level"])
    baseline, detected_previous = _remove_top_level_keys(baseline)
    previous = state.get("previous_top_level") if had_managed else detected_previous
    if not isinstance(previous, dict):
        previous = detected_previous

    parsed_baseline = tomllib.loads(baseline or "")
    existing_provider = parsed_baseline.get("model_providers", {}).get(PROVIDER_ID)
    if existing_provider:
        raise ConfigError(f"配置中已存在未受本工具管理的提供商：{PROVIDER_ID}")

    current_backup = _backup(config_path, target_dir / "backups")
    baseline_backup = state.get("baseline_backup")
    if not baseline_backup or not Path(baseline_backup).exists():
        baseline_backup = str(current_backup)

    catalog_path, auth_command, auth_args = _copy_runtime_files(source_root, target_dir)
    credential_method = store_secret(api_key, target_dir)
    defaults, provider = _config_blocks(
        base_url,
        model,
        catalog_path.resolve(),
        auth_command,
        auth_args,
    )
    merged = f"{defaults}\n\n{baseline.strip()}\n\n{provider}\n"
    _validate_toml(merged)
    _atomic_write(config_path, merged)
    state = {
        "schema": 1,
        "installed_at": datetime.now(timezone.utc).isoformat(),
        "baseline_backup": baseline_backup,
        "latest_backup": str(current_backup),
        "previous_top_level": previous,
        "model": model,
        "base_url": base_url,
        "credential_method": credential_method,
    }
    _write_state(target_dir, state)
    return {
        "installed": True,
        "model": model,
        "base_url": base_url,
        "backup": str(current_backup),
        "credential_method": credential_method,
        "config_path": str(config_path),
        "restart_required": True,
    }


def uninstall(home: Path, remove_credential: bool = True) -> dict[str, Any]:
    config_path = home / "config.toml"
    target_dir = runtime_dir(home)
    state = _load_state(target_dir)
    if not config_path.exists():
        if remove_credential:
            delete_secret(target_dir)
        return {"installed": False, "changed": False}
    current = config_path.read_text(encoding="utf-8")
    _validate_toml(current)
    has_managed_marker = any(
        marker in current
        for marker in (DEFAULTS_BEGIN, DEFAULTS_END, PROVIDER_BEGIN, PROVIDER_END)
    )
    if not has_managed_marker:
        if remove_credential:
            delete_secret(target_dir)
        return {"installed": False, "changed": False}
    cleaned = strip_managed_blocks(current)
    cleaned, _ = _remove_top_level_keys(cleaned)
    previous = state.get("previous_top_level", {})
    if isinstance(previous, dict):
        cleaned = _restore_top_level(cleaned, previous)
    _validate_toml(cleaned)
    backup = _backup(config_path, target_dir / "backups")
    _atomic_write(config_path, cleaned.rstrip() + "\n")
    if remove_credential:
        delete_secret(target_dir)
    state["uninstalled_at"] = datetime.now(timezone.utc).isoformat()
    state["latest_backup"] = str(backup)
    _write_state(target_dir, state)
    return {"installed": False, "changed": True, "backup": str(backup), "restart_required": True}


def _codex_version() -> str | None:
    try:
        result = subprocess.run(
            ["codex", "--version"], check=False, capture_output=True, text=True, timeout=5
        )
        return result.stdout.strip() if result.returncode == 0 else None
    except (OSError, subprocess.SubprocessError):
        return None


def status(home: Path) -> dict[str, Any]:
    config_path = home / "config.toml"
    target_dir = runtime_dir(home)
    text = config_path.read_text(encoding="utf-8") if config_path.exists() else ""
    state = _load_state(target_dir)
    installed = DEFAULTS_BEGIN in text and PROVIDER_BEGIN in text
    codex_version = _codex_version()
    return {
        "installed": installed,
        "codex_detected": codex_version is not None,
        "codex_version": codex_version,
        "codex_home": str(home),
        "config_path": str(config_path),
        "credential_saved": bool(read_secret(target_dir)),
        "model": state.get("model"),
        "base_url": state.get("base_url"),
        "credential_method": state.get("credential_method"),
        "restart_required": False,
    }
