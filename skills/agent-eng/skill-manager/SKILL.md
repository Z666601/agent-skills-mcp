---
name: skill-manager
description: 技能库审计与瘦身。凡用户提到"技能太多/skill太多/管理技能/审计技能/清理技能/技能占上下文/上下文开销/skill audit"，或要求统计技能token开销、找重复重叠技能、禁用或恢复技能时使用。包装本机已装的 asm (agent-skill-manager) CLI。
when_to_use: 用户提到技能太多/管理技能/审计技能/清理技能/技能占上下文/上下文开销，或要统计技能 token 开销、找重复重叠技能、禁用/恢复技能时使用。
---

# 技能审计与管理（asm 包装）

前置事实：asm v2.18.0 已通过 `npm install -g agent-skill-manager` 装好；配置（`asm config path` 查看）里 hermes provider 已指向本机真实目录 `<本机 Hermes 技能目录>`。asm 扫描覆盖：Hermes 顶层技能 26 个 + 通用 `.agents/skills`（如 agent-reach、本技能）。

## 按需求选命令

| 用户想要 | 命令 |
|----------|------|
| 总量与常驻token开销 | `asm stats --tokens` |
| 找重复安装 | `asm audit` |
| 找功能重叠（不同名干同样事） | `asm audit overlap` |
| 找"不值得常驻"的技能 | `asm audit residency` |
| 禁用（可逆，改名 SKILL.md→.disabled） | `asm disable <名字>` |
| 恢复 | `asm enable <名字>` |
| 看单个技能详情/正文 | `asm inspect <名字>` / `asm get <名字>` |

## 流程

1. 审计类请求：跑对应命令，**原样呈现结果并给出你的解读**（哪个该禁、为什么、禁了省多少）。
2. 禁用类请求：先展示该技能的 `asm inspect` 信息和禁用后果，**获得用户确认后再执行**；禁止未经确认批量 disable。
3. 报告末尾附恢复方式：`asm enable <名字>`。

## 红线（都有原因）

- **绝不触碰 ZCode 官方插件缓存** `<ZCode 官方插件缓存目录>`——那里的技能由 ZCode 插件系统管理（启用/禁用走插件开关），asm 改动会破坏插件完整性检查。
- `disable` 的原理是把 SKILL.md 改名为 SKILL.md.disabled，目录保留、完全可逆——所以"删掉"需求也先用 disable 实现，真删除让用户自己 `asm uninstall`。
- 配置里 `customPaths` 保持为空：该功能在 Windows 上有 bug（数组或对象格式都会让 `asm list` 崩溃，v2.18.0 实测）。
- Hermes 索引约 115 个技能（含嵌套子技能），asm 只能看到顶层目录；嵌套技能属于其父技能的一部分，不单独处理。
- 数字（token 数、重叠度）直接引用 asm 输出，不要自己估算后冒充 asm 的结果。
