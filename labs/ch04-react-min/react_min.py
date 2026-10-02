"""U5（第 5 天 · 2026-10-02）：不看示例，手写最小 ReAct 循环。

母本参考（只对结构，不抄代码）：`references/hello-agents/code/chapter4/ReAct.py` 与 4.2 节。
本文件是**自己重写**的 40 行级最小实现，用来把「ReAct 到底比一次提示词强在哪」变成可比的两组数据：

  路线 A：ReAct 循环 —— 思考(Thought) → 行动(Action: 调工具) → 观察(Observation)，最多 4 步
  路线 B：一次提示词 —— 让模型直接输出 JSON 答案，不给任何工具

任务需要一个模型自己不知道的实时事实（当前时间），所以 A 能算对、B 只能猜：
  "现在到 2026-10-07 00:00 还有多少小时？再把这个小时数换算成天（保留 1 位小数）。"

运行：.venv/Scripts/python.exe react_min.py
"""
import ast
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
MAX_STEPS = 4

QUESTION = "现在到 2026-10-07 00:00 还有多少小时？再把这个小时数换算成天（保留 1 位小数）。"

# ---------------- 工具（两个，都是本地确定性计算） ----------------
_ALLOWED = (ast.Expression, ast.BinOp, ast.UnaryOp, ast.Constant, ast.Add, ast.Sub,
            ast.Mult, ast.Div, ast.FloorDiv, ast.Mod, ast.Pow, ast.USub, ast.UAdd,
            ast.Load, ast.Tuple)


def calculate(expression: str) -> str:
    expr = str(expression).strip()
    if not re.fullmatch(r"[0-9+\-*/%.()\s]+", expr):
        return f"错误：表达式含不允许的字符：{expr!r}"
    tree = ast.parse(expr, mode="eval")
    for node in ast.walk(tree):
        if not isinstance(node, _ALLOWED):
            return f"错误：表达式含不允许的语法：{type(node).__name__}"
    return f"{expr} = {eval(compile(tree, '<calc>', 'eval'), {'__builtins__': {}}, {})}"


def now() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S") + " (UTC+08)"


TOOLS = {"calculate": calculate, "now": lambda: now()}
TOOL_DOC = "\n".join([
    "- now()：获取当前时间（北京时间）",
    '- calculate(expression="..." )：算术计算，例如 calculate(expression="156.85 * 7")',
])

REACT_PROMPT = """你是会使用工具的问题求解器。每轮只输出两行：

Thought: 你的思考（一句话）
Action: 你要做的下一步，只能是 tool(args) 或 Finish[最终答案]

可用工具：
{tools}

规则：
- 需要事实（比如当前时间）时必须调工具，不要凭记忆猜
- 收集到足够信息后用 Finish[...] 结束，答案里带上关键数字

问题：{question}

已发生的步骤：
{history}
"""


def call(cli, messages, tools=None):
    r = cli.chat.completions.create(model=MODEL, messages=messages, temperature=0, max_tokens=4096,
                                    **({"tools": tools} if tools else {}))
    u = r.usage
    return r.choices[0].message.content or "", (u.total_tokens if u else 0), r.choices[0].finish_reason


def parse(text):
    th = re.search(r"Thought:\s*(.*?)(?=\nAction:|$)", text, re.DOTALL)
    # 只取 Action 之后的**第一行**：模型有时会在同一次输出里自己编出 "Observation:" 行，
    # 第一版用 re.DOTALL 跨行捕获，把伪造的 Observation 也吃进来，导致"无法识别的 Action"（见 out/react_run_v2_multiline.json）
    ac = re.search(r"Action:\s*([^\n]*)", text)
    return (th.group(1).strip() if th else ""), (ac.group(1).strip() if ac else "")


def faked_observation(text):
    """模型是否在同一次输出里自导自演了 Observation（协议违规，应丢弃）。"""
    return bool(re.search(r"^\s*Observation\s*:", text, re.MULTILINE))


