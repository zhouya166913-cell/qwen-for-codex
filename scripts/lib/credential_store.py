from __future__ import annotations

import ctypes
import ctypes.wintypes
import getpass
import os
import platform
import subprocess
from pathlib import Path


SERVICE_NAME = "QwenForCodex-DashScope"
WINDOWS_TARGET = "QwenForCodex:DashScopeAPIKey"
FALLBACK_FILE = "credential.key"


class CredentialError(RuntimeError):
    pass


def _fallback_path(runtime_dir: Path) -> Path:
    return runtime_dir / FALLBACK_FILE


def _store_private_file(secret: str, runtime_dir: Path) -> str:
    path = _fallback_path(runtime_dir)
    runtime_dir.mkdir(parents=True, exist_ok=True)
    path.write_text(secret, encoding="utf-8")
    try:
        os.chmod(path, 0o600)
    except OSError:
        pass
    return "private_file"


def _read_private_file(runtime_dir: Path) -> str | None:
    path = _fallback_path(runtime_dir)
    if not path.exists():
        return None
    value = path.read_text(encoding="utf-8").strip()
    return value or None


def _delete_private_file(runtime_dir: Path) -> None:
    path = _fallback_path(runtime_dir)
    if path.exists():
        path.unlink()


class _CredentialW(ctypes.Structure):
    _fields_ = [
        ("Flags", ctypes.wintypes.DWORD),
        ("Type", ctypes.wintypes.DWORD),
        ("TargetName", ctypes.wintypes.LPWSTR),
        ("Comment", ctypes.wintypes.LPWSTR),
        ("LastWritten", ctypes.wintypes.FILETIME),
        ("CredentialBlobSize", ctypes.wintypes.DWORD),
        ("CredentialBlob", ctypes.POINTER(ctypes.c_ubyte)),
        ("Persist", ctypes.wintypes.DWORD),
        ("AttributeCount", ctypes.wintypes.DWORD),
        ("Attributes", ctypes.c_void_p),
        ("TargetAlias", ctypes.wintypes.LPWSTR),
        ("UserName", ctypes.wintypes.LPWSTR),
    ]


def _windows_api():
    advapi32 = ctypes.WinDLL("Advapi32.dll", use_last_error=True)
    advapi32.CredWriteW.argtypes = [ctypes.POINTER(_CredentialW), ctypes.wintypes.DWORD]
    advapi32.CredWriteW.restype = ctypes.wintypes.BOOL
    advapi32.CredReadW.argtypes = [
        ctypes.wintypes.LPCWSTR,
        ctypes.wintypes.DWORD,
        ctypes.wintypes.DWORD,
        ctypes.POINTER(ctypes.POINTER(_CredentialW)),
    ]
    advapi32.CredReadW.restype = ctypes.wintypes.BOOL
    advapi32.CredDeleteW.argtypes = [ctypes.wintypes.LPCWSTR, ctypes.wintypes.DWORD, ctypes.wintypes.DWORD]
    advapi32.CredDeleteW.restype = ctypes.wintypes.BOOL
    advapi32.CredFree.argtypes = [ctypes.c_void_p]
    return advapi32


def _store_windows(secret: str) -> str:
    api = _windows_api()
    encoded = secret.encode("utf-16-le")
    blob = ctypes.create_string_buffer(encoded)
    credential = _CredentialW()
    credential.Type = 1  # CRED_TYPE_GENERIC
    credential.TargetName = WINDOWS_TARGET
    credential.CredentialBlobSize = len(encoded)
    credential.CredentialBlob = ctypes.cast(blob, ctypes.POINTER(ctypes.c_ubyte))
    credential.Persist = 2  # CRED_PERSIST_LOCAL_MACHINE
    credential.UserName = getpass.getuser()
    if not api.CredWriteW(ctypes.byref(credential), 0):
        raise CredentialError(f"Windows 凭据管理器写入失败（错误 {ctypes.get_last_error()}）")
    return "windows_credential_manager"


def _read_windows() -> str | None:
    api = _windows_api()
    pointer = ctypes.POINTER(_CredentialW)()
    if not api.CredReadW(WINDOWS_TARGET, 1, 0, ctypes.byref(pointer)):
        error = ctypes.get_last_error()
        if error == 1168:  # ERROR_NOT_FOUND
            return None
        raise CredentialError(f"Windows 凭据管理器读取失败（错误 {error}）")
    try:
        credential = pointer.contents
        raw = ctypes.string_at(credential.CredentialBlob, credential.CredentialBlobSize)
        return raw.decode("utf-16-le").strip() or None
    finally:
        api.CredFree(pointer)


def _delete_windows() -> None:
    api = _windows_api()
    if not api.CredDeleteW(WINDOWS_TARGET, 1, 0):
        error = ctypes.get_last_error()
        if error != 1168:
            raise CredentialError(f"Windows 凭据管理器删除失败（错误 {error}）")


def _run_security(args: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["security", *args],
        check=False,
        capture_output=True,
        text=True,
        timeout=10,
    )


def _store_macos(secret: str) -> str:
    result = _run_security(
        ["add-generic-password", "-U", "-a", getpass.getuser(), "-s", SERVICE_NAME, "-w", secret]
    )
    if result.returncode != 0:
        raise CredentialError("macOS 钥匙串写入失败")
    return "macos_keychain"


def _read_macos() -> str | None:
    result = _run_security(["find-generic-password", "-a", getpass.getuser(), "-s", SERVICE_NAME, "-w"])
    if result.returncode == 44:
        return None
    if result.returncode != 0:
        raise CredentialError("macOS 钥匙串读取失败")
    return result.stdout.strip() or None


def _delete_macos() -> None:
    result = _run_security(["delete-generic-password", "-a", getpass.getuser(), "-s", SERVICE_NAME])
    if result.returncode not in (0, 44):
        raise CredentialError("macOS 钥匙串删除失败")


def store_secret(secret: str, runtime_dir: Path, allow_file_fallback: bool = True) -> str:
    value = secret.strip()
    if len(value) < 8:
        raise CredentialError("API Key 格式无效")
    try:
        system = platform.system()
        if system == "Windows":
            method = _store_windows(value)
        elif system == "Darwin":
            method = _store_macos(value)
        else:
            if not allow_file_fallback:
                raise CredentialError("当前系统没有可用的凭据存储实现")
            return _store_private_file(value, runtime_dir)
        _delete_private_file(runtime_dir)
        return method
    except (CredentialError, OSError, subprocess.SubprocessError):
        if platform.system() in {"Windows", "Darwin"} or not allow_file_fallback:
            raise
        return _store_private_file(value, runtime_dir)


def read_secret(runtime_dir: Path) -> str | None:
    try:
        return read_secret_for_update(runtime_dir)
    except (CredentialError, OSError, subprocess.SubprocessError):
        return _read_private_file(runtime_dir)


def read_secret_for_update(runtime_dir: Path) -> str | None:
    """Read the current secret without hiding native credential-store failures.

    Configuration updates use this strict variant so they never overwrite an
    existing credential unless it can first be snapshotted for rollback.
    """

    system = platform.system()
    if system == "Windows":
        value = _read_windows()
    elif system == "Darwin":
        value = _read_macos()
    else:
        value = None
    return value or _read_private_file(runtime_dir)


def delete_secret(runtime_dir: Path) -> None:
    system = platform.system()
    if system == "Windows":
        _delete_windows()
    elif system == "Darwin":
        _delete_macos()
    _delete_private_file(runtime_dir)
