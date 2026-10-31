---
name: windows-mcp
description: "操作/control 用户的 Windows 电脑时必用：桌面自动化、鼠标点击、键盘输入、快捷键、截图看屏幕、打开/切换/调整应用窗口、滚动、拖拽、读剪贴板、发通知、管理进程/注册表、抓取网页。触发词：操作电脑、控制电脑、点一下、帮我点、打开某个软件/应用、屏幕上、桌面上、截图、screenshot、computer use、desktop automation、GUI 自动化。工具前缀 mcp__windows-mcp__。"
---

# Windows-MCP：操作这台 Windows 电脑

通过 MCP 服务器 **windows-mcp**（GitHub: CursorTouch/Windows-MCP，源码在
`~/.agents/tools/Windows-MCP`，由 `uvx windows-mcp serve` 启动，已注册于
`~/.zcode/cli/config.json`）直接操控用户桌面。共 20 个工具，前缀 `mcp__windows-mcp__`。

**若这些工具在本会话不存在**：服务器未连接（多因会话早于配置创建）。让用户重启 ZCode
或到 设置 → MCP 查看 windows-mcp 状态；临时任务可让用户开新会话。

## 优先级原则

- 能用专用工具/API/CLI/文件读写完成的（改代码、读写文本文件、跑命令），不要动 GUI。
- GUI 操作仅用于：必须走应用界面的操作、需要"看到"屏幕、用户明确要求点按输入。
- 系统类任务优先 `PowerShell` / `FileSystem` / `Process`，比截图点击快且准。

## 标准操作循环

1. **观察**：`Screenshot`（快，含鼠标位置和窗口列表）或 `Snapshot`（重，含无障碍树、
   可交互元素 id、滚动区域；浏览器窗口可用 `use_dom=True` 抽 DOM）。
2. **行动**：`Click`(x,y) / `Type` / `Shortcut` / `Scroll` / `Move`(drag=True 拖拽)。
3. **验证**：再截一次，确认结果落地。未确认≠成功。

坐标规则：截图与点击同一 UIA 坐标系，截图上读到的像素坐标直接用，无 DPI 换算。
截图上限 1920×1080；已知目标区域时用 `region=[left,top,right,bottom]`（虚拟桌面像素）
省 token。多显示器用 `display=[0]` / `[0,1]`（从 0 起）。每次截图后屏幕会闪橙红边框，
属正常反馈，不是故障。

## 工具速查

| 组 | 工具 | 要点 |
|---|---|---|
| 捕获 | Screenshot / Snapshot / Scrape / DisplayInventory | Snapshot 拿元素 id；Scrape 抓整页网页；DisplayInventory 查显示器与 DPI |
| 输入 | Click / Type / Scroll / Move / Shortcut / MultiSelect / MultiEdit | Type 整段灌入（不适合 IDE 写代码）；MultiEdit 批量填多输入框；MultiSelect 批量选文件/勾选框 |
| 等待 | Wait / WaitFor | WaitFor 轮询等待文本/窗口/元素出现，优于固定 sleep |
| 系统 | App / PowerShell / FileSystem / Registry / Process / Clipboard / Notification | PowerShell 是万能后门；Clipboard 读写剪贴板 |

## 与内置浏览器（browser-use/IAB）协同

网页任务优先走 browser-use 的 `mcp__node_repl__js`（DOM 精确定位、可 evaluate），
windows-mcp 只做兜底（真窗口切换、真键盘、系统级）。实测边界与手法（2026-10-02
QQ 邮箱发信全程验证）：

- **IAB 弹不出文件选择框**：点上传按钮无任何反应（webview 无对话框能力）。
  出路二选一：换系统真浏览器（Edge/Chrome，文件框可驱动，见下节）；或页内注入（见下）。
