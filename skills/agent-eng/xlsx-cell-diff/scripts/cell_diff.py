# -*- coding: utf-8 -*-
"""cell_diff.py —— 两个 xlsx 的逐格差异（改前 → 改后），供工单与复审直接引用。

用法：
  py cell_diff.py OLD.xlsx NEW.xlsx [--sheet 总表 --sheet 台账] [--out report.md]
                                    [--max 300] [--full] [--values] [--links]

退出码：0 = 两表一致；1 = 有差异（可直接当门禁）；2 = 参数/读写错误。

实现要点（源脚本踩过的坑都写在这里）：
  * 每个工作簿只加载一次；默认 read_only=True 逐行流式比较，不把两张表整个搬进内存。
  * 默认比较公式原文（data_only=False）。加 --values 才比较缓存值 —— openpyxl 的
    data_only 只能拿到 *上次 Excel/WPS 打开并保存时* 缓存的计算结果，脚本刚生成的
    工作簿里公式格会返回 None（那是"没有缓存"，不是"值为空"，别当成缺陷）。
  * 列按表头名对齐，列序变了也能对上；改名/增删列单独报结构差异。表头缺失或重名时
    退回按列号对齐，并在报告里写明用了哪种对齐方式。
  * 日期/数字常以 float 或 datetime 回来（44925.0 与 44925 视为同值），比较前归一化。
  * --links 需要完整对象模型（read_only 下 cell 没有 hyperlink，工作表没有 merged_cells），
    会额外给出超链接目标差异与合并区变化；内存开销大，只在小表上用。
"""
import argparse
import difflib
import io
import os
import re
import sys
from itertools import zip_longest

try:
    import openpyxl
    from openpyxl.utils import get_column_letter as GL
except ImportError:
    sys.stderr.write("NEED openpyxl: py -m pip install openpyxl\n")
    sys.exit(2)

SNIP = 64


def conv():
    """GBK 控制台上打印中文 / ①★ 之类不炸。"""
    for s in (sys.stdout, sys.stderr):
        try:
            s.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass


def norm(v):
    """单元格值 → 可比较字符串；整型 float 抹掉 .0。"""
    if v is None:
        return ""
    if isinstance(v, float) and v.is_integer():
        return str(int(v))
    return str(v)


def flat(v):
    """压掉换行/竖线，但首尾空格必须显形（否则「CIM一期␣」和「CIM一期」看起来一样）。"""
    if v == "":
        return "（空）"
    if not v.strip():
        return "（纯空白 %d 字符）" % len(v)
    s = re.sub(r"\s+", " ", v.strip()).replace("|", "\\|")
    return "%s%s%s" % ("␣" if v[0] in " \t\n　" else "", s, "␣" if v[-1] in " \t\n　" else "")


def segs(a, b, full=False):
    """逐格「改前 → 改后」。短格直接给整值，长格只报变动片段；--full 一律给整值。"""
    if full or (len(a) <= SNIP and len(b) <= SNIP):
        return ["%s → %s" % (flat(a), flat(b))]
    out = []
    for tag, i1, i2, j1, j2 in difflib.SequenceMatcher(None, a, b, autojunk=False).get_opcodes():
        if tag == "equal":
            continue
        out.append("%s→%s" % (flat(a[i1:i2]), flat(b[j1:j2])))
    if not out:
        out = ["（同字不同格式/类型）"]
    return [x if len(x) <= SNIP * 2 else x[:SNIP] + "…" + x[-SNIP:] for x in out]


def val_at(row, i):
    return norm(row[i].value) if i < len(row) else ""


def names(row):
    """表头名 → 列号；有重名返回 None（让调用方退回列号对齐）。"""
    out = {}
    for i, c in enumerate(row):
        n = norm(c.value).strip()
        if n:
            if n in out:
                return None
            out[n] = i
    return out if out else None


def load(path, values, links):
    if links:
        return openpyxl.load_workbook(path, data_only=values)
    return openpyxl.load_workbook(path, read_only=True, data_only=values)


