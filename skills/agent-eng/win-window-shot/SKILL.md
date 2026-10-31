---
name: win-window-shot
description: "Windows 悬浮窗可见性取证工具：抓被遮挡/离屏窗口的真实像素（PrintWindow PW_RENDERFULLCONTENT），以及\"这个窗口现在真的在屏幕上吗\"的定点像素证据（抓屏 + 桌面底色参照 + 谁压在上面 + topmost 重试 + 最小化其他窗口后复测，用完必恢复）。纯 ctypes + Pillow，无 pywin32。触发词：验证悬浮窗/桌宠/气泡窗有没有渲染、抓被遮挡的窗口、证明 topmost/layered 合成生效、截图是黑的或空白、agent 说\"已渲染\"但屏幕上什么都没有。"
---

# win-window-shot — 窗口真实可见性取证

纪律（她的硬性要求，见 `~/.qoder-cn/memory/feedback-window-visibility-verify.md`）：
**进程的 flag、fps 计数器、"rendered" 自报都不是证据。证据 = 真截图 + 定点像素读数。**
两个脚本各管一半：`winshot.py` 管"窗口里画了什么"（不受遮挡影响），
`vischeck.py` 管"屏幕上此刻有没有它"（受遮挡影响，所以要证明遮挡关系）。
没跑脚本的步骤一律写「未执行」并给可复现命令，不许用"应该渲染了"顶替证据。

## 1. 抓窗口内容（遮挡/离屏也能抓）

```bat
:: 先看桌面都有谁（z-order 前→后：hwnd/pid/class/title/rect/visible/topmost/layered）
py "C:\Users\<user>\.agents\skills\win-window-shot\scripts\winshot.py" --list

:: 按类名抓（桌宠角色窗是本项目实测类名，仅作示例，脚本里没有写死默认值）
py "...\winshot.py" --class AgentCharWnd --out .\pet.png

:: 多个选择器：--class/--title(子串)/--pid/--hwnd(0xHEX 或十进制) 可重复，彼此 OR
py "...\winshot.py" --title dsh-pet --pid 39212 --hwnd 0x00480EDE --out .\w.png
```

输出每窗一行：`size / mean_rgb / unique_colors / alpha_nonzero / printwindow / -> OK|BLANK`。
命中多窗口时 `--out` 自动插 hwnd（`w_0x480EDE.png`）。
退出码：`0` 正常 / `1` 没有匹配 / `2` 抓出来是空白 / `3` API 失败。

## 2. 证明"现在真的看得见"

```bat
:: 默认检查窗口中心 1 个点；--auto-points 加中心+四分位共 5 点
py "C:\Users\<user>\.agents\skills\win-window-shot\scripts\vischeck.py" --class AgentCharWnd --auto-points --out .\evidence.png

:: 固定点（自己盯住气泡文字/角色身体那块，别拿透明洞当证据）
py "...\vischeck.py" --title AGENT_CHAR_lanky --points "2378,1212:body" --points "2378,1143:head"

:: 失败就先 SetWindowPos 重试（TOP → TOPMOST），再失败就最小化其他大窗后复测（用完全部恢复）
py "...\vischeck.py" --class AgentCharWnd --auto-points --bring-topmost --minimize-others --min-size 1000x600

:: 参照色：桌面某个纯壁纸点，或直接给 rgb
py "...\vischeck.py" --hwnd 0x00400742 --desktop-corner 5,700
py "...\vischeck.py" --hwnd 0x00400742 --ref-color 0,20,35 --threshold 24
```

退出码：`0` 全部点 PASS 且归因到目标窗口 / `1` 有点 FAIL 或像素全属于别的窗口 /
`2` 没匹配 / `3` API 失败。

每点一行证据：`PASS|FAIL <label> at x,y: rgb=(...) ref=(...) delta=N threshold=12 top-window=0x.../class`。
最后每窗一行裁决：`VISIBLE` / `PARTIAL` / `AMBIGUOUS`（像素差于底色但都被别的窗口压着，
等于没证明）/ `NOT-VISIBLE`。

