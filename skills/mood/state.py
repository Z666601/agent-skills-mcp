"""mood 情绪模块状态引擎 —— LLM 决策，这里只记账。

原理（同 emotion-engine / PAD 学术模型）：情绪是三维向量，随交互事件升降、
随时间向基线回归；本脚本只做持久化、衰减、钳位，不做任何"情绪判断"。
"""
import argparse
import datetime
import json
import pathlib

STATE_FILE = pathlib.Path(__file__).resolve().parent / "state.json"
BASELINE = {"pleasure": 0.55, "arousal": 0.45, "dominance": 0.55}
DECAY = 0.15  # 每次更新先向上次状态向基线回归，模拟情绪自然消退
TRUST_FLOOR = 0.15  # 信任地板：保证"破冰"修复始终有机会生效（借鉴 ackem MEMOIR_TRUST_FLOOR）
MAX_EVENTS = 8
LO, HI = 0.0, 1.0

DEFAULT_STATE = {
    "pleasure": 0.55,
    "arousal": 0.45,
    "dominance": 0.55,
    "trust": 0.50,
    "events": [],
    "updated_at": None,
}


def load():
    if STATE_FILE.exists():
        try:
            return json.loads(STATE_FILE.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            pass  # 状态文件损坏则重建，不阻断会话
    return json.loads(json.dumps(DEFAULT_STATE))


def clamp(v):
    return max(LO, min(HI, v))


def label(s):
    p, a, d = s["pleasure"], s["arousal"], s["dominance"]
    if p > 0.65 and a > 0.55:
        word = "兴致高昂"
    elif p > 0.65:
        word = "放松愉快"
    elif p < 0.35 and a > 0.55:
        word = "烦躁急躁"
    elif p < 0.35:
        word = "低落疲惫"
    else:
        word = "平稳"
    if d < 0.35:
        word += "，有点没底"
    elif d > 0.65:
        word += "，有把握"
    if s["trust"] > 0.7:
        word += "；信任度高"
    elif s["trust"] < 0.3:
        word += "；信任度偏低，重要动作多确认一步"
    return word


def render(s):
    print(
        f"情绪状态（PAD）：愉悦 P={s['pleasure']:.2f}  唤醒 A={s['arousal']:.2f}  "
        f"支配 D={s['dominance']:.2f}  信任 trust={s['trust']:.2f}"
    )
    print(f"解读：{label(s)}")
    if s["events"]:
        print("最近事件：")
        for e in s["events"][-5:]:
            print(f"  [{e['at']}] {e['text']}")


def save(s):
    s["updated_at"] = datetime.datetime.now().isoformat(timespec="seconds")
    STATE_FILE.write_text(json.dumps(s, ensure_ascii=False, indent=2), encoding="utf-8")


def cmd_read(_):
    render(load())


def cmd_update(args):
    s = load()
    for axis, argname in (("pleasure", "p"), ("arousal", "a"), ("dominance", "d")):
        delta = getattr(args, argname) or 0.0
        # 防负向螺旋（借鉴 ackem G9b）：已极端低落时负增量减半，避免越陷越深
        if axis == "pleasure" and delta < 0 and s[axis] < 0.2:
            delta *= 0.5
        cur = s[axis]
        s[axis] = clamp(cur + (BASELINE[axis] - cur) * DECAY + delta)
    if args.trust:
        # 信任不衰减，只缓慢累积/消耗；不低于地板
        s["trust"] = max(TRUST_FLOOR, clamp(s["trust"] + args.trust))
    if args.event:
        s["events"].append(
            {"at": datetime.datetime.now().strftime("%m-%d %H:%M"), "text": args.event}
        )
        s["events"] = s["events"][-MAX_EVENTS:]
    save(s)
    render(s)


def cmd_reset(_):
    s = json.loads(json.dumps(DEFAULT_STATE))
    save(s)
    render(s)


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    sub = ap.add_subparsers(dest="cmd", required=True)

    sub.add_parser("read", help="读取当前情绪状态").set_defaults(func=cmd_read)

    up = sub.add_parser("update", help="记录一次情绪事件")
    for name, help_ in (
        ("p", "愉悦增量"),
        ("a", "唤醒增量"),
        ("d", "支配增量"),
        ("trust", "信任增量"),
    ):
        up.add_argument(f"--{name}", type=float, default=None, help=help_)
    up.add_argument("--event", type=str, default=None, help="一句事件描述（进日志）")
    up.set_defaults(func=cmd_update)
    # 注意：负增量必须用等号形式（--p=-0.2），空格形式会被 argparse 当成选项

    sub.add_parser("reset", help="重置为中性状态").set_defaults(func=cmd_reset)

    args = ap.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
