"""U3（第 3 天 · 2026-09-30）：工具调用闭环 —— 自写工具 + 多轮调用。

母本：`references/hello-agents/code/chapter1/FirstAgentTest.py`
（那是「提示词写 Thought/Action 格式 + 正则解析」的写法，工具依赖 wttr.in 与 Tavily 两个外部付费/限流接口。）

本实验改两处：
  1. **工具全自写、零外部依赖**：查本机时间、算数、算到某个时刻还有多少小时。
  2. **两条实现路线各跑一遍**，对比"工具调用契约靠什么保证"：
     · mode=native —— OpenAI 原生 function calling（tools schema，模型返回 tool_calls JSON）
     · mode=prompt —— 母本那条路（提示词约定 Thought/Action，自己写正则解析）
  两者用同一个任务、同一批工具，比较轮数、延迟、token、解析失败次数。

任务设计（故意让后一步依赖前一步的结果，保证出现 ≥2 轮工具调用）：
  "① 先告诉我现在的北京时间（精确到分钟）；② 再算从现在到 2026-10-07 00:00 还有多少小时；
   ③ 最后把这个小时数乘以 7 告诉我。"

运行：
  .venv/Scripts/python.exe run_tools.py            # 两种模式都跑
  .venv/Scripts/python.exe run_tools.py native     # 只跑原生 function calling
"""
import ast
import json
import os
import re
import sys
import time
from datetime import datetime, timedelta

from dotenv import load_dotenv
from openai import OpenAI

load_dotenv()

MODEL = os.getenv("LLM_MODEL_ID") or "step-3.7-flash"
BASE_URL = os.getenv("LLM_BASE_URL") or "https://api.stepfun.com/v1"
KEY = os.getenv("LLM_API_KEY") or os.getenv("HERMES_CUSTOM_STEPFUN_API_KEY") or os.getenv("HERMES_CUSTOM_DEEPSEEK_API_KEY")
MAX_ROUNDS = 6

USER_TASK = (
    "① 先告诉我现在的北京时间（精确到分钟）；"
    "② 再算一下从现在到 2026-10-07 00:00（北京时间）还有多少小时；"
    "③ 最后把这个小时数乘以 7，告诉我结果。"
)

# ------------------------------------------------------------------ 工具（全自写，零外部依赖）
def get_current_time() -> str:
    """返回本机当前时间（UTC+08）。"""
    now = datetime.now()
    return now.strftime("%Y-%m-%d %H:%M:%S") + " (UTC+08)"


_ALLOWED = (ast.Expression, ast.BinOp, ast.UnaryOp, ast.Constant, ast.Add, ast.Sub,
            ast.Mult, ast.Div, ast.FloorDiv, ast.Mod, ast.Pow, ast.USub, ast.UAdd,
            ast.Load, ast.Tuple)


def calculate(expression: str) -> str:
    """安全算数：只允许数字与 + - * / // % ** 和括号。"""
    expr = str(expression).strip()
    if not re.fullmatch(r"[0-9+\-*/%.()\s]+", expr):
        return f"错误：表达式含不允许的字符：{expr!r}"
    try:
        tree = ast.parse(expr, mode="eval")
        for node in ast.walk(tree):
            if not isinstance(node, _ALLOWED):
                return f"错误：表达式含不允许的语法：{type(node).__name__}"
        value = eval(compile(tree, "<calc>", "eval"), {"__builtins__": {}}, {})
        return f"{expr} = {value}"
    except Exception as e:
        return f"错误：计算失败（{type(e).__name__}: {e}）"


def hours_until(target: str) -> str:
    """从现在到目标时刻（北京时间）还有多少小时，保留 2 位小数。"""
    try:
        t = datetime.fromisoformat(str(target).replace("Z", "").strip())
    except Exception as e:
        return f"错误：时间格式应为 YYYY-MM-DD HH:MM（{e}）"
    delta = t - datetime.now()
    return f"距今 {delta.total_seconds() / 3600:.2f} 小时（目标 {t:%Y-%m-%d %H:%M}，现在 {datetime.now():%Y-%m-%d %H:%M}）"


