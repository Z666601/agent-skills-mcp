# -*- coding: utf-8 -*-
"""table_check.py —— xlsx 交付前的机检门禁：一次跑完所有结构校验，逐项 PASS/FAIL。

用法：
  py table_check.py FILE.xlsx [--rules RULES.json] [--enum "页签:列=值1,值2"]
                [--key "页签:列"] [--sheet 页签] [--write] [--raw]

退出码：0 = 全部跑完且全 PASS；1 = 有 FAIL 或有 SKIP（没跑成的检查不算通过）；
2 = 参数/读写错误。

设计（沿用交付包 自检.py 的骨架，把任务专属的东西挪进 JSON）：
  * 免规则的通用检查每个表都跑：表头齐不齐、整行重复、夹空行、首尾空格。
  * 主键唯一、必填非空、枚举取值、行数与声称总数对账、合计与总额对账、跨页签引用，
    全部由 RULES.json 描述，代码里不写死任何某次交付的页签名/列名/取值。
  * 列一律按表头名定位（全角半角括号与空格归一化后精确匹配，退化到唯一前缀），
    客户挪列序不会把检查带崩。
  * 合并单元格按左上角取值扩散到整块，避免"值只在 A1、C7 读成空"的假 FAIL。
  * 默认 data_only=True 取缓存计算值；脚本刚生成、没被 Excel/WPS 打开保存过的文件里
    公式格会读成 None，这时用 --raw 看公式原文，或让其在 Excel/WPS 里保存一次再机检。
  * 检查跑不成 → 明确记 SKIP + 原因 + 复现命令，绝不写 PASS。
"""
import argparse
import io
import json
import os
import re
import sys
import collections
from datetime import date, datetime

try:
    import openpyxl
    from openpyxl.utils import get_column_letter as GL
except ImportError:
    sys.stderr.write("NEED openpyxl: py -m pip install openpyxl\n")
    sys.exit(2)

MAXCOORD = 20


def conv():
    for s in (sys.stdout, sys.stderr):
        try:
            s.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass


def nn(s):
    """列名/取值比较用的归一化文本：去空白、全角括号转半角。"""
    return re.sub(r"\s+", "", "" if s is None else str(s)).replace("（", "(").replace("）", ")")


def txt(v):
    """单元格 → 展示用字符串（日期/浮点的坑在这里处理）。"""
    if v is None:
        return ""
    if isinstance(v, datetime):
        return v.strftime("%Y-%m-%d %H:%M:%S") if (v.hour or v.minute or v.second) else v.strftime("%Y-%m-%d")
    if isinstance(v, date):
        return v.strftime("%Y-%m-%d")
    if isinstance(v, float) and v.is_integer():
        return str(int(v))
    return str(v).strip()


def num(v):
    """能认成数字就返回 float，否则 None（容忍千分位逗号与全角逗号）。"""
    if isinstance(v, bool):
        return None
    if isinstance(v, (int, float)):
        return float(v)
    s = txt(v).replace(",", "").replace("，", "")
    if not s or s.startswith("="):
        return None
    try:
        return float(s)
    except ValueError:
        return None


ROWS = {}


def grid(ws):
    """整表取值 + 合并单元格按左上角扩散（read_only 拿不到 merged_cells，故用普通加载）。"""
    g = [[c.value for c in row] for row in ws.iter_rows()]
    width = max([len(r) for r in g] or [0])
    for r in g:
        r.extend([None] * (width - len(r)))
    for rng in ws.merged_cells.ranges:
        v = ws.cell(rng.min_row, rng.min_col).value
        for r in range(rng.min_row, min(rng.max_row, len(g)) + 1):
            for c in range(rng.min_col, min(rng.max_col, width) + 1):
                g[r - 1][c - 1] = v
    return g


def sheet_grid(name):
    if name not in ROWS:
        ROWS[name] = grid(ROWS["!wb"][name])
    return ROWS[name]


class Chks(object):
    def __init__(self, cmd):
        self.items = []
        self.cmd = cmd

    def add(self, status, name, detail=""):
        self.items.append((status, name, detail))
        print("%s %02d %s%s" % (status, len(self.items), name, "" if not detail else " | " + detail))

    def ok(self, name, detail=""):
        self.add("PASS", name, detail)

    def fail(self, name, detail=""):
        self.add("FAIL", name, detail)

    def skip(self, name, why):
        self.add("SKIP", name, "未执行：%s。复现：%s" % (why, self.cmd))

    def counts(self):
        c = collections.Counter(s for s, _, _ in self.items)
        return c["PASS"], c["FAIL"], c["SKIP"]


