#!/bin/bash
set -u

PROJECT_ROOT="$(cd "$(dirname "$0")" && pwd)"
cd "$PROJECT_ROOT" || exit 1

pause_on_error() {
  printf '\n启动没有完成：%s\n' "$1"
  printf '请保留这个窗口并截图反馈。\n'
  read -r -p "按回车键关闭..." _
  exit 1
}

is_usable_python() {
  "$1" -c 'import sys; raise SystemExit(0 if sys.version_info >= (3, 11) else 1)' >/dev/null 2>&1
}

printf '[1/3] 正在检查运行环境...\n'
PYTHON_COMMAND=""
if [ "${QWEN_FOR_CODEX_FORCE_PORTABLE:-0}" != "1" ]; then
  for candidate in python3 python; do
    if command -v "$candidate" >/dev/null 2>&1 && is_usable_python "$candidate"; then
      PYTHON_COMMAND="$(command -v "$candidate")"
      break
    fi
  done
fi

if [ -z "$PYTHON_COMMAND" ]; then
  printf '[2/3] 首次运行，正在自动准备运行环境（无需手动安装）...\n'
  RUNTIME_ROOT="$PROJECT_ROOT/.runtime"
  UV_DIR="$RUNTIME_ROOT/uv"
  PYTHON_DIR="$RUNTIME_ROOT/python"
  CACHE_DIR="$RUNTIME_ROOT/cache"
  UV_COMMAND="$UV_DIR/uv"
  mkdir -p "$UV_DIR" "$PYTHON_DIR" "$CACHE_DIR" || pause_on_error "无法创建运行环境目录。"

  if [ ! -x "$UV_COMMAND" ]; then
    case "$(uname -m)" in
      arm64|aarch64)
        UV_ASSET="uv-aarch64-apple-darwin.tar.gz"
        UV_HASH="cfe454573412ff7380d15fc7dae5997ab53ffce72fce0a78e91ddbc84001acd2"
        ;;
      x86_64)
        UV_ASSET="uv-x86_64-apple-darwin.tar.gz"
        UV_HASH="bb7b805bdcf3d0bc8c74ceb94569e6b3e8aa35bd492acdbb9d46bf46d9d4ff6b"
        ;;
      *)
        pause_on_error "当前 Mac 芯片类型暂不支持。"
        ;;
    esac
    UV_ARCHIVE="$RUNTIME_ROOT/$UV_ASSET"
    if ! curl -fL --retry 2 -o "$UV_ARCHIVE" "https://github.com/astral-sh/uv/releases/download/0.13.1/$UV_ASSET"; then
      pause_on_error "运行环境下载失败，请检查网络后重新双击启动文件。"
    fi
    ACTUAL_HASH="$(shasum -a 256 "$UV_ARCHIVE" | awk '{print $1}')"
    if [ "$ACTUAL_HASH" != "$UV_HASH" ]; then
      rm -f "$UV_ARCHIVE"
      pause_on_error "运行环境校验失败，请重新下载本工具后再试。"
    fi
    if ! tar -xzf "$UV_ARCHIVE" -C "$UV_DIR" --strip-components=1; then
      pause_on_error "运行环境解压失败。"
    fi
    rm -f "$UV_ARCHIVE"
  fi
  [ -x "$UV_COMMAND" ] || pause_on_error "运行环境下载失败，请检查网络后重试。"

  export UV_PYTHON_INSTALL_DIR="$PYTHON_DIR"
  export UV_PYTHON_INSTALL_BIN=false
  export UV_CACHE_DIR="$CACHE_DIR"
  export UV_NO_CONFIG=1
  "$UV_COMMAND" python install 3.12 --no-progress || pause_on_error "Python 运行环境准备失败，请检查网络后重试。"
  PYTHON_COMMAND="$("$UV_COMMAND" python find 3.12 | tail -n 1)"
  [ -x "$PYTHON_COMMAND" ] || pause_on_error "没有找到刚刚准备好的 Python 运行环境。"
else
  printf '[2/3] 运行环境已就绪。\n'
fi

if [ "${QWEN_FOR_CODEX_MODE:-setup}" = "restore" ]; then
  printf '[3/3] 正在恢复原来的 ChatGPT / Codex 模型配置...\n'
  SETUP_ARGS=("$PROJECT_ROOT/scripts/setup.py" "--uninstall")
else
  printf '[3/3] 正在打开 Qwen for Codex 设置页面...\n'
  if [ "${QWEN_FOR_CODEX_NO_OPEN:-0}" = "1" ]; then
    SETUP_ARGS=("$PROJECT_ROOT/scripts/setup.py" "--no-open")
  else
    SETUP_ARGS=("$PROJECT_ROOT/scripts/setup.py" "--open")
  fi
fi
if [ -n "${QWEN_FOR_CODEX_TEST_HOME:-}" ]; then
  SETUP_ARGS+=("--codex-home" "$QWEN_FOR_CODEX_TEST_HOME")
fi
"$PYTHON_COMMAND" "${SETUP_ARGS[@]}" || pause_on_error "操作没有完成。"
if [ "${QWEN_FOR_CODEX_MODE:-setup}" = "restore" ]; then
  printf '已恢复原来的 ChatGPT / Codex 模型配置。\n'
  printf '请完全关闭 Codex，再重新打开。\n'
  read -r -p "按回车键关闭..." _
else
  printf '设置页面已在浏览器中打开，这个窗口现在可以关闭。\n'
fi
