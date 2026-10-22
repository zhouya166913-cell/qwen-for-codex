param(
    [ValidateSet("setup", "restore")]
    [string]$Mode = "setup"
)

$ErrorActionPreference = "Stop"
[Console]::OutputEncoding = [System.Text.UTF8Encoding]::new()
$env:PYTHONUTF8 = "1"
$env:PYTHONIOENCODING = "utf-8"

$projectRoot = Split-Path -Parent $PSScriptRoot
Set-Location -LiteralPath $projectRoot

function Test-PythonCommand {
    param(
        [Parameter(Mandatory = $true)][string]$Command,
        [string[]]$PrefixArgs = @()
    )
    try {
        & $Command @PrefixArgs -c "import sys; raise SystemExit(0 if sys.version_info >= (3, 11) else 1)" 2>$null
        return $LASTEXITCODE -eq 0
    } catch {
        return $false
    }
}

function Find-SystemPython {
    $candidates = @(
        @{ Name = "py.exe"; Args = @("-3") },
        @{ Name = "python3.exe"; Args = @() },
        @{ Name = "python.exe"; Args = @() }
    )
    foreach ($candidate in $candidates) {
        $command = Get-Command $candidate.Name -ErrorAction SilentlyContinue
        if ($null -ne $command -and (Test-PythonCommand -Command $command.Source -PrefixArgs $candidate.Args)) {
            return @{ Command = $command.Source; Args = $candidate.Args }
        }
    }
    return $null
}

try {
    Write-Host "[1/3] 正在检查运行环境..."
    $python = if ($env:QWEN_FOR_CODEX_FORCE_PORTABLE -eq "1") { $null } else { Find-SystemPython }
    if ($null -eq $python) {
        Write-Host "[2/3] 首次运行，正在自动准备运行环境（无需手动安装）..."
        $runtimeRoot = Join-Path $projectRoot ".runtime"
        $uvDir = Join-Path $runtimeRoot "uv"
        $pythonDir = Join-Path $runtimeRoot "python"
        $cacheDir = Join-Path $runtimeRoot "cache"
        $uvExe = Join-Path $uvDir "uv.exe"
        New-Item -ItemType Directory -Force -Path $runtimeRoot | Out-Null

        if (-not (Test-Path -LiteralPath $uvExe)) {
            $isArm64 = $env:PROCESSOR_ARCHITECTURE -eq "ARM64" -or $env:PROCESSOR_ARCHITEW6432 -eq "ARM64"
            if ($isArm64) {
                $assetName = "uv-aarch64-pc-windows-msvc.zip"
                $expectedHash = "ec7846a5939b4654afee24f2d82bf6fde71bd7a6952d7748f1135ab301dd0a49"
            } else {
                $assetName = "uv-x86_64-pc-windows-msvc.zip"
                $expectedHash = "3b2661a463a5baea7f5076ea2b25ab71d77f36a6c0d809e5350651792f80a672"
            }
            $archivePath = Join-Path $runtimeRoot $assetName
            $downloadUrl = "https://github.com/astral-sh/uv/releases/download/0.13.1/$assetName"
            Invoke-WebRequest -UseBasicParsing -Uri $downloadUrl -OutFile $archivePath
            $stream = [System.IO.File]::OpenRead($archivePath)
            try {
                $sha256 = [System.Security.Cryptography.SHA256]::Create()
                try {
                    $hashBytes = $sha256.ComputeHash($stream)
                    $actualHash = -join ($hashBytes | ForEach-Object { $_.ToString("x2") })
                } finally {
                    $sha256.Dispose()
                }
            } finally {
                $stream.Dispose()
            }
            if ($actualHash -ne $expectedHash) {
                Remove-Item -LiteralPath $archivePath -Force
                throw "运行环境校验失败，请重新下载本工具后再试。"
            }
            if ([System.IO.Directory]::Exists($uvDir)) {
                [System.IO.Directory]::Delete($uvDir, $true)
            }
            [System.IO.Directory]::CreateDirectory($uvDir) | Out-Null
            Add-Type -AssemblyName System.IO.Compression.FileSystem
            [System.IO.Compression.ZipFile]::ExtractToDirectory($archivePath, $uvDir)
            Remove-Item -LiteralPath $archivePath -Force
        }
        if (-not (Test-Path -LiteralPath $uvExe)) {
            throw "运行环境下载失败，请检查网络后重新双击启动文件。"
        }

        $env:UV_PYTHON_INSTALL_DIR = $pythonDir
        $env:UV_PYTHON_INSTALL_BIN = "false"
        $env:UV_CACHE_DIR = $cacheDir
        $env:UV_NO_CONFIG = "1"
        & $uvExe python install 3.12 --no-progress
        if ($LASTEXITCODE -ne 0) {
            throw "Python 运行环境准备失败，请检查网络后重试。"
        }
        $pythonPath = (& $uvExe python find 3.12 | Select-Object -Last 1).Trim()
        if (-not (Test-Path -LiteralPath $pythonPath)) {
            throw "没有找到刚刚准备好的 Python 运行环境。"
        }
        $python = @{ Command = $pythonPath; Args = @() }
    } else {
        Write-Host "[2/3] 运行环境已就绪。"
    }

    if ($Mode -eq "restore") {
        Write-Host "[3/3] 正在恢复原来的 ChatGPT / Codex 模型配置..."
        $setupArgs = @((Join-Path $projectRoot "scripts\setup.py"), "--uninstall")
    } else {
        Write-Host "[3/3] 正在打开 Qwen for Codex 设置页面..."
        $openFlag = if ($env:QWEN_FOR_CODEX_NO_OPEN -eq "1") { "--no-open" } else { "--open" }
        $setupArgs = @((Join-Path $projectRoot "scripts\setup.py"), $openFlag)
    }
    if (-not [string]::IsNullOrWhiteSpace($env:QWEN_FOR_CODEX_TEST_HOME)) {
        $setupArgs += @("--codex-home", $env:QWEN_FOR_CODEX_TEST_HOME)
    }
    & $python.Command @($python.Args) @setupArgs
    if ($LASTEXITCODE -ne 0) {
        throw "操作没有完成。"
    }
    if ($Mode -eq "restore") {
        Write-Host "已恢复原来的 ChatGPT / Codex 模型配置。"
        Write-Host "请完全关闭 Codex，再重新打开。"
    } else {
        Write-Host "设置页面已在浏览器中打开，这个窗口现在可以关闭。"
    }
    exit 0
} catch {
    Write-Host ""
    Write-Host "启动没有完成：$($_.Exception.Message)" -ForegroundColor Red
    Write-Host "请保留这个窗口并截图反馈。"
    exit 1
}
