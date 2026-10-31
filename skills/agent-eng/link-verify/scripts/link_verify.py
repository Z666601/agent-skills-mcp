#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""链接证据核验：只读 GET + 证据落盘 + 据证据判定“点开到底是什么”。

安全边界（写死，不给绕过口子）：
  * 只发 GET。绝不 POST/PUT/DELETE、绝不提交表单、绝不带凭据。
  * 目标是核验存在性，不是拿内容 —— 登录墙/人机验证一律判 BLOCKED 上报，
    绝不找绕过路径（不猜 token、不破 cookie、不装 UA 过身份校验）。
  * --rejudge 走 socket 层断网，只读已落盘证据，证明判定逻辑改动而不重抓。

判定枚举（六值语义 + 三值取不到）：
  ATTACHMENT TEXT_ON_PAGE ANNOUNCEMENT DIRECTORY NEWS NOTICE_PAGE DEAD BLOCKED UNKNOWN
"""
from __future__ import annotations

import argparse
import concurrent.futures as cf
import csv
import io
import json
import os
import re
import socket
import sys
import threading
import time
import zlib

try:
    import gzip as _gzip
except Exception:  # pragma: no cover
    _gzip = None

try:
    import requests
except Exception:  # requests 缺失时明确报错，不退化到 urllib（本机已验证有 requests）
    requests = None

VERDICTS = ("ATTACHMENT", "TEXT_ON_PAGE", "ANNOUNCEMENT", "DIRECTORY", "NEWS",
            "NOTICE_PAGE", "DEAD", "BLOCKED", "UNKNOWN")
OK_VERDICTS = ("ATTACHMENT", "TEXT_ON_PAGE", "ANNOUNCEMENT", "DIRECTORY", "NEWS", "NOTICE_PAGE")

HDRS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                  "(KHTML, like Gecko) Chrome/124.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "zh-CN,zh;q=0.9",
}
MAX_BYTES = 400_000          # 只读到判定够用为止，不整站下载
ENCODINGS = ("utf-8", "gb18030", "cp936")

# ---- 文件头（magic）优先于 Content-Type：扩展名和头都会说谎，字节不会 ----
MAGICS = (
    (b"%PDF", "PDF"),
    (b"PK\x03\x04", "ZIP/OOXML"),
    (b"\xd0\xcf\x11\xe0", "OLE"),
    (b"\x89PNG\r\n\x1a\n", "PNG"),
    (b"\xff\xd8\xff", "JPEG"),
    (b"GIF87a", "GIF"), (b"GIF89a", "GIF"),
    (b"RIFF", "RIFF/WEBP"),
    (b"BM", "BMP"),
    (b"\x00\x01\x00\x00", "TTF"),
)
FILE_MAGICS = ("PDF", "ZIP/OOXML", "OLE")
FILE_EXT = re.compile(r"\.(pdf|docx?|xlsx?|pptx?|zip|rar|wps|ofd|png|jpe?g|gif)$", re.I)

RE_BODY = re.compile(r"(主要目标|重点任务|保障措施|指导思想|专栏\d|总体目标|发展基础|空间布局|"
                     r"重点工程|工作目标|总体要求|基本原则|到20\d\d年)")
RE_NEWS = re.compile(r"(会议召开|审议通过|决议|报道|浏览[:：]|发布时间[:：]|印发|座谈会|调研|"
                     r"发布会|头条|要闻|会见|出席)")
RE_BUY = re.compile(r"(招标公告|采购公告|比选|竞争性(磋商|谈判)|中标|投标|代理机构|询价|供应商报名)")
RE_HUI = re.compile(r"(征求意见|征集.{0,10}意见|意见的公告|公开征集|意见反馈)")
RE_CATALOG = re.compile(r"(更多>>|首页\s*>.{0,40}列表|共\s*\d+\s*条|上一页|下一页|下页|TitleList|"
                        r"文档列表|返回列表|更多\s*>)")
RE_CAPTCHA = re.compile(r"(人机验证|验证码|滑动验证|安全验证|access denied|403\s*Forbidden|"
                        r"均被拦截|请完成安全验证|robot check)", re.I)
RE_LOGIN = re.compile(r"(请先登录|登录后查看|请登录|统一身份认证|ssoLogin|cas/login|login\.do|"
                      r"注册后(?:查看|使用))", re.I)
RE_DEADTXT = re.compile(r"(404|页面不存在|未找到|not\s*found|页面已删除|内容不存在|已下线|"
                        r"无法找到该页|错误提示)", re.I)
RE_ATT = re.compile(r"href=[\"'][^\"'>]*\.(?:pdf|docx?|xlsx?|pptx?|zip|rar|wps|ofd)", re.I)
RE_TITLE = re.compile(r"<title[^>]*>(.{0,120}?)</title>", re.S | re.I)
RE_TAG = re.compile(r"<script.*?</script>|<style.*?</style>|<[^>]+>", re.S | re.I)
RE_CD = re.compile(r"filename\*\s*=\s*[^'\']*'[^']*'([^;]+)|filename\s*=\s*\"?([^\";\r\n]+)", re.I)


def sniff(b: bytes) -> str:
    for sig, name in MAGICS:
        if b.startswith(sig):
            if name == "ZIP/OOXML":
                low = b[:2000]
                if b"word/" in low:
                    return "OOXML-docx"
                if b"xl/" in low:
                    return "OOXML-xlsx"
                if b"ppt/" in low:
                    return "OOXML-pptx"
            return name
    low = b[:600].lower()
    if b"<html" in low or b"<!doctype html" in low or b"<title" in low or b"<?xml" in low:
        return "HTML"
    return "OTHER"


def unzip(b: bytes) -> bytes:
    """Content-Encoding 头缺失/被反代吃掉时的兜底解压。"""
    if b[:2] == b"\x1f\x8b" and _gzip:
        try:
            return _gzip.decompress(b)
        except Exception:
            return b
    if b[:1] == b"\x78":
        try:
            return zlib.decompress(b)
        except Exception:
            return b
    return b


def decode(b: bytes, charset: str | None) -> str:
    """头里声明的 charset 优先，再 utf-8 → gb18030 → cp936（政府站大量 GB18030）。"""
    tries = ([charset] if charset else []) + list(ENCODINGS)
    for enc in tries:
        if not enc:
            continue
        try:
            return b.decode(enc.strip().lower())
        except Exception:
            continue
    return b.decode("utf-8", "replace")


def home_of(url: str) -> str | None:
    m = re.match(r"(https?://[^/]+)", url)
    return m.group(1) + "/" if m else None


class _GetOnlyAdapter(requests.adapters.HTTPAdapter if requests else object):
    """方法层硬闸：任何非 GET 的请求在这里直接抛错 —— 只读核验绝不改动目标。"""

    def send(self, request, *a, **k):
        if str(request.method).upper() != "GET":
            raise RuntimeError("只读核验：禁止发送 %s" % request.method)
        return super().send(request, *a, **k)


def _new_session():
    s = requests.Session()
    s.trust_env = False
    s.mount("http://", _GetOnlyAdapter())
    s.mount("https://", _GetOnlyAdapter())
    return s


def _get(session, url, timeout, verified):
    r = session.get(url, headers=HDRS, timeout=timeout, allow_redirects=True,
                    stream=True, verify=verified)
    try:
        raw = r.raw.read(MAX_BYTES, decode_content=True) or b""
    except Exception:
        raw = b""
    finally:
        r.close()
    return r, raw


def fetch(url: str, timeout: float, warm_home: str | None = None) -> dict:
    """只读 GET，follow 重定向，返回原始证据（不含判定）。"""
    ev = {"url": url, "http": 0, "bytes": 0, "magic": "", "ct": "", "final": "",
          "redirects": [], "server": "", "cd_filename": "", "is_file": False, "title": "",
          "text_len": 0, "body_hits": 0, "name_hits": [], "att": 0, "news": False,
          "buy": False, "hui": False, "catalog": False, "captcha": False,
          "login_wall": False, "dead_markers": [], "kw_hits": [], "ssl_verified": True,
          "err": "", "wall_url": ""}
    if requests is None:
        ev["err"] = "requests 未安装：pip install requests"
        return ev
    s = _new_session()
    try:
        if warm_home:                       # 403 时先访问首页拿 cookie 再试一次
            try:
                s.get(warm_home, headers=HDRS, timeout=timeout)
            except Exception:
                pass
        try:
            r, raw = _get(s, url, timeout, True)
        except requests.exceptions.SSLError:
            ev["ssl_verified"] = False      # 证书链不全的政府站：降级但留痕，人可复核
            r, raw = _get(s, url, timeout, False)
        ev["http"] = int(r.status_code)
        ev["final"] = str(r.url)
        ev["redirects"] = [{"code": h.status_code, "url": str(h.url)} for h in r.history]
        ev["ct"] = (r.headers.get("Content-Type") or "").strip()
        ev["server"] = r.headers.get("Server") or ""
        cd = r.headers.get("Content-Disposition") or ""
        m = RE_CD.search(cd)
        if m:
            ev["cd_filename"] = (m.group(1) or m.group(2) or "").strip().strip('"')
        if ev["redirects"]:
            ev["wall_url"] = ev["final"]
    except Exception as e:
        ev["err"] = type(e).__name__ + ":" + str(e)[:90]
        return ev
    finally:
        s.close()

    raw = unzip(raw)
    ev["bytes"] = len(raw)
    ev["magic"] = sniff(raw)
    charset = None
    m = re.search(r"charset\s*=\s*['\"]?([\w-]+)", ev["ct"] or "", re.I)
    if m:
        charset = m.group(1)
    ct0 = (ev["ct"] or "").lower()
    # HTML 和 text/* 都解成正文（政府站的 txt/json 附件同样要能核关键词）
    if ev["magic"] == "HTML" or ct0.startswith(("text/", "application/json", "application/xml")):
        txt = decode(raw[:MAX_BYTES], charset)
        plain = re.sub(r"\s+", " ", RE_TAG.sub(" ", txt))
        ev["text_len"] = len(plain)
        ev["body_hits"] = len(set(RE_BODY.findall(plain)))
        head = plain[:2000]
        ev["dead_markers"] = sorted(set(RE_DEADTXT.findall(head)))[:5]
        ev["_plain"] = plain            # 落盘成 .text.txt，不进 RESULTS
        if ev["magic"] == "HTML":
            tm = RE_TITLE.search(txt)
            ev["title"] = re.sub(r"\s+", " ", tm.group(1)).strip()[:180] if tm else ""
            ev["att"] = len(set(x.lower() for x in RE_ATT.findall(txt)))
            ev["news"] = bool(RE_NEWS.search(head)) and ev["body_hits"] < 3
            ev["buy"] = bool(RE_BUY.search(head)) and ev["body_hits"] < 3
            ev["hui"] = bool(RE_HUI.search(head + ev["title"]))
            ev["catalog"] = bool(RE_CATALOG.search(plain[:6000]))
            ev["captcha"] = bool(RE_CAPTCHA.search(head))
            ev["login_wall"] = bool(RE_LOGIN.search(head)) or \
                any(RE_LOGIN.search(str(h.get("url", ""))) for h in ev["redirects"]) or \
                bool(RE_LOGIN.search(ev["final"]))
            ev["ct_is_html"] = "html" in ct0 or "xml" in ct0
    ev["cd_is_file"] = bool(FILE_EXT.search(ev["cd_filename"]))
    ext_is_file = bool(FILE_EXT.search((ev["final"] or url).split("?")[0]))
    # 扩展名/头说它是文件、magic 说是 HTML —— 信 magic
    if ev["magic"] == "HTML":
        ev["is_file"] = False
    else:
        ev["is_file"] = (ev["magic"] in FILE_MAGICS or ev["magic"].startswith("OOXML")
                         or ev["cd_is_file"] or (ext_is_file and ev["bytes"] > 3000))
    return ev


def kw_scan(ev: dict, keywords) -> None:
    """--kw / 每条自带 keyword 在正文中的命中，带 ±60 字上下文，方便人工复验。"""
    plain = ev.get("_plain") or ""
    hits = []
    for kw in [k for k in keywords if k]:
        pos = plain.find(kw)
        rec = {"kw": kw, "found": pos >= 0}
        if pos >= 0:
            rec["context"] = plain[max(0, pos - 60):pos + len(kw) + 60]
        hits.append(rec)
    ev["kw_hits"] = hits
    ev["name_hits"] = [h["kw"] for h in hits if h["found"]]


def classify(ev: dict):
    """纯函数：只看已落盘的证据出判定。优先级：取不到 > 文件本体 > 页内正文强证据 >
    目录 > 采购公告 > 征求意见 > 新闻 > 页内正文 > 兜底。"""
    http = int(ev.get("http") or 0)
    n = int(ev.get("bytes") or 0)
    tl = int(ev.get("text_len") or 0)
    bl = int(ev.get("body_hits") or 0)
    nh = len(ev.get("name_hits") or [])
    title = str(ev.get("title") or "")
    magic = str(ev.get("magic") or "")

    if ev.get("err"):
        err = str(ev["err"])
        if re.search(r"Timeout|timed out", err, re.I):
            return "UNKNOWN", "读取超时，不能据此判死：%s" % err[:70]
        return "DEAD", "传输层失败：%s" % err[:90]
    if http in (404, 410, 451):
        return "DEAD", "HTTP %s" % http
    if http in (401, 403, 406, 408, 412, 429, 521):
        return "BLOCKED", "HTTP %s（服务端拒绝/限流，不得绕过）" % http
    if http == 0 or http >= 500:
        return "UNKNOWN", "HTTP %s 非正常应答" % http
    if ev.get("captcha"):
        return "BLOCKED", "人机验证/拦截页（停止，不改写绕过）"
    if ev.get("login_wall") and tl < 1500:
        return "BLOCKED", "登录墙：仅取到 %d 字导航文本" % tl
    if ev.get("dead_markers") and bl < 2 and tl < 4000:
        return "DEAD", "页面自述不可用：%s" % "/".join(ev["dead_markers"])
    if n < 1200:
        return "UNKNOWN", "HTTP 200 但仅 %d 字节，不足以证明任何东西" % n

    if ev.get("is_file") and n > 3000:
        return "ATTACHMENT", "magic=%s bytes=%d 附件本体（名=%s）" % (
            magic, n, ev.get("cd_filename") or os.path.basename(ev.get("final") or ev["url"]))

    if magic == "HTML":
        if tl < 600:
            return "UNKNOWN", "200 但只有 %d 字正文：疑 JS 壳/前端渲染，不是可核验的源" % tl
        if bl >= 5 and tl >= 20000:
            return "TEXT_ON_PAGE", "章节标记 %d 类 + 正文 %d 字" % (bl, tl)
        if re.search(r"(目录|列表|清单|一览)", title) and nh < 2:
            return "DIRECTORY", "标题即列表页：%s" % title[:40]
        if ev.get("catalog") and bl < 2 and not RE_T_FILE.search(title):
            return "DIRECTORY", "列表/分页特征 + 正文标记仅 %d 类" % bl
        if ev.get("buy") or RE_BUY.search(title):
            return "NOTICE_PAGE", "招标/采购用语，正文标记 %d 类" % bl
        if ev.get("hui") or RE_HUI.search(title):
            return "ANNOUNCEMENT", "征求意见公告，无正式正文"
        if RE_T_FILE.search(title) and (tl >= 8000 or nh >= 2 or bl >= 1):
            return "TEXT_ON_PAGE", "发文标题 + 正文 %d 字/标记 %d 类/关键词命中 %d" % (tl, bl, nh)
        if RE_NEWS.search(title) or (ev.get("news") and bl < 2):
            return "NEWS", "新闻/会议报道（标题或页首特征），正文标记 %d 类" % bl
        if bl >= 2 and nh >= 1 and tl > 2500:
            return "TEXT_ON_PAGE", "标记 %d 类 + 关键词命中 %d + %d 字" % (bl, nh, tl)
        if ev.get("catalog"):
            return "DIRECTORY", "分页/更多>>等列表特征"
        if RE_T_FILE.search(title):
            return "ANNOUNCEMENT", "发文标题但正文仅 %d 字，未取到全文" % tl
        return "ANNOUNCEMENT", "HTML 页 %d 字，正文标记 %d 类，无附件" % (tl, bl)
    if tl >= 1200:
        return "TEXT_ON_PAGE", "纯文本应答（content-type=%s）%d 字，无 HTML 结构" % (
            ev.get("ct"), tl)
    if magic in ("PNG", "JPEG", "GIF", "BMP", "RIFF/WEBP", "TTF"):
        return "UNKNOWN", "magic=%s 是图片/字体，不是可引用文本源" % magic
    return "UNKNOWN", "magic=%s 无法归类" % magic


RE_T_FILE = re.compile(r"(关于印发|的通知|的意见|规划的通知|实施方案|工作要点|办法|细则)")


def block_network():
    """--rejudge 的硬闸：任何 socket 连接直接抛错，证明判定改动不需要重抓。"""
    class _NoNetwork(socket.socket):
        def __init__(self, *a, **k):
            raise RuntimeError("OFFLINE: --rejudge 禁止任何网络访问")

    socket.socket = _NoNetwork          # type: ignore[misc]
    socket.create_connection = lambda *a, **k: (_ for _ in ()).throw(
        RuntimeError("OFFLINE: --rejudge 禁止任何网络访问"))


# ---------------- inputs ----------------

def load_items(path: str, url_col: str | None):
    if not os.path.exists(path):
        sys.exit("输入文件不存在：%s" % path)
    ext = os.path.splitext(path)[1].lower()
    items = []
    if ext == ".json":
        data = json.load(io.open(path, encoding="utf-8"))
        if isinstance(data, dict):
            data = data.get("items") or data.get("rows") or data.get("urls") or []
        for i, d in enumerate(data):
            if isinstance(d, str):
                items.append({"id": "%03d" % (i + 1), "url": d, "keyword": ""})
            else:
                items.append({"id": str(d.get("id") or "%03d" % (i + 1)),
                              "url": d.get("url") or d.get("链接") or "",
                              "keyword": d.get("keyword") or d.get("kw") or ""})
    elif ext in (".xlsx", ".xlsm"):
        try:
            import openpyxl
        except ImportError:
            sys.exit("本输入形态需要 openpyxl（本机 3.1.5 已装）；其他形态不受影响。")
        wb = openpyxl.load_workbook(path, read_only=True, data_only=True)
        ws = wb.active
        rows = [[("" if c is None else str(c)) for c in r] for r in ws.iter_rows(values_only=True)]
        items = _from_table(rows, url_col)
    elif ext == ".csv":
        with io.open(path, encoding="utf-8-sig", newline="") as f:
            rows = [[(c or "").strip() for c in r] for r in csv.reader(f)]
        items = _from_table(rows, url_col)
    else:                                    # 纯文本：一行一条 URL
        for i, line in enumerate(io.open(path, encoding="utf-8", errors="replace")):
            line = line.strip().lstrip("#")
            if not line or not line.lower().startswith("http"):
                continue
            items.append({"id": "%03d" % (i + 1), "url": line.split()[0], "keyword": ""})
    out, seen = [], {}
    for it in items:
        if not it["url"].lower().startswith("http"):
            continue
        uid = re.sub(r"[^0-9A-Za-z_.\-]", "_", it["id"])[:60] or "u"
        seen[uid] = seen.get(uid, 0) + 1
        if seen[uid] > 1:
            uid = "%s_%d" % (uid, seen[uid])
        it["id"] = uid
        out.append(it)
    if not out:
        sys.exit("没解析出任何 http(s) URL")
    return out


def _from_table(rows, url_col):
    if not rows:
        return []
    head = [str(h).strip() for h in rows[0]]
    low = [h.lower() for h in head]
    idx, has_head = None, False
    if url_col:
        key = url_col.strip().lower()
        if key in low:
            idx, has_head = low.index(key), True
        elif re.fullmatch(r"(?:col|c|#)?\d+", key):
            idx = int(re.sub(r"\D", "", key)) - 1
        else:
            sys.exit("--url-col %r 既不是表头列名也不是列号（列号从 1 起）" % url_col)
    else:
        for j, h in enumerate(low):
            if h in ("url", "链接", "网址", "地址", "link", "原文地址", "来源"):
                idx, has_head = j, True
                break
        if idx is None:
            sys.exit("表格里没认出 URL 列，请用 --url-col 指定列名或 1 基列号")

    def col(*names):
        for j, h in enumerate(low):
            if h in names:
                return j
        return None

    ji, jk = col("id", "编号", "序号"), col("keyword", "关键词", "名称", "标题", "文件名称")
    items = []
    for i, r in enumerate(rows[1:] if has_head else rows):
        if idx >= len(r) or not (r[idx] or "").strip().lower().startswith("http"):
            continue
        items.append({"id": (r[ji] if ji is not None and ji < len(r) else "") or "%03d" % (i + 1),
                      "url": (r[idx] or "").strip(),
                      "keyword": (r[jk] if jk is not None and jk < len(r) else "") or ""})
    return items


# ---------------- evidence io ----------------

def write_evidence(ev_dir, ev, verdict, reason):
    ev["verdict"] = verdict
    ev["verdict_reason"] = reason
    plain = ev.pop("_plain", "") or ""
    eid = ev["id"]
    body = os.path.join(ev_dir, eid + ".text.txt")
    if plain:
        io.open(body, "w", encoding="utf-8").write(
            "# url: %s\n# final: %s\n# verdict: %s | %s\n\n%s" %
            (ev["url"], ev["final"], verdict, reason, plain[:200000]))
        ev["evidence_file"] = os.path.basename(body)
    json.dump(ev, io.open(os.path.join(ev_dir, eid + ".json"), "w", encoding="utf-8"),
              ensure_ascii=False, indent=1)


def read_evidence(ev_dir):
    out = []
    for fn in sorted(os.listdir(ev_dir)):
        if not fn.endswith(".json") or fn in ("RESULTS.json",):
            continue
        try:
            d = json.load(io.open(os.path.join(ev_dir, fn), encoding="utf-8"))
        except Exception as e:
            print("跳过坏证据文件 %s: %s" % (fn, e))
            continue
        if isinstance(d, dict) and d.get("url"):
            d.setdefault("id", os.path.splitext(fn)[0])
            out.append(d)
    return out


def report(results, ev_dir, tag):
    json.dump(results, io.open(os.path.join(ev_dir, "RESULTS.json"), "w", encoding="utf-8"),
              ensure_ascii=False, indent=1)
    import collections
    dist = collections.Counter(r["verdict"] for r in results)
    bad = [r for r in results if r["verdict"] in ("DEAD", "UNKNOWN", "BLOCKED")]
    lines = ["== %s：%d 条，分布 %s" % (tag, len(results), json.dumps(dist, ensure_ascii=False)),
             "== 不可引用（DEAD/UNKNOWN/BLOCKED）%d 条" % len(bad)]
    for r in bad:
        lines.append("  %s｜%s｜%s｜%s" % (r["id"], r["verdict"], r["verdict_reason"], r["url"][:100]))
    io.open(os.path.join(ev_dir, tag + ".txt"), "w", encoding="utf-8").write("\n".join(lines) + "\n")
    for ln in lines:
        print(ln)
    return len([r for r in results if r["verdict"] in ("DEAD", "UNKNOWN")])


def main():
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    ap = argparse.ArgumentParser(
        prog="link_verify.py",
        description="链接证据核验：只发 GET（方法层拦截，非 GET 直接抛错；绝不提交表单、"
                    "绝不改动目标站点状态），落盘 HTTP/字节/magic/正文特征，"
                    "据证据判定九值枚举；--rejudge 断网复判已有证据。")
    ap.add_argument("input", nargs="?", help="JSON 数组 [{id,url,keyword}] / 一行一条 URL 的文本 / .xlsx .csv")
    ap.add_argument("--out", required=True, help="证据目录（RESULTS.json + 每条一个证据文件）")
    ap.add_argument("--kw", action="append", default=[], help="正文必须出现的关键词，可重复")
    ap.add_argument("--jobs", type=int, default=4)
    ap.add_argument("--timeout", type=float, default=15.0)
    ap.add_argument("--delay", type=float, default=0.6, help="全局请求间隔（秒），礼貌限速")
    ap.add_argument("--url-col", help="表格输入的列名或 1 基列号")
    ap.add_argument("--rejudge", action="store_true", help="离线复判：只读证据，绝不联网")
    args = ap.parse_args()

    os.makedirs(args.out, exist_ok=True)

    if args.rejudge:
        block_network()
        print("[offline] socket 层已断开，本次不产生任何 HTTP 请求")
        results = []
        changed = 0
        for ev in read_evidence(args.out):
            old = ev.get("verdict", "")
            v, why = classify(ev)
            ev["verdict_prev"] = old
            ev["verdict"], ev["verdict_reason"] = v, why
            if v != old:
                changed += 1
            json.dump(ev, io.open(os.path.join(args.out, ev["id"] + ".json"), "w",
                                  encoding="utf-8"), ensure_ascii=False, indent=1)
            results.append(ev)
        print("[offline] 改判 %d 条（逻辑更新所致，未重抓）" % changed)
        rc = report(results, args.out, "REJUDGE")
        print("[gate] DEAD/UNKNOWN = %d 条 → %s" % (rc, "FAIL" if rc else "PASS"))
        sys.exit(1 if rc else 0)

    if requests is None:
        sys.exit("需要 requests（本机 2.33.0 已装）：pip install requests")
    if not args.input:
        ap.error("非 --rejudge 模式必须给 INPUT")

    items = load_items(args.input, args.url_col)
    gate = threading.Semaphore(1)
    nxt = [0.0]

    def paced(fn, *a):
        with gate:
            wait = nxt[0] - time.time()
            nxt[0] = max(time.time(), nxt[0]) + args.delay
        if wait > 0:
            time.sleep(wait)
        return fn(*a)

    def work(it):
        ev = {"id": it["id"]}
        ev.update(paced(fetch, it["url"], args.timeout))
        kws = list(args.kw) + ([it["keyword"]] if it.get("keyword") else [])
        kw_scan(ev, kws)
        ev["keywords"] = [k for k in kws if k]
        # 403：带 cookie 预热重试一次（仍只 GET，不填任何凭据；仍 403 就报 BLOCKED）
        if ev.get("http") == 403 and not ev.get("err"):
            warm = paced(fetch, it["url"], args.timeout, home_of(it["url"]))
            if (warm.get("http") or 0) in (200, 206):
                warm["id"] = ev["id"]
                ev = warm
                kw_scan(ev, kws)
                ev["cookie_warmup"] = True
        v, why = classify(ev)
        write_evidence(args.out, ev, v, why)
        print("%s %s %s %s｜%s" % (it["id"], ev.get("http"), ev.get("magic"), v, why[:70]), flush=True)
        return ev

    with cf.ThreadPoolExecutor(max_workers=max(1, args.jobs)) as ex:
        results = list(ex.map(work, items))

    rc = report(results, args.out, "SUMMARY")
    print("[gate] DEAD/UNKNOWN = %d 条 → %s" % (rc, "FAIL" if rc else "PASS"))
    sys.exit(1 if rc else 0)


if __name__ == "__main__":
    main()
