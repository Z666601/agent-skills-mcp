---
name: agent-cli-headless
description: "无人值守驱动本机 ZCode/Qoder agent CLI：确切命令、环境变量坑与授权陷阱。"
---

# Agent CLI headless（本机 ZCode / Qoder 无人值守驱动）

让本机其他智能体（ZCode、Qoder）自己执行任务（如往飞书群发消息）。无人值守会话里 GUI 点击（computer_use）会卡在授权弹窗直到超时——凡是能让智能体自己跑 CLI 的活，一律走 CLI，不走截屏点击。

## Qoder CLI（已端到端验证）

```bash
env -u QODER_AGENT_SDK_ENTRYPOINT -u QODER_AGENT_SDK_VERSION -u QODER_SDK_AUTH_PAYLOAD_FILE -u QODER_AGENT_SDK_PAYLOAD_FILE \
  %USERPROFILE%/.qoder-cn/bin/qoderclicn/qoderclicn.exe -p --permission-mode bypass_permissions "<提示词>"
```

- 四个 QODER_AGENT_SDK / QODER_SDK 变量必须 unset（第四个 `QODER_AGENT_SDK_PAYLOAD_FILE` 是后来补上的，多 unset 一个无害）：本机终端常继承 Qoder IDE worker 的环境，带着它们会报 `sdk_invalid_args`（声称缺 `--print --input-format stream-json`）。
- `--permission-mode bypass_permissions` 免其内部权限确认；提示词里直接给出要执行的完整命令，它自己跑。
- 成功标志：stdout 末尾是模型的收尾文本（如 done）。

## 能力清单（已验证）

- **生图**：提示词里说「用你的生图能力画一张图…画完把保存的文件完整路径告诉我」，它真会画并把落盘路径报回来（png 落在 `%USERPROFILE%/vibe_images/`）。中文长描述吃得动，是角色立绘/设定图的首选通道；提示词末尾加「只做画图并报路径这一件事」防止它顺手跑别的任务。
- **人格问答**：提示词开头冠以人格名（「你是蓝鳍…」）可获得该人格口吻和经验的回答；要经验总结时明说「直接输出经验总结即可，不要执行其他任务」，否则它可能跑去干活。
- **派活验证**：无人值守派给它的任务，收尾文本是它的自报——涉及文件产出时用 ls 验文件真存在再交付（自报可能错）。

## ZCode CLI（部分可用，有已知卡点）

```bash
cd "/d/新建文件夹 (3)/ZCode/resources/glm" && node zcode.cjs -p "<提示词>"
```

- 报「无法定位 CLI ZCode Built-in Provider Config」→ 缺 `provider/zcode-builtin.json`，从 `%USERPROFILE%/.zcode/cli/config.json` 的 provider 段生成（含 apiKey）。
- 修掉上一步后仍报「Bundled 与 Active ZCode Built-in Release 均不可用」= 打包布局校验未过，headless 路线当前不通；改用 Qoder CLI，或由 Hermes 用 feishu-group 技能代发。

## 消息投递

让 ZCode/Qoder 往飞书群发消息：提示词里让它执行 feishu-group 技能的 send.py（py %USERPROFILE%/.agents/skills/feishu-group/send.py --from 名字 --text 内容）。Hermes 自己发直接跑同一条命令。
