# Qwen for Codex

> 当前下载版：v0.2.0 聚合测试版。已完成本地配置、模型目录、切换和恢复流程验证；建议先让少量客户验证各模型的实际 Codex 对话与工具调用。

只粘贴一次阿里云百炼 API Key，就能把百炼中的模型加入 Codex 原生模型选择器。v0.2 首次运行默认接入 Qwen、DeepSeek、GLM，也可以选择“仅千问”。客户不需要打开终端、不需要修改配置文件，也不需要先安装开发环境。

这里的“聚合”是指：使用同一个阿里云百炼中国内地 Key 和同一个百炼接口安装多个模型系列。它不是多家平台、多组 API Key 的转发代理。

## 使用方法

### 第一步：下载并解压

点击 [下载 Qwen for Codex v0.2.0 聚合测试版](https://github.com/zhouya166913-cell/qwen-for-codex/releases/download/v0.2.0/Qwen-for-Codex-v0.2.0.zip)，下载完成后先解压 ZIP，不能直接在压缩包里运行。

### 第二步：双击启动

- Windows：双击 `启动 Qwen for Codex.bat`
- macOS：双击 `启动 Qwen for Codex.command`

启动器会先检查运行环境。电脑里已有可用 Python 时直接使用；没有时会自动下载到本工具的 `.runtime` 文件夹，不会修改系统 PATH，也不需要管理员手动安装。

### 第三步：选择模式并粘贴 API Key

浏览器会自动打开本地设置页：

1. 选择“聚合模型”或“仅千问”；首次使用默认选择聚合模型。
2. 粘贴阿里云百炼 API Key。
3. 点击页面中的接入按钮。
4. 页面显示成功后，完全关闭并重新打开 Codex。

重新打开后，Codex 默认使用 `Qwen 3.8 Max`。v0.2 聚合模式会在模型选择器中加入：

- Qwen 3.8 Max
- Qwen 3.8 Flash
- Qwen 3.7 Plus
- Qwen 3.7 Flash
- DeepSeek V4.1 Flash
- DeepSeek V4 Pro
- GLM 5.3
- GLM 5.2

“仅千问”模式只加入上面的四个 Qwen 模型。之后可以再次双击启动文件切换模式；本工具会替换自己管理的模型目录，不会反复堆叠配置。

Kimi 暂未加入这一版。阿里云官方页面目前对 Kimi 的 Responses API 兼容状态存在不一致说明，待兼容性得到确认并完成真实工具调用验证后再考虑加入。

## 一键恢复 ChatGPT / Codex 原模型

需要从千问迁回原来的 ChatGPT / Codex 模型时：

- Windows：双击 `恢复 Codex 原模型.bat`
- macOS：双击 `恢复 Codex 原模型.command`

恢复程序会移除本工具添加的模型提供商和模型目录、恢复接入前的模型设置，并删除本工具保存的百炼 API Key。它不会退出、删除或修改客户的 ChatGPT 账号。完成后完全关闭并重新打开 Codex。

## 程序自动完成的事情

- 用一次极小的真实请求确认 API Key 可用。
- 备份用户原有的 `~/.codex/config.toml`。
- 根据所选模式安装 Codex 自定义模型提供商和模型目录。
- 把 API Key 保存到 Windows 凭据管理器或 macOS 钥匙串。
- 将默认模型切换为 Qwen 3.8 Max。
- 支持重复运行更新 Key、在聚合模型和仅千问之间切换，并可一键恢复原配置。

API Key 会由客户电脑直接发送给阿里云百炼，用于验证和后续模型调用；不会经过我们的服务器，也不会写进项目、GitHub、浏览器存储或 Codex 配置文件。

## 支持范围

- Windows 10/11（x64 或 ARM64）
- macOS 12 或更高版本（Intel 或 Apple 芯片）
- Codex Desktop 或 Codex CLI
- 阿里云百炼中国内地 API Key

如果 Codex 由企业管理员通过 `requirements.toml` 锁定模型提供商，本工具不会也不能绕过管理员策略。

## 常见问题

### 双击后提示下载失败

首次运行且电脑没有 Python 时，需要联网自动准备约几十 MB 的运行环境。检查网络后再次双击即可，已经下载成功的文件不会重复下载。

### 配置成功但模型列表没有变化

Codex 只在启动时读取模型目录。请完全退出 Codex，再重新打开。

### macOS 提示无法运行启动文件

请确认 ZIP 已经解压，再右键启动文件并选择“打开”。正式发布包会保留可执行权限。

## 安全设计

- 设置服务只监听 `127.0.0.1`，不会暴露到局域网。
- 写操作同时校验随机会话令牌、Host 和 Origin。
- 页面使用严格 CSP，不加载第三方脚本、字体或分析代码。
- API Key 不进入本工具日志；Windows 不通过命令行参数传递，macOS 交由系统 `security` 工具写入钥匙串。
- Windows 与 macOS 均使用系统凭据存储，写入失败会停止配置，不会降级成明文文件。
- 修改配置前先备份；安装、模式切换和恢复使用互斥锁与失败回滚，重复运行不会堆叠重复配置。

## 技术参考

- [Codex 自定义模型提供商](https://learn.chatgpt.com/docs/config-file/config-advanced)
- [Codex 配置参考](https://learn.chatgpt.com/docs/config-file/config-reference)
- [阿里云百炼 Responses API](https://help.aliyun.com/zh/model-studio/qwen-api-via-openai-responses)
- [uv 自动安装 Python](https://docs.astral.sh/uv/guides/install-python/)

## 许可证

MIT
