"""
U17（第 16 天 · 2026-10-13）：框架内置 Skill/Task/TodoWrite/DevLog 工具的实际用途。

U7/U15 都看到框架自动注册了 4 个内置工具但从未深究。本单元读源码 + 实测验证：
  1. SkillTool     —— 按需加载领域知识（skills/ 目录，渐进式披露，tool_result 注入）
  2. TaskTool      —— 子代理隔离上下文（独立历史、工具过滤、摘要返回）
  3. TodoWriteTool —— 任务进度管理（memory/todos/，声明式覆盖、单线程强制）
  4. DevLogTool    —— 开发日志（memory/devlogs/，category+content+metadata）

实测任务（必须触发内置工具的典型场景）：
  "把'调研并总结三个最常用的 Agent 评测指标'拆成待办清单，
   记一条开发日志说明为什么要做这个调研，
   然后完成调研给出三个指标。"

运行：.venv/Scripts/python.exe builtin_tools_probe.py
输出：out/builtin_tools_run.json（含各工具调用 + 落盘文件核对）
"""
import glob
import json
import os
import time
from datetime import datetime

import hello_agents
from dotenv import load_dotenv
from hello_agents import HelloAgentsLLM, ReActAgent, ToolRegistry

load_dotenv()

MODEL = os.getenv("LLM_MODEL_ID") or "step-3.7-flash"
BASE_URL = os.getenv("LLM_BASE_URL") or "https://api.stepfun.com/v1"
KEY = os.getenv("LLM_API_KEY") or os.getenv("HERMES_CUSTOM_STEPFUN_API_KEY")

QUESTION = (
    "先调用 TodoWrite 把'调研并总结三个最常用的 Agent 评测指标'这个任务拆成待办清单（3 步），"
    "再调用 DevLog 记一条 development 类别的日志说明为什么要做这个调研，"
    "最后直接回答：三个最常用的 Agent 评测指标是什么？"
)


def extract_events(lab_dir):
    """读最新框架 trace。"""
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
        raise SystemExit("缺少密钥")

    llm = HelloAgentsLLM(model=MODEL, api_key=KEY, base_url=BASE_URL, temperature=0)
    registry = ToolRegistry()

    agent = ReActAgent(
        name="内置工具探针",
        llm=llm,
        system_prompt="你是助手。任务拆分用 TodoWrite，记录决策/问题用 DevLog，需要专业知识用 Skill。",
        tool_registry=registry)  # 不注册自定义工具：只测框架自动注册的 4 个内置工具

    print("=" * 70)
    print(f"框架：{getattr(hello_agents, '__version__', '?')}｜Agent: ReActAgent｜模型：{MODEL}")
    print(f"自动注册的工具：{list(registry._tools.keys()) if hasattr(registry, '_tools') else '?'}")
    print("-" * 70)

    t0 = time.perf_counter()
    try:
        answer = agent.run(QUESTION)
        err = None
    except Exception as e:
        answer, err = None, f"{type(e).__name__}: {e}"
    secs = round(time.perf_counter() - t0, 2)
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
            results.setdefault(ev["payload"]["tool_name"], []).append(ev["payload"].get("result", ""))

    # 落盘核对：内置工具写到哪里
    disk = {}
    for d, label in [("memory/todos", "待办"), ("memory/devlogs", "开发日志"),
                     ("memory/skills", "技能"), ("memory/traces", "trace")]:
        p = os.path.join(lab_dir, d)
        files = sorted(glob.glob(p + "/*"), key=os.path.getmtime) if os.path.exists(p) else []
        disk[label] = [os.path.basename(f) for f in files[-3:]] if files else "（无此目录）"

    record = {
        "ts": datetime.now().isoformat(timespec="seconds"),
        "framework_version": getattr(hello_agents, "__version__", "?"),
        "model": MODEL,
        "question": QUESTION,
        "answer": answer,
        "error": err,
        "seconds": secs,
        "auto_registered_tools": list(registry._tools.keys()) if hasattr(registry, "_tools") else [],
        "calls": calls,
        "results": results,
        "disk_files": disk,
        "trace_file": os.path.basename(trace_path) if trace_path else None,
        "checks": {
            "调用了TodoWrite": any(c["tool"] == "TodoWrite" for c in calls),
            "调用了DevLog": any(c["tool"] == "DevLog" for c in calls),
            "调用了Skill": any(c["tool"] == "Skill" for c in calls),
            "待办落盘": disk["待办"] != "（无此目录）",
            "日志落盘": disk["开发日志"] != "（无此目录）",
        },
    }
    out = os.path.join(lab_dir, "out", "builtin_tools_run.json")
    os.makedirs(os.path.dirname(out), exist_ok=True)
    with open(out, "w", encoding="utf-8") as f:
        json.dump(record, f, ensure_ascii=False, indent=2)

    print("\n" + "-" * 70)
    print(f"调用序列：{[c['tool'] for c in calls]}")
    print(f"落盘核对：{disk}")
    print(f"校验：{record['checks']}")
    print(f"证据写入：{out}")


if __name__ == "__main__":
    main()