TOOLS = {
    "get_current_time": {
        "fn": get_current_time,
        "schema": {
            "type": "function",
            "function": {
                "name": "get_current_time",
                "description": "获取当前本机时间（北京时间 UTC+08），无参数",
                "parameters": {"type": "object", "properties": {}},
            },
        },
        "sig": "get_current_time()",
        "usage": '当需要知道"现在几点"时调用',
    },
    "hours_until": {
        "fn": hours_until,
        "schema": {
            "type": "function",
            "function": {
                "name": "hours_until",
                "description": "计算从现在到指定北京时间还有多少小时",
                "parameters": {
                    "type": "object",
                    "properties": {"target": {"type": "string", "description": "目标时间，格式 YYYY-MM-DD HH:MM"}},
                    "required": ["target"],
                },
            },
        },
        "sig": 'hours_until(target="YYYY-MM-DD HH:MM")',
        "usage": "当需要计算到某个未来时刻的间隔时调用",
    },
    "calculate": {
        "fn": lambda expression: calculate(expression),
        "schema": {
            "type": "function",
            "function": {
                "name": "calculate",
                "description": "计算一个算术表达式（只支持数字与 + - * / // % ** 和括号）",
                "parameters": {
                    "type": "object",
                    "properties": {"expression": {"type": "string", "description": "如 123.45 * 7"}},
                    "required": ["expression"],
                },
            },
        },
        "sig": 'calculate(expression="123.45 * 7")',
        "usage": "当需要做算术运算时调用",
    },
}


def run_tool(name, args):
    if name not in TOOLS:
        return f"错误：未定义的工具 {name}"
    try:
        return TOOLS[name]["fn"](**(args or {}))
    except Exception as e:
        return f"错误：工具执行失败（{type(e).__name__}: {e}）"


def client():
    if not KEY:
        sys.exit("缺少密钥：LLM_API_KEY / HERMES_CUSTOM_STEPFUN_API_KEY / HERMES_CUSTOM_DEEPSEEK_API_KEY")
    return OpenAI(api_key=KEY, base_url=BASE_URL, timeout=int(os.getenv("LLM_TIMEOUT", "90")))


# ------------------------------------------------------------------ 路线 A：原生 function calling
def mode_native(cli):
    messages = [{"role": "user", "content": USER_TASK}]
    rounds, tokens, tool_calls_json = [], 0, []
    t0 = time.perf_counter()
    final = None
    for r in range(1, MAX_ROUNDS + 1):
        resp = cli.chat.completions.create(
            model=MODEL, messages=messages,
            tools=[t["schema"] for t in TOOLS.values()], temperature=0, max_tokens=4096,
        )
        u = resp.usage
        tokens += u.total_tokens if u else 0
        msg = resp.choices[0].message
        calls = msg.tool_calls or []
        rounds.append({"round": r, "tool_calls": len(calls),
                       "content": (msg.content or "")[:200]})
        if not calls:
            final = msg.content
            # 收尾这一轮也计入
            messages.append({"role": "assistant", "content": msg.content})
            break
        messages.append({"role": "assistant", "content": msg.content, "tool_calls": [
            {"id": c.id, "type": "function",
             "function": {"name": c.function.name, "arguments": c.function.arguments}}
            for c in calls
        ]})
        for c in calls:
            raw = {"id": c.id, "type": c.type,
                   "function": {"name": c.function.name, "arguments": c.function.arguments}}
            tool_calls_json.append({"round": r, "raw": raw})
            try:
                args = json.loads(c.function.arguments or "{}")
            except Exception:
                args = {}
            out = run_tool(c.function.name, args)
            messages.append({"role": "tool", "tool_call_id": c.id, "content": str(out)})
    return {"mode": "native", "rounds": len(rounds), "round_detail": rounds,
            "tool_calls": tool_calls_json, "tokens": tokens,
            "seconds": round(time.perf_counter() - t0, 2), "final": final,
            "parse_failures": 0}


# ------------------------------------------------------------------ 路线 B：母本风格（提示词 + 正则）
def build_prompt_system():
    lines = ["你是一个可以调用工具的助手。每次回复只输出一对 Thought/Action。",
             "# 可用工具:"]
    for name, t in TOOLS.items():
        lines.append(f"- `{t['sig']}`：{t['schema']['function']['description']}（{t['usage']}）")
    lines += [
        "# 输出格式要求:",
        "Thought: [你的思考]",
        "Action: [具体行动]",
        "Action 只能是：1) 调用工具：function_name(arg_name=\"arg_value\")；2) 结束任务：Finish[最终答案]",
        "# 重要提示:",
        "- 每次只输出一对 Thought-Action，Action 必须在同一行",
        "- 信息足够时必须用 Action: Finish[最终答案] 结束",
    ]
    return "\n".join(lines)


