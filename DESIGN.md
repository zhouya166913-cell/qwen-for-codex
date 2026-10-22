---
name: Qwen for Codex
description: 面向非技术用户的本地连接校准台，让百炼中的多种模型以可信、克制的方式接入 Codex。
colors:
  paper: "#f2f5f7"
  surface: "#ffffff"
  ink: "#122033"
  muted: "#526176"
  line: "#ccd4de"
  navy: "#10233f"
  navy-soft: "#183455"
  route-accent: "#7cc4ff"
  primary: "#1769e0"
  primary-hover: "#0e51b2"
  primary-soft: "#eef5ff"
  success: "#167a57"
  success-soft: "#dff4eb"
  danger: "#b53535"
  danger-soft: "#fae8e7"
typography:
  display:
    fontFamily: 'Bahnschrift, "Avenir Next", "Microsoft YaHei UI", sans-serif'
    fontSize: "clamp(38px, 5.2vw, 66px)"
    fontWeight: 720
    lineHeight: 1.04
    letterSpacing: "-0.035em"
  title:
    fontFamily: 'Bahnschrift, "Avenir Next", "Microsoft YaHei UI", sans-serif'
    fontSize: "17px"
    fontWeight: 680
    letterSpacing: "-0.015em"
  body:
    fontFamily: 'Bahnschrift, "Avenir Next", "Microsoft YaHei UI", sans-serif'
    fontSize: "15px"
    fontWeight: 400
    lineHeight: 1.72
  label:
    fontFamily: 'Bahnschrift, "Avenir Next", "Microsoft YaHei UI", sans-serif'
    fontSize: "13px"
    fontWeight: 680
  mono-input:
    fontFamily: '"Cascadia Mono", "SFMono-Regular", Consolas, monospace'
    fontSize: "15px"
    fontWeight: 400
    letterSpacing: "0.01em"
rounded:
  control-sm: "9px"
  mark: "10px"
  control: "12px"
  instruction: "14px"
  workspace: "16px"
  pill: "999px"
spacing:
  xs: "8px"
  sm: "12px"
  md: "20px"
  lg: "28px"
  xl: "42px"
components:
  button-primary:
    backgroundColor: "{colors.primary}"
    textColor: "{colors.surface}"
    typography: "{typography.label}"
    rounded: "{rounded.control}"
    height: "56px"
    width: "100%"
  button-primary-hover:
    backgroundColor: "{colors.primary-hover}"
    textColor: "{colors.surface}"
    rounded: "{rounded.control}"
  key-field:
    backgroundColor: "{colors.surface}"
    textColor: "{colors.ink}"
    typography: "{typography.mono-input}"
    rounded: "{rounded.control}"
    height: "56px"
    width: "100%"
  workspace:
    backgroundColor: "{colors.surface}"
    textColor: "{colors.ink}"
    rounded: "{rounded.workspace}"
  device-state:
    backgroundColor: "{colors.surface}"
    textColor: "{colors.muted}"
    typography: "{typography.label}"
    rounded: "{rounded.pill}"
    height: "34px"
---

# Design System: Qwen for Codex

## Overview

**Creative North Star: “连接校准台”**

本界面采用 Operate 模式：用户的目标不是浏览内容，而是在一次本地会话中安全完成 Codex 与阿里云百炼模型的连接。视觉隐喻来自克制的仪器工作台——左侧或顶部路线区像固定接线图，右侧操作区像校准面板；所有视觉反馈都服务于“现在在哪一步、下一步做什么、密钥如何使用”。方向来源记录为候选方向 4、seed 60075376，最终独立审查结论为 **SHIP**。

界面层级固定为：品牌与设备状态栏 → 四段连接路线 → 单一主任务（标题、说明、接入方式、API Key、主按钮）→ 动态模型清单 → 环境与密钥流向说明。成功后结果在原操作区原位接替表单，不弹出新窗口，不制造第二条主流程。

**Key Characteristics:**

- 日光感浅灰背景承托白色工作区，深海军蓝只承担流程结构面。
- 钴蓝只用于主行动、链接、焦点和进度；绿色表示已就绪或已完成；红色只表示错误或危险恢复。
- 文字直白、非技术化，先说结果与用户动作，再补充配置细节。
- 当前视觉标记由页面 CSS 几何构成；在没有正式品牌资产前，不延伸或杜撰 logo、插画与品牌图形。

