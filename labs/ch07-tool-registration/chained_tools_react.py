"""
U16（第 15 天 · 2026-10-12）：工具调用链——验证"工具 A 的输出 → 工具 B 的输入"这条依赖链真发生了。

任务（强依赖，缺一不可）：
  "距离 2026-11-01 00:00 还有多少小时？用计算器把这个小时数除以 7，告诉我结果（保留两位小数）。"
链条：hours_until("2026-11-01 00:00") → "距今 468.x 小时" → 提取数字 → calculate("468.x/7") → "= 66.86"

U16 关键发现（踩坑，与 U15 的"工具全对答案错"互补）：
  用 SimpleAgent 跑同一任务 3 次，工具链全部正确（hours_until→468.x→calculate→66.86），
  但 agent 每次都在拿到结果后回答"抱歉，我无法回答这个问题"——工具全对、收尾失败。
  换成 ReActAgent（同模型同温度同工具同任务）一次就回答 66.86。
  → 结论：框架的 agent 类型决定"收尾能力"，SimpleAgent 拿到 tool_result 后只有 45 token
    就放弃，ReActAgent 会继续思考并给出最终答案。选框架不是选 API，是选行为。

运行：.venv/Scripts/python.exe chained_tools_react.py
输出：out/chained_react_run.json（含依赖链证据 + 自动校验）
"""
import ast
import glob
import inspect
import json
import os
import re
import time
from datetime import datetime

import hello_agents
from dotenv import load_dotenv
from hello_agents import HelloAgentsLLM, ReActAgent, ToolRegistry

load_dotenv()

MODEL = os.getenv("LLM_MODEL_ID") or "step-3.7-flash"
BASE_URL = os.getenv("LLM_BASE_URL") or "https://api.stepfun.com/v1"
KEY = os.getenv("LLM_API_KEY") or os.getenv("HERMES_CUSTOM_STEPFUN_API_KEY")


def get_current_time() -> str:
    """返回本机当前时间（UTC+08）。"""
    now = datetime.now()
    return now.strftime("%Y-%m-%d %H:%M:%S") + " (UTC+08)"


_ALLOWED = (ast.Expression, ast.BinOp, ast.UnaryOp, ast.Constant, ast.Add, ast.Sub,
            ast.Mult, ast.Div, ast.FloorDiv, ast.Mod, ast.Pow, ast.USub, ast.UAdd,
            ast.Load, ast.Tuple)


def calculate(expression: str) -> str:
    """安全算数：只允许数字与 + - * / // % ** 和括号（AST 白名单，无注入）。"""
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


def tool_adapter(fn):
    """框架 1.0.0 兼容：execute_tool 对函数工具位置式传参 func(input_text)，零参函数要丢弃参数。"""
    if len(inspect.signature(fn).parameters) == 0:
        return lambda *a, **k: fn()
    return fn


QUESTION = "距离 2026-11-01 00:00 还有多少小时？用计算器把这个小时数除以 7，告诉我结果（保留两位小数）。"


def extract_events(lab_dir):
    """读最新框架 trace（事件字段是 event，写盘有缓冲）。"""
    time.sleep(0.5)
    traces = sorted(glob.glob(os.path.join(lab_dir, "memory", "traces", "*.jsonl")),
                    key=os.path.getmtime)
    if not traces:
        return [], None
    path = traces[-1]
    events = []
    with open(path, encoding="utf-8") as f:
        for line in f:
            try:
                ev = json.loads(line)
            except Exception:
                continue
            if ev.get("event") in ("tool_call", "tool_result", "model_output"):
                events.append(ev)
    return events, path


