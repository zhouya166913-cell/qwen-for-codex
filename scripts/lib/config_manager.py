from __future__ import annotations

import getpass
import hashlib
import json
import os
import platform
import re
import shutil
import subprocess
import tempfile
import tomllib
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterator

from .credential_store import delete_secret, read_secret, read_secret_for_update, store_secret


DEFAULTS_BEGIN = "# >>> qwen-for-codex defaults >>>"
DEFAULTS_END = "# <<< qwen-for-codex defaults <<<"
PROVIDER_BEGIN = "# >>> qwen-for-codex provider >>>"
PROVIDER_END = "# <<< qwen-for-codex provider <<<"
MANAGED_KEYS = ("model", "model_provider", "model_reasoning_effort", "model_catalog_json")
PROVIDER_ID = "qwen_model_studio"
MODE_DIRECT = "direct"
MODE_AGGREGATE = "aggregate"
DEFAULT_MODE = MODE_DIRECT
MODE_CONFIG: dict[str, dict[str, str]] = {
    MODE_DIRECT: {
        "label": "仅千问",
        "catalog_filename": "qwen-model-catalog.json",
        "provider_name": "Alibaba Cloud Model Studio · Qwen",
        "default_model": "qwen3.8-max",
    },
    MODE_AGGREGATE: {
        "label": "聚合模型",
        "catalog_filename": "aggregate-model-catalog.json",
        "provider_name": "Alibaba Cloud Model Studio · Qwen / DeepSeek / GLM",
        "default_model": "qwen3.8-max",
    },
}
VALID_MODES = frozenset(MODE_CONFIG)
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


class OperationBusyError(ConfigError):
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


def _atomic_write_bytes(path: Path, content: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    handle, temporary = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".tmp", dir=path.parent)
    temporary_path = Path(temporary)
    try:
        with os.fdopen(handle, "wb") as stream:
            stream.write(content)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary_path, path)
    finally:
        if temporary_path.exists():
            temporary_path.unlink()