## Colors

色彩是状态编码，不是装饰。浅色工作面保证可读性，深色路线面维持方向感，单一钴蓝把注意力收敛到当前动作。

### Primary

- **校准钴蓝（`primary`）**：唯一主按钮、链接、焦点、进度线与方向箭头。
- **按压深蓝（`primary-hover`）**：主按钮悬停和文字链接的高对比状态，不用于大面积铺底。
- **选择浅蓝（`primary-soft`）**：接入方式选中态和轻量操作悬停，只作局部状态底色。

### Secondary

- **结构海军蓝（`navy`）**：桌面左侧路线面板、移动端顶部路线带和品牌标记底色。
- **活动海军蓝（`navy-soft`）**：深色面板中当前步骤的局部强调。
- **线路浅蓝（`route-accent`）**：完成节点、进度连线、深底图标笔画；不得取代主按钮蓝。

### Tertiary

- **完成绿（`success` / `success-soft`）**：设备已就绪、接入成功、已安装提示。
- **警示红（`danger` / `danger-soft`）**：表单错误与确认恢复；常态页面不使用红色吸引注意。

### Neutral

- **工作台纸灰（`paper`）**：页面最外层背景。
- **仪器白（`surface`）**：主要操作面、输入框和次级按钮。
- **主墨色（`ink`）**：标题与关键正文。
- **说明灰蓝（`muted`）**：辅助说明、模型用途和页脚信息。
- **刻度线（`line`）**：容器边界、分隔线与设备状态外框。

**The One Action Color Rule.** 同一视口内，钴蓝只强化一条主动作路径；不要把普通卡片或装饰背景也涂成主色。

**The Semantic State Rule.** 蓝色表示可操作或进行中，绿色表示成功，红色表示错误或危险；状态不得只靠颜色，还必须配合文字、位置或图标。

## Typography

**Display Font:** Bahnschrift，回退至 Avenir Next、Microsoft YaHei UI、sans-serif
**Body Font:** Bahnschrift，回退至 Avenir Next、Microsoft YaHei UI、sans-serif
**Input Font:** Cascadia Mono，回退至 SFMono-Regular、Consolas、monospace

**Character:** 标题紧凑、有设备铭牌般的确定性；正文保持友好、清晰。仅 API Key 输入使用等宽字体，让密钥形态稳定且易核对。

### Hierarchy

- **Display**：仅用于页面主任务和成功结果标题；桌面使用流式字号，手机固定为 42px，最多约 12 个中文字符宽，禁止再叠加副标题式装饰。
- **Title**：用于路线区、模型清单等一级区块标题。
- **Body**：用于引导句和说明，长句控制在约 44–50ch；移动端引导文字使用 15px。
- **Label**：用于字段标签、按钮、状态与模型名称；关键操作可用 680–700 字重。
- **Microcopy**：11–13px，仅用于辅助信息，需保持足够对比，不承担关键决策。

**The Plain Language Rule.** 面向非技术用户时使用“检测、备份、接入、重新打开”等动作词；避免把 Responses API、配置块等实现术语放进主流程。

## Layout

桌面端容器最大宽度为 1180px，左右至少留 20px；顶部状态栏后进入双栏工作区，路线面板约占 0.72fr，操作面板约占 1.55fr，工作区最小高度 680px。操作内容最大宽度 660px并在右栏居中。主要纵向节奏来自 24、28、38、42px，组件内部以 8、12、20px 为主；新增内容必须沿用这组节奏，不临时发明密集间距。

### Responsive hierarchy

- **桌面（> 820px）**：四步路线纵向固定在左侧，隐私说明始终可见；模型清单两列展示。
- **平板与窄屏（≤ 820px）**：工作区改为单列；路线压缩为顶部四列横向进度，隐藏路线引言、步骤副说明与左栏隐私块，操作区内边距收紧。
- **手机（≤ 560px）**：页面全宽、工作区取消圆角和阴影，顶栏高度 66px，操作区左右留 20px；模型清单改为单列，页脚隐藏。状态胶囊可截断但不得挤压品牌名称。
- **最小支持宽度**：320px。主按钮、输入框和恢复确认按钮在此宽度下仍须可点击，不允许横向滚动。

