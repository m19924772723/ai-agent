"""U6（第 6 天 · 2026-10-03）：三种经典范式的同题对照。

母本参考：第 4 章 4.2 ReAct / 4.3 Plan-and-Solve / 4.4 Reflection（只对结构，代码自写）。
目的：同一道题、同一批工具，三种控制流各跑一遍，把「适用场景 / 成本 / 失败模式」变成可比数据。

题目：这批 12 条用户反馈里最主要的问题是哪一类？给出条数，并提出 2 条可执行建议（数字必须准确）。
工具：count(keyword) —— 在 12 条反馈里数包含该关键词的条数（本地、确定性）；all() —— 列出全部反馈。

三条路线：
  1. plan-and-solve：先出计划（JSON 步骤表）→ 逐步执行（可调工具）→ 汇总成最终答案
  2. react：Thought/Action/Observation 循环，逐步逼近
  3. reflection：先直接作答 → 拿工具结果自我批评 → 修订一版

评分：脚本自己用真值检查最终答案里是否出现「正确条数」和「正确的类别词」，这就是客观的成败判据。

运行：.venv/Scripts/python.exe run_paradigms.py
"""
import json
import os
import re
import sys
import time
from datetime import datetime

from dotenv import load_dotenv
from openai import OpenAI

load_dotenv()

MODEL = os.getenv("LLM_MODEL_ID") or "step-3.7-flash"
BASE_URL = os.getenv("LLM_BASE_URL") or "https://api.stepfun.com/v1"
KEY = os.getenv("LLM_API_KEY") or os.getenv("HERMES_CUSTOM_STEPFUN_API_KEY") or os.getenv("HERMES_CUSTOM_DEEPSEEK_API_KEY")

FEEDBACK = [
    ("崩溃", "付款的时候页面直接闪退了，钱扣了订单没生成"),
    ("卡顿", "商品列表加载特别慢，滑一次要等三四秒"),
    ("崩溃", "登录一直提示验证码错误，换浏览器也一样"),
    ("卡顿", "搜索转圈好几秒才出结果，等得心累"),
    ("需求", "希望搜索页能支持按时间排序"),
    ("卡顿", "订单列表翻页到第二页就卡住不动了"),
    ("崩溃", "打开详情页白屏，刷新三次才好"),
    ("提示缺失", "退款提交后没有任何提示，不知道成功没有"),
    ("卡顿", "首页图片加载很慢，半天不出图"),
    ("需求", "能不能加一个导出 Excel 的按钮"),
    ("提示缺失", "支付成功后没收到通知，客服入口也找不到"),
    ("需求", "建议把常用功能放到首页，现在要点三层"),
]
# 真值由代码统计得出，不靠人手写
TRUTH = {}
for label, _ in FEEDBACK:
    TRUTH[label] = TRUTH.get(label, 0) + 1
DOMINANT_LABEL = max(TRUTH, key=TRUTH.get)
DOMINANT_COUNT = TRUTH[DOMINANT_LABEL]
DOMINANT_KEYWORDS = {"卡顿": ("慢", "卡"), "崩溃": ("闪退", "崩溃", "白屏"), "需求": ("希望", "建议", "能不能"), "提示缺失": ("没有提示", "没收到")}

QUESTION = ("这批用户反馈里最主要的问题是哪一类？给出该类条数，并提出 2 条可执行建议。"
            "数字必须由工具统计得出，不要凭印象。")

TOOL_DOC = """- count(kw)：统计 12 条反馈里包含 kw 的条数；kw 可以是多个词，用逗号分隔表示"任意命中"，例如 count("慢,卡,转圈")
- all()：列出全部 12 条反馈"""


def tool_count(keyword):
    """支持多关键词 OR 计数：第一版只支持单个子串，模型写 count("加载慢/转圈") 直接得 0，被迫心算（见 out/paradigms_v1_harnessbug.json）。"""
    raw = str(keyword).strip().strip('"').strip("'")
    kws = [k.strip() for k in re.split(r"[,，/、|]+", raw) if k.strip()]
    if not kws:
        return "错误：请在 count(...) 里给出至少一个关键词"
    hits = [(lab, t) for lab, t in FEEDBACK if any(k in t for k in kws)]
    detail = "；".join(f"[{lab}] {t[:16]}" for lab, t in hits[:4])
    return f"含 {kws} 中任意一个词的反馈有 {len(hits)} 条：{detail}"