def align(ha, hb, ncol):
    """表头配对：返回 ([(旧列, 新列)], 改名[(旧列, 新列, 旧名, 新名)], 删除列, 新增列)。0-based。

    规则：两边表头都能唯一命名时按名字配对；剩下数量相等的孤儿列按列号配成"改名"；
    数量不等时孤儿列算删除/新增；没表头的列一律按列号对位补比（否则这些列的数据
    会被静默跳过，那是漏检）。表头有重名或整行没名字时退回全表按列号对位。
    """
    na, nb = names(ha), names(hb)
    if not na or not nb:
        rng = range(ncol)
        return ([(i, i) for i in rng],
                [(i, i, val_at(ha, i), val_at(hb, i)) for i in rng
                 if val_at(ha, i) != val_at(hb, i)],
                [], [])
    pairs = [(na[k], nb[k]) for k in nb if k in na]
    used_a = {p[0] for p in pairs}
    used_b = {p[1] for p in pairs}
    la = sorted(v for v in na.values() if v not in used_a)
    lb = sorted(v for v in nb.values() if v not in used_b)
    renamed = []
    if len(la) == len(lb):
        for ia, ib in zip(la, lb):
            renamed.append((ia, ib, val_at(ha, ia), val_at(hb, ib)))
            pairs.append((ia, ib))
        drop_a, drop_b = [], []
    else:
        drop_a, drop_b = la, lb
    used_a |= {p[0] for p in pairs}
    used_b |= {p[1] for p in pairs}
    free_a = [i for i in range(ncol) if i not in used_a and i not in drop_a]
    free_b = [i for i in range(ncol) if i not in used_b and i not in drop_b]
    pairs += list(zip(free_a, free_b))
    k = min(len(free_a), len(free_b))
    only_a = sorted(drop_a + free_a[k:])
    only_b = sorted(drop_b + free_b[k:])
    return sorted(pairs), renamed, only_a, only_b