**The Persistent Route Rule.** 四步路线在所有断点都必须可见，只改变方向和信息密度，不可折叠成汉堡菜单或完全隐藏。

## Elevation & Depth

系统采用“单层悬浮工作台”：页面背景与白色主工作区靠色差分层，桌面工作区使用唯一的大范围柔和阴影；手机端回归原生全幅平面。按钮仅在可交互状态使用较小的蓝色环境阴影，成功提示与模型列表依靠色块、边线和留白，不继续叠加卡片阴影。

### Shadow Vocabulary

- **Workspace ambient**（`0 22px 58px rgba(16, 35, 63, 0.12)`）：只用于桌面主工作区。
- **Primary action**（`0 10px 24px rgba(23, 105, 224, 0.22)`）：只用于可点击的主按钮；悬停可轻微加深，禁用时移除。
- **Active step**（`0 8px 20px rgba(4, 15, 30, 0.28)`）：只用于深色路线面板中的当前节点。

**The One Floating Surface Rule.** 不要把输入区、模型列表和说明逐个做成悬浮卡片；层级首先靠排版、边线和底色建立。

## Shapes

形状语言来自现代仪器：主容器是克制的大圆角，输入与主要按钮共享 12px 圆角，成功指示与工作区使用更大的 14–16px 圆角，次级操作使用 9px。状态使用完全胶囊，步骤编号使用正圆。边框统一为细实线，不使用虚线、玻璃描边或装饰性切角。

品牌标记保持现有 34px 深色圆角方形与内部浅蓝十字刻度的 CSS 几何构成；除非提供正式品牌资产，不得凭空增加图腾、Qwen 官方标志或 Codex 官方标志。

## Components

### Top bar and device state

- 品牌区左对齐，设备状态右对齐；状态胶囊包含灯点与明确文本，并通过 `role="status"` 播报检测结果。
- 灰灯表示检测中，绿灯表示就绪或已识别，红灯表示页面失效；文案必须同步变化，不能只有灯点变色。

### Route progress

- 共四步：识别 Codex → 检测 API Key → 安装模型目录 → 重新打开 Codex。
- 当前步骤使用描边浅蓝节点与高亮文字，已完成步骤使用实心浅蓝节点，未到达步骤保持低对比。
- 进度只前进到真实或正在执行的阶段；失败后回到可重试状态，成功后固定在第 4 步。
- 连接线动画统一使用 `transform`：桌面 `scaleY()`、窄屏 `scaleX()`，时长 500ms，缓动为 `cubic-bezier(0.16, 1, 0.3, 1)`。

### API Key field

- 字段由等宽输入区和“显示/隐藏”文字按钮组成，整体高度 56px、圆角 12px；焦点落在整体容器上，使用主色边框和外扩焦点环。
- 默认 `type="password"`、`autocomplete="off"`、关闭拼写检查；切换可见性后保持输入焦点，并同步 `aria-label`。
- 空值或长度明显不足时，在字段下方输出可执行的中文错误并把焦点送回输入框；不得显示、记录或复述用户输入的 Key。

### Access mode picker

- 位于 API Key 字段之前，使用原生 `fieldset`、`legend`、`radio` 和 `label`，确保键盘和读屏器可直接操作。
- 只提供“聚合模型（推荐）”与“仅千问”两个选项。首次运行默认聚合模式；检测到已有安装时使用当前模式，避免更新 Key 时意外改变模型范围。
- 聚合模式说明“一次加入 Qwen、DeepSeek、GLM”，仅千问说明“保持精简，只显示千问模型”。两种模式都只使用一个百炼 Key。
- 选择区是同一边框容器内的两段选项，不做厂商品牌卡片，不使用第三方 logo；桌面横向两列，手机纵向排列，每项触控高度不低于 64px。

### Primary button

- 全宽 56px，是页面唯一实心主按钮；按钮文案随当前模式和已安装状态变化，例如“接入全部模型”“只接入千问”“升级为聚合模型”“切换为仅千问”“更新当前配置”。
- 加载时禁用输入、显隐按钮与主按钮，文案改为“正在检测并配置…”，底部显示 3px 进度线；禁止用不可判断结束时间的百分比。
- 悬停仅允许颜色加深、阴影增强和 `translateY(-1px)`；不得改变宽高造成布局抖动。