- **页面元素点击三招按序升级**：locator.click 卡 actionability →
  `locator.evaluate(el => el.click())` 程序化点击 → `tab.cua.click({x,y})` 真实点击
  （过 isTrusted 检查，如"发送"按钮；坐标先 evaluate `getBoundingClientRect` 取）。
- **自定义组件输入会被框架弹回**（execCommand / native setter 都会被重置）：
  `evaluate(el => el.focus())` → `cua.keypress Ctrl+A` → `cua.type` 三连，实测稳定。
- **嵌套 iframe**（QQ 扫码登录头像）用 `frameLocator("iframe").frameLocator("iframe")`。
- **evaluate 大参数会打死 broker**（报 "response id mismatch"，连小调用也跟着失败）：
  恢复 = 重新 `browser.tabs.list()` + `tabs.get()` 重建绑定；传大数据按 ≤1MB/块循环
  evaluate 塞 `window.__buf` 数组，页内 join 拼装（12MB 单发必挂，1MB×13 实测稳）。
- **无文件框注入附件**（任何有 `input[type=file]` 的上传页通用）：Node `fs` 读文件
  → base64 分块传页内 → `atob` → `new File([bytes], name)` → `DataTransfer` →
  `input.files = dt.files` → 派发 input+change。9MB 附件实测一次成功。
- https 页面 fetch `http://127.0.0.1` 被混合内容策略拦截，别指望本地 HTTP 中转。
- 同一份自动保存的草稿/文档别在两个会话同时开着（旧会话的自动保存会覆盖新改动），
  切换通道前先关旧标签页。

## 焦点纪律与文件对话框（真浏览器/桌面应用）

- **Shortcut/Click 一律发给前台窗口**：用户正在用电脑时会抢焦点（实测粘进微信）。
  每簇键鼠操作前 `WaitFor active_window` 确认目标在前台；窗口名可能含零宽字符
  （`Microsoft\u200b Edge`）导致匹配假失败——以报错里报出的实际活动窗口名为准。
- **长文本进输入框用剪贴板**：`Clipboard set` → Ctrl+V，比 Type 快且不受 IME 影响。
- **驱动系统文件选择框**：点文件名框 → 粘贴目标文件夹完整路径 → Enter（框内导航）
  → 点列表任一文件 → Ctrl+A 全选 → 点"打开"。对话框关闭即提交，随后页面自行接管上传。
- **控件定位一律 OCR 定量**：UIA 树经常不暴露对话框/自绘控件，Edge 页面尤其稀疏；
  `PIL.ImageGrab.grab(bbox)` 存图 → RapidOCR 拿坐标。视觉模型报的坐标贴裁剪边时
  不可信，只让它做语义判读（是什么），坐标（在哪里）交给 OCR。

## 本机注意事项（用户系统为中文 zh-CN）

- `App` 工具在非英文系统上官方声明可能不稳：启动应用优先用
  `PowerShell`（如 `Start-Process winword` 或完整路径），`App` 留作窗口 resize/切换用；
  彻底失效可在 config 的 env 加 `WINDOWS_MCP_EXCLUDE_TOOLS=App`。
- 应用名/窗口标题直接用用户原话，不要翻译（"网易云音乐app" ≠ "网易云音乐"）。
- 高分屏截图过大时 env 可加 `WINDOWS_MCP_SCREENSHOT_SCALE=0.5`。

## 剪贴板中文乱码（zh-CN 必坑）

往剪贴板放中文时，禁止把文本经 stdin 管道喂给 `Set-Clipboard`（`$input | Set-Clipboard`
或 subprocess input=）——编码在中转层被二次转换，剪贴板里是 mojibake，且长度看着正常、
极难察觉。正确做法：先把文本写进 UTF-8 文件，再从文件读：

```powershell
Set-Clipboard -Value (Get-Content -Raw -Encoding UTF8 'D:/path/file.md')
```

写入后必须回读验证：`Get-Clipboard -Raw` 比对首行 + 去空白后的字符数与源文件一致
（直接比 EndsWith 可能因 CRLF 差异误报 False）。

