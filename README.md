# Qwen for Codex

只粘贴一次阿里云百炼 API Key，就能把千问加入 Codex 原生模型选择器。客户不需要打开终端、不需要修改配置文件，也不需要先安装开发环境。

## 使用方法

### 第一步：下载并解压

点击 [下载 Qwen for Codex](https://github.com/zhouya166913-cell/qwen-for-codex/archive/refs/heads/main.zip)，下载完成后先解压 ZIP，不能直接在压缩包里运行。

### 第二步：双击启动

- Windows：双击 `启动 Qwen for Codex.bat`
- macOS：双击 `启动 Qwen for Codex.command`

启动器会先检查运行环境。电脑里已有可用 Python 时直接使用；没有时会自动下载到本工具的 `.runtime` 文件夹，不会修改系统 PATH，也不需要管理员手动安装。

### 第三步：粘贴 API Key

浏览器会自动打开本地设置页：

1. 粘贴阿里云百炼 API Key。
2. 点击“立即接入 Codex”。
3. 页面显示成功后，完全关闭并重新打开 Codex。

重新打开后，Codex 默认使用 `Qwen 3.8 Max`，模型选择器中还可以切换：

- Qwen 3.8 Flash
- Qwen 3.7 Plus
- Qwen 3.7 Flash

## 一键恢复 ChatGPT / Codex 原模型

需要从千问迁回原来的 ChatGPT / Codex 模型时：

- Windows：双击 `恢复 Codex 原模型.bat`
- macOS：双击 `恢复 Codex 原模型.command`

恢复程序会移除本工具添加的千问提供商、恢复接入前的模型设置，并删除本工具保存的百炼 API Key。它不会退出、删除或修改客户的 ChatGPT 账号。完成后完全关闭并重新打开 Codex。

## 程序自动完成的事情

- 用一次极小的真实请求确认 API Key 可用。
- 备份用户原有的 `~/.codex/config.toml`。
- 安装 Codex 自定义模型提供商和千问模型目录。
- 把 API Key 保存到 Windows 凭据管理器或 macOS 钥匙串。
- 将默认模型切换为 Qwen 3.8 Max。
- 支持重复运行更新 Key，并可一键恢复原配置。

API Key 不会写进项目、GitHub、浏览器存储或 Codex 配置文件。

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
- API Key 不进入命令行参数和日志。
- Windows 与 macOS 均使用系统凭据存储，写入失败会停止配置，不会降级成明文文件。
- 修改配置前先备份；重复运行不会堆叠重复配置。

## 技术参考

- [Codex 自定义模型提供商](https://learn.chatgpt.com/docs/config-file/config-advanced)
- [Codex 配置参考](https://learn.chatgpt.com/docs/config-file/config-reference)
- [阿里云百炼 Responses API](https://help.aliyun.com/zh/model-studio/qwen-api-via-openai-responses)
- [uv 自动安装 Python](https://docs.astral.sh/uv/guides/install-python/)

## 许可证

MIT
