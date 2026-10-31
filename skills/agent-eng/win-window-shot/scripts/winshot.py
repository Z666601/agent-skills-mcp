#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""winshot.py -- print a real window to PNG even when it is occluded or off-screen.

ctypes + Pillow only (no pywin32). Technique distilled from the throwaway probes in
%USERPROFILE%\\Documents\\Qoder\\2026-10-30\\5d73564e\\ (_capwins.py/_z*.py/_pidwin.py).

Why PrintWindow instead of a screen grab: PrintWindow asks the *window itself* to paint
into a memory DC, so the result does not depend on z-order, topmost state or screen
position -- a window buried under three browsers or parked off the primary monitor still
comes out pixel-perfect. It is the only honest way to inspect a floating pet/bubble window
that is currently covered.

Exit codes: 0 ok / 1 nothing matched / 2 a capture came back blank / 3 API failure.
"""

import argparse
import ctypes
import os
import sys
import ctypes.wintypes as wt
from ctypes import wintypes

try:
    from PIL import Image, ImageStat
except ImportError:  # pragma: no cover
    sys.exit("Pillow is required: py -m pip install pillow")

user32 = ctypes.windll.user32
gdi32 = ctypes.windll.gdi32
kernel32 = ctypes.windll.kernel32

# --- Win32 constants worth remembering -------------------------------------------
PW_CLIENTONLY = 0x1
PW_RENDERFULLCONTENT = 0x2          # Windows 8.1+; without it DWM/GPU-composited
                                    # windows (Chromium/Electron/WPF) print blank
DIB_RGB_COLORS = 0
GWL_EXSTYLE = -20
WS_EX_TOPMOST = 0x00000008
WS_EX_LAYERED = 0x00080000
WS_EX_TRANSPARENT = 0x00000020
SM_XVIRTUALSCREEN, SM_YVIRTUALSCREEN = 76, 77
SM_CXVIRTUALSCREEN, SM_CYVIRTUALSCREEN = 78, 79


class WinShotError(RuntimeError):
    pass


def _sig(fn, restype, *argtypes):
    fn.restype = restype
    fn.argtypes = list(argtypes)
    return fn


_sig(kernel32.FormatMessageW, wintypes.UINT, wintypes.UINT, wintypes.HMODULE,
     wintypes.UINT, wintypes.UINT, wintypes.LPWSTR, wintypes.INT, wintypes.LPVOID)
_sig(user32.GetWindowDC, wintypes.HDC, wintypes.HWND)
_sig(user32.ReleaseDC, ctypes.c_int, wintypes.HWND, wintypes.HDC)
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
_sig(user32.GetWindowLongW, ctypes.c_long, wintypes.HWND, ctypes.c_int)
_sig(user32.PrintWindow, wintypes.BOOL, wintypes.HWND, wintypes.HDC, wintypes.UINT)
_sig(gdi32.CreateCompatibleDC, wintypes.HDC, wintypes.HDC)
_sig(gdi32.CreateCompatibleBitmap, wintypes.HBITMAP, wintypes.HDC, ctypes.c_int, ctypes.c_int)
_sig(gdi32.SelectObject, wintypes.HGDIOBJ, wintypes.HDC, wintypes.HGDIOBJ)
_sig(gdi32.DeleteObject, wintypes.BOOL, wintypes.HGDIOBJ)
_sig(gdi32.DeleteDC, wintypes.BOOL, wintypes.HDC)
_sig(gdi32.GetDIBits, ctypes.c_int, wintypes.HDC, wintypes.HBITMAP, wintypes.UINT,
     wintypes.UINT, wintypes.LPVOID, ctypes.c_void_p, wintypes.UINT)


def win_err(what):
    """Every ctypes return value goes through here -- no silent zeros."""
    code = ctypes.GetLastError()
    buf = ctypes.create_unicode_buffer(512)
    n = kernel32.FormatMessageW(0x100 | 0x200, None, code, 0, buf, 512, None)
    text = buf.value.strip() if n else "no message"
    raise WinShotError("%s failed: %s (GetLastError=%d)" % (what, text, code))


def make_dpi_aware():
    """Switch to physical pixels *before* reading a single coordinate.

    At 125/150% display scaling a DPI-unaware process lives in a virtualized 96-DPI
    world: GetWindowRect returns shrunken logical rects and PIL's screen grab comes
    back resampled, so a fixed-point pixel check samples the wrong pixel and a
    PrintWindow bitmap no longer matches what the panel shows. Per-Monitor-V2 makes
    rects, grab and capture all physical. SetProcessDpiAwarenessContext also fails
    with ERROR_ACCESS_DENIED (5) when the host process already set awareness -- that
    is success for us, not an error.
    """
    ctx_per_monitor_v2 = ctypes.c_void_p(-4)
    if hasattr(user32, "SetProcessDpiAwarenessContext"):
        _sig(user32.SetProcessDpiAwarenessContext, wintypes.BOOL, ctypes.c_void_p)
        if user32.SetProcessDpiAwarenessContext(ctx_per_monitor_v2):
            return "per-monitor-v2"
        if ctypes.GetLastError() == 5:
            return "already-set"
    if hasattr(ctypes.windll, "shcore"):
        _sig(ctypes.windll.shcore.SetProcessDpiAwareness, ctypes.c_long, ctypes.c_int)
        if ctypes.windll.shcore.SetProcessDpiAwareness(2) in (0, -1010):
            return "per-monitor"
    if user32.SetProcessDPIAware():
        return "system"
    return "UNAWARE-pixel-checks-unreliable"


class BITMAPINFOHEADER(ctypes.Structure):
    _fields_ = [("biSize", wintypes.DWORD), ("biWidth", ctypes.c_long),
                ("biHeight", ctypes.c_long), ("biPlanes", wintypes.WORD),
                ("biBitCount", wintypes.WORD), ("biCompression", wintypes.DWORD),
                ("biSizeImage", wintypes.DWORD), ("biXPelsPerMeter", ctypes.c_long),
                ("biYPelsPerMeter", ctypes.c_long), ("biClrUsed", wintypes.DWORD),
                ("biClrImportant", wintypes.DWORD)]


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
        win_err("GetWindowRect(0x%X)" % (hwnd & 0xFFFFFFFF))
    return r


def win_size(hwnd):
    r = win_rect(hwnd)
    return r.left, r.top, r.right - r.left, r.bottom - r.top


def win_pid(hwnd):
    pid = wintypes.DWORD()
    user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
    return pid.value


def exstyle(hwnd):
    # GetWindowLongW truncates the 64-bit style word harmlessly for our bit tests,
    # but use the Ptr variant when the OS offers it.
    fn = getattr(user32, "GetWindowLongPtrW", None)
    if fn is not None:
        _sig(fn, ctypes.c_ssize_t, wintypes.HWND, ctypes.c_int)
        return fn(hwnd, GWL_EXSTYLE)
    return user32.GetWindowLongW(hwnd, GWL_EXSTYLE)


def is_topmost(hwnd):
    return bool(exstyle(hwnd) & WS_EX_TOPMOST)


def is_layered(hwnd):
    return bool(exstyle(hwnd) & WS_EX_LAYERED)


def is_root(hwnd):
    """Skip child windows: PrintWindow/EnumWindows mixes them in and they confuse
    class/title selectors."""
    GA_ROOT = 2
    return user32.GetAncestor(hwnd, GA_ROOT) == hwnd


def enumerate_windows(only_visible=False, root_only=True):
    """Z-ordered front -> back. EnumWindows walks the real z-order, so index 0 is
    what the user actually sees on top; that ordering is the whole point when you
    need to know who is occluding whom."""
    rows = []
    WNDENUMPROC = ctypes.WINFUNCTYPE(wt.BOOL, wintypes.HWND, wintypes.LPARAM)
    _sig(user32.EnumWindows, wintypes.BOOL, WNDENUMPROC, wintypes.LPARAM)

    def cb(hwnd, _lparam):
        try:
            if only_visible and not user32.IsWindowVisible(hwnd):
                return True
            if root_only and not is_root(hwnd):
                return True
            x, y, w, h = win_size(hwnd)
            if w <= 0 or h <= 0:
                return True
            rows.append({
                "z": len(rows), "hwnd": hwnd, "pid": win_pid(hwnd),
                "class": win_class(hwnd), "title": win_title(hwnd),
                "x": x, "y": y, "w": w, "h": h,
                "visible": bool(user32.IsWindowVisible(hwnd)),
                "iconic": bool(user32.IsIconic(hwnd)),
                "topmost": is_topmost(hwnd), "layered": is_layered(hwnd),
            })
        except Exception as exc:  # never let a callback exception cross the ABI
            sys.stderr.write("enum cb skipped %r: %s\n" % (hwnd, exc))
        return True

    keep = WNDENUMPROC(cb)  # hold a reference until EnumWindows returns
    if not user32.EnumWindows(keep, 0):
        win_err("EnumWindows")
    return rows


def select(rows, classes=(), titles=(), pids=(), hwnds=(), visible_only=False):
    """Selectors are OR-ed; values inside a selector are OR-ed too (repeatable flags).
    --class exact (case-insensitive), --title substring (case-insensitive)."""
    out = []
    for r in rows:
        if visible_only and not r["visible"]:
            continue
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


def capture(hwnd, path, flags=(PW_RENDERFULLCONTENT, PW_CLIENTONLY | PW_RENDERFULLCONTENT, 0)):
    """PrintWindow -> memory DC -> GetDIBits (32bpp, top-down) -> PIL RGBA -> PNG."""
    x, y, w, h = win_size(hwnd)
    if w <= 0 or h <= 0:
        raise WinShotError("window 0x%X has size %dx%d -- minimized windows cannot be "
                           "printed; restore it first" % (hwnd, w, h))
    hdc = user32.GetWindowDC(hwnd)
    if not hdc:
        win_err("GetWindowDC(0x%X)" % hwnd)
    try:
        mdc = gdi32.CreateCompatibleDC(hdc)
        if not mdc:
            win_err("CreateCompatibleDC")
        try:
            bmp = gdi32.CreateCompatibleBitmap(hdc, w, h)
            if not bmp:
                win_err("CreateCompatibleBitmap(%dx%d)" % (w, h))
            try:
                if not gdi32.SelectObject(mdc, bmp):
                    win_err("SelectObject")
                printed = 0
                used = None
                for flag in flags:
                    printed = user32.PrintWindow(hwnd, mdc, flag)
                    if printed:
                        used = flag
                        break
                bi = BITMAPINFOHEADER()
                bi.biSize = ctypes.sizeof(BITMAPINFOHEADER)
                bi.biWidth = w
                # negative height == top-down DIB: row 0 is the top scanline, which is
                # what PIL wants. Positive would give a vertically flipped image.
                bi.biHeight = -h
                bi.biPlanes = 1
                bi.biBitCount = 32
                bi.biCompression = 0  # BI_RGB -> memory layout is BGRA, stride w*4
                buf = ctypes.create_string_buffer(w * h * 4)
                got = gdi32.GetDIBits(mdc, bmp, 0, h, buf, ctypes.byref(bi), DIB_RGB_COLORS)
                if got == 0:
                    win_err("GetDIBits(%dx%d)" % (w, h))
                img = Image.frombuffer("RGBA", (w, h), buf, "raw", "BGRA", 0, 1)
                stats = image_stats(img)
                # 32bpp GDI bitmaps carry garbage/zero alpha; alpha is meaningless here,
                # so normalise it or the PNG renders as nothing in every viewer.
                if stats["alpha_nonzero"] == 0.0:
                    img.putalpha(255)
                img.save(path)
                return {"path": path, "w": w, "h": h, "x": x, "y": y,
                        "printwindow": bool(printed), "flag": used,
                        "scanlines": got, "stats": stats}
            finally:
                gdi32.DeleteObject(bmp)
        finally:
            gdi32.DeleteDC(mdc)
    finally:
        if not user32.ReleaseDC(hwnd, hdc):
            # ReleaseDC returns 0 on an already-released/invalid handle: worth knowing
            # about, but not worth dying for at process exit.
            sys.stderr.write("warning: ReleaseDC(0x%X) returned 0\n" % hwnd)


def image_stats(img):
    """Cheap summary that separates a real bitmap from a blank one.
    All loops stay inside Pillow's C imaging (getcolors/getextrema/histogram), so a
    4K-size window still summarises in well under a second."""
    rgb = img.convert("RGB")
    mean = tuple(int(v) for v in ImageStat.Stat(rgb).mean)
    extrema = rgb.getextrema()  # ((rmin,rmax),(gmin,gmax),(bmin,bmax))
    colors = rgb.getcolors(1024 * 1024)
    uniq = len(colors) if colors is not None else -1  # -1 == >1M distinct
    alpha = img.getchannel("A")
    a_min, a_max = alpha.getextrema()
    hist = alpha.histogram()
    opaque = (sum(hist[1:]) / float(hist[0] + sum(hist[1:]))) if hist else 0.0
    flat = uniq <= 1 or (max(mx for _, mx in extrema) - min(mn for mn, _ in extrema)) <= 0
    return {"mean": mean, "extrema": extrema, "unique": uniq,
            "alpha_min": a_min, "alpha_max": a_max, "alpha_nonzero": opaque,
            "blank": flat}


def grab_region(x, y, w, h):
    """Screen grab fallback in *physical* pixels (needs the DPI-awareness call above).
    Includes layered windows explicitly: PIL's default BitBlt path skips WS_EX_LAYERED
    surfaces, so without include_layered_windows a pet/bubble window simply is not in
    the bitmap."""
    from PIL import ImageGrab
    vx = user32.GetSystemMetrics(SM_XVIRTUALSCREEN)
    vy = user32.GetSystemMetrics(SM_YVIRTUALSCREEN)
    vw = user32.GetSystemMetrics(SM_CXVIRTUALSCREEN)
    vh = user32.GetSystemMetrics(SM_CYVIRTUALSCREEN)
    bbox = (vx, vy, vx + vw, vy + vh)
    try:
        return ImageGrab.grab(bbox=bbox, all_screens=True, include_layered_windows=True)
    except TypeError:  # older Pillow without the layered/all_screens kwargs
        return ImageGrab.grab()


def out_path_for(args, hwnd):
    if args.out:
        stem, ext = os.path.splitext(args.out)
        if ext.lower() not in (".png", ""):
            stem, ext = args.out, ".png"
        if args.multi_name:
            return "%s_0x%X%s" % (stem, hwnd, ext or ".png")
        return args.out
    return "winshot_0x%X.png" % hwnd


def main(argv=None):
    ap = argparse.ArgumentParser(
        prog="winshot.py",
        description="PrintWindow capture of any window (occluded or off-screen is fine).")
    ap.add_argument("--class", dest="classes", action="append", default=[],
                    metavar="NAME", help="window class, exact, repeatable "
                    "(e.g. AgentCharWnd -- documented example, not a default)")
    ap.add_argument("--title", dest="titles", action="append", default=[],
                    metavar="SUB", help="title substring, repeatable")
    ap.add_argument("--pid", dest="pids", action="append", type=int, default=[],
                    metavar="N", help="process id, repeatable")
    ap.add_argument("--hwnd", dest="hwnds", action="append", type=parse_hwnd, default=[],
                    metavar="H", help="0xHEX or decimal hwnd, repeatable")
    ap.add_argument("--list", action="store_true",
                    help="print the Z-ordered window table and exit")
    ap.add_argument("--visible-only", action="store_true",
                    help="restrict selectors to visible windows")
    ap.add_argument("--out", metavar="PATH.png", help="output PNG (default winshot_<hwnd>.png)")
    ap.add_argument("--grab-fallback", action="store_true",
                    help="if PrintWindow comes back blank, also save a screen-grab crop of "
                         "the window rect (works only while the window is actually on screen; "
                         "needed for UpdateLayeredWindow surfaces, which PrintWindow cannot see)")
    args = ap.parse_args(argv)

    mode = make_dpi_aware()
    rows = enumerate_windows()
    hits = select(rows, args.classes, args.titles, args.pids, args.hwnds,
                  args.visible_only)
    args.multi_name = len(hits) > 1

    if args.list:
        print("dpi=%s virtual=%dx%d windows=%d" % (
            mode, user32.GetSystemMetrics(SM_CXVIRTUALSCREEN),
            user32.GetSystemMetrics(SM_CYVIRTUALSCREEN), len(rows)))
        print("z  hwnd       pid     vis top lay rect(x,y,w,h)           class                 title")
        for r in rows:
            print("%-2d 0x%08X %-7d %-3s %-3s %-3s %-25s %-20s %s" % (
                r["z"], r["hwnd"] & 0xFFFFFFFF, r["pid"],
                "Y" if r["visible"] else "n", "Y" if r["topmost"] else "n",
                "Y" if r["layered"] else "n",
                "%d,%d,%d,%d" % (r["x"], r["y"], r["w"], r["h"]),
                r["class"][:20], r["title"][:48]))
        return 0

    if not hits:
        sys.stderr.write("no window matched (dpi=%s). Try --list to see classes/titles.\n" % mode)
        return 1

    rc = 0
    for r in hits:
        path = out_path_for(args, r["hwnd"])
        try:
            res = capture(r["hwnd"], path)
        except WinShotError as exc:
            sys.stderr.write("hwnd=0x%08X class=%s CAPTURE-FAILED %s\n" %
                             (r["hwnd"] & 0xFFFFFFFF, r["class"], exc))
            rc = 3
            continue
        s = res["stats"]
        verdict = "BLANK" if s["blank"] or not res["printwindow"] else "OK"
        extra = ""
        if verdict == "BLANK" and args.grab_fallback:
            gpath = os.path.splitext(res["path"])[0] + ".grab.png"
            try:
                shot = grab_region(r["x"], r["y"], r["w"], r["h"])
                vx = user32.GetSystemMetrics(SM_XVIRTUALSCREEN)
                vy = user32.GetSystemMetrics(SM_YVIRTUALSCREEN)
                crop = shot.crop((r["x"] - vx, r["y"] - vy,
                                  r["x"] - vx + r["w"], r["y"] - vy + r["h"]))
                crop.save(gpath)
                gs = image_stats(crop.convert("RGBA"))
                extra = " grab_out=%s grab_size=%dx%d grab_mean=%s grab_unique=%s -> %s" % (
                    gpath, crop.size[0], crop.size[1], gs["mean"], gs["unique"],
                    "BLANK" if gs["blank"] else "VISIBLE")
                if not gs["blank"]:
                    verdict = "BLANK->GRAB-OK"
                    rc = 0 if rc == 0 else rc
            except Exception as exc:
                extra = " grab-fallback-failed: %s" % exc
        print("hwnd=0x%08X pid=%d class=%s title=%r rect=%d,%d %dx%d visible=%s topmost=%s "
              "layered=%s printwindow=%s flag=%s scanlines=%d out=%s size=%dx%d "
              "mean_rgb=%s unique_colors=%s alpha_nonzero=%.3f -> %s" % (
                  r["hwnd"] & 0xFFFFFFFF, r["pid"], r["class"], r["title"][:40],
                  r["x"], r["y"], r["w"], r["h"], r["visible"], r["topmost"], r["layered"],
                  res["printwindow"], res["flag"], res["scanlines"], res["path"],
                  res["w"], res["h"], s["mean"], s["unique"], s["alpha_nonzero"], verdict))
        if verdict == "BLANK" and rc == 0:
            rc = 2
    if rc == 0:
        print("dpi=%s all captures non-uniform" % mode)
    return rc


if __name__ == "__main__":
    try:
        sys.exit(main())
    except WinShotError as exc:
        sys.stderr.write("winshot: %s\n" % exc)
        sys.exit(3)