def run_react(cli):
    history, steps, tokens = [], [], 0
    t0 = time.perf_counter()
    for i in range(1, MAX_STEPS + 1):
        prompt = REACT_PROMPT.format(tools=TOOL_DOC, question=QUESTION,
                                     history="\n".join(history) or "（无）")
        text, tk, fin = call(cli, [{"role": "user", "content": prompt}])
        tokens += tk
        thought, action = parse(text)
        step = {"step": i, "thought": thought, "action": action, "raw": text[:400],
                "finish_reason": fin, "faked_observation": faked_observation(text)}
        if step["faked_observation"]:
            # 协议违规：模型自己写了 Observation。丢弃它的伪造观察，只用我们的真实工具结果。
            step["note"] = "模型自造了 Observation 行，已忽略，改为回填真实工具结果"
        if not action:
            step["observation"] = "（解析不到 Action，循环结束）"
            steps.append(step)
            break
        if action.startswith("Finish"):
            final = re.match(r"Finish\[(.*)\]", action, re.DOTALL)
            step["observation"] = "（结束）"
            steps.append(step)
            return {"answer": (final.group(1).strip() if final else action), "steps": steps,
                    "tokens": tokens, "seconds": round(time.perf_counter() - t0, 2)}
        m = re.match(r"(\w+)\((.*)\)\s*$", action, re.DOTALL)
        if m and m.group(1) in TOOLS:
            args_str = m.group(2).strip()
            # 支持三种写法：tool() / tool(值) / tool(name="值") —— 第一版漏了第三种，模型写的
            # calculate(expression="...") 被整串当成表达式传进去，连续 3 步报错（见 out/react_run_v1_parsebug.json）
            if "=" in args_str:
                args_str = args_str.split("=", 1)[1].strip()
            args_str = args_str.strip().strip('"').strip("'")
            try:
                out = TOOLS[m.group(1)](args_str) if args_str else TOOLS[m.group(1)]()
            except Exception as e:
                out = f"错误：{type(e).__name__}: {e}"
        else:
            out = f"错误：无法识别的 Action（{action}），请只用 tool(args) 或 Finish[...]"
        step["observation"] = out
        steps.append(step)
        history.append(f"Thought: {thought}\nAction: {action}\nObservation: {out}")
    return {"answer": None, "steps": steps, "tokens": tokens,
            "seconds": round(time.perf_counter() - t0, 2)}


def run_oneshot(cli):
    """对照组：一次提示词直接要答案，不给工具（模型只能凭记忆猜当前时间）。"""
    prompt = (f"请只输出 JSON，不要解释：{{\"answer\": \"...\", \"unit\": \"小时\", \"days\": \"...\"}}\n"
              f"问题：{QUESTION}")
    t0 = time.perf_counter()
    text, tk, fin = call(cli, [{"role": "user", "content": prompt}])
    return {"prompt": prompt, "raw": text, "tokens": tk, "finish_reason": fin,
            "seconds": round(time.perf_counter() - t0, 2)}


def main():
    if not KEY:
        sys.exit("缺少密钥：LLM_API_KEY / HERMES_CUSTOM_STEPFUN_API_KEY")
    cli = OpenAI(api_key=KEY, base_url=BASE_URL, timeout=int(os.getenv("LLM_TIMEOUT", "90")))

    print(f"模型：{MODEL}｜问题：{QUESTION}\n" + "=" * 70)
    react = run_react(cli)
    print(f"\n[路线A ReAct] 步数 {len(react['steps'])}｜{react['seconds']} s｜{react['tokens']} token")
    for s in react["steps"]:
        print(f"  第{s['step']}步 思考: {s['thought'][:60]}")
        print(f"       行动: {s['action'][:80]}")
        print(f"       观察: {str(s.get('observation'))[:100]}")
    print(f"  最终答案: {react['answer']}")

    one = run_oneshot(cli)
    print(f"\n[路线B 一次提示词] {one['seconds']} s｜{one['tokens']} token｜finish={one['finish_reason']}")
    print(f"  输出: {one['raw'][:300]}")

    out = os.path.join(os.path.dirname(os.path.abspath(__file__)), "out", "react_run.json")
    os.makedirs(os.path.dirname(out), exist_ok=True)
    with open(out, "w", encoding="utf-8") as f:
        json.dump({"ts": datetime.now().isoformat(timespec="seconds"), "model": MODEL,
                   "question": QUESTION, "react": react, "oneshot": one}, f, ensure_ascii=False, indent=2)
    print(f"\n证据写入：{out}")


if __name__ == "__main__":
    main()
