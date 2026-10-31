---
name: link-verify
description: 引用链接取证核验：把"原文可查/可下载"这种话变成落盘证据。只读 GET 抓 URL，记 HTTP 状态/字节数/magic/正文特征/关键词命中/登录墙，判九值枚举；证据可离线复判。触发词：核验引用链接、原文可下载是不是真的、台账里的 URL 复测、学术数据不能造假、链接死亡、把这批链接跑一遍证据。
---

# link-verify：引用链接取证与复判

写论文/公文/核验报告时，每个被引用的 URL 必须**可证明真实**，每个数字必须可溯源。
这个技能把散会在 2026-09 台账核验里的一次性脚本（`verify_urls.py` / `p05_classify.py` /
`rejudge_links.py` / `probe3.py`）收成两个通用工具：

- `scripts/link_verify.py` —— 抓 + 判 + 证据落盘 + 离线复判（九值枚举）
- `scripts/url_extract.py` —— 从中文表述里抠 URL（提取与核验是两步，分开）

**核心纪律**：判定只能由落盘的事实推出（HTTP/字节/magic/正文特征/附件数），
不能由"我记得这个链接是这么写的"推出。证据文件留下来，人是最终复核者。

## 何时用

- 交付任何带引用 URL 的稿子**之前**（不是之后）
- 有人说"原文可查""附件可下载"，你要把这句话写成能核的话
- 判定逻辑改了（比如目录页被误判成新闻），要用老证据复判而不重抓
- 台账/清单类批量链接复测（xlsx/csv 直接喂）

不适用：需要登录才能看的内容（判 BLOCKED 上报，别绕）、需要跑 JS 才能出正文的页面
（判 UNKNOWN，另找静态源）、图片型 PDF 的页码断言（本工具不解析 PDF 内容，见坑）。

## 命令

```bash
S=%USERPROFILE%/.agents/skills/link-verify/scripts

# 1) 从中文稿里先抠出 URL（不联网）
py "$S/url_extract.py" 稿子.txt [--dedupe]        # 一行一条，末行给条数

# 2) 逐条取证（只 GET；--jobs 并发但全局 --delay 限速）
py "$S/link_verify.py" INPUT --out ev --kw 关键词 [--kw 再一个] \
    [--jobs 4] [--timeout 15] [--delay 0.6]
echo $?                                            # 有 DEAD/UNKNOWN 即 1，可直接当闸门

# 3) 离线复判：改了 classify 后重出判定，绝不重抓
py "$S/link_verify.py" --out ev --rejudge
```

INPUT 三种形态，任选：
| 形态 | 说明 |
|---|---|
| `.json` | `[{"id":"A1","url":"https://…","keyword":"十四五"}]`，id/keyword 可省 |
| `.txt` | 一行一条 URL（`#` 开头忽略） |
| `.xlsx` / `.csv` | 用 `--url-col 列名` 或 `--url-col 3`（1 基）；表头有 编号/名称 时自动当 id/keyword |

依赖：`requests`（本机 2.33.0 已装，缺了直接报错不退化到 urllib）；表格输入另需
`openpyxl`（本机 3.1.5 已装；没装只影响 .xlsx 输入，其他形态照跑）。

产出（全在 `--out` 目录）：
- `RESULTS.json` —— 每条一行完整证据 + `verdict` + `verdict_reason`
- `<id>.json` —— 单条证据；`<id>.text.txt` —— 去标签正文，人可直接搜关键词
- `SUMMARY.txt` / `REJUDGE.txt` —— 分布 + 全部不可引用条目

## 九值枚举：允许你写下什么话