def tool_all():
    return "\n".join(f"{i+1}. {t}" for i, (_, t) in enumerate(FEEDBACK))


TOOLS = {"count": tool_count, "all": lambda: tool_all()}


def grade(answer: str):
    """客观判分：是否说出正确条数 + 正确类别关键词。"""
    if not answer:
        return {"ok": False, "reason": "无答案"}
    nums = re.findall(r"\d+", answer)
    hit_num = str(DOMINANT_COUNT) in nums
    kws = DOMINANT_KEYWORDS[DOMINANT_LABEL]
    hit_kw = any(k in answer for k in kws)
    return {"ok": hit_num and hit_kw, "hit_number": hit_num, "hit_keyword": hit_kw,
            "expect_number": DOMINANT_COUNT, "expect_label": DOMINANT_LABEL}


def client():
    if not KEY:
        sys.exit("缺少密钥：LLM_API_KEY / HERMES_CUSTOM_STEPFUN_API_KEY")
    return OpenAI(api_key=KEY, base_url=BASE_URL, timeout=int(os.getenv("LLM_TIMEOUT", "90")))


class Meter:
    def __init__(self):
        self.tokens = 0
        self.calls = 0
        self.tool_calls = 0
        self.t0 = time.perf_counter()

    def ask(self, cli, prompt, system=None):
        msgs = ([{"role": "system", "content": system}] if system else []) + [{"role": "user", "content": prompt}]
        r = cli.chat.completions.create(model=MODEL, messages=msgs, temperature=0, max_tokens=4096)
        self.calls += 1
        if r.usage:
            self.tokens += r.usage.total_tokens
        return r.choices[0].message.content or ""

    def secs(self):
        return round(time.perf_counter() - self.t0, 2)


def parse_tool_call(text):
    m = re.search(r"count\(\s*([^)]*)\)|all\(\s*\)", text)
    if not m:
        return None
    if m.group(0).startswith("all"):
        return "all", ""
    return "count", m.group(1)


# ---------------------------------------------------------------- 路线 1：Plan-and-Solve
def moon_plan_and_solve(cli, meter):
    plan = meter.ask(cli, f"""把解决下面这个问题的步骤写成 JSON 数组（3-4 步，每步一句话，能调工具的写清调哪个）：
{QUESTION}

反馈数据：{tool_all()}

只输出 JSON 数组，例如 ["第一步：用 count 统计…", "第二步：…"]""")
    m = re.search(r"\[.*\]", plan, re.DOTALL)
    steps = json.loads(m.group(0)) if m else []
    trace = [{"step": "计划", "content": plan[:400]}]
    findings = []
    for i, s in enumerate(steps, 1):
        out = meter.ask(cli, f"""原始问题：{QUESTION}
计划第 {i} 步：{s}
已收集到的信息：{chr(10).join(findings) or "（无）"}

需要调工具就**只回复一行工具调用**（例如 count("慢,卡,转圈") 或 all()，关键词换成你真正要查的，不要照抄示例）；不需要工具就直接回复该步的结论（一行）。""")
        call = parse_tool_call(out)
        if call:
            meter.tool_calls += 1
            obs = TOOLS[call[0]](call[1]) if call[0] == "count" else TOOLS[call[0]]()
            findings.append(f"{s} → {obs}")
            trace.append({"step": f"执行{i}", "tool": call, "observation": obs[:200]})
        else:
            findings.append(f"{s} → {out[:120]}")
            trace.append({"step": f"执行{i}", "content": out[:200]})
    answer = meter.ask(cli, f"""问题：{QUESTION}
已知信息：
{chr(10).join(findings)}

请给出最终答案（含：最主要问题类别、该类条数、2 条可执行建议）。""")
    return {"answer": answer, "trace": trace, "steps": len(steps)}