def col_of(hdr, want):
    """按表头名定位列（0-based）。找不到返回 (None, 候选列表)。"""
    t = nn(want)
    for i, h in enumerate(hdr):
        if nn(txt(h)) == t:
            return i, []
    pref = [i for i, h in enumerate(hdr) if nn(txt(h)).startswith(t) and t]
    if len(pref) == 1:
        return pref[0], []
    cands = [txt(h) for h in hdr if txt(h)]
    return None, cands


def used_cols(g, hr):
    """表头行的实际列宽（截掉尾部空列）。"""
    n = 0
    for i, h in enumerate(g[hr - 1] if len(g) >= hr else []):
        if any(nn(txt(r[i])) for r in g if i < len(r)):
            n = i + 1
    return max(n, len([h for h in (g[hr - 1] if len(g) >= hr else []) if txt(h)]))


def data_rows(g, hr, ds=None):
    """数据行索引列表（0-based）+ 最后一个有内容行号。"""
    start = (ds - 1) if ds else hr
    last = 0
    for i, r in enumerate(g):
        if i >= start and any(nn(txt(v)) for v in r):
            last = i
    return list(range(start, last + 1)), last


def stated_value(ref, C):
    """{"sheet":.., "cell":"B7"} 或 {"sheet":.., "label":"项目总数"} → 数字。
    label 命中后优先取右邻格，取不到取下方格（竖排口径表常见）。"""
    sh = ref.get("sheet")
    if not sh or sh not in ROWS["!wb"].sheetnames:
        C.skip("定位 %s" % ref, "页签「%s」不存在，现有页签 %s" % (sh, ROWS["!wb"].sheetnames))
        return None
    g = sheet_grid(sh)
    if ref.get("cell"):
        m = re.match(r"^([A-Z]+)(\d+)$", ref["cell"].strip().upper())
        if not m:
            C.skip("定位 %s" % ref, "cell 写法不是 A1 形式")
            return None
        r, c = int(m.group(2)) - 1, 0
        for i, ch in enumerate(m.group(1)):
            c = c * 26 + (ord(ch) - 64)
        c -= 1
        v = g[r][c] if r < len(g) and c < len(g[r]) else None
    else:
        lab = nn(ref.get("label"))
        hit = None
        for ri, row in enumerate(g):
            for ci, v in enumerate(row):
                if nn(txt(v)) == lab:
                    hit = (ri, ci)
                    break
            if hit:
                break
        if not hit:
            C.skip("定位「%s」" % ref.get("label"), "页签「%s」里找不到这个标签（含全半角归一化）" % sh)
            return None
        ri, ci = hit
        v = None
        for x in g[ri][ci + 1:]:
            if num(x) is not None:
                v = x
                break
        if v is None and ri + 1 < len(g) and ci < len(g[ri + 1]):
            v = g[ri + 1][ci]
    n = num(v)
    if n is None:
        C.skip("取数 %s" % ref, "定位到的格是「%s」，不是数字" % txt(v))
    return n


