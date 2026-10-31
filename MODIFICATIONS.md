# 改动记录

记录本镜像（agent-skills-mcp）与私有主库（skills）之间的同步动作。日期一律以主库提交时间为准。

## 2026-10-31 —— 技能库合并与上游升级

主库当天做了一次大整理：目录数 35 → 83，并把分散在三个位置的技能源合并为单一源。本镜像随之重建。

### 1. 合并（新增技能源）

| 来源 | 数量 | 处理 |
| --- | --- | --- |
| `.qoder-cn/skills` | 5 | 并入私库并保持启用（academic-paper-reviewer、obsidian-vault、pdf、skill-router、xlsx） |
| `.qoder-cn/skills-library` | 43 | 以 `SKILL.md.disabled` 形式存档（退役件，不占常驻上下文） |

两个来源目录已清空删除，此后私库为唯一技能源。镜像只收其中**能公开且仍启用**的部分，详见下文第 5 节。

### 2. 上游升级

| 技能 | 版本 | 内容 |
| --- | --- | --- |
| mcp-builder | v1 → v2 | 换用新版 MCP SDK 的构建指南；⚠️ 上游 anthropics/skills 无许可证，镜像不收 |
| archify | 3.0.1 → 3.2.0 | 新增 ERD / Class / Tree / Timeline / Waterfall 五类图与 explainer；许可证由 MIT 改为 Apache-2.0；删除旧 `lifecycle/grid-routing.mjs`（并入 shared 路由） |
| impeccable | 4.7.0 → 4.8.0 | 保留本地加装的 Agentsskills 小节与"与 frontend-design 配对"一节，仅同步上游正文 |

### 3. 适配（让技能能在本机跑通）

| 技能 | 改动 |
| --- | --- |
| vision-forensics | frontmatter 的折叠块 `description: >` 改为单行，避免部分解析器把后续字段吞进 description |
| win-window-shot | 同上，折叠块改单行 |
| ui-ux-pro-max | 命令里的 `${CLAUDE_PLUGIN_ROOT}` 占位符换成本机绝对路径（4 条命令试跑通过）；**镜像版已替换为 `%USERPROFILE%`** |
| thesis-creator | 工作区根改为 `桌面文件/thesis-workspace/`；补三条红线（不得编造数据、交付前必须机检、未执行的步骤不得写成已执行） |

### 4. frontmatter 修复（YAML 非法导致技能加载失败）

| 技能 | 症状 |
| --- | --- |
| agent-reach | 安装时把 `description: >` 折叠块内容误粘进了 `when_to_use`，两个字段错位 |
| cad-insight-pro | `summary` 字段的值吞掉了紧随其后的 `license` 行 |
| photoshop-expert | `description` 含半角冒号却未加引号，YAML 解析直接报错 |

### 5. 镜像收录范围（相对主库的取舍）

- **收**：自研技能（无隐私、无凭据）+ 许可证明确为 MIT / Apache-2.0 / BSD 的第三方技能。本次新增收录
  agent-cli-headless、link-verify、win-window-shot、xlsx-cell-diff、text-swap、draw-your-font、
  frontend-design、impeccable。
- **不收**：anthropics/skills 无许可证件（mcp-builder、canvas-design、theme-factory、webapp-testing，
  以及 pdf/xlsx/docx/powerpoint 的 Anthropic 专有 LICENSE）；非白名单许可证（lieflat-gongwen 为
  PolyForm NC）；无许可证或无来源（academic-paper-reviewer、agent-reach）；个人/私人技能
  （mood、companion、feishu-group、skill-router、obsidian-vault、dafeiyu-*、minimax-code-imagegen、
  beautiful-article）；全部 `SKILL.md.disabled` 退役件。
- **移出**：较上一版镜像移除 beautiful-article（正文含本机路径）、lieflat-gongwen（许可证）、
  cad-automation / cad-designer / ponytail（主库已退役），`skills/cad/` 类别随之取消。
- 完整名单与逐条原因见 [README](README.md#本镜像与私有主库的差异不含哪些为什么)。

### 6. 公开版脱敏

镜像文件逐字节取自主库 `git cat-file blob HEAD:<path>`（不读工作区，避免 CRLF 与树不一致），再跑一遍替换：

| 规则 | 替换为 | 本次命中 |
| --- | --- | --- |
| Windows 用户目录绝对路径（反斜杠） | `%USERPROFILE%` | 2 |
| 同上（正斜杠） | `%USERPROFILE%` | 18 |
| 个人笔记库绝对路径 | `$OBSIDIAN_VAULT` | 0 |
| 邮箱前缀（用户名 + `@`） | `<user>@` | 0 |
| `QQ` 上下文中的号码 | `<redacted>` | 0 |
| 裸用户名（Windows 账户名 / QQ 号） | `<user>` | 7 |
| 中国大陆手机号（前后须为词边界） | `<PHONE>` | 0 |
| **合计** | | **27** |

命中文件 9 个，集中在 ui-ux-pro-max、agent-cli-headless、thesis-creator、skill-manager、win-window-shot、link-verify、impeccable 的 SKILL.md 与两个 winshot/vischeck 脚本。

不是替换而是**不收**的：含真实姓名、手机号、私人群的技能整目录不进镜像（见第 5 节），避免"脱敏后仍有上下文泄露"。

> 注意：手机号规则最初写成"前后非数字"，在 impeccable 的字体索引 JSON 里误命中 131 次字形路径数据（如 `___19800000002j`），已收紧为词边界（`\w` 亦排除）后归零；上一版替换随之回滚重做。