# ---------------------------------------------------------------- 路线 2：ReAct
def moon_react(cli, meter, max_steps=5):
    history, trace = [], []
    for i in range(1, max_steps + 1):
        text = meter.ask(cli, f"""你是会调工具的助手。每轮必须输出两行：
Thought: 一句话
Action: 一行工具调用，例如 count("慢,卡,转圈") 或 all()，或 Finish[最终答案]

（关键词换成你真正要查的词，不要照抄示例；**如果缺少 Action 行，本轮视为失败**）

工具：
{TOOL_DOC}

问题：{QUESTION}
已发生：
{chr(10).join(history) or "（无）"}""")
        th = re.search(r"Thought:\s*(.*?)(?=\nAction:|$)", text, re.DOTALL)
        ac = re.search(r"Action:\s*([^\n]*)", text)
        thought = th.group(1).strip() if th else ""
        action = ac.group(1).strip() if ac else ""
        rec = {"step": i, "thought": thought[:100], "action": action[:120]}
        if not action:
            rec["observation"] = "（解析不到 Action，终止）"
            trace.append(rec)
            break
        if action.startswith("Finish"):
            fm = re.match(r"Finish\[(.*)\]", action, re.DOTALL)
            trace.append(rec)
            return {"answer": fm.group(1).strip() if fm else action, "trace": trace, "steps": i}
        call = parse_tool_call(action)
        if not call:
            out = "错误：Action 只能是 count(keyword)/all()/Finish[...]"
        else:
            meter.tool_calls += 1
            out = TOOLS[call[0]](call[1]) if call[0] == "count" else TOOLS[call[0]]()
        rec["observation"] = out[:200]
        trace.append(rec)
        history.append(f"Thought: {thought}\nAction: {action}\nObservation: {out}")
    return {"answer": None, "trace": trace, "steps": len(trace)}


# ---------------------------------------------------------------- 路线 3：Reflection
def moon_reflection(cli, meter):
    draft = meter.ask(cli, f"""问题：{QUESTION}

反馈数据：
{tool_all()}

请直接给出答案。""")
    trace = [{"round": 1, "kind": "初稿", "content": draft[:400]}]
    crit = meter.ask(cli, f"""下面是对这个问题的第一版回答，请严格自我批评（只看事实与数字是否站得住）：

问题：{QUESTION}
第一版回答：{draft}

如果需要核对数字，请**只回复一行工具调用**（例如 count("慢,卡,转圈") 或 all()，关键词换成你真正要查的）；否则回复 `OK:` 加上你认为需要改的点（一行）。""")
    call = parse_tool_call(crit)
    evidence = ""
    if call:
        meter.tool_calls += 1
        evidence = TOOLS[call[0]](call[1]) if call[0] == "count" else TOOLS[call[0]]()
        trace.append({"round": 2, "kind": "自查调工具", "tool": call, "observation": evidence[:200]})
        crit = meter.ask(cli, f"""这是工具返回的真实数据：{evidence}

现在请给出需要修改的点（一行，`OK:` 开头），或回复 `无问题`。""")
    trace.append({"round": 2, "kind": "自我批评", "content": crit[:300]})
    final = meter.ask(cli, f"""问题：{QUESTION}
第一版回答：{draft}
真实数据：{evidence or "（未查）"}
自我批评：{crit}

请给出修订后的最终答案（含：最主要问题类别、该类条数、2 条可执行建议）。""")
    trace.append({"round": 3, "kind": "修订稿", "content": final[:400]})
    return {"answer": final, "draft": draft, "trace": trace, "steps": 3}


def main():
    cli = client()
    print(f"模型：{MODEL}\n真值：{TRUTH} → 最主要问题 = {DOMINANT_LABEL}（{DOMINANT_COUNT} 条）\n" + "=" * 70)
    results = []
    for name, fn in (("plan-and-solve", moon_plan_and_solve), ("react", moon_react), ("reflection", moon_reflection)):
        meter = Meter()
        try:
            out = fn(cli, meter)
        except Exception as e:
            out = {"answer": None, "trace": [], "error": f"{type(e).__name__}: {e}"}
        out.update(paradigm=name, tokens=meter.tokens, api_calls=meter.calls,
                   tool_calls=meter.tool_calls, seconds=meter.secs(), grade=grade(out.get("answer")))
        results.append(out)
        g = out["grade"]
        print(f"\n[{name}] 步数={out.get('steps')} 工具调用={meter.tool_calls} token={meter.tokens}"
              f" 耗时={meter.secs()}s 判分={'✅' if g['ok'] else '❌'} ({g})")
        print(f"  答案：{(out.get('answer') or '（无）')[:260]}")

    out_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "out", "paradigms.json")
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump({"ts": datetime.now().isoformat(timespec="seconds"), "model": MODEL,
                   "question": QUESTION, "truth": TRUTH, "dominant": [DOMINANT_LABEL, DOMINANT_COUNT],
                   "results": results}, f, ensure_ascii=False, indent=2)
    print(f"\n证据写入：{out_path}")


if __name__ == "__main__":
    main()