def main():
    ap = argparse.ArgumentParser(description="两个 xlsx 的逐格差异（改前→改后），可当交付门禁")
    ap.add_argument("old", help="改前快照 xlsx")
    ap.add_argument("new", help="改后现表 xlsx")
    ap.add_argument("--sheet", action="append", default=[], dest="sheets",
                    help="只比这几个页签，可重复；默认比两边共有的全部页签")
    ap.add_argument("--out", help="同时把报告写成 markdown/txt 文件")
    ap.add_argument("--max", type=int, default=300, dest="mx",
                    help="最多列多少格变动，0=不限（默认 300）")
    ap.add_argument("--full", action="store_true", help="打印改前/改后完整值（默认只打印变动片段）")
    ap.add_argument("--values", action="store_true",
                    help="比较公式的缓存值（需文件被 Excel/WPS 打开保存过）；默认比较公式原文")
    ap.add_argument("--links", action="store_true",
                    help="额外比较超链接目标与合并区（走完整对象模型，内存开销大）")
    a = ap.parse_args()
    conv()

    for p in (a.old, a.new):
        if not os.path.isfile(p):
            sys.stderr.write("文件不存在：%s\n" % p)
            return 2
    cmd = 'py "%s" "%s" "%s"%s%s%s' % (
        os.path.abspath(__file__), a.old, a.new,
        "".join(' --sheet "%s"' % s for s in a.sheets),
        " --values" if a.values else "", " --links" if a.links else "")
    try:
        wa = load(a.old, a.values, a.links)
        wb = load(a.new, a.values, a.links)
    except Exception as e:
        sys.stderr.write("读不了：%s\n原因可能是文件被 Excel 占用、不是 xlsx、或加密。复现：%s\n" % (e, cmd))
        return 2

    L = ["# 逐格差异（脚本实测，非人工判读）", "",
         "改前：%s" % a.old, "改后：%s" % a.new,
         "复现：%s" % cmd,
         "取值口径：%s" % ("缓存计算值（data_only，无缓存的公式格读作空）" if a.values
                       else "单元格原文（公式显示为 =…）")]

    na, nb = wa.sheetnames, wb.sheetnames
    want = a.sheets or [s for s in na if s in nb] + [s for s in nb if s not in na]
    common = [s for s in want if s in na and s in nb]
    added = [s for s in want if s not in na and s in nb]
    removed = [s for s in want if s in na and s not in nb]
    absent = [s for s in want if s not in na and s not in nb]

    L.append("\n## 页签")
    L.append("共有 %d ｜ 新增 %s ｜ 删除 %s ｜ 两边都没有 %s" % (
        len(common), "、".join(added) or "无", "、".join(removed) or "无", "、".join(absent) or "无"))
    for s in added:
        L.append("- 新增页签「%s」%d 行 × %d 列（无改前基线，不逐格展开）"
                 % (s, wb[s].max_row, wb[s].max_column))
    for s in removed:
        L.append("- 删除页签「%s」改前 %d 行 × %d 列" % (s, wa[s].max_row, wa[s].max_column))
    for s in absent:
        L.append("- 未执行：页签「%s」两个文件里都不存在，没比。复现：%s" % (s, cmd))

    all_cells = []
    struct = 0
    for s in common:
        sa, sb = wa[s], wb[s]
        ga, gb = sa.iter_rows(), sb.iter_rows()
        ha, hb = list(next(ga, [])), list(next(gb, []))
        L.append("\n### %s" % s)
        if (sa.max_row, sa.max_column) != (sb.max_row, sb.max_column):
            struct += 1
        L.append("- 规模 %d 行 × %d 列 → %d 行 × %d 列（%+d 行 / %+d 列）" % (
            sa.max_row, sa.max_column, sb.max_row, sb.max_column,
            sb.max_row - sa.max_row, sb.max_column - sa.max_column))

        ncol = max(sa.max_column, sb.max_column)
        pairs, renamed, only_a, only_b = align(ha, hb, ncol)
        named = bool(names(ha)) and bool(names(hb))
        aligned_by = ("表头名（列序变了也能对上）" if named else "列号（表头缺失或有重名）") +             "，无表头列按列号补比"
        if only_a or only_b:
            struct += 1
        if only_a:
            L.append("- 删除列（改前有、改后没有）：%s" % "、".join(
                "%s1「%s」" % (GL(i + 1), flat(val_at(ha, i))) for i in only_a))
        if only_b:
            L.append("- 新增列（改后才有）：%s" % "、".join(
                "%s1「%s」" % (GL(i + 1), flat(val_at(hb, i))) for i in only_b))
        L.append("- 列对齐方式：%s（配对 %d 列）" % (aligned_by, len(pairs)))
        moved = [(ia, ib) for ia, ib in pairs if ia != ib]
        if moved:
            struct += 1
            L.append("- 列位移动（列序变了，按名对上）：%s" % "、".join(
                "%s↔%s" % (GL(ia + 1), GL(ib + 1)) for ia, ib in moved))
        if a.links:
            ma, mb = {str(r) for r in sa.merged_cells.ranges}, {str(r) for r in sb.merged_cells.ranges}
            if ma != mb:
                struct += 1
                L.append("- 合并区变化：新增 %s ｜ 解除 %s"
                         % ("、".join(sorted(mb - ma)) or "无", "、".join(sorted(ma - mb)) or "无"))

        cells, add_rows, del_rows = [], 0, 0
        struct += len(renamed)
        for ia, ib, o, n in renamed:
            cells.append(((1, ib), "%s1" % GL(ib + 1) + ("" if ia == ib else "（旧 %s1）" % GL(ia + 1)),
                          segs(o, n, a.full)))
        for i in only_a:
            if val_at(ha, i):
                cells.append(((1, i), "%s1（删除列）" % GL(i + 1),
                              ["%s → （改后无此列）" % flat(val_at(ha, i))]))
        for i in only_b:
            if val_at(hb, i):
                cells.append(((1, i), "%s1（新增列）" % GL(i + 1),
                              ["（改前无此列） → %s" % flat(val_at(hb, i))]))

        for rn, (rowa, rowb) in enumerate(zip_longest(ga, gb), start=2):
            if rowa is None:
                add_rows += 1
                for ib, c in enumerate(rowb):
                    if norm(c.value):
                        cells.append(((rn, ib), "%s%d（新增行）" % (GL(ib + 1), rn),
                                      ["（改前无第 %d 行） → %s" % (rn, flat(norm(c.value)))]))
                continue
            if rowb is None:
                del_rows += 1
                for ia, c in enumerate(rowa):
                    if norm(c.value):
                        cells.append(((rn, ia), "%s%d（删除行）" % (GL(ia + 1), rn),
                                      ["%s → （改后无第 %d 行）" % (flat(norm(c.value)), rn)]))
                continue
            rowa, rowb = list(rowa), list(rowb)
            for ia, ib in pairs:
                va, vb = val_at(rowa, ia), val_at(rowb, ib)
                la = lb = ""
                if a.links:
                    ca, cb = sa.cell(rn, ia + 1), sb.cell(rn, ib + 1)
                    la = ca.hyperlink.target if ca.hyperlink else ""
                    lb = cb.hyperlink.target if cb.hyperlink else ""
                if va == vb and la == lb:
                    continue
                sg = segs(va, vb, a.full) if va != vb else ["链:%s→%s" % (flat(la), flat(lb))]
                cells.append(((rn, ib), GL(ib + 1) + str(rn) + ("" if ia == ib else "（旧 %s）" % GL(ia + 1)), sg))
            for ib in only_b:
                v = val_at(rowb, ib)
                if v:
                    cells.append(((rn, ib), "%s%d（新增列）" % (GL(ib + 1), rn), ["（改前无此列） → %s" % flat(v)]))
            for ia in only_a:
                v = val_at(rowa, ia)
                if v:
                    cells.append(((rn, ia), "%s%d（删除列）" % (GL(ia + 1), rn), ["%s → （改后无此列）" % flat(v)]))
        struct += add_rows + del_rows
        if add_rows:
            L.append("- 改后多 %d 行（改前数据止于第 %d 行；新增格的逐格坐标见下表「新增行」标记）"
                     % (add_rows, sa.max_row))
        if del_rows:
            L.append("- 改后少 %d 行（改前有、改后没有的行止于第 %d 行；逐格见「删除行」标记）"
                     % (del_rows, sb.max_row + 1))
        cells.sort(key=lambda x: x[0])
        L.append("- 变更格数 %d" % len(cells))
        for _, coord, sg in cells:
            all_cells.append((s, coord, sg))

    L.append("\n## 逐格清单（共 %d 格）" % len(all_cells))
    if not all_cells:
        L.append("无单元格差异。")
    shown = all_cells if a.mx <= 0 else all_cells[:a.mx]
    for s, coord, sg in shown:
        L.append("| %s | %s | %s |" % (s, coord, "；".join(sg[:3]) + ("；…" if len(sg) > 3 else "")))
    if len(shown) < len(all_cells):
        L.append("\n（还有 %d 格未列出；全列请加 --max 0，复现：%s --max 0）"
                 % (len(all_cells) - len(shown), cmd))

    text = "\n".join(L) + "\n"
    print(text)
    if a.out:
        d = os.path.dirname(os.path.abspath(a.out))
        if not os.path.isdir(d):
            sys.stderr.write("--out 目录不存在：%s\n" % d)
            return 2
        with io.open(a.out, "w", encoding="utf-8") as f:
            f.write(text)
        print("已写出报告：" + a.out)
    if absent:
        return 2
    return 1 if (all_cells or struct or added or removed) else 0


if __name__ == "__main__":
    sys.exit(main())