@contextmanager
def _operation_lock(target_dir: Path) -> Iterator[None]:
    """Serialize configuration changes across tabs and launcher processes."""

    target_dir.mkdir(parents=True, exist_ok=True)
    lock_path = target_dir / "operation.lock"
    stream = lock_path.open("a+b")
    locked = False
    try:
        stream.seek(0, os.SEEK_END)
        if stream.tell() == 0:
            stream.write(b"\0")
            stream.flush()
        stream.seek(0)
        try:
            if os.name == "nt":
                import msvcrt

                msvcrt.locking(stream.fileno(), msvcrt.LK_NBLCK, 1)
            else:
                import fcntl

                fcntl.flock(stream.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError as exc:
            raise OperationBusyError("另一个配置操作正在进行，请稍后再试。") from exc
        locked = True
        yield
    finally:
        if locked:
            try:
                stream.seek(0)
                if os.name == "nt":
                    import msvcrt

                    msvcrt.locking(stream.fileno(), msvcrt.LK_UNLCK, 1)
                else:
                    import fcntl

                    fcntl.flock(stream.fileno(), fcntl.LOCK_UN)
            except OSError:
                pass
        stream.close()


def _snapshot_text(path: Path) -> tuple[bool, str]:
    return (True, path.read_text(encoding="utf-8")) if path.exists() else (False, "")


def _restore_text(path: Path, snapshot: tuple[bool, str]) -> None:
    existed, content = snapshot
    if existed:
        _atomic_write(path, content)
    else:
        path.unlink(missing_ok=True)


def _restore_credential(previous_secret: str | None, target_dir: Path) -> None:
    if previous_secret:
        store_secret(previous_secret, target_dir)
    else:
        delete_secret(target_dir)


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
        if stripped.startswith("["):
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
        state = json.loads(path.read_text(encoding="utf-8"))
        return state if isinstance(state, dict) else {}
    except (OSError, json.JSONDecodeError):
        return {}


def _load_state_for_update(target_dir: Path, *, managed_config: bool) -> dict[str, Any]:
    path = target_dir / "state.json"
    if not path.exists():
        if managed_config:
            raise ConfigError(
                "检测到本工具配置，但恢复信息已丢失。为避免覆盖原配置，本次未执行；"
                f"请先检查备份目录：{target_dir / 'backups'}"
            )
        return {}
    try:
        state = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ConfigError(
            "恢复信息已损坏。为避免覆盖原配置，本次未执行；"
            f"请先检查备份目录：{target_dir / 'backups'}"
        ) from exc
    if not isinstance(state, dict):
        raise ConfigError("恢复信息格式无效，本次未修改 Codex 配置。")
    if managed_config and not isinstance(state.get("previous_top_level"), dict):
        raise ConfigError(
            "恢复信息不完整。为避免无法还原 ChatGPT 配置，本次未执行；"
            f"请先检查备份目录：{target_dir / 'backups'}"
        )
    return state


def _write_state(target_dir: Path, state: dict[str, Any]) -> None:
    _atomic_write(target_dir / "state.json", json.dumps(state, ensure_ascii=False, indent=2) + "\n")


def _mode_config(mode: str) -> dict[str, str]:
    config = MODE_CONFIG.get(mode)
    if config is None:
        raise ConfigError("不支持的接入方式，请刷新设置页后重试")
    return config


def _load_catalog(source_root: Path, mode: str) -> tuple[Path, dict[str, Any]]:
    mode_config = _mode_config(mode)
    catalog_path = source_root / "assets" / mode_config["catalog_filename"]
    if not catalog_path.is_file():
        raise ConfigError(f"安装资源缺失：{catalog_path.name}")
    try:
        catalog = json.loads(catalog_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ConfigError(f"模型目录无效：{catalog_path.name}") from exc
    models = catalog.get("models") if isinstance(catalog, dict) else None
    if not isinstance(models, list) or not models:
        raise ConfigError(f"模型目录无效：{catalog_path.name}")
    seen: set[str] = set()
    for item in models:
        if not isinstance(item, dict):
            raise ConfigError(f"模型目录无效：{catalog_path.name}")
        slug = item.get("slug")
        display_name = item.get("display_name")
        description = item.get("description")
        if (
            not isinstance(slug, str)
            or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]{0,127}", slug)
            or not isinstance(display_name, str)
            or not display_name.strip()
            or not isinstance(description, str)
            or not description.strip()
            or slug in seen
        ):
            raise ConfigError(f"模型目录无效：{catalog_path.name}")
        seen.add(slug)
    if mode_config["default_model"] not in seen:
        raise ConfigError(f"模型目录缺少默认模型：{mode_config['default_model']}")
    return catalog_path, catalog


def catalog_summaries(source_root: Path) -> dict[str, dict[str, Any]]:
    summaries: dict[str, dict[str, Any]] = {}
    for mode in (MODE_AGGREGATE, MODE_DIRECT):
        _, catalog = _load_catalog(source_root, mode)
        mode_config = _mode_config(mode)
        summaries[mode] = {
            "label": mode_config["label"],
            "default_model": mode_config["default_model"],
            "models": [
                {
                    "slug": item["slug"],
                    "display_name": item["display_name"],
                    "description": item["description"],
                }
                for item in catalog["models"]
            ],
        }
    return summaries


def _content_addressed_copy(source: Path, target_dir: Path, stem: str) -> Path:
    try:
        content = source.read_bytes()
    except OSError as exc:
        raise ConfigError(f"安装资源无法读取：{source.name}") from exc
    digest = hashlib.sha256(content).hexdigest()[:16]
    target = target_dir / f"{stem}-{digest}{source.suffix}"
    if not target.exists() or target.read_bytes() != content:
        _atomic_write_bytes(target, content)
    return target


def _copy_runtime_files(
    source_root: Path, target_dir: Path, mode: str
) -> tuple[Path, str, list[str]]:
    catalog_source, _ = _load_catalog(source_root, mode)
    target_dir.mkdir(parents=True, exist_ok=True)
    catalog_target = _content_addressed_copy(catalog_source, target_dir, f"model-catalog-{mode}")

    system = platform.system()
    if system == "Windows":
        helper_source = source_root / "scripts" / "runtime" / "read_windows_credential.ps1"
        if not helper_source.exists():
            raise ConfigError(f"安装资源缺失：{helper_source.name}")
        helper_target = _content_addressed_copy(
            helper_source, target_dir, "read-windows-credential"
        )
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
    provider_name: str,
) -> tuple[str, str]:
    defaults = "\n".join(
        [
            DEFAULTS_BEGIN,
            f"model = {_toml_string(model)}",
            f"model_provider = {_toml_string(PROVIDER_ID)}",
            f"model_catalog_json = {_toml_string(str(catalog_path))}",
            DEFAULTS_END,
        ]
    )
    provider = "\n".join(
        [
            PROVIDER_BEGIN,
            f"[model_providers.{PROVIDER_ID}]",
            f"name = {_toml_string(provider_name)}",
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
    model: str | None = None,
    mode: str = DEFAULT_MODE,
) -> dict[str, Any]:
    mode_config = _mode_config(mode)
    _, catalog = _load_catalog(source_root, mode)
    selected_model = model or mode_config["default_model"]
    valid_models = {item["slug"] for item in catalog["models"]}
    if selected_model not in valid_models:
        raise ConfigError("不支持的默认模型")
    config_path = home / "config.toml"
    target_dir = runtime_dir(home)
    with _operation_lock(target_dir):
        config_snapshot = _snapshot_text(config_path)
        state_path = target_dir / "state.json"
        state_snapshot = _snapshot_text(state_path)
        current = config_snapshot[1]
        _validate_toml(current)
        had_managed = DEFAULTS_BEGIN in current or PROVIDER_BEGIN in current
        state = _load_state_for_update(target_dir, managed_config=had_managed)
        previous_secret = read_secret_for_update(target_dir)

        baseline = strip_managed_blocks(current)
        if had_managed:
            baseline = _restore_top_level(baseline, state["previous_top_level"])
        baseline, detected_previous = _remove_top_level_keys(baseline)
        previous = state.get("previous_top_level") if had_managed else detected_previous
        if not isinstance(previous, dict):
            previous = detected_previous

        parsed_baseline = tomllib.loads(baseline or "")
        existing_provider = parsed_baseline.get("model_providers", {}).get(PROVIDER_ID)
        if existing_provider:
            raise ConfigError(f"配置中已存在未受本工具管理的提供商：{PROVIDER_ID}")

        catalog_path, auth_command, auth_args = _copy_runtime_files(source_root, target_dir, mode)
        defaults, provider = _config_blocks(
            base_url,
            selected_model,
            catalog_path.resolve(),
            auth_command,
            auth_args,
            mode_config["provider_name"],
        )
        merged = f"{defaults}\n\n{baseline.strip()}\n\n{provider}\n"
        _validate_toml(merged)

        current_backup = _backup(config_path, target_dir / "backups")
        baseline_backup = state.get("baseline_backup")
        if not baseline_backup or not Path(baseline_backup).exists():
            baseline_backup = str(current_backup)

        credential_touched = False
        config_write_started = False
        try:
            credential_touched = True
            credential_method = store_secret(api_key, target_dir)
            next_state = {
                "schema": 2,
                "installed_at": datetime.now(timezone.utc).isoformat(),
                "baseline_backup": baseline_backup,
                "latest_backup": str(current_backup),
                "previous_top_level": previous,
                "mode": mode,
                "model": selected_model,
                "base_url": base_url,
                "credential_method": credential_method,
            }
            _write_state(target_dir, next_state)
            if _snapshot_text(config_path) != config_snapshot:
                raise ConfigError("检测到 Codex 配置刚刚被其他程序修改，本次切换已取消。")
            config_write_started = True
            _atomic_write(config_path, merged)
        except Exception as exc:
            rollback_errors: list[str] = []
            if config_write_started:
                try:
                    _restore_text(config_path, config_snapshot)
                except Exception:
                    rollback_errors.append("Codex 配置")
            try:
                _restore_text(state_path, state_snapshot)
            except Exception:
                rollback_errors.append("恢复信息")
            if credential_touched:
                try:
                    _restore_credential(previous_secret, target_dir)
                except Exception:
                    rollback_errors.append("API Key")
            if rollback_errors:
                parts = "、".join(rollback_errors)
                raise ConfigError(
                    f"切换失败，且以下内容无法自动回滚：{parts}。请不要重开 Codex，先从备份恢复。"
                ) from exc
            raise

        return {
            "installed": True,
            "mode": mode,
            "model": selected_model,
            "model_count": len(catalog["models"]),
            "provider_name": mode_config["provider_name"],
            "base_url": base_url,
            "backup": str(current_backup),
            "credential_method": credential_method,
            "config_path": str(config_path),
            "restart_required": True,
        }


def uninstall(home: Path, remove_credential: bool = True) -> dict[str, Any]:
    config_path = home / "config.toml"
    target_dir = runtime_dir(home)
    with _operation_lock(target_dir):
        config_snapshot = _snapshot_text(config_path)
        state_path = target_dir / "state.json"
        state_snapshot = _snapshot_text(state_path)
        current = config_snapshot[1]
        if current:
            _validate_toml(current)
        has_managed_marker = any(
            marker in current
            for marker in (DEFAULTS_BEGIN, DEFAULTS_END, PROVIDER_BEGIN, PROVIDER_END)
        )
        if not config_snapshot[0] or not has_managed_marker:
            if remove_credential:
                delete_secret(target_dir)
            return {"installed": False, "changed": False}

        state = _load_state_for_update(target_dir, managed_config=True)
        previous_secret = read_secret_for_update(target_dir) if remove_credential else None
        cleaned = strip_managed_blocks(current)
        cleaned, _ = _remove_top_level_keys(cleaned)
        cleaned = _restore_top_level(cleaned, state["previous_top_level"])
        cleaned = cleaned.rstrip() + "\n"
        _validate_toml(cleaned)
        backup = _backup(config_path, target_dir / "backups")
        next_state = dict(state)
        next_state["uninstalled_at"] = datetime.now(timezone.utc).isoformat()
        next_state["latest_backup"] = str(backup)

        credential_touched = False
        config_write_started = False
        try:
            if remove_credential:
                credential_touched = True
                delete_secret(target_dir)
            _write_state(target_dir, next_state)
            if _snapshot_text(config_path) != config_snapshot:
                raise ConfigError("检测到 Codex 配置刚刚被其他程序修改，本次还原已取消。")
            config_write_started = True
            _atomic_write(config_path, cleaned)
        except Exception as exc:
            rollback_errors: list[str] = []
            if config_write_started:
                try:
                    _restore_text(config_path, config_snapshot)
                except Exception:
                    rollback_errors.append("Codex 配置")
            try:
                _restore_text(state_path, state_snapshot)
            except Exception:
                rollback_errors.append("恢复信息")
            if credential_touched:
                try:
                    _restore_credential(previous_secret, target_dir)
                except Exception:
                    rollback_errors.append("API Key")
            if rollback_errors:
                parts = "、".join(rollback_errors)
                raise ConfigError(
                    f"还原失败，且以下内容无法自动回滚：{parts}。请不要重开 Codex，先从备份恢复。"
                ) from exc
            raise

        return {
            "installed": False,
            "changed": True,
            "backup": str(backup),
            "restart_required": True,
        }


def _codex_version() -> str | None:
    try:
        result = subprocess.run(
            ["codex", "--version"], check=False, capture_output=True, text=True, timeout=5
        )
        return result.stdout.strip() if result.returncode == 0 else None
    except (OSError, subprocess.SubprocessError):
        return None


def status(home: Path, source_root: Path | None = None) -> dict[str, Any]:
    config_path = home / "config.toml"
    target_dir = runtime_dir(home)
    text = config_path.read_text(encoding="utf-8") if config_path.exists() else ""
    state = _load_state(target_dir)
    installed = DEFAULTS_BEGIN in text and PROVIDER_BEGIN in text
    saved_mode = state.get("mode", DEFAULT_MODE)
    mode = saved_mode if saved_mode in VALID_MODES else DEFAULT_MODE
    codex_version = _codex_version()
    result = {
        "installed": installed,
        "codex_detected": codex_version is not None,
        "codex_version": codex_version,
        "codex_home": str(home),
        "config_path": str(config_path),
        "credential_saved": bool(read_secret(target_dir)),
        "mode": mode,
        "model": state.get("model"),
        "base_url": state.get("base_url"),
        "credential_method": state.get("credential_method"),
        "restart_required": False,
    }
    if source_root is not None:
        result["catalogs"] = catalog_summaries(source_root)
    return result
