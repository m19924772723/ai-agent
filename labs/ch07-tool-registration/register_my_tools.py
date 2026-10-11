"""
U15（第 14 天 · 2026-10-11）：把我的 3 个工具注册进 chapter7 框架，跑通并留日志证据。

母本参考：`references/hello-agents/code/chapter7/my_advanced_search.py`（多源整合工具，
依赖 Tavily/SerpAPI 外部密钥——我们不装）与 `my_calculator_tool.py`（用 ToolRegistry 注册函数）。
验收点：**自己的** 3 个工具（来自 U3 `labs/ch01-toolcall/run_tools.py`，零外部依赖）：
  · get_current_time —— 本机当前时间（UTC+08）【零参函数】
  · calculate        —— 安全算数（白名单语法树求值，无 eval 注入风险）
  · hours_until      —— 到目标时刻还有多少小时
把它们注册进框架，跑一个**必须依次调用全部 3 个工具**的任务：
  "现在几点？算 (137+85)*12 等于几？距离 2026-11-01 00:00 还有多少小时？"

U15 踩坑（2026-10-11 首次运行发现，与 U8 同源的框架适配问题）：
  框架 1.0.0 的 ToolRegistry.execute_tool() 对「函数工具」是 `func(input_text)` 位置式传参
  ——零参函数（get_current_time）会报 `takes 0 positional arguments but 1 was given`。
  第一版答案"碰巧正确"：时间值是从 hours_until 成功结果里的"现在 13:15"间接拿的，
  掩盖了 get_current_time 实际失败 —— 典型的「答案对、工具错」隐性失败。
  修复：tool_adapter() 按函数签名自适应——零参函数丢弃框架硬塞的参数。
  教训：接入框架时要验证每个工具真的执行成功，不能只看最终答案。

运行：.venv/Scripts/python.exe register_my_tools.py
输出：out/my_tools_run.json（含 trace 提取的工具调用证据）
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
from hello_agents import HelloAgentsLLM, SimpleAgent, ToolRegistry

load_dotenv()

MODEL = os.getenv("LLM_MODEL_ID") or "step-3.7-flash"
BASE_URL = os.getenv("LLM_BASE_URL") or "https://api.stepfun.com/v1"
KEY = os.getenv("LLM_API_KEY") or os.getenv("HERMES_CUSTOM_STEPFUN_API_KEY")

# ------------------------------------------------------------------ 我的 3 个工具（U3 原版，零外部依赖）
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
    """适配框架 1.0.0：execute_tool 对函数工具位置式传参 func(input_text)。

    零参函数会被塞进一个位置参数而报错 → 按签名自适应：
      0 参 → 包装成丢弃参数的调用；≥1 参 → 原样（calculate/hours_until 正常接参）。"""
    n = len(inspect.signature(fn).parameters)
    if n == 0:
        return lambda *a, **k: fn()
    return fn


QUESTION = "现在几点？帮我算一下 (137+85)*12 等于几？再告诉我距离 2026-11-01 00:00 还有多少小时？"


def extract_tool_evidence(lab_dir):
    """从框架自带 trace（memory/traces/*.jsonl）提取 tool_call / tool_result 事件。
    这是「日志证明工具被正确选择」的一手证据源（get_history 不保留中间过程）。"""
    time.sleep(0.5)  # 框架 trace 是异步/缓冲写盘，等它落盘再读
    traces = sorted(glob.glob(os.path.join(lab_dir, "memory", "traces", "*.jsonl")),
                    key=os.path.getmtime)
    if not traces:
        return [], None
        return [], None
    path = traces[-1]
    print(f"[extract] 读 {os.path.basename(path)}（{os.path.getsize(path)} 字节，共 {len(traces)} 个 trace）")
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

    registry.register_function(
        name="get_current_time",
        description="获取当前日期时间，北京时间（UTC+08），精确到秒",
        func=tool_adapter(get_current_time))
    registry.register_function(
        name="calculate",
        description="安全计算数学表达式，支持 + - * / // % ** 和括号，例如 '(137+85)*12'",
        func=tool_adapter(calculate))
    registry.register_function(
        name="hours_until",
        description="计算从现在到目标时刻（格式 YYYY-MM-DD HH:MM）还有多少小时",
        func=tool_adapter(hours_until))

    agent = SimpleAgent(
        name="我的工具Agent",
        llm=llm,
        system_prompt="你是助手。用户问时间、算术、距目标时刻时长时，必须先调用对应工具，不要自己编答案。",
        tool_registry=registry)

    print("=" * 70)
    print(f"框架版本：{getattr(hello_agents, '__version__', '?')}｜模型：{MODEL}｜温度：0")
    print(f"已注册工具：{agent.list_tools()}")
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
    trace_events, trace_path = extract_tool_evidence(lab_dir)

    # 从 trace 重建工具调用序列（step 顺序）
    calls, results = [], {}
    for ev in trace_events:
        if ev.get("event") == "tool_call":
            calls.append({"step": ev.get("step"), "tool": ev["payload"]["tool_name"],
                          "args": ev["payload"].get("args")})
        elif ev.get("event") == "tool_result":
            p = ev["payload"]
            results[p["tool_name"]] = {"result": p.get("result"), "工具成功": "错误" not in str(p.get("result", ""))}
    tool_summary = {c["tool"]: results.get(c["tool"], {}).get("工具成功", "无结果") for c in calls}

    record = {
        "ts": datetime.now().isoformat(timespec="seconds"),
        "framework_version": getattr(hello_agents, "__version__", "?"),
        "model": MODEL,
        "question": QUESTION,
        "registered_tools": str(agent.list_tools()),
        "answer": answer,
        "error": err,
        "seconds": secs,
        "expect": {"calc": (137 + 85) * 12},
        "tool_calls": calls,
        "tool_results": results,
        "tool_success_summary": tool_summary,
        "trace_file": os.path.basename(trace_path) if trace_path else None,
        "工具全部成功": all(tool_summary.values()) and len(calls) >= 3,
    }
    out = os.path.join(lab_dir, "out", "my_tools_run.json")
    os.makedirs(os.path.dirname(out), exist_ok=True)
    with open(out, "w", encoding="utf-8") as f:
        json.dump(record, f, ensure_ascii=False, indent=2)
    print(f"\n证据写入：{out}")
    print(f"trace 工具调用：{len(calls)} 次 → {tool_summary}")
    print(f"期望：计算 = {(137 + 85) * 12}；工具全部成功 = {record['工具全部成功']}")


if __name__ == "__main__":
    main()