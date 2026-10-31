#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""从中文表述里抠出 URL：只管提取与修正，不联网（提取和核验是两步，核验用 link_verify.py）。

处理中文稿的三类脏活：全角括号/引号/书名号粘连、尾部中文标点、括号不配对，
以及占位假链接（example.com、详见…、xxx）。
"""
from __future__ import annotations

import argparse
import io
import re
import sys

# URL 本体允许的 ASCII 字符；全角括号一并收进来，由 fix_tail 判断是正文括号还是句子括号
CORE = r"A-Za-z0-9\-._~:/?#\[\]@!$&'()*+,;=%"
RE_URL = re.compile(r"https?://[" + CORE + "\uff08\uff09]+")
# 结尾一律要剥掉的标点（不属于 URL）
TRAIL = ".,;:!?、。，；：！？'\"“”‘’«»"
# 收束符 → 起始符，及反向表
PAIRS = {")": "(", "\uff09": "\uff08", "]": "[", "】": "【", "」": "「",
         "』": "『", "》": "《", "\u201d": "\u201c", "\u2019": "\u2018"}
REV = {v: k for k, v in PAIRS.items()}
OPENS = set(PAIRS.values())
PLACEHOLDER = re.compile(
    r"(example\.(com|org|net|cn)|examples?\.|\btest\.(com|cn)|your[-_]?(domain|site|url|com)|"
    r"localhost|127\.0\.0\.1|0\.0\.0\.0|www\.xx\.com|[\u4e00-\u9fff\uff08\uff09()]{0,4}"
    r"(?:详见|见附件|此处填写|待补充|略))", re.I)
CJK = re.compile(r"[\u4e00-\u9fff\u3000-\u303f\uff00-\uffff]")


def fix_tail(u: str) -> str:
    """剥尾巴：尾部标点、不配对的收束符、不配对的起始符。"""
    while True:
        if not u:
            return u
        c = u[-1]
        if c in TRAIL:
            u = u[:-1]
            continue
        p = PAIRS.get(c)
        if p is not None and u.count(p) < u.count(c):      # 句子自己的括号，不是 URL 的
            u = u[:-1]
            continue
        if c in OPENS and u.count(c) > u.count(REV.get(c, "\x00")):   # 多余的起始符
            u = u[:-1]
            continue
        return u


def extract(text: str):
    kept, dropped = [], []
    for raw in RE_URL.findall(text or ""):
        u = fix_tail(raw)
        # 中文正文里紧贴 URL 的汉字已被字符类挡在外面；再检查主体是否已碎成句子
        if len(u) < len("http://x.co") + 3:
            dropped.append((u, "过短"))
            continue
        host = u.split("://", 1)[1].split("/", 1)[0]
        if CJK.search(host):
            dropped.append((u, "主机名含中文（占位/误粘）"))
            continue
        if PLACEHOLDER.search(u):
            dropped.append((u, "占位符"))
            continue
        if "…" in u or "..." in host:
            dropped.append((u, "省略号占位"))
            continue
        kept.append(u)
    return kept, dropped


def main():
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    ap = argparse.ArgumentParser(prog="url_extract.py",
                                 description="从中文文本提取 URL（不联网，纯文本处理）。")
    ap.add_argument("text_file", help="含 URL 的中文文本（.txt/.md/任意文本）")
    ap.add_argument("--dedupe", action="store_true", help="按出现顺序去重")
    args = ap.parse_args()

    text = io.open(args.text_file, encoding="utf-8", errors="replace").read()
    kept, dropped = extract(text)
    n0 = len(kept)
    if args.dedupe:
        kept = list(dict.fromkeys(kept))
    for u in kept:
        print(u)
    print("# 提取 %d 条，输出 %d 条%s" % (n0, len(kept), "（已去重）" if args.dedupe else ""))
    for u, why in dropped:
        print("# 丢弃：%s ｜%s" % (u[:80], why), file=sys.stderr)
    sys.exit(0 if kept else 1)


if __name__ == "__main__":
    main()