### Model bench and installed note

- 模型清单是由服务端目录摘要动态生成的信息表，不在 HTML 和 JavaScript 中重复写死；桌面两列、手机单列，名称与用途通过细分隔线对齐，并用 `aria-live="polite"` 播报模式切换后的数量变化。
- 聚合模式显示 Qwen、DeepSeek、GLM，仅千问模式只显示 Qwen；模型目录必须与实际写入 Codex 的目录保持一致。
- 已安装提示使用浅绿面板，显示当前接入方式，并允许展开“恢复原来的 Codex 配置”；恢复前必须二次确认，并明确“只移除本工具添加的模型配置”。

### Success view

- 成功态原位替换表单，并将键盘焦点移到结果区域；结构为成功符号、明确结果、最后一步和补充说明。
- “关闭 Codex → 重新打开”是必须保留的操作指令，不能用泛化的“完成”取代；成功说明需要写明默认模型及另外可切换的模型数量。

### Accessibility and motion

- 所有按钮、链接和输入必须可键盘访问，并保留 3px 可见焦点环与 3px 外偏移；触控目标高度优先达到 44px，既有小按钮不得低于 38px。
- 错误使用 `role="alert"` 与礼貌实时播报；成功切换后主动聚焦结果区。装饰 SVG 必须 `aria-hidden="true"`。
- 系统开启 `prefers-reduced-motion: reduce` 时，将动画与过渡压缩至近乎瞬时；不得用动画作为理解状态的必要条件。

### Safety and privacy copy

- 只承诺已经由实现保证的事实：“Key 从这台电脑直发阿里云百炼”“不经过我们的服务器”“保存到系统凭据库”“不会进入项目、GitHub、浏览器存储或 Codex 明文配置”。不得声称 Key 完全不离开本机，因为验证和推理必须将它发送给阿里云。
- 区分“配置成功”“API 连通”“模型工具链兼容”；未知时明确说明，不使用“绝对安全”“完全兼容”等扩大承诺。
- 任何错误、日志、成功提示和恢复确认都不得回显 Key；安全文案应贴近输入区或路线面板，而不是藏进帮助页。

## Do's and Don'ts

### Do:

- **Do** 保持一屏一个主任务，让非技术用户只需要选择接入方式、输入一个 API Key 并理解下一步。
- **Do** 使用既有 token、字号、间距和圆角；新增状态先映射到蓝/绿/红语义，再设计具体组件。
- **Do** 在桌面和移动端同时验证四步进度、输入错误、加载、成功、已安装和恢复确认。
- **Do** 保持所有布局动画为 `transform` 或不影响排版的视觉属性。质量追溯：终检 detector 曾因解析能力限制降级为 regex 扫描；其识别出的两处布局型进度过渡均已改为 `transform`（桌面纵向 `scaleY`、窄屏横向 `scaleX`）。
- **Do** 将“仅监听本机、系统凭据库、配置自动备份”等事实写成易懂的用户结果，并确保文案与实现同步。

### Don't:

- **Don't** 把它改成聊天界面、营销落地页、开发者控制台或居中的单字段 SaaS 卡片；它是一次性本地配置工具。
- **Don't** 引入霓虹渐变、玻璃拟态、科技网格、粒子、过量光效或大面积品牌色；这些会破坏可信的校准台语义。
- **Don't** 隐藏四步路线、删除模型清单、跳过恢复二次确认，或让成功态离开当前上下文。
- **Don't** 在没有正式素材时杜撰品牌资产，也不要使用第三方 logo 暗示官方背书。
- **Don't** 将 API Key 存入页面持久化、项目文件或明文配置，也不要用“完全留在本机”等错误文案隐藏它会直发阿里云的事实；凭据存储失败时必须停止流程并明确报错。
- **Don't** 通过 `width`、`height`、`top`、`left` 等布局属性制作进度动画；也不要绕过减少动画偏好。
- **Don't** 未经完整桌面与移动端回归就改动 `820px`、`560px` 两个断点、四步状态映射或唯一主按钮结构。