## 已知坑（都来自本机实测，别指望绕过）

- **PrintWindow 返回成功但全黑/全透明**：GPU 合成窗口和纯 UpdateLayeredWindow 表面它看不见；
  判据是 `unique_colors=1` + `mean_rgb` 单值（本机 `AgentCharWnd` 三窗全中此枪），
  要内容就加 `--grab-fallback` 走抓屏裁剪（前提是窗口确实在屏上）。
- **ImageGrab 默认漏掉分层窗口**：BitBlt 路径不合成 `WS_EX_LAYERED`，必须
  `include_layered_windows=True`（本脚本已带），否则桌宠在图里凭空消失。
- **EnumWindows 的顺序就是真实 z-order（前→后）**：判断"谁压在谁上面"只能按这个顺序扫 rect，
  不能按 hwnd 大小或创建先后猜。
- **DPI 陷阱**：非 DPI-aware 进程里 `GetWindowRect` 和抓屏都被虚拟化（125/150% 缩放时坐标全偏），
  定点像素打偏即整轮结论作废 → 两脚本启动第一件事是
  `SetProcessDpiAwarenessContext(-4)`（PER_MONITOR_AWARE_V2），回退 `SetProcessDPIAware`；
  返回 `ERROR_ACCESS_DENIED(5)` 说明宿主已设过，视为成功。
- **GetDIBits 取像素**：`BITMAPINFOHEADER.biHeight` 必须写**负值**（top-down，否则上下颠倒），
  32bpp BI_RGB 的内存序是 **BGRA**、stride = `w*4`；GDI 给的 alpha 字节无意义（常全 0），
  全 0 时脚本会把 alpha 归一成 255，不然 PNG 打开就是空白。
- **ULW 的 alpha 必须预乘**（premultiplied）：`BLENDFUNCTION(BlendOp=AC_SRC_OVER=0,
  AlphaFormat=1, SourceConstantAlpha=255)` + `UpdateLayeredWindow(..., ULW_ALPHA=2)`，
  直写非预乘的 RGB 会得到白边/暗边；`CreateDIBSection` 的 `biHeight` 同样取负。
- **最小化别人要有礼貌**：只动"可见、非最小化、非目标、非 shell（Progman/WorkerW/Shell_TrayWnd）、
  面积够大"的窗口，`ShowWindow(SW_SHOWMINIMIZED=6)` → 抓图 → `finally` 里 `SW_RESTORE=9`
  逐个恢复并打印 `restored N/M`，失败/异常也不漏；M≠N 时列出仍是图标态的 hwnd。
- **`SetWindowPos` 返回 1 ≠ 窗口真上去了**：owning 进程会自己重排（本机 `AgentCharWnd` 被提升到
  TOPMOST 后 exstyle 的 topmost 位仍为 0），脚本会重读 exstyle 和 z 序号打印
  `promote(...): z-order a->b topmost-now=...`，以这行为准。
- **`IsWindowVisible=True` ≠ 在屏幕上**：DWM 可以 cloak（虚拟桌面/UWP 挂起），
  所以脚本查 `DwmGetWindowAttribute(DWMWA_CLOAKED=14)`。
- **最小化窗口（rect 在 -32000）抓不到内容**：PrintWindow 只会给你标题条大小的空白，先恢复再抓。
- **深色桌宠 vs 深色壁纸**：低对比时 delta 只有 9-10，默认 `--threshold 12` 会误判 FAIL，
  挑角色身上亮处定点或降阈值——阈值是判据的一部分，报结论要带上它。

## 不做什么

- 不模拟输入：不点击、不敲键盘、不快捷键、不做窗口动画——那些走 `windows-mcp` / `computer-use`。
- 不改被测应用，不激活/抢前台（只调 z-order，且只在你显式给 `--bring-topmost` 时）。
- 不验动画：`--auto-points` 只答"这儿有像素吗"；要验动作必须间隔抓两张图自己比。
- 不做 UI 元素定位/OCR：定位交给 `vision-forensics`。
