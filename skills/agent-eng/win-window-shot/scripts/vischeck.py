#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""vischeck.py -- answer "is this window actually on screen right now?" with pixel evidence.

ctypes + Pillow only. Distilled from the throwaway probes in
%USERPROFILE%\\Documents\\Qoder\\2026-10-30\\5d73564e\\ (_z2.py/_z3.py/_topmost_test.py/
_cap_v.py/_cap_stage.py/_verify_vis.py).

The rule this tool exists for: a process's own log line, an fps counter or a "rendered"
flag is NOT proof of visibility. Proof is a real screen grab plus fixed-point pixel reads
that differ from the desktop behind them. Every check prints the sampled RGB.

Exit codes: 0 all points PASS / 1 some point FAIL / 2 no window matched / 3 API failure.
"""

import argparse
import ctypes
import sys
import time
import ctypes.wintypes as wt
from ctypes import wintypes

try:
    from PIL import ImageGrab
except ImportError:  # pragma: no cover
    sys.exit("Pillow is required: py -m pip install pillow")

user32 = ctypes.windll.user32
kernel32 = ctypes.windll.kernel32
dwmapi = ctypes.windll.dwmapi

PW_RENDERFULLCONTENT = 0x2
GWL_EXSTYLE = -20
WS_EX_TOPMOST = 0x00000008
WS_EX_LAYERED = 0x00080000
WS_EX_TRANSPARENT = 0x00000020
SW_HIDE, SW_SHOWMINIMIZED, SW_SHOW, SW_RESTORE = 0, 6, 5, 9
HWND_TOP, HWND_TOPMOST = 0, -1
SWP_NOSIZE, SWP_NOMOVE, SWP_SHOWWINDOW, SWP_NOACTIVATE = 0x1, 0x2, 0x40, 0x10
DWMWA_CLOAKED = 14
SM_XVIRTUALSCREEN, SM_YVIRTUALSCREEN = 76, 77
SM_CXVIRTUALSCREEN, SM_CYVIRTUALSCREEN = 78, 79
# never minimize the shell itself -- sources that hit these classes and stayed sane
SHELL_CLASSES = ("Progman", "WorkerW", "Shell_TrayWnd", "Shell_SecondaryTrayWnd",
                 "NotifyIconOverflowWindow", "Windows.UI.Core.CoreWindow")

DEFAULT_MIN_SIZE = (1600, 900)


class VisError(RuntimeError):
    pass


def _sig(fn, restype, *argtypes):
    fn.restype = restype
    fn.argtypes = list(argtypes)
    return fn


_sig(kernel32.FormatMessageW, wintypes.UINT, wintypes.UINT, wintypes.HMODULE,
     wintypes.UINT, wintypes.UINT, wintypes.LPWSTR, wintypes.INT, wintypes.LPVOID)
_sig(user32.GetClassNameW, ctypes.c_int, wintypes.HWND, wintypes.LPWSTR, ctypes.c_int)
_sig(user32.GetWindowTextLengthW, ctypes.c_int, wintypes.HWND)
_sig(user32.GetWindowTextW, ctypes.c_int, wintypes.HWND, wintypes.LPWSTR, ctypes.c_int)
_sig(user32.GetWindowThreadProcessId, wintypes.UINT, wintypes.HWND,
     ctypes.POINTER(wintypes.DWORD))
_sig(user32.GetWindowRect, wintypes.BOOL, wintypes.HWND, ctypes.POINTER(wintypes.RECT))
_sig(user32.IsWindow, wintypes.BOOL, wintypes.HWND)
_sig(user32.IsWindowVisible, wintypes.BOOL, wintypes.HWND)
_sig(user32.IsIconic, wintypes.BOOL, wintypes.HWND)
_sig(user32.GetAncestor, wintypes.HWND, wintypes.HWND, ctypes.c_uint)
_sig(user32.GetSystemMetrics, ctypes.c_int, ctypes.c_int)
_sig(user32.ShowWindow, wintypes.BOOL, wintypes.HWND, ctypes.c_int)
_sig(user32.SetWindowPos, wintypes.BOOL, wintypes.HWND, wintypes.HWND, ctypes.c_int,
     ctypes.c_int, ctypes.c_int, ctypes.c_int, wintypes.UINT)
_sig(user32.GetDC, wintypes.HDC, wintypes.HWND)
_sig(user32.ReleaseDC, ctypes.c_int, wintypes.HWND, wintypes.HDC)
_sig(dwmapi.DwmGetWindowAttribute, ctypes.c_long, wintypes.HWND, wintypes.DWORD,
     ctypes.c_void_p, wintypes.DWORD)


def win_err(what):
    code = ctypes.GetLastError()
    buf = ctypes.create_unicode_buffer(512)
    n = kernel32.FormatMessageW(0x100 | 0x200, None, code, 0, buf, 512, None)
    raise VisError("%s failed: %s (GetLastError=%d)" % (
        what, buf.value.strip() if n else "no message", code))


def make_dpi_aware():
    """Physical pixels or nothing.

    At 125/150% scaling a DPI-unaware process sees virtualized coordinates: window rects
    come back scaled down and PIL's grab comes back resampled, so a fixed point "x,y"
    picked from the real screen lands on a different pixel and every PASS/FAIL verdict is
    noise. Awareness must be set before the first metric call, at import/startup time.
    """
    ctx = ctypes.c_void_p(-4)  # DPI_AWARENESS_CONTEXT_PER_MONITOR_AWARE_V2
    if hasattr(user32, "SetProcessDpiAwarenessContext"):
        _sig(user32.SetProcessDpiAwarenessContext, wintypes.BOOL, ctypes.c_void_p)
        if user32.SetProcessDpiAwarenessContext(ctx):
            return "per-monitor-v2"
        if ctypes.GetLastError() == 5:  # host already set it: fine, we are aware
            return "already-set"
    if hasattr(ctypes.windll, "shcore"):
        _sig(ctypes.windll.shcore.SetProcessDpiAwareness, ctypes.c_long, ctypes.c_int)
        if ctypes.windll.shcore.SetProcessDpiAwareness(2) in (0, -1010):
            return "per-monitor"
    if user32.SetProcessDPIAware():
        return "system"
    return "UNAWARE-pixel-checks-unreliable"


def win_class(hwnd):
    buf = ctypes.create_unicode_buffer(256)
    user32.GetClassNameW(hwnd, buf, 256)
    return buf.value


def win_title(hwnd):
    n = user32.GetWindowTextLengthW(hwnd)
    if n <= 0:
        return ""
    buf = ctypes.create_unicode_buffer(n + 1)
    user32.GetWindowTextW(hwnd, buf, n + 1)
    return buf.value


def win_rect(hwnd):
    r = wintypes.RECT()
    if not user32.GetWindowRect(hwnd, ctypes.byref(r)):
        win_err("GetWindowRect")
    return r


def win_pid(hwnd):
    pid = wintypes.DWORD()
    user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
    return pid.value


def exstyle(hwnd):
    fn = getattr(user32, "GetWindowLongPtrW", None)
    if fn is not None:
        _sig(fn, ctypes.c_ssize_t, wintypes.HWND, ctypes.c_int)
        return fn(hwnd, GWL_EXSTYLE)
    return user32.GetWindowLongW(hwnd, GWL_EXSTYLE)


def is_cloaked(hwnd):
    """DWM can hide a window while IsWindowVisible still says True (virtual desktops,
    UWP suspend). Without this check you "see" windows that are not on the screen."""
    val = wintypes.DWORD()
    hr = dwmapi.DwmGetWindowAttribute(hwnd, DWMWA_CLOAKED, ctypes.byref(val),
                                      ctypes.sizeof(val))
    if hr != 0:
        return False  # attribute unsupported (pre-Win8) -> assume not cloaked
    return val.value != 0


def enumerate_windows(only_root=True):
    """Z order, front to back. This order IS the occlusion answer: the first entry whose
    rect covers a point is the window whose pixels the user sees there."""
    rows = []
    WNDENUMPROC = ctypes.WINFUNCTYPE(wt.BOOL, wintypes.HWND, wintypes.LPARAM)
    _sig(user32.EnumWindows, wintypes.BOOL, WNDENUMPROC, wintypes.LPARAM)

    def cb(hwnd, _l):
        try:
            if only_root and user32.GetAncestor(hwnd, 2) != hwnd:
                return True
            r = win_rect(hwnd)
            w, h = r.right - r.left, r.bottom - r.top
            if w <= 0 or h <= 0:
                return True
            rows.append({"z": len(rows), "hwnd": hwnd, "pid": win_pid(hwnd),
                         "class": win_class(hwnd), "title": win_title(hwnd),
                         "x": r.left, "y": r.top, "w": w, "h": h,
                         "visible": bool(user32.IsWindowVisible(hwnd)),
                         "iconic": bool(user32.IsIconic(hwnd)),
                         "cloaked": is_cloaked(hwnd),
                         "topmost": bool(exstyle(hwnd) & WS_EX_TOPMOST),
                         "layered": bool(exstyle(hwnd) & WS_EX_LAYERED),
                         "clickthrough": bool(exstyle(hwnd) & WS_EX_TRANSPARENT)})
        except Exception as exc:
            sys.stderr.write("enum cb skipped: %r\n" % exc)
        return True

    keep = WNDENUMPROC(cb)
    if not user32.EnumWindows(keep, 0):
        win_err("EnumWindows")
    return rows


def select(rows, classes=(), titles=(), pids=(), hwnds=()):
    out = []
    for r in rows:
        if (r["class"].lower() in [c.lower() for c in classes]
                or any(t.lower() in r["title"].lower() for t in titles)
                or r["pid"] in pids or r["hwnd"] in hwnds):
            out.append(r)
    return out


def parse_hwnd(text):
    t = text.strip()
    try:
        return int(t, 16) if t.lower().startswith("0x") else int(t, 10)
    except ValueError:
        raise argparse.ArgumentTypeError("bad hwnd %r (use 0x1A2B or decimal)" % text)


def parse_point(text):
    """'x,y' or 'x,y:label' -- absolute physical screen coordinates."""
    label = ""
    if ":" in text:
        text, label = text.split(":", 1)
    parts = text.replace(" ", "").split(",")
    if len(parts) != 2:
        raise argparse.ArgumentTypeError("bad point %r (want x,y:label)" % text)
    try:
        return (int(parts[0]), int(parts[1]), label or ("%s,%s" % tuple(parts)))
    except ValueError:
        raise argparse.ArgumentTypeError("bad point %r (integers only)" % text)


def parse_color(text):
    parts = text.replace(" ", "").split(",")
    if len(parts) != 3:
        raise argparse.ArgumentTypeError("bad color %r (want r,g,b)" % text)
    try:
        return tuple(int(v) for v in parts)
    except ValueError:
        raise argparse.ArgumentTypeError("bad color %r (integers only)" % text)


def parse_size(text):
    parts = text.replace(" ", "").split("x")
    if len(parts) != 2:
        raise argparse.ArgumentTypeError("bad size %r (want WxH)" % text)
    return int(parts[0]), int(parts[1])


def grab_screen():
    """Real screen grab over the whole virtual desktop, layered surfaces included.
    Returns (image, origin_x, origin_y): image pixel = screen coord - origin."""
    vx = user32.GetSystemMetrics(SM_XVIRTUALSCREEN)
    vy = user32.GetSystemMetrics(SM_YVIRTUALSCREEN)
    vw = user32.GetSystemMetrics(SM_CXVIRTUALSCREEN)
    vh = user32.GetSystemMetrics(SM_CYVIRTUALSCREEN)
    try:
        img = ImageGrab.grab(bbox=(vx, vy, vx + vw, vy + vh), all_screens=True,
                             include_layered_windows=True)
    except TypeError:  # older Pillow: no all_screens/include_layered_windows kwargs
        img = ImageGrab.grab()
        return img, 0, 0
    if img is None:
        raise VisError("ImageGrab returned None -- no desktop/session to grab (SSH/service "
                       "session? run inside the interactive session)")
    return img, vx, vy


def top_at(rows, sx, sy):
    """Front-most on-screen window covering a screen point, or None."""
    for r in rows:
        if not r["visible"] or r["iconic"] or r["cloaked"] or r["clickthrough"]:
            continue
        if r["class"] in ("Progman", "WorkerW"):
            continue
        if r["x"] <= sx < r["x"] + r["w"] and r["y"] <= sy < r["y"] + r["h"]:
            return r
    return None


def sample(img, origin, sx, sy):
    px, py = sx - origin[0], sy - origin[1]
    if not (0 <= px < img.size[0] and 0 <= py < img.size[1]):
        return None
    p = img.getpixel((px, py))
    return tuple(p[:3])


def channel_delta(a, b):
    return max(abs(x - y) for x, y in zip(a, b))


def auto_points(r, stride_ok=True):
    """Center + mid-edges. A pet/character window is mostly per-pixel-alpha transparent,
    so the exact center is often a legitimate hole: give the caller several fixed points
    and let the occluder column decide, not a single pixel."""
    cx, cy = r["x"] + r["w"] // 2, r["y"] + r["h"] // 2
    pts = [(cx, cy, "center")]
    if stride_ok:
        pts += [(r["x"] + r["w"] // 4, cy, "left-quarter"),
                (r["x"] + 3 * r["w"] // 4, cy, "right-quarter"),
                (cx, r["y"] + r["h"] // 4, "top-quarter"),
                (cx, r["y"] + 3 * r["h"] // 4, "bottom-quarter")]
    return pts


def check_points(img, origin, rows, points, ref, threshold, tag, target=None):
    """PASS = the pixel differs from the reference. ATTRIBUTED = the front-most window at
    that pixel is the target itself. A PASS whose pixels belong to another window proves
    nothing about the target, so both numbers come back."""
    lines, passed, attributed = [], 0, 0
    for (sx, sy, label) in points:
        px = sample(img, origin, sx, sy)
        if px is None:
            lines.append("%s FAIL %s at %d,%d: outside the grabbed desktop" % (
                tag, label, sx, sy))
            continue
        d = channel_delta(px, ref)
        top = top_at(rows, sx, sy)
        who = "0x%08X/%s" % (top["hwnd"] & 0xFFFFFFFF, top["class"]) if top else "desktop"
        mine = top is None or target is None or top["hwnd"] == target
        ok = d >= threshold
        passed += 1 if ok else 0
        attributed += 1 if (ok and mine) else 0
        lines.append("%s %s %s at %d,%d: rgb=%s ref=%s delta=%d threshold=%d "
                     "top-window=%s%s" % (
                         tag, "PASS" if ok else "FAIL", label, sx, sy,
                         px, ref, d, threshold, who,
                         "" if mine else " <- NOT the target"))
    return lines, passed, attributed


def bring_topmost(hwnd, flags, label):
    if not user32.SetWindowPos(hwnd, label, 0, 0, 0, 0, flags):
        win_err("SetWindowPos(0x%X -> %s)" % (hwnd, "TOP" if label == HWND_TOP else "TOPMOST"))
    return True


def minimize_others(rows, keep, min_size):
    """Same etiquette the probes learned the hard way: minimize only big, visible,
    non-iconic windows that are not targets and not the shell; remember every one; restore
    every one afterwards even if the check fails or blows up."""
    targets = {r["hwnd"] for r in keep}
    picked = []
    for r in rows:
        if not r["visible"] or r["iconic"] or r["hwnd"] in targets:
            continue
        if r["class"] in SHELL_CLASSES:
            continue
        if r["w"] >= min_size[0] and r["h"] >= min_size[1]:
            if not user32.ShowWindow(r["hwnd"], SW_SHOWMINIMIZED):
                # ShowWindow returns 0 when the state did not change -- still recorded,
                # so the restore pass below can put it back either way.
                sys.stderr.write("note: ShowWindow(minimize) 0x%08X returned 0\n"
                                 % (r["hwnd"] & 0xFFFFFFFF))
            picked.append(r["hwnd"])
    return picked


def restore_all(picked):
    ok = 0
    for hwnd in picked:
        if user32.IsWindow(hwnd):
            user32.ShowWindow(hwnd, SW_RESTORE)
        if not user32.IsIconic(hwnd):
            ok += 1
    return ok


def main(argv=None):
    ap = argparse.ArgumentParser(
        prog="vischeck.py",
        description="Prove a window is really visible: fixed-point pixels vs desktop "
                    "background, plus who is on top at each point.")
    ap.add_argument("--class", dest="classes", action="append", default=[], metavar="NAME",
                    help="window class, exact, repeatable (example: AgentCharWnd)")
    ap.add_argument("--title", dest="titles", action="append", default=[], metavar="SUB",
                    help="title substring, repeatable")
    ap.add_argument("--pid", dest="pids", action="append", type=int, default=[], metavar="N")
    ap.add_argument("--hwnd", dest="hwnds", action="append", type=parse_hwnd, default=[],
                    metavar="H", help="0xHEX or decimal, repeatable")
    ap.add_argument("--points", dest="points", action="append", type=parse_point, default=[],
                    metavar="x,y:label", help="fixed point to check, repeatable")
    ap.add_argument("--auto-points", action="store_true",
                    help="also check center + quarter points of every matched window")
    ap.add_argument("--desktop-corner", default="2,2", metavar="x,y",
                    help="background reference pixel (default top-left, 2,2)")
    ap.add_argument("--ref-color", type=parse_color, default=None, metavar="r,g,b",
                    help="explicit reference color; overrides --desktop-corner")
    ap.add_argument("--threshold", type=int, default=12, metavar="N",
                    help="max-channel difference from the reference needed for PASS (default 12)")
    ap.add_argument("--bring-topmost", action="store_true",
                    help="on FAIL: SetWindowPos TOP (then TOPMOST) and re-check")
    ap.add_argument("--minimize-others", action="store_true",
                    help="on FAIL: minimize covering windows, re-check, then restore them all")
    ap.add_argument("--min-size", type=parse_size, default="1600x900", metavar="WxH",
                    help="smallest window area to consider for --minimize-others")
    ap.add_argument("--settle", type=float, default=0.8, metavar="SEC",
                    help="wait after changing z-order/minimizing before grabbing")
    ap.add_argument("--out", metavar="PATH.png", help="save the evidence grab as PNG")
    args = ap.parse_args(argv)

    mode = make_dpi_aware()
    if not (args.classes or args.titles or args.pids or args.hwnds):
        ap.error("need at least one of --class/--title/--pid/--hwnd")

    rows = enumerate_windows()
    hits = select(rows, args.classes, args.titles, args.pids, args.hwnds)
    print("dpi=%s matched=%d threshold=%d min-size=%sx%s" % (
        mode, len(hits), args.threshold, args.min_size[0], args.min_size[1]))
    if not hits:
        sys.stderr.write("no window matched. Use winshot.py --list to find class/title.\n")
        return 2

    final_fail = 0
    for r in hits:
        state = []
        if not r["visible"]:
            state.append("IsWindowVisible=False")
        if r["iconic"]:
            state.append("minimized")
        if r["cloaked"]:
            state.append("DWM-cloaked")
        if state:
            print("hwnd=0x%08X class=%s title=%r NOT-ON-SCREEN (%s) -> FAIL" % (
                r["hwnd"] & 0xFFFFFFFF, r["class"], r["title"][:32], ",".join(state)))
            final_fail += 1
            continue

        pts = list(args.points)
        if args.auto_points or not pts:
            pts += auto_points(r)
        img, ox, oy = grab_screen()
        if args.out:
            img.save(args.out)
        origin = (ox, oy)
        if args.ref_color is not None:
            ref = args.ref_color
        else:
            cx, cy = (int(v) for v in args.desktop_corner.replace(" ", "").split(",")[:2])
            ref = sample(img, origin, cx, cy)
            if ref is None:
                raise VisError("desktop corner %d,%d is outside the grabbed desktop" % (cx, cy))
            print("reference: desktop corner %d,%d rgb=%s" % (cx, cy, ref))
            cover = top_at(rows, cx, cy)
            if cover and cover["class"] not in ("Progman", "WorkerW"):
                print("WARNING reference point is covered by 0x%08X/%s (%r) -- that is a "
                      "window, not bare desktop. Pick a --desktop-corner over the wallpaper, "
                      "pass --ref-color, or use --minimize-others." % (
                          cover["hwnd"] & 0xFFFFFFFF, cover["class"], cover["title"][:24]))
        def evaluate(image, origin_, rows_, ref_, tag):
            lines, passed, attrib = check_points(image, origin_, rows_, pts, ref_,
                                                 args.threshold, tag, r["hwnd"])
            for line in lines:
                print(line)
            return passed, attrib

        passed, attrib = evaluate(img, origin, rows, ref, "pass1")
        # "weak" = some point matches the background, or no passing point belongs to the
        # target window itself (someone else is on top there).
        weak = (passed < len(pts)) or (attrib == 0)

        if weak and args.bring_topmost:
            flags = SWP_NOMOVE | SWP_NOSIZE | SWP_SHOWWINDOW
            if not r["topmost"]:
                print("note: target is not WS_EX_TOPMOST; promoting it for the retry")
            for insert, name in ((HWND_TOP, "HWND_TOP"), (HWND_TOPMOST, "HWND_TOPMOST")):
                bring_topmost(r["hwnd"], flags, insert)
                time.sleep(max(args.settle, 0.3))
                rows2 = enumerate_windows()
                z2 = next((x["z"] for x in rows2 if x["hwnd"] == r["hwnd"]), -1)
                print("promote(%s): SetWindowPos returned success; z-order %d->%d "
                      "topmost-now=%s (the owning app can re-assert its own order, so "
                      "trust this line, not the return value)" % (
                          name, r["z"], z2, bool(exstyle(r["hwnd"]) & WS_EX_TOPMOST)))
                img, ox, oy = grab_screen()
                if args.out:
                    img.save("%s.after-%s.png" % (
                        args.out[:-4] if args.out.endswith(".png") else args.out, name))
                passed, attrib = evaluate(img, (ox, oy), rows2, ref, "after-%s" % name)
                weak = (passed < len(pts)) or (attrib == 0)
                if not weak:
                    break

        if weak and args.minimize_others:
            picked = []
            try:
                picked = minimize_others(enumerate_windows(), [r], args.min_size)
                print("minimize-others: minimized %d covering windows" % len(picked))
                time.sleep(max(args.settle, 1.0))
                rows3 = enumerate_windows()
                img, ox, oy = grab_screen()
                if args.out:
                    img.save("%s.alone.png" % (args.out[:-4] if args.out.endswith(".png")
                                              else args.out))
                cx, cy = (int(v) for v in args.desktop_corner.replace(" ", "").split(",")[:2])
                ref2 = args.ref_color if args.ref_color is not None else \
                    (sample(img, (ox, oy), cx, cy) or ref)
                print("alone reference rgb=%s" % (ref2,))
                passed, attrib = evaluate(img, (ox, oy), rows3, ref2, "alone")
                weak = (passed < len(pts)) or (attrib == 0)
            finally:
                ok = restore_all(picked)
                print("minimize-others: restored %d/%d windows" % (ok, len(picked)))
                if ok != len(picked):
                    sys.stderr.write("WARNING: these windows are still minimized: %s\n"
                                     % ["0x%X" % (h & 0xFFFFFFFF) for h in picked
                                        if user32.IsIconic(h)])

        if passed == len(pts) and attrib == len(pts):
            verdict = "VISIBLE"
        elif passed and attrib:
            verdict = "PARTIAL(%d/%d points proved)" % (attrib, len(pts))
        elif passed:
            verdict = ("AMBIGUOUS(%d/%d points differ from the background but every one of "
                       "them is covered by another window)" % (passed, len(pts)))
        else:
            verdict = "NOT-VISIBLE(all %d points equal the desktop background)" % len(pts)
        print("hwnd=0x%08X pid=%d class=%s title=%r rect=%d,%d %dx%d visible=%s topmost=%s "
              "layered=%s points=%d passed=%d attributed=%d -> %s" % (
                  r["hwnd"] & 0xFFFFFFFF, r["pid"], r["class"], r["title"][:32],
                  r["x"], r["y"], r["w"], r["h"], r["visible"], r["topmost"], r["layered"],
                  len(pts), passed, attrib, verdict))
        if verdict != "VISIBLE":
            final_fail += 1

    return 0 if final_fail == 0 else 1


if __name__ == "__main__":
    try:
        sys.exit(main())
    except VisError as exc:
        sys.stderr.write("vischeck: %s\n" % exc)
        sys.exit(3)
