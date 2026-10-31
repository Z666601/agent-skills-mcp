# PowerShell + UIAutomation 驱动 Electron 桌面应用

适用：MCP windows-mcp 工具不可用，`computer_use` 的 `app=` 只能命中置顶小窗（宠物/悬浮窗），
或应用聊天区不在 AX 树里的情况。全部脚本写成 `utf-8-sig` 文件再 `powershell -File` 执行。

## 1. 按 pid 找真正的主窗口

`Get-Process -Id <pid>).MainWindowHandle` 可能是置顶小窗；枚举后取面积最大的可见窗口。

```powershell
Add-Type @"
using System; using System.Text; using System.Runtime.InteropServices;
public class W {
  public delegate bool EnumProc(IntPtr h, IntPtr l);
  [DllImport("user32.dll")] public static extern bool EnumWindows(EnumProc cb, IntPtr l);
  [DllImport("user32.dll")] public static extern int GetWindowThreadProcessId(IntPtr h, out int pid);
  [DllImport("user32.dll", CharSet=CharSet.Unicode)] public static extern int GetWindowText(IntPtr h, StringBuilder s, int n);
  [DllImport("user32.dll")] public static extern bool IsWindowVisible(IntPtr h);
  [DllImport("user32.dll")] public static extern bool GetWindowRect(IntPtr h, out RECT r);
  [StructLayout(LayoutKind.Sequential)] public struct RECT { public int L,T,R,B; }
}
"@
$pidTarget = 3928
$best = [IntPtr]::Zero; $bestArea = 0
$cb = [W+EnumProc]{
  param($h,$l)
  $p2 = 0; [void][W]::GetWindowThreadProcessId($h, [ref]$p2)
  if ($p2 -eq $pidTarget -and [W]::IsWindowVisible($h)) {
    $r = New-Object W+RECT; [void][W]::GetWindowRect($h, [ref]$r)
    $a = ($r.R-$r.L)*($r.B-$r.T)
    if ($a -gt $script:bestArea) { $script:bestArea = $a; $script:best = $h }
  }
  return $true
}
[void][W]::EnumWindows($cb, [IntPtr]::Zero)
$root = [System.Windows.Automation.AutomationElement]::FromHandle($best)
```

## 2. 找输入框（不要猜坐标）

```powershell
Add-Type -AssemblyName UIAutomationClient; Add-Type -AssemblyName UIAutomationTypes
$c = New-Object System.Windows.Automation.PropertyCondition(
  [System.Windows.Automation.AutomationElement]::ControlTypeProperty,
  [System.Windows.Automation.ControlType]::Edit)
$ed = $root.FindFirst([System.Windows.Automation.TreeScope]::Descendants, $c)
$r = $ed.Current.BoundingRectangle   # 真实屏幕坐标，DPI 无关
```

Electron 的 `loop-rich-editor` 这类 contenteditable 会作为 Edit 暴露；`Name` 就是占位文案
（如“新的任务”“发送消息”），可用来确认当前在哪个页面。

## 3. 点按钮用 InvokePattern，不点坐标

```powershell
$cond = New-Object System.Windows.Automation.PropertyCondition(
  [System.Windows.Automation.AutomationElement]::NameProperty, "在 lanky 中新建任务")
$btn = $root.FindFirst([System.Windows.Automation.TreeScope]::Descendants, $cond)
$btn.GetCurrentPattern([System.Windows.Automation.InvokePattern]::Pattern).Invoke()
```

按钮名从 AX/UIA 列表里抄原文（中文照抄，别翻译）。

## 4. 往 contenteditable 里灌中文 + 回车发送

```powershell
[void][U3]::SetForegroundWindow($hwnd)
$cx = [int]($r.X + $r.Width/2); $cy = [int]($r.Y + $r.Height/2)
[void][U3]::SetCursorPos($cx,$cy)
[U3]::mouse_event(0x0002,0,0,0,[IntPtr]::Zero); [U3]::mouse_event(0x0004,0,0,0,[IntPtr]::Zero)
Set-Clipboard -Value (Get-Content -Raw -Encoding UTF8 'C:/path/input.txt')
# Ctrl+V
[U3]::keybd_event(0x11,0,0,[IntPtr]::Zero); [U3]::keybd_event(0x56,0,0,[IntPtr]::Zero)
[U3]::keybd_event(0x56,0,2,[IntPtr]::Zero); [U3]::keybd_event(0x11,0,2,[IntPtr]::Zero)
# 回车发送
[U3]::keybd_event(0x0D,0,0,[IntPtr]::Zero); [U3]::keybd_event(0x0D,0,2,[IntPtr]::Zero)
```

`keybd_event` 的 `flags`：按下 0，抬起 2。

SetForegroundWindow 被系统拒绝时，先 `AttachThreadInput(前景线程, 目标线程, true)` 再设前景，
设完解绑。

## 5. 读回校验（发完长度归 0 才算发出去）

```powershell
$tp = $ed.GetCurrentPattern([System.Windows.Automation.TextPattern]::Pattern)
$len = $tp.DocumentRange.GetText(-1).Length      # 发送成功后为 0
# 有的页面只支持 ValuePattern：
$vp = $ed.GetCurrentPattern([System.Windows.Automation.ValuePattern]::Pattern); $vp.Current.Value
```

聊天记录不在 Edit 里时，遍历 `ControlType.Text` 的 `Name`，按 `BoundingRectangle` 排位置。
中文经 bash 管道会变 GBK 乱码，输出前转 hex，再由 Python `bytes.fromhex(...).decode('utf-8')` 还原：

```powershell
$b=[System.Text.Encoding]::UTF8.GetBytes($t.Current.Name)
"T|" + [int]$r.X + "," + [int]$r.Y + "|" + (($b | %{ $_.ToString("x2") }) -join "")
```

## 6. 执行姿势

- 脚本文件用 `utf-8-sig` 写（PS 5.1 默认按 GBK 读 .ps1，中文会 ParseError）。
- `powershell -Command '...'` 整串用单引号，否则 bash 先吃掉 `$var`。
- Python 侧用 `subprocess.run(..., capture_output=True)` 再 `decode('gbk','replace')` 或按 hex 还原。
- 状态查询脚本只读；创建/发送动作单独一个脚本，避免“验证”重复触发副作用。
- 等待用轮询读文本（每次 20-30s），不要凭猜的时间点断言完成。
