# Agent Skills & MCP 工具箱

做智能体（Agent）用得上的 **skill** 与 **MCP** 收集。全部来自真实在用的环境：本人日常运行的自研 skill、实测筛选后的第三方 skill（按分类安装），以及一个真实 AI 教育项目的思路蒸馏。

每个技能是一个文件夹，放进 `~/.agents/skills/` 即被 agent 发现并按需加载（读取其中 `SKILL.md` 的 frontmatter）。

## skills/writing/ —— 写作与文档

### beautiful-article —— 文章美化（MIT）
把网页 URL / PDF / DOCX / Markdown / 截图等素材，编辑设计成一篇可离线打开和分享的**单文件 HTML 网页长文**。基于 reacticle 语义组件协议——不手写裸 HTML/CSS，而是"语义组件 + 主题约束的自由层"，按"素材→规划→双确认→生成→终审→修复"的 harness 流程推进，默认 100% 信息保留。
**用途/触发**："把这篇做成网页文章 / 生成一篇可分享的 HTML 长文 / render this as a beautiful web article"。适合公众号长文、教程、 briefing、方案分析的可视化交付。只做文章，不做后台/dashboard。
来源：[ConardLi/garden-skills](https://github.com/ConardLi/garden-skills) · MIT

### lieflat-gongwen —— 公文写作 DNA（PolyForm NC 1.0.0，非商业）
基于真实公文**全量统计**的公文内容写作技能（管"写什么、怎么写"，不管排版）。分公文族与党建族两族：调研报告 / 领导讲话 / 工作意见 / 经验材料 / 工作方案 / 经验总结六类公文文体，加千字级党建与基层经验材料。提供**可验收的数值参数**（段落配比、句长等）、骨架公式、标题技法，并带自动化自检脚本。
**用途/触发**："写一篇调研报告 / 起草领导讲话 / 写份工作意见 / 让这篇稿子更有公文味 / 检查这篇公文的参数对不对"。
来源：[larashero3-dotcom/lieflat-gongwen](https://github.com/larashero3-dotcom/lieflat-gongwen) · ⚠️ 非商业许可证，商用需获授权

### thesis-creator —— 毕业论文全流程（MIT）
面向中国本科生的毕业论文辅助系统：从选题到交稿的端到端工作流，含**降重优化、AIGC 痕迹降低和本地检测**。
**用途/触发**："帮我写论文 / 帮我降重"。
来源：[Stars-OC/thesis-creator](https://github.com/Stars-OC/thesis-creator) · MIT

**写作方向更多推荐（只给链接）**：[Tomsawyerhu/Chinese-WebNovel-Skill](https://github.com/Tomsawyerhu/Chinese-WebNovel-Skill)（833★，中文网文写作，无许可证）· [KaguraNanaga/official-document-writing-skill](https://github.com/KaguraNanaga/official-document-writing-skill)（296★，GB/T 9704 公文结构化写作，MIT）· [mizzlelover/gongwen-gbt9704-skill](https://github.com/mizzlelover/gongwen-gbt9704-skill)（本人在用的 GB/T 9704 公文**排版**技能，管格式不管内容）

## skills/coding-style/ —— 编码与输出风格

### ponytail —— 懒惰高级工程师（自研）
强制最简可行方案的编码风格：标准库/平台原生优先、最短可用 diff、YAGNI（不值得做的不做）；lite/full/ultra 三档强度。红线：输入校验、防数据丢失的错误处理和安全不做简化。
**用途/触发**：任何写代码/改代码/评审/技术选型的任务。

### caveman —— 原始人腔省 token（Apache-2.0）
"why use many token when few token do trick"——把输出压到最省的说话风格，实测砍约 65% 输出 token。与 ponytail 是官配（ponytail 文档明写 "pair with Caveman"）：一个管懒，一个管省。
来源：[JuliusBrussee/caveman](https://github.com/JuliusBrussee/caveman) · Apache-2.0

## skills/agent-eng/ —— 智能体工程

### skill-manager —— 技能库审计（自研）
包装 [agent-skill-manager](https://www.npmjs.com/package/agent-skill-manager)（asm）CLI：统计常驻 token 开销、找重复安装与功能重叠、评估"不值得常驻"的技能、禁用/恢复。附 Windows 实测踩坑记录（customPaths bug、官方插件缓存红线）。
**用途/触发**："技能太多 / 审计技能 / 省上下文"。

### windows-mcp —— Windows 桌面自动化流程（自研）
配合 [windows-mcp](https://pypi.org/project/windows-mcp/) MCP 服务器操控 Windows 的操作方法论：鼠标点击、键盘输入、快捷键、截图回看、窗口管理、滚动拖拽、剪贴板、进程/注册表。
**用途/触发**：任何需要操作原生 Windows 应用/桌面的任务。

### vision-forensics —— 视觉取证（自研）
让模型"看图"并据图行动的工作流，核心纪律：**任何视觉读数在像素定量复核之前都只是假设**。把看图拆成四类流程——看图问答（裁剪优先、CDN 时效管理）、图像取证对比（视觉报的缺陷必须 numpy 全分辨率复核，复核不过直接驳回）、设计稿/截图→前端代码（切栅格逐区提取、生成后逐区像素 diff 验收）、GUI 自动化（定位→换算→操作→闭环截图）。grounding 输出强制带原始分辨率像素坐标与证据。
**用途/触发**：看截图、视觉验收、两图找差异、设计稿还原代码、屏幕找控件。
由本机视觉取证实战管线与 [Anionex/agent-vision-toolkit](https://github.com/Anionex/agent-vision-toolkit) 的结构化任务拆分、grounding 坐标证据规范融合而成（去除了外部 API 依赖与应用绑定）。

## skills/cad/ —— CAD 自动化

### cad-automation —— CAD 自动绘图 v1.1.0（自研）
驱动 AutoCAD（兼容中望、浩辰）二次开发：Python（pyautocad/win32com）、AutoLISP、C#、VBA 连接 CAD 画图改图、图层管理、标注、块与属性、三维建模、批量处理、文件转换。管"写代码把图画出来"。

### cad-designer —— CAD 设计指导 v1.1.0（自研）
国标制图规范、图层/标注标准、参数化设计思路、批量出图策略、设计检查清单。管"怎么设计才对"，不写代码——与 cad-automation 是"设计师 + 程序员"分工。

## skills/design/ —— 设计与视觉

### ui-ux-pro-max —— UI/UX 设计主技能（MIT）
专业级 UI/UX 设计智能：界面设计决策、审美约束、多平台适配。
来源：[nextlevelbuilder/ui-ux-pro-max-skill](https://github.com/nextlevelbuilder/ui-ux-pro-max-skill) · MIT

### banner-design —— 横幅/营销图（MIT）
同上仓库的子技能：横幅与营销视觉设计。
**用途/触发**：做 banner、封面图、营销素材。

### slides —— 幻灯片/课件（MIT）
同上仓库的子技能：幻灯片与课件设计。
**用途/触发**：做演示文稿、教学课件。

### archify —— 可验证的图表（MIT）
生成**可验证**的架构图/工作流图/时序图/数据流图/生命周期图：自包含 HTML、带动效、可导出；自带渲染器、布局修复与校验脚本（需本地 Node.js）。
来源：[tt-a1i/archify](https://github.com/tt-a1i/archify) · MIT

### scroll-craft —— 滚动叙事落地页（MIT，选择性调用）
高端滚动驱动网页：先规划访客旅程、页面文法、情绪峰值和"专属签名动效"，再做带独立视觉层的三维 Hero、克制的动效、独立的移动端构图。支持用现有照片/视频素材或生成写实素材。
**⚠️ 选择性调用**——只用于：营销主页、产品发布页、作品集、餐饮/服务品牌页这类"要讲故事"的页面。普通后台、文档页、表单页**不要**叫它，普通的用 ui-ux-pro-max 就够。
来源：[nateherkai/scroll-craft](https://github.com/nateherkai/scroll-craft) · MIT

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

本仓库自身代码 MIT。第三方技能遵循其原仓库许可证（见各技能标注，其中 lieflat-gongwen 为 PolyForm 非商业许可证），版权归原作者。
