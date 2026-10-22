#!/bin/bash
set -u

PROJECT_ROOT="$(cd "$(dirname "$0")" && pwd)"
export QWEN_FOR_CODEX_MODE=restore
exec "$PROJECT_ROOT/启动 Qwen for Codex.command"