| verdict | 证据含义 | 稿子里能写 | 不能写 |
|---|---|---|---|
| `ATTACHMENT` | magic 是 PDF/OLE/OOXML 且 >3KB | 「原文可下载（PDF/DOCX，N 字节，文件名 X）」 | 内容页数、正文数字 |
| `TEXT_ON_PAGE` | 正文可读且含章节标记/关键词命中 | 「正文见该页：<标题>」+ 引原文句 | 「附件下载」 |
| `ANNOUNCEMENT` | 公告页，只有标题级信息 | 「该事项已发公告（页面未附全文）」 | 「原文可查」「数据见原文」 |
| `DIRECTORY` | 列表/目录页 | 「线索：该栏目下列有 X」 | 任何具体数字或原文 |
| `NEWS` | 新闻报道/会议稿 | 「媒体报道称 X（报道，非文件）」 | 「据文件」「原文可下载」 |
| `NOTICE_PAGE` | 招标/采购公告 | 「采购/招标公告：<标题>，发布日期」 | 中标金额除非正文写死并核过 |
| `DEAD` | 404/410/DNS 失败/页面自述不存在 | 「该链接已失效（HTTP 404，取证于 <日期>）」 | 任何引用 |
| `BLOCKED` | 401/403/412/429/登录墙/人机验证 | 「**不可核验**：需登录/被拦截」 | 任何"内容就是 X"的断言 |
| `UNKNOWN` | <1.2KB、JS 壳、magic 认不出、读超时 | 「无法确证」 | 一切 —— 这条要么换源要么删掉 |

DEAD/UNKNOWN/BLOCKED 一律如实上报（退出码非 0 就是为这个），**绝不糊**：
不许写"经查证"、不许用搜索引擎摘要冒充原文、不许为凑一个数字编个来源。
`--rejudge` 输出与上次不一致时，逐条看 `REJUDGE.txt` 的改判清单再定稿。

## 踩过的坑（都来自源脚本实测）

- **200 ≠ 有内容**：JS 渲染的列表页回 200 但正文只剩导航壳。故 magic=HTML 且去标签后
  <600 字一律 UNKNOWN，不算源。
- **magic 优先于头和扩展名**：`.pdf` 结尾的 URL 常返回一个 HTML 报错页；
  `Content-Type: text/html` 的二进制也见过。信字节头（`%PDF`/`PK\x03\x04`/`\xd0\xcf\x11\xe0`），
  不信头也不信扩展名。
- **GB18030 站点**：声明缺失或写错的不少，按 header → utf-8 → gb18030 → cp936 依次试，
  别默认 utf-8 然后 `errors="ignore"` 把关键词吞掉（那样"关键词命中=否"是假证据）。
- **.gov.cn 302 到登录/统一身份认证**：光看最终 URL 看不出来，故把重定向链每一跳和最终 URL
  都过一遍登录特征；403 只带 cookie 预热重试一次（GET 首页，不填任何凭据）。
- **超时不能当死亡**：ReadTimeout 判 UNKNOWN，DNS/连接拒绝才判 DEAD。
- **证书链不全**：默认校验证书；SSLError 时降级重试并在证据里写 `ssl_verified:false`，
  留痕给人复核，不静默关校验。
- **PDF 首页文字证明不了页码**：本工具不解析 PDF 版面。要写"见 P05 第 3 页"必须另有
  页数证据（pdf 技能里的 `page_audit.py --assert-text`），别拿取到字节数当页数。
- **中文正文粘连**：全角括号/书名号会把 URL 咬掉一截或多带尾巴，`url_extract.py` 处理
  配对与剥尾，但抠完仍要人扫一眼条数（stderr 会列丢弃原因）。

## 红线

只读取证。**不许**用这个工具拿凭据、猜 token、破 cookie、绕人机验证或压别人站
（并发 ≤4、全局 `--delay 0.6` 是默认值，别调成 0 打生产站）。页面在登录墙后面，
正确产出是 `BLOCKED` 加一句"不可核验"，不是绕过去。只发 GET —— 传输层挂了
`_GetOnlyAdapter`，任何非 GET 请求直接抛错（`session.post(...)` 实测被拦）。
