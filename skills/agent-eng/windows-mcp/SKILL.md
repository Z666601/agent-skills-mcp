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

## 本机注意事项（用户系统为中文 zh-CN）

- `App` 工具在非英文系统上官方声明可能不稳：启动应用优先用
  `PowerShell`（如 `Start-Process winword` 或完整路径），`App` 留作窗口 resize/切换用；
  彻底失效可在 config 的 env 加 `WINDOWS_MCP_EXCLUDE_TOOLS=App`。
- 应用名/窗口标题直接用用户原话，不要翻译（"网易云音乐app" ≠ "网易云音乐"）。
- 高分屏截图过大时 env 可加 `WINDOWS_MCP_SCREENSHOT_SCALE=0.5`。

## 安全红线

该服务器**无沙箱、全系统权限、无回滚**：`PowerShell`/`FileSystem`/`Registry`/`Process`
都能造成不可逆操作。删除、格式化、注册表写入、杀进程前必须向用户确认；拖拽文件前确认
源与目标。遥测已通过 `ANONYMIZED_TELEMETRY=false` 关闭。

## 备用通道

ZCode 官方 `computer-use` 插件（无障碍树优先、不抢焦点）也随应用内置，若用户在
设置 → 插件管理 中启用，其技能会出现在列表中；两者可并存，本 skill 为默认通道。
