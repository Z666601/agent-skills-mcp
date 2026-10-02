# Agent Skills & MCP 工具箱

做智能体（Agent）用得上的 **skill** 与 **MCP** 收集。全部来自真实在用的环境：本人日常运行的自研 skill、实测过的第三方项目，以及一个真实 AI 教育项目的思路蒸馏。

## skills/ —— 开箱即用的技能

每个目录是一个完整 skill：把文件夹放进 `~/.agents/skills/`（或你的 agent 对应技能目录），agent 读取其中的 `SKILL.md`（YAML frontmatter 声明名称/触发时机/描述）即可按需加载。

| 技能 | 用途 |
| --- | --- |
| ponytail | 编码风格技能：强制最简可行方案（懒惰高级工程师视角），防过度设计 |
| skill-manager | 技能库审计：统计 token 开销、找重复/重叠技能、禁用与恢复（包装 asm CLI，含 Windows 踩坑记录） |
| windows-mcp | Windows 桌面自动化操作流程：配合 windows-mcp MCP 服务器控制鼠标/键盘/窗口/截图/注册表 |
| cad-automation | 驱动 AutoCAD/中望/浩辰自动画图：pyautocad、win32com、AutoLISP、C#、VBA，批量处理与标注 v1.1.0 |
| cad-designer | CAD 设计指导：制图规范（国标）、图层/标注标准、参数化思路、批量出图策略 v1.1.0 |
| mood | 跨会话情绪状态层：PAD 三维（愉悦/唤醒/支配）+ 信任系数 + 时间衰减，agent 心情有连续性。引擎只记账（state.py），情绪判断由模型自己做 |

## docs/ —— 实战蒸馏

- [智教学：AI 教研学情系统的智能体增强思路](docs/zhijiaoxue-ideas.md) —— 一个真实落地的 AI 教育项目（面向中学教师的教案生成→双闸校验→教师签发→判分复核→学情报告闭环；Node.js 标准库零依赖 + qwen-plus 可选）里蒸馏出的 agent/skill/MCP 思路与可复用模式。

## 推荐的第三方项目（实测过才收录）

| 项目 | 是什么 | 获取 |
| --- | --- | --- |
| Agent-Reach | 全网调研技能+CLI：搜索/读网页/社媒内容/行情，15 平台多后端路由 | [github.com/Panniantong/Agent-Reach](https://github.com/Panniantong/Agent-Reach) |
| text-to-cad | 文本转 3D：build123d 参数化建模、STEP/DXF/STL 出图、DFM 检查，附 13 个 agent skill | [github.com/earthtojake/text-to-cad](https://github.com/earthtojake/text-to-cad) |
| windows-mcp（MCP 服务器） | 让 agent 操控 Windows 桌面：截图、点击、打字、窗口管理、进程/注册表 | pypi: `windows-mcp` |
| agent-skill-manager（asm） | 技能库管理 CLI：审计 token 开销、重叠检测、启用/禁用技能 | npm: `agent-skill-manager` |
| MCP 官方示例服务器 | filesystem / fetch / memory 等参考实现 | [github.com/modelcontextprotocol/servers](https://github.com/modelcontextprotocol/servers) |

MCP 生态速查：[registry.modelcontextprotocol.io](https://registry.modelcontextprotocol.io)

## License

MIT
