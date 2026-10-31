# Agent Skills & MCP 工具箱

做智能体（Agent）用得上的 **skill** 与 **MCP** 收集。全部来自真实在用的环境：本人日常运行的自研 skill、实测筛选后的第三方 skill（按分类安装），以及一个真实 AI 教育项目的思路蒸馏。

每个技能是一个文件夹，放进 `~/.agents/skills/` 即被 agent 发现并按需加载（读取其中 `SKILL.md` 的 frontmatter）。

本仓库是私有主库的分类镜像，只收录能公开的技（自研 + MIT / Apache-2.0 / BSD 第三方）。改动记录见 [MODIFICATIONS.md](MODIFICATIONS.md)。

## 技能清单

### skills/agent-eng/ —— 智能体工程

| 技能 | 一句话 | 来源 / 许可 |
| --- | --- | --- |
| [agent-cli-headless](skills/agent-eng/agent-cli-headless) | 无人值守驱动 agent CLI：确切命令、环境变量坑、授权陷阱 | 自研 |
| [link-verify](skills/agent-eng/link-verify) | 引用链接取证：只读 GET 落盘 HTTP 状态/字节/magic/正文特征，判九值枚举，证据可离线复判 | 自研 |
| [skill-manager](skills/agent-eng/skill-manager) | 技能库审计（包装 asm CLI）：常驻 token 开销、重复安装、启用/禁用 | 自研 |
| [vision-forensics](skills/agent-eng/vision-forensics) | 视觉取证四流程；视觉读数必须过像素定量复核才可作改动依据 | 自研（灵感：[Anionex/agent-vision-toolkit](https://github.com/Anionex/agent-vision-toolkit)） |
| [win-window-shot](skills/agent-eng/win-window-shot) | 悬浮窗可见性取证：PrintWindow 抓被遮挡窗口真实像素 + "它真在屏幕上吗"的定点像素证据 | 自研 |
| [windows-mcp](skills/agent-eng/windows-mcp) | 配合 windows-mcp MCP 服务器的 Windows 桌面操作方法论（含焦点纪律、对话框驱动） | 自研 |
| [xlsx-cell-diff](skills/agent-eng/xlsx-cell-diff) | xlsx 逐格改前改后取证 + 单表结构机检，退出码当流水线门禁 | 自研 |

### skills/design/ —— 设计与视觉

| 技能 | 一句话 | 来源 / 许可 |
| --- | --- | --- |
| [archify](skills/design/archify) | 可验证的架构/流程/时序/数据流/生命周期/ERD/类图/树/时间线图，自包含 HTML 带动效可导出 | [tt-a1i/archify](https://github.com/tt-a1i/archify) · Apache-2.0 |
| [banner-design](skills/design/banner-design) | 横幅/营销图设计子技能 | [nextlevelbuilder/ui-ux-pro-max-skill](https://github.com/nextlevelbuilder/ui-ux-pro-max-skill) · MIT |
| [draw-your-font](skills/design/draw-your-font) | 把一张手写照片做成可安装字体（TTF/WOFF/WOFF2） | MIT（著作权人见仓库 LICENSE） |
| [frontend-design](skills/design/frontend-design) | 前端视觉语言与审美方向，克制模板化默认样式；与 impeccable 配对 | [anthropics/skills](https://github.com/anthropics/skills) · Apache-2.0 |
| [impeccable](skills/design/impeccable) | 前端设计质量 v4.8.0：设计规范、命令手册、反模式检测、live 浏览器迭代 | [pbakaus/impeccable](https://github.com/pbakaus/impeccable) · Apache-2.0 |
| [scroll-craft](skills/design/scroll-craft) | 滚动叙事沉浸式落地页（只用于营销页/发布页/作品集，普通后台别叫它） | [nateherkai/scroll-craft](https://github.com/nateherkai/scroll-craft) · MIT |
| [slides](skills/design/slides) | 幻灯片/课件设计子技能 | [nextlevelbuilder/ui-ux-pro-max-skill](https://github.com/nextlevelbuilder/ui-ux-pro-max-skill) · MIT |
| [text-swap](skills/design/text-swap) | 图片上取字填字：擦掉旧文字/手迹、贴上新文字 | 自研 |
| [ui-ux-pro-max](skills/design/ui-ux-pro-max) | UI/UX 设计主技能：风格/配色/字体/UX 规则的可检索知识库 | [nextlevelbuilder/ui-ux-pro-max-skill](https://github.com/nextlevelbuilder/ui-ux-pro-max-skill) · MIT |

### skills/writing/ —— 写作与文档

| 技能 | 一句话 | 来源 / 许可 |
| --- | --- | --- |
| [thesis-creator](skills/writing/thesis-creator) | 本科毕业论文全流程：选题→交稿，含降重、AIGC 痕迹降低与本地检测 | [Stars-OC/thesis-creator](https://github.com/Stars-OC/thesis-creator) · MIT |

### skills/coding-style/ —— 编码与输出风格

| 技能 | 一句话 | 来源 / 许可 |
| --- | --- | --- |
| [caveman](skills/coding-style/caveman) | "原始人腔"省 token：砍约 65% 输出，lite/full/ultra + wenyan 四档 | [JuliusBrussee/caveman](https://github.com/JuliusBrussee/caveman) · Apache-2.0 |

## 本镜像与私有主库的差异：不含哪些、为什么

镜像来自私有主库 `skills/` 全量目录（83 个），按"能公开"筛掉 65 个。三类原因：

**1. 许可证不允许再分发或不在白名单**

| 技能 | 原因 |
| --- | --- |
| mcp-builder / canvas-design / theme-factory / webapp-testing | 来自 anthropics/skills，该仓无开源许可证，仅授权在 Anthropic 服务内使用 |
| pdf / xlsx / docx / powerpoint | 同上，LICENSE.txt 为 Anthropic 专有条款（"governed by your agreement with Anthropic"） |
| lieflat-gongwen | PolyForm Noncommercial 1.0.0，非 MIT/Apache/BSD 白名单许可 |
| academic-paper-reviewer | 无 LICENSE 文件、无明确来源，无法确认可否再分发 |
| agent-reach | 上游未附许可证（README 亦标注"见原仓库"） |

**2. 个人/私人技能（含身份、凭据、私人库路径或私人工作流）**

| 技能 | 原因 |
| --- | --- |
| mood / companion | 个人情绪与关系状态层，运行时含私人日记 |
| feishu-group | 往私人飞书群发消息，凭据走本机 env |
| skill-router | 指向本机技能库绝对路径与个人分拣偏好 |
| obsidian-vault | 直接读写私人笔记库绝对路径 |
| dafeiyu-bilibili / dafeiyu-organs | 个人桌宠人格与账号运营脚本 |
| minimax-code-imagegen | 绑定本机桌面应用与本地控件坐标 |
| beautiful-article | 正文含本机绝对路径与个人工作流约定 |

**3. 已退役件（私有主库中为 `SKILL.md.disabled`，共 50 个，其中 43 个是 2026-10-31 归档的）**

退役技能不公开：它们不进任何 agent 的技能列表，公开只会误导使用者。因此本镜像也没有
cad-automation、cad-designer、ponytail、ttc-cad、ttc-dxf、arxiv、deep-research、docx、
powerpoint、xlsx、json-canvas、humanizer、markdown-viewer 等。

例外说明：`gongwen-gbt9704` 是独立 git 仓库（MIT），不在私有主库内，故不随本镜像分发，请直接取上游。

## docs/ —— 实战蒸馏

- [智教学：AI 教研学情系统的智能体增强思路](docs/zhijiaoxue-ideas.md) —— 真实落地的 AI 教育项目（教案生成→双闸校验→教师签发→判分复核→学情报告闭环；Node.js 标准库零依赖 + qwen-plus 可选）蒸馏出的 8 条增强思路、11 项工具清单与 5 个可复用工程模式。

## 推荐链接（实测过但不随仓库分发）

| 项目 | 是什么 | 星数 | 为什么只给链接 |
| --- | --- | --- | --- |
| [anthropics/skills](https://github.com/anthropics/skills) | Anthropic 官方 19 技能（docx/pdf/pptx/xlsx、mcp-builder、skill-creator、frontend-design 等） | 179K★ | 仓库未附开源许可证，不做再分发 |
| [obra/superpowers](https://github.com/obra/superpowers) | TDD/调试/规划方法论技能框架 | 294K★ | 框架型，按其插件机制整装 |
| [mattpocock/skills](https://github.com/mattpocock/skills) | Matt Pocock 实战工程技能集 | 274K★ | 合集型，按需自取 |
| [addyosmani/agent-skills](https://github.com/addyosmani/agent-skills) | Addy Osmani 生产级工程技能 | 100K★ | 合集型 |
| [wshobson/agents](https://github.com/wshobson/agents) | 多平台 agent 插件市场（子智能体编排） | 40K★ | 市场型 |
| [Graphify-Labs/graphify](https://github.com/Graphify-Labs/graphify) | 代码库→可查询知识图谱 | 123K★ | 需配套 CLI |
| [mvanhorn/last30days-skill](https://github.com/mvanhorn/last30days-skill) | 近 30 天跨平台话题综述 | 63K★ | 与 Agent-Reach 相邻 |
| [multica-ai/andrej-karpathy-skills](https://github.com/multica-ai/andrej-karpathy-skills) | Karpathy 编码陷阱单文件蒸馏 | 216K★ | 是全局配置不是 skill 目录 |
| [Leonxlnx/taste-skill](https://github.com/Leonxlnx/taste-skill) | 反"AI 味"设计品味合集 | 91K★ | 与 ui-ux-pro-max 重叠 |
| [K-Dense-AI/scientific-agent-skills](https://github.com/K-Dense-AI/scientific-agent-skills) | 177 个科研技能 + 100+ 科学数据库 | 47K★ | 领域专精 |
| [VoltAgent/awesome-agent-skills](https://github.com/VoltAgent/awesome-agent-skills) | 1000+ 技能目录 | 35K★ | 索引 |
| [ComposioHQ/awesome-claude-skills](https://github.com/ComposioHQ/awesome-claude-skills) | 经典 Claude 技能精选列表 | 76K★ | 索引 |

MCP 生态速查：[registry.modelcontextprotocol.io](https://registry.modelcontextprotocol.io) · 官方示例服务器：[modelcontextprotocol/servers](https://github.com/modelcontextprotocol/servers)

## License

本仓库自身代码 MIT。第三方技能遵循其原仓库许可证，版权归原作者（各技能目录内保留原 LICENSE）。
