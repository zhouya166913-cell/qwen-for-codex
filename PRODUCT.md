# Product

<!-- impeccable:product-schema 1 -->

## Platform

web

## Stack

Python 标准库驱动的本地配置服务，前端使用原生 HTML、CSS 和 JavaScript。Windows 通过 `.bat`、macOS 通过 `.command` 启动；启动器先检测本机环境，缺少 Python 时使用项目内的便携运行环境自动补齐。

## Users

主要用户是使用 Codex Desktop 或 Codex CLI、但不懂终端和配置文件的普通客户。他们希望继续使用 Codex 的项目、文件和工具工作流，同时使用自己付费的阿里云百炼模型。

## Product Purpose

Qwen for Codex 将阿里云百炼配置为 Codex 自定义模型提供商。用户下载并解压工具后双击对应系统的启动文件，在自动打开的本地页面中选择接入方式并输入一个百炼 API Key，即可完成连通性检测、Codex 配置备份和原生模型选择器接入。首次运行默认选择“聚合模型”，一次加入 Qwen、DeepSeek、GLM；用户也可以选择“仅千问”。成功标准是重启 Codex 后，用户能在原生模型选择器中看到所选目录中的模型并发起调用。

## Positioning

它不是独立聊天客户端，也不是多平台、多 API Key 的转发代理；它负责通过同一个阿里云百炼中国内地接口，把用户选择的模型目录接入 Codex 自身的模型提供商机制，使用户保留 Codex 原有工作界面与工作流。这里的“聚合”只表示一个百炼 Key 对应多个模型系列，不表示模型请求会经过本项目运营方的服务器。

## Operating Context

用户从 GitHub 下载 ZIP 并解压。Windows 双击 `启动 Qwen for Codex.bat`，macOS 双击 `启动 Qwen for Codex.command`；启动器自动检测并补齐运行环境，然后打开仅监听 `127.0.0.1` 的设置页。页面提供“聚合模型”和“仅千问”两个明确选项，除此之外只要求输入一个百炼 API Key；地域、接口地址和默认模型均由程序预设。配置完成后用户重启 Codex，并从原生模型选择器切换模型。用户可再次运行设置页更新 Key 或切换模式；需要迁回 ChatGPT 时，双击对应系统的“恢复 Codex 原模型”文件。

## Capabilities and Constraints

- 正式支持 Windows 与 macOS，兼容 Codex Desktop 和 Codex CLI 共用的用户级 `config.toml`。
- Codex 自定义模型提供商要求兼容 Responses API；阿里云百炼提供该接口，但具体模型的工具调用兼容性需要逐项验证。
- v0.2 聚合目录只收录已由阿里云 Responses API 文档明确列出的 Qwen、DeepSeek、GLM 模型。Kimi 因阿里云官方页面对其 Responses 兼容状态存在冲突，本版暂不加入。
- 模式切换只能替换本工具管理的模型目录和默认模型，不得覆盖用户其他 Codex 设置，也不得创建常驻本地代理。
- 自定义提供商配置必须写入用户级 Codex 配置，项目级 `.codex/config.toml` 不生效。
- Codex 在启动时加载模型目录，因此配置成功后必须重启客户端。
- 程序必须先备份现有配置，只管理带有自身标记的配置块，并提供恢复能力。
- API Key 会从用户电脑直接发送给阿里云百炼做验证和后续推理；不得经过本项目运营方服务器，也不得写入仓库、页面存储或 `config.toml` 明文。Windows 与 macOS 必须写入系统凭据存储，写入失败时停止安装并给出错误；不允许静默降级为明文文件。
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
- 一次输入完成：默认流程只让普通用户选择接入方式并粘贴一个 API Key，不暴露接口地址、模型 slug 等技术配置。
- 可恢复：任何配置写入前先备份，重复安装不叠加垃圾配置，卸载能恢复。
- 密钥最小暴露：浏览器页面不持久化密钥，日志和错误信息不回显密钥。
- 兼容性诚实：明确区分“配置成功”“API 连通”和“Codex 工具链完整兼容”。

## Accessibility & Inclusion

设置页支持键盘操作、可见焦点、语义化表单、状态播报、足够色彩对比，并在窄屏和系统减少动画设置下保持可用。