## PowerShell + UIAutomation：MCP/computer_use 都够不到时

Electron 应用（Qoder、Cursor、VSCode 派生）常把聊天区放进不暴露 AX 的 webview：
截图工具的 `capture app=<名字>` 只抓该进程**最顶层**窗口（如 `Qoder Desktop Pet` 桌面宠物），
元素全是宠物那几个，坐标缩放后点到屏幕外。此时不要继续盲点坐标，改走 UIA：

1. `EnumWindows` 按 pid 取**面积最大**的可见窗口句柄——`Process.MainWindowHandle` 在带置顶
   小窗的应用里指向宠物/悬浮窗，不能用。QQNT 这类托盘化应用：`Get-Process QQ` 里只有一个
   进程带标题（通常就叫 "QQ"）且 hwnd≠0，先 `ShowWindow(hwnd,9)`+`SetForegroundWindow` 托出
   主窗再 UIA/capture；cua-driver 的 `list_windows` 可能根本不列它（托盘窗口不算桌面窗口）。
2. `AutomationElement.FromHandle` → 找 `ControlType.Edit`（Electron 的 contenteditable
   常暴露为 Edit，class 形如 `loop-rich-editor`），拿到真实 rect。
3. 优先 `InvokePattern.Invoke()` 点按钮（如"在工作区 X 中新建任务"），不用坐标，不怕 DPI。
4. 输入：`SetForegroundWindow` → `SetCursorPos` 到 Edit 中心 → `mouse_event` 点击 →
   剪贴板 (UTF-8 文件) + `keybd_event` Ctrl+V；发送用 VK_RETURN (0x0D)。
5. 验证：`TextPattern.DocumentRange.GetText(-1)` 或 `ValuePattern.Current.Value`；发送成功的
   标志是长度归 0，再读页面 Text 元素确认消息已进对话、状态变成"整理信息中…"。

完整可复用脚本（EnumWindows 取主窗、Invoke、粘贴、读回校验）见
`references/uia-powershell-recipes.md`。**UIA 输出的中文 Name 必须经 hex 编码传回**，由
Python `bytes.fromhex(...).decode('utf-8')` 还原——直接 `Write-Output $name` 过 bash 管道
会 GBK 乱码（配方文件里有现成的 hex 模式）。

**中文字面量坑**：`powershell -File` 在 PS 5.1 下按 ANSI(GBK) 读脚本，UTF-8 无 BOM 的
.ps1 里中文会变乱码并触发一堆 ParseError——写脚本文件时用 `utf-8-sig`（带 BOM）。
命令行 `powershell -Command "...$var..."` 会被 bash 吃掉 `$`，整串用单引号包起来。

**验证脚本必须只读**：查状态、截图、读文本要单独成脚本；把"新建任务"这类创建动作写进
验证脚本会每跑一次多建一个空任务。动作与校验分文件。

## 安全红线

该服务器**无沙箱、全系统权限、无回滚**：`PowerShell`/`FileSystem`/`Registry`/`Process`
都能造成不可逆操作。删除、格式化、注册表写入、杀进程前必须向用户确认；拖拽文件前确认
源与目标。遥测已通过 `ANONYMIZED_TELEMETRY=false` 关闭。

- **关机/重启别答应**：`shutdown`/重启在 agent 的硬性黑名单里，工具层无条件拦截（用户确认了也不行，`--yolo` 也绕不过）。主人要关机时直接告诉他：自己按 `Win+X` → 关机，或在自己终端跑 `shutdown /s /t 5`（反悔用 `shutdown /a`）。

## 备用通道

ZCode 官方 `computer-use` 插件（无障碍树优先、不抢焦点）也随应用内置，若用户在
设置 → 插件管理 中启用，其技能会出现在列表中；两者可并存，本 skill 为默认通道。