def main():
    if not KEY:
        raise SystemExit("缺少密钥：LLM_API_KEY / HERMES_CUSTOM_STEPFUN_API_KEY")

    llm = HelloAgentsLLM(model=MODEL, api_key=KEY, base_url=BASE_URL, temperature=0)
    registry = ToolRegistry()
    registry.register_function(name="get_current_time",
                               description="获取当前日期时间，北京时间（UTC+08），精确到秒",
                               func=tool_adapter(get_current_time))
    registry.register_function(name="calculate",
                               description="安全计算数学表达式，支持 + - * / // % ** 和括号，例如 '(468.05/7)'",
                               func=tool_adapter(calculate))
    registry.register_function(name="hours_until",
                               description="计算从现在到目标时刻（格式 YYYY-MM-DD HH:MM）还有多少小时",
                               func=tool_adapter(hours_until))

    agent = ReActAgent(
        name="工具链Agent",
        llm=llm,
        system_prompt="你是助手。求小时数必须先调用 hours_until 拿到精确值，禁止自己心算；"
                      "拿到小时数后必须用 calculate 做除法，最后把计算结果作为答案告诉用户。",
        tool_registry=registry)

    print("=" * 70)
    print(f"框架：{getattr(hello_agents, '__version__', '?')}｜Agent: ReActAgent｜模型：{MODEL}｜温度：0")
    print(f"已注册：{list(registry._functions.keys()) if hasattr(registry, '_functions') else '?'}")
    print("-" * 70)

    t0 = time.perf_counter()
    try:
        answer = agent.run(QUESTION)
        err = None
    except Exception as e:
        answer, err = None, f"{type(e).__name__}: {e}"
    secs = round(time.perf_counter() - t0, 2)
    print(f"问题：{QUESTION}")
    print(f"回答（{secs} s）：{answer}")
    if err:
        print(f"异常：{err}")

    lab_dir = os.path.dirname(os.path.abspath(__file__))
    events, trace_path = extract_events(lab_dir)

    calls, results = [], {}
    for ev in events:
        if ev.get("event") == "tool_call":
            calls.append({"step": ev.get("step"), "tool": ev["payload"]["tool_name"],
                          "args": ev["payload"].get("args")})
        elif ev.get("event") == "tool_result":
            results[ev["payload"]["tool_name"]] = ev["payload"].get("result", "")

    hours_num = None
    hr_res = results.get("hours_until", "")
    m = re.search(r"距今 ([\d.]+) 小时", hr_res)
    if m:
        hours_num = float(m.group(1))

    chained = False
    calc_arg = None
    for c in calls:
        if c["tool"] == "calculate":
            a = str(c["args"].get("input", "") if isinstance(c["args"], dict) else c["args"])
            calc_arg = a
            if hours_num is not None and any(
                    abs(float(x) - hours_num) < 0.5 for x in re.findall(r"[\d.]+", a)):
                chained = True

    expect = hours_num / 7 if hours_num else None
    expect_str = f"{expect:.2f}" if expect is not None else None
    answer_ok = expect_str is not None and expect_str in (answer or "")

    hrs_step = calc_step = None
    for c in calls:
        if c["tool"] == "hours_until":
            hrs_step = c["step"]
        if c["tool"] == "calculate":
            calc_step = c["step"]
    order_ok = hrs_step is not None and calc_step is not None and calc_step >= hrs_step

    record = {
        "ts": datetime.now().isoformat(timespec="seconds"),
        "framework_version": getattr(hello_agents, "__version__", "?"),
        "agent_type": "ReActAgent",
        "model": MODEL,
        "question": QUESTION,
        "answer": answer,
        "error": err,
        "seconds": secs,
        "calls": calls,
        "hours_until_result": hr_res,
        "hours_num": hours_num,
        "calc_arg": calc_arg,
        "expect": {"hours/7": expect_str, "hours": hours_num},
        "checks": {
            "调用了两个工具": len({c["tool"] for c in calls}) >= 2,
            "calculate参数来自hours结果(链)": chained,
            "顺序正确(hours先于calc)": order_ok,
            "答案与真值一致": answer_ok,
        },
        "trace_file": os.path.basename(trace_path) if trace_path else None,
        "对比SimpleAgent": "同一任务 SimpleAgent 3 次都答'无法回答'（工具链全对但收尾失败）；ReActAgent 1 次答对",
    }
    out = os.path.join(lab_dir, "out", "chained_react_run.json")
    os.makedirs(os.path.dirname(out), exist_ok=True)
    with open(out, "w", encoding="utf-8") as f:
        json.dump(record, f, ensure_ascii=False, indent=2)

    print("\n" + "-" * 70)
    print(f"工具调用序列：{[c['tool'] for c in calls]}")
    print(f"hours_until 结果：{hr_res[:70]}")
    print(f"calculate 参数：{calc_arg}   ← 来自 hours_until 结果？{chained}")
    print(f"期望答案：{expect_str}（{hours_num:,.2f} / 7）")
    print(f"校验：链={chained} 顺序={order_ok} 答案={answer_ok}")
    print(f"证据写入：{out}")


if __name__ == "__main__":
    main()