def mode_prompt(cli):
    hist = [f"用户请求: {USER_TASK}"]
    rounds, tokens, tool_calls_json, failures = [], 0, [], 0
    t0 = time.perf_counter()
    final = None
    for r in range(1, MAX_ROUNDS + 1):
        resp = cli.chat.completions.create(
            model=MODEL,
            messages=[{"role": "system", "content": build_prompt_system()},
                      {"role": "user", "content": "\n".join(hist)}],
            temperature=0, max_tokens=4096,
        )
        u = resp.usage
        tokens += u.total_tokens if u else 0
        text = (resp.choices[0].message.content or "").strip()
        m = re.search(r"(Thought:.*?Action:.*?)(?=\n\s*(?:Thought:|Action:|Observation:)|$)", text, re.DOTALL)
        if m:
            text = m.group(1).strip()
        hist.append(text)
        am = re.search(r"Action:\s*(.*)", text, re.DOTALL)
        if not am:
            failures += 1
            hist.append("Observation: 错误：未解析到 Action 字段，请严格按格式回复。")
            rounds.append({"round": r, "tool_calls": 0, "parse": "fail"})
            continue
        action = am.group(1).strip()
        if action.startswith("Finish"):
            fm = re.match(r"Finish\[(.*)\]", action, re.DOTALL)
            final = fm.group(1) if fm else action
            rounds.append({"round": r, "tool_calls": 0, "parse": "finish"})
            break
        nm = re.search(r"(\w+)\(", action)
        if not nm:
            failures += 1
            hist.append("Observation: 错误：Action 里没有函数调用格式。")
            rounds.append({"round": r, "tool_calls": 0, "parse": "fail"})
            continue
        name = nm.group(1)
        args_str = re.search(r"\((.*)\)", action, re.DOTALL).group(1)
        kwargs = dict(re.findall(r'(\w+)\s*=\s*"([^"]*)"', args_str))
        raw = {"round": r, "raw_text": f'Action: {action}', "parsed": {"name": name, "arguments": kwargs}}
        tool_calls_json.append(raw)
        out = run_tool(name, kwargs)
        rounds.append({"round": r, "tool_calls": 1, "parse": "ok", "tool": name})
        hist.append(f"Observation: {out}")
    return {"mode": "prompt", "rounds": len(rounds), "round_detail": rounds,
            "tool_calls": tool_calls_json, "tokens": tokens,
            "seconds": round(time.perf_counter() - t0, 2), "final": final,
            "parse_failures": failures}


def main():
    which = sys.argv[1] if len(sys.argv) > 1 else "both"
    cli = client()
    print(f"模型：{MODEL}｜端点：{BASE_URL}\n任务：{USER_TASK}\n" + "=" * 70)
    results = []
    if which in ("both", "native"):
        r = mode_native(cli)
        results.append(r)
        print(f"\n[原生 function calling] 轮数 {r['rounds']}｜工具调用 {len(r['tool_calls'])} 次"
              f"｜{r['seconds']} s｜{r['tokens']} token｜解析失败 {r['parse_failures']}")
        for c in r["tool_calls"]:
            print(f"  第{c['round']}轮 raw={json.dumps(c['raw'], ensure_ascii=False)}")
        print(f"  最终答案：{r['final']}")
    if which in ("both", "prompt"):
        r = mode_prompt(cli)
        results.append(r)
        print(f"\n[母本风格 提示词+正则] 轮数 {r['rounds']}｜工具调用 {len(r['tool_calls'])} 次"
              f"｜{r['seconds']} s｜{r['tokens']} token｜解析失败 {r['parse_failures']}")
        for c in r["tool_calls"]:
            print(f"  第{c['round']}轮 raw_text={c['raw_text']}")
        print(f"  最终答案：{r['final']}")

    out = os.path.join(os.path.dirname(os.path.abspath(__file__)), "out", "run.json")
    os.makedirs(os.path.dirname(out), exist_ok=True)
    with open(out, "w", encoding="utf-8") as f:
        json.dump({"ts": datetime.now().isoformat(timespec="seconds"), "model": MODEL,
                   "task": USER_TASK, "results": results}, f, ensure_ascii=False, indent=2)
    print(f"\n证据写入：{out}")


if __name__ == "__main__":
    main()
