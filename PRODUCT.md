# Product

<!-- impeccable:product-schema 1 -->

## Platform

web

## Stack

Python 标准库驱动的本地配置服务，前端使用原生 HTML、CSS 和 JavaScript。Windows 通过 `.bat`、macOS 通过 `.command` 启动；启动器先检测本机环境，缺少 Python 时使用项目内的便携运行环境自动补齐。

## Users

主要用户是使用 Codex Desktop 或 Codex CLI、但不懂终端和配置文件的普通客户。他们希望继续使用 Codex 的项目、文件和工具工作流，同时把推理请求切换到自己付费的阿里云百炼千问模型。

## Product Purpose

Qwen for Codex 将阿里云百炼配置为 Codex 自定义模型提供商。用户下载并解压工具后双击对应系统的启动文件，再在自动打开的本地页面中输入百炼 API Key，即可完成连通性检测、Codex 配置备份、千问模型目录安装和原生模型选择器接入。成功标准是重启 Codex 后，用户能在原生模型选择器中看到并使用千问模型。

## Positioning

它不是独立聊天客户端，也不是把问题转发给千问的一次性脚本；它负责把千问接入 Codex 自身的模型提供商和模型目录机制，使用户保留 Codex 原有工作界面与工作流。

## Operating Context

用户从 GitHub 下载 ZIP 并解压。Windows 双击 `启动 Qwen for Codex.bat`，macOS 双击 `启动 Qwen for Codex.command`；启动器自动检测并补齐运行环境，然后打开仅监听 `127.0.0.1` 的设置页。页面只要求输入一个百炼 API Key，地域、接口地址和默认模型均由程序预设。配置完成后用户重启 Codex，并从原生模型选择器切换模型。需要迁回 ChatGPT 时，双击对应系统的“恢复 Codex 原模型”文件。

## Capabilities and Constraints

- 正式支持 Windows 与 macOS，兼容 Codex Desktop 和 Codex CLI 共用的用户级 `config.toml`。
- Codex 自定义模型提供商要求兼容 Responses API；阿里云百炼提供该接口，但具体模型的工具调用兼容性需要逐项验证。
- 自定义提供商配置必须写入用户级 Codex 配置，项目级 `.codex/config.toml` 不生效。
- Codex 在启动时加载模型目录，因此配置成功后必须重启客户端。
- 程序必须先备份现有配置，只管理带有自身标记的配置块，并提供恢复能力。
- API Key 不得写入仓库、页面存储或 `config.toml` 明文。Windows 与 macOS 必须写入系统凭据存储，写入失败时停止安装并给出错误；不允许静默降级为明文文件。
- 自动准备的运行环境必须限制在项目自己的 `.runtime` 目录，不修改系统 PATH；系统已有 Python 3.11+ 时不得重复下载。
- 未经用户确认，不创建 GitHub 远程仓库，也不推送代码。

## Brand Commitments

产品工作名为“Qwen for Codex”。界面语言以简体中文为主，呈现为可信、克制、清晰的开发工具，不使用夸张科技感、廉价模板感或大量装饰性渐变。

## Evidence on Hand

- 用户提供了 Codex 原生模型选择器截图，明确要求千问进入同一选择体验。
- OpenAI 官方文档确认 Codex 支持用户级自定义模型提供商与自定义模型目录。
- 阿里云官方文档确认百炼支持 OpenAI 兼容的 Responses API。
- 当前没有真实百炼 API Key，最终在线推理验证需要用户自行执行或稍后提供测试环境；代码与本地配置流程仍需完成自动化测试。

## Product Principles

- 原生接入优先：目标是进入 Codex 模型选择器，而不是另做聊天窗口。
- 一次输入完成：默认流程只向普通用户索取 API Key。
- 可恢复：任何配置写入前先备份，重复安装不叠加垃圾配置，卸载能恢复。
- 密钥最小暴露：浏览器页面不持久化密钥，日志和错误信息不回显密钥。
- 兼容性诚实：明确区分“配置成功”“API 连通”和“Codex 工具链完整兼容”。

## Accessibility & Inclusion

设置页支持键盘操作、可见焦点、语义化表单、状态播报、足够色彩对比，并在窄屏和系统减少动画设置下保持可用。