def main():
    ap = argparse.ArgumentParser(description="xlsx 交付机检门禁：逐条 PASS/FAIL/SKIP，有 FAIL 非零退出")
    ap.add_argument("file", help="要机检的 xlsx")
    ap.add_argument("--rules", help="规则 JSON（页签/主键/必填/枚举/对账）")
    ap.add_argument("--enum", action="append", default=[], metavar="页签:列=值1,值2",
                    help="命令行补枚举域，可重复；省略页签则套到所有含该列的页签")
    ap.add_argument("--key", action="append", default=[], metavar="页签:列",
                    help="命令行补主键列，可重复")
    ap.add_argument("--sheet", action="append", default=[], dest="only",
                    help="只检这几个页签，可重复；默认检全部可见页签")
    ap.add_argument("--write", action="store_true", help="把同样结果写到工作簿旁边的 -自检结果.txt")
    ap.add_argument("--raw", action="store_true", help="读公式原文而不是缓存值")
    a = ap.parse_args()
    conv()

    if not os.path.isfile(a.file):
        sys.stderr.write("文件不存在：%s\n" % a.file)
        return 2
    cmd = 'py "%s" "%s"' % (os.path.abspath(__file__), a.file)
    if a.rules:
        cmd += ' --rules "%s"' % a.rules
    if a.raw:
        cmd += " --raw"
    try:
        wb = openpyxl.load_workbook(a.file, data_only=not a.raw)
    except Exception as e:
        sys.stderr.write("读不了：%s\n复现：%s\n" % (e, cmd))
        return 2
    rules = {}
    if a.rules:
        if not os.path.isfile(a.rules):
            sys.stderr.write("规则文件不存在：%s\n" % a.rules)
            return 2
        try:
            rules = json.load(io.open(a.rules, encoding="utf-8"))
        except Exception as e:
            sys.stderr.write("规则 JSON 读不了：%s\n" % e)
            return 2
    for spec in a.key:
        sh, col = spec.split(":", 1) if ":" in spec else (None, spec)
        for t in [sh] if sh else list(wb.sheetnames):
            rules.setdefault("sheets", {}).setdefault(t, {})["key"] = col
    for spec in a.enum:
        scope, rest = spec.split(":", 1) if ":" in spec else (None, spec)
        if "=" not in rest:
            sys.stderr.write("--enum 写法应为 列=值1,值2：%s\n" % spec)
            return 2
        col, vals = rest.split("=", 1)
        targets = [scope] if scope else list(wb.sheetnames)
        for t in targets:
            rules.setdefault("sheets", {}).setdefault(t, {}).setdefault("enums", {})[col] = \
                [v for v in re.split(r"[,，]", vals) if v != ""]

    ROWS.clear()
    ROWS["!wb"] = wb
    C = Chks(cmd)
    print("FILE %s" % a.file)
    print("规则 %s ｜ 取值 %s ｜ 页签 %s" % (a.rules or "仅通用检查",
          "公式缓存值（--raw 可看原文）" if not a.raw else "公式原文",
          "、".join(wb.sheetnames)))

    sheets = a.only or [s for s in wb.sheetnames if wb[s].sheet_state == "visible"]
    for s in wb.sheetnames:
        if s not in sheets:
            print("（跳过页签 %s：不在 --sheet 列表或为隐藏页）" % s)
    if not sheets:
        C.fail("有可检页签", "一个页签都没匹配上：%s" % wb.sheetnames)

    for s in sheets:
        if s not in wb.sheetnames:
            C.skip("页签「%s」存在" % s, "文件里没有这个页签，现有页签 %s" % wb.sheetnames)
            continue
        g = sheet_grid(s)
        rule = rules.get("sheets", {}).get(s, {})
        hr = int(rule.get("header_row", 1))
        if not g or len(g) < hr:
            C.fail("页签「%s」有表头行" % s, "只有 %d 行" % len(g))
            continue
        n = used_cols(g, hr)
        if n == 0:
            C.fail("页签「%s」表头行非空" % s, "第 %d 行全空" % hr)
            continue
        hdr = g[hr - 1][:n]
        blanks = [GL(i + 1) + str(hr) for i in range(n)
                  if not txt(hdr[i]) and any(i < len(r) and nn(txt(r[i])) for r in g[hr:])]
        if blanks:
            C.fail("页签「%s」表头无空列" % s,
                   "%d 列有数据无标题：%s%s" % (len(blanks), "、".join("%s!%s" % (s, x) for x in blanks[:MAXCOORD]),
                                               "…共 %d" % len(blanks) if len(blanks) > MAXCOORD else ""))
        else:
            C.ok("页签「%s」表头无空列" % s, "%d 列全有标题" % n)

        drows, last = data_rows(g, hr, rule.get("data_start"))
        empty_inside = [i + 1 for i in range(hr, last) if not any(nn(txt(v)) for v in g[i])]
        if empty_inside:
            C.fail("页签「%s」无夹空行" % s,
                   "%d 行：%s%s" % (len(empty_inside),
                                    "、".join("%s!A%d" % (s, r) for r in empty_inside[:MAXCOORD]),
                                    "…共 %d" % len(empty_inside) if len(empty_inside) > MAXCOORD else ""))
        else:
            C.ok("页签「%s」无夹空行" % s, "数据行 %d 行（第 %d–%d 行）" % (len(drows), hr + 1, last + 1))

        seen, dup = {}, []
        for i in drows:
            k = tuple(nn(txt(v)) for v in g[i][:n])
            if k in seen:
                dup.append("%s!A%d（与第 %d 行整行相同）" % (s, i + 1, seen[k]))
            else:
                seen[k] = i + 1
        if dup:
            C.fail("页签「%s」无整行重复" % s, "%d 处：%s%s" % (len(dup), "、".join(dup[:MAXCOORD]),
                                                             "…共 %d" % len(dup) if len(dup) > MAXCOORD else ""))
        else:
            C.ok("页签「%s」无整行重复" % s, "%d 行互不相同" % len(drows))

        ws_ = []
        for i in drows:
            for j, v in enumerate(g[i][:n]):
                t = "" if v is None else str(v)
                if t and t != t.strip() and len(ws_) < MAXCOORD * 4:
                    ws_.append("%s!%s%d" % (s, GL(j + 1), i + 1))
        if ws_:
            C.fail("页签「%s」无首尾空格" % s, "%d 格：%s%s" % (len(ws_), "、".join(ws_[:MAXCOORD]),
                                                             "…共 %d" % len(ws_) if len(ws_) > MAXCOORD else ""))
        else:
            C.ok("页签「%s」无首尾空格" % s)

        if rule.get("expect_rows") is not None:
            want = int(rule["expect_rows"])
            (C.ok if len(drows) == want else C.fail)(
                "页签「%s」行数=%d" % (s, want), "实 %d 行（第 %d–%d 行）" % (len(drows), hr + 1, last + 1))
        if rule.get("stated_rows"):
            v = stated_value(rule["stated_rows"], C)
            if v is not None:
                (C.ok if int(v) == len(drows) else C.fail)(
                    "页签「%s」行数与声明总数一致" % s, "声明 %d ｜ 实 %d" % (int(v), len(drows)))

        key = rule.get("key")
        if key:
            ci, cands = col_of(hdr, key)
            if ci is None:
                C.skip("页签「%s」主键「%s」唯一非空" % (s, key), "找不到该列，现有表头：%s" % "、".join(cands[:12]))
            else:
                vals, blank, dup = collections.defaultdict(list), [], []
                for i in drows:
                    v = nn(txt(g[i][ci]))
                    if not v:
                        blank.append("%s!%s%d" % (s, GL(ci + 1), i + 1))
                    else:
                        vals[v].append(i + 1)
                dup = ["%s!%s%d（%s 出现 %d 次）" % (s, GL(ci + 1), r, k, len(vals[k]))
                       for k, rows in vals.items() if len(rows) > 1 for r in rows[1:]]
                bad = blank + dup
                if bad:
                    C.fail("页签「%s」一行一事项：主键「%s」唯一非空" % (s, key),
                           "空 %d ／ 重复 %d ｜ %s%s" % (len(blank), len(dup), "、".join(bad[:MAXCOORD]),
                                                        "…共 %d" % len(bad) if len(bad) > MAXCOORD else ""))
                else:
                    C.ok("页签「%s」一行一事项：主键「%s」唯一非空" % (s, key),
                         "%d 行 %d 个不同键（列 %s）" % (len(drows), len(vals), GL(ci + 1)))

        for col in rule.get("required", []):
            ci, cands = col_of(hdr, col)
            if ci is None:
                C.skip("页签「%s」必填列「%s」非空" % (s, col), "找不到该列，现有表头：%s" % "、".join(cands[:12]))
                continue
            miss = ["%s!%s%d" % (s, GL(ci + 1), i + 1) for i in drows if not nn(txt(g[i][ci]))]
            (C.ok if not miss else C.fail)(
                "页签「%s」必填列「%s」填满" % (s, col),
                "%d/%d 行非空" % (len(drows) - len(miss), len(drows)) if not miss
                else "缺 %d 格：%s%s" % (len(miss), "、".join(miss[:MAXCOORD]),
                                       "…共 %d" % len(miss) if len(miss) > MAXCOORD else ""))

        for col, allowed in rule.get("enums", {}).items():
            ci, cands = col_of(hdr, col)
            if ci is None:
                C.skip("页签「%s」枚举列「%s」" % (s, col), "找不到该列，现有表头：%s" % "、".join(cands[:12]))
                continue
            al = {nn(x) for x in allowed}
            bad, dist = [], collections.Counter()
            for i in drows:
                v = nn(txt(g[i][ci]))
                dist[v or "（空）"] += 1
                if v not in al and not (not v and "" in allowed):
                    bad.append("%s!%s%d(=%s)" % (s, GL(ci + 1), i + 1, txt(g[i][ci])[:20] or "空"))
            (C.ok if not bad else C.fail)(
                "页签「%s」枚举列「%s」只 %d 值" % (s, col, len(allowed)),
                str(dict(dist)) if not bad else
                "越界 %d 格：%s%s ｜ 实际分布 %s" % (len(bad), "、".join(bad[:MAXCOORD]),
                                                  "…共 %d" % len(bad) if len(bad) > MAXCOORD else "", dict(dist)))

        for col, ref in rule.get("refs", {}).items():
            ci, cands = col_of(hdr, col)
            tgt = ref.get("sheet")
            if ci is None:
                C.skip("页签「%s」引用列「%s」" % (s, col), "找不到该列，现有表头：%s" % "、".join(cands[:12]))
                continue
            if not tgt or tgt not in wb.sheetnames:
                C.skip("页签「%s」→「%s」引用完整" % (s, tgt), "目标页签不存在，现有页签 %s" % wb.sheetnames)
                continue
            th = int(ref.get("header_row", 1))
            tg = sheet_grid(tgt)
            tci, tcands = col_of(tg[th - 1][:used_cols(tg, th)], ref.get("key", col))
            if tci is None:
                C.skip("页签「%s」→「%s」引用完整" % (s, tgt), "目标页签找不到键列「%s」，现有表头：%s"
                       % (ref.get("key", col), "、".join(tcands[:12])))
                continue
            pool = {nn(txt(r[tci])) for r in tg[th:] if nn(txt(r[tci]))}
            miss = ["%s!%s%d(=%s)" % (s, GL(ci + 1), i + 1, txt(g[i][ci])[:20])
                    for i in drows if nn(txt(g[i][ci])) and nn(txt(g[i][ci])) not in pool]
            (C.ok if not miss else C.fail)(
                "页签「%s」的「%s」都在「%s!%s」里" % (s, col, tgt, ref.get("key", col)),
                "%d 个取值全部有对应条目" % len(pool) if not miss
                else "落空 %d 格：%s%s" % (len(miss), "、".join(miss[:MAXCOORD]),
                                        "…共 %d" % len(miss) if len(miss) > MAXCOORD else ""))

        st = rule.get("stated_sum")
        if st:
            ci, cands = col_of(hdr, st.get("column", ""))
            if ci is None:
                C.skip("页签「%s」列「%s」合计对账" % (s, st.get("column")),
                       "找不到该列，现有表头：%s" % "、".join(cands[:12]))
            else:
                vals = [num(g[i][ci]) for i in drows]
                got = sum(v for v in vals if v is not None)
                nonnum = ["%s!%s%d(=%s)" % (s, GL(ci + 1), i + 1, txt(g[i][ci])[:20])
                          for i, v in zip(drows, vals) if v is None and nn(txt(g[i][ci]))]
                want = stated_value(st.get("stated", {}), C)
                if want is not None:
                    tol = float(st.get("tolerance", 0.01))
                    (C.ok if abs(got - want) <= tol else C.fail)(
                        "页签「%s」「%s」合计与声明一致" % (s, st.get("column")),
                        "实算 %.4f ｜ 声明 %.4f ｜ 容差 %g%s" % (got, want, tol,
                        "；非数字格 %d：%s" % (len(nonnum), "、".join(nonnum[:10])) if nonnum else ""))

    p, f, k = C.counts()
    print("\nTOTAL %d 项 ｜ PASS %d / FAIL %d / SKIP %d" % (len(C.items), p, f, k))
    if f:
        print("FAIL 明细：" + "、".join(n for s, n, _ in C.items if s == "FAIL"))
    if k:
        print("未执行明细：" + "、".join(n for s, n, _ in C.items if s == "SKIP"))
    if a.write:
        out = os.path.splitext(os.path.abspath(a.file))[0] + "-自检结果.txt"
        with io.open(out, "w", encoding="utf-8") as fh:
            fh.write("FILE %s\n复现 %s\n\n" % (a.file, cmd))
            for i, (s, n, d) in enumerate(C.items, start=1):
                fh.write("%s %02d %s%s\n" % (s, i, n, "" if not d else " | " + d))
            fh.write("\nTOTAL %d 项 ｜ PASS %d / FAIL %d / SKIP %d\n" % (len(C.items), p, f, k))
            if k:
                fh.write("未执行：%s\n" % "、".join(n for s, n, _ in C.items if s == "SKIP"))
            fh.write("说明：SKIP = 该检查没跑成（列名/页签找不到等），不等于通过。\n")
        print("已写出：" + out)
    return 0 if (f == 0 and k == 0) else 1


if __name__ == "__main__":
    sys.exit(main())
