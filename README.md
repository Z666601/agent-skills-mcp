# Agent Skills & MCP 工具箱

做智能体（Agent）用得上的 **skill** 与 **MCP** 收集。全部来自真实在用的环境：本人日常运行的自研 skill、实测筛选后的第三方 skill（按分类安装），以及一个真实 AI 教育项目的思路蒸馏。

## skills/ —— 按分类安装的技能

每个技能是一个文件夹，放进 `~/.agents/skills/` 即被 agent 发现并按需加载（读取其中 `SKILL.md` 的 frontmatter）。

### coding-style/ —— 编码与输出风格

| 技能 | 用途 | 来源与许可 |
| --- | --- | --- |
| ponytail | 编码风格技能：强制最简可行方案（懒惰高级工程师视角），防过度设计 | 自研 |
| caveman | "原始人腔"输出风格，砍约 65% token；与 ponytail 官配 | [JuliusBrussee/caveman](https://github.com/JuliusBrussee/caveman) · Apache-2.0 |

### agent-eng/ —— 智能体工程

| 技能 | 用途 | 来源与许可 |
| --- | --- | --- |
| skill-manager | 技能库审计：统计 token 开销、找重复/重叠技能、禁用与恢复（包装 asm CLI，含 Windows 踩坑记录） | 自研 |
| windows-mcp | Windows 桌面自动化操作流程：配合 windows-mcp MCP 服务器控制鼠标/键盘/窗口/截图/注册表 | 自研 |

### cad/ —— CAD 自动化

| 技能 | 用途 | 来源与许可 |
| --- | --- | --- |
| cad-automation | 驱动 AutoCAD/中望/浩辰自动画图：pyautocad、win32com、AutoLISP、C#、VBA，批量处理与标注 v1.1.0 | 自研 |
| cad-designer | CAD 设计指导：制图规范（国标）、图层/标注标准、参数化思路、批量出图策略 v1.1.0 | 自研 |

### design/ —— 设计与视觉

| 技能 | 用途 | 来源与许可 |
| --- | --- | --- |
| ui-ux-pro-max | UI/UX 设计智能主技能：专业级界面设计决策 | [nextlevelbuilder/ui-ux-pro-max-skill](https://github.com/nextlevelbuilder/ui-ux-pro-max-skill) 子技能 · MIT |
| banner-design | 横幅/营销图设计 | 同上 · MIT |
| slides | 幻灯片/课件设计 | 同上 · MIT |
| archify | 生成可验证的架构/流程/时序图——自包含 HTML 动效，可导出 | [tt-a1i/archify](https://github.com/tt-a1i/archify) · MIT |

## docs/ —— 实战蒸馏

- [智教学：AI 教研学情系统的智能体增强思路](docs/zhijiaoxue-ideas.md) —— 一个真实落地的 AI 教育项目（教案生成→双闸校验→教师签发→判分复核→学情报告闭环；Node.js 标准库零依赖 + qwen-plus 可选）里蒸馏出的 agent/skill/MCP 思路与可复用模式。

## 推荐链接（实测过但不随仓库分发）

| 项目 | 是什么 | 星数 | 为什么只给链接 |
| --- | --- | --- | --- |
| [anthropics/skills](https://github.com/anthropics/skills) | Anthropic 官方技能库：19 个技能（docx/pdf/pptx/xlsx、mcp-builder、skill-creator、webapp-testing、canvas-design、theme-factory、frontend-design 等） | 179K★ | 仓库未附开源许可证，不做再分发；本仓库 `mcp-builder`/`webapp-testing`/`canvas-design`/`theme-factory` 即出自此处（仅私有库安装） |
| [obra/superpowers](https://github.com/obra/superpowers) | TDD/调试/规划的开发方法论技能框架 | 294K★ | 框架型，按其插件机制整装 |
| [mattpocock/skills](https://github.com/mattpocock/skills) | Matt Pocock 的实战工程技能集 | 274K★ | 合集型，按需自取 |
| [addyosmani/agent-skills](https://github.com/addyosmani/agent-skills) | Addy Osmani 的生产级工程技能 | 100K★ | 合集型 |
| [wshobson/agents](https://github.com/wshobson/agents) | 多平台 agent 插件市场（子智能体编排） | 40K★ | 市场型 |
| [Graphify-Labs/graphify](https://github.com/Graphify-Labs/graphify) | 代码库→可查询知识图谱（本地 AST，无向量库） | 123K★ | 需配套 CLI |
| [mvanhorn/last30days-skill](https://github.com/mvanhorn/last30days-skill) | 跨 Reddit/X/YouTube/HN 的近 30 天话题综述 | 63K★ | 与 Agent-Reach 功能相邻 |
| [multica-ai/andrej-karpathy-skills](https://github.com/multica-ai/andrej-karpathy-skills) | Karpathy 编码陷阱观察蒸馏的单文件 CLAUDE.md | 216K★ | 是全局配置不是 skill 目录 |
| [Leonxlnx/taste-skill](https://github.com/Leonxlnx/taste-skill) | 反"AI 味"设计品味技能合集 | 91K★ | 与 ui-ux-pro-max 重叠，已二选一 |
| [K-Dense-AI/scientific-agent-skills](https://github.com/K-Dense-AI/scientific-agent-skills) | 177 个科研技能 + 100+ 科学数据库 | 47K★ | 领域专精，按需安装 |
| [VoltAgent/awesome-agent-skills](https://github.com/VoltAgent/awesome-agent-skills) | 1000+ 技能目录 | 35K★ | 索引 |
| [ComposioHQ/awesome-claude-skills](https://github.com/ComposioHQ/awesome-claude-skills) | 经典 Claude 技能精选列表 | 76K★ | 索引 |

MCP 生态速查：[registry.modelcontextprotocol.io](https://registry.modelcontextprotocol.io) · 官方示例服务器：[modelcontextprotocol/servers](https://github.com/modelcontextprotocol/servers)

## License

本仓库自身代码 MIT。第三方技能遵循其原仓库许可证（见各表格标注），版权归原作者。
