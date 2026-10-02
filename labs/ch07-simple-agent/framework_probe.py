"""U7（第 7 天 · 2026-10-04）：框架帮我做了什么 —— 用 hello-agents 框架搭一个带工具的 Agent。

母本参考：`references/hello-agents/code/chapter7/my_simple_agent.py`（子类化 SimpleAgent）。
本文件不重写框架，只做**探针**：用框架的公开 API 搭一个 agent，然后打印它替我们做了什么：
  · 类层次（MRO）：SimpleAgent / ReActAgent / PlanSolveAgent / ReflectionAgent 都继承自 Agent
  · 工具注册：ToolRegistry.register_tool / register_function
  · 系统提示词增强：框架自动把「可用工具」描述拼进 system prompt
  · 工具调用循环：run() 内部自己完成 调用→执行→回填
  · 会话与历史：add_message / get_history / save_session

任务：让 agent 用计算器算 (123+456)*7/3 保留两位小数，并统计一句话的字符数。

运行：.venv/Scripts/python.exe framework_probe.py
"""
import json
import os
import time
from datetime import datetime

import hello_agents
from dotenv import load_dotenv
from hello_agents import (CalculatorTool, Config, HelloAgentsLLM, Message,
                          PlanSolveAgent, ReActAgent, ReflectionAgent,
                          SimpleAgent, ToolRegistry)

load_dotenv()

MODEL = os.getenv("LLM_MODEL_ID") or "step-3.7-flash"
BASE_URL = os.getenv("LLM_BASE_URL") or "https://api.stepfun.com/v1"
KEY = os.getenv("LLM_API_KEY") or os.getenv("HERMES_CUSTOM_STEPFUN_API_KEY") or os.getenv("HERMES_CUSTOM_DEEPSEEK_API_KEY")

QUESTION = "用计算器算 (123+456)*7/3，保留两位小数；再告诉我 '你好 hello' 有几个字符。"


def word_count(text: str) -> str:
    """统计字符数（含空格）。"""
    s = str(text)
    return f"'{s}' 共 {len(s)} 个字符"


def main():
    if not KEY:
        raise SystemExit("缺少密钥：LLM_API_KEY / HERMES_CUSTOM_STEPFUN_API_KEY")

    llm = HelloAgentsLLM(model=MODEL, api_key=KEY, base_url=BASE_URL, temperature=0)
    registry = ToolRegistry()
    registry.register_tool(CalculatorTool())
    registry.register_function(word_count, name="word_count", description="统计字符串的字符数")

    agent = SimpleAgent(name="探针Agent", llm=llm,
                        system_prompt="你是助手，需要计算或数数时必须调用工具。",
                        tool_registry=registry)

    enhanced = agent._get_enhanced_system_prompt() if hasattr(agent, "_get_enhanced_system_prompt") else agent.system_prompt

    print("=" * 70)
    print(f"框架版本：{getattr(hello_agents, '__version__', '?')}｜模型：{MODEL}")
    print(f"已注册工具：{agent.list_tools()}")
    print("-" * 70)
    print("框架自动增强后的 system prompt（前 600 字）：")
    print(enhanced[:600])
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

    history = []
    try:
        for m in agent.get_history():
            history.append({"role": getattr(m, "role", "?"), "content": str(getattr(m, "content", m))[:300]})
    except Exception as e:
        history = [{"error": f"{type(e).__name__}: {e}"}]

    classes = {c.__name__: [b.__name__ for b in c.__mro__] for c in
               (SimpleAgent, ReActAgent, PlanSolveAgent, ReflectionAgent)}

    record = {
        "ts": datetime.now().isoformat(timespec="seconds"),
        "framework_version": getattr(hello_agents, "__version__", "?"),
        "model": MODEL,
        "question": QUESTION,
        "registered_tools": str(agent.list_tools()),
        "enhanced_system_prompt": enhanced[:1200],
        "answer": answer,
        "error": err,
        "seconds": secs,
        "history": history,
        "class_hierarchy": classes,
        "expect": {"calc": "1351.00", "chars_of_你好hello": len("你好 hello")},
        # 注：第一版这里手写成 7，其实 "你好 hello" = 你/好/空格/h/e/l/l/o = 8 —— 连判据本身也要算，不要手写期望值
    }
    out = os.path.join(os.path.dirname(os.path.abspath(__file__)), "out", "framework_run.json")
    os.makedirs(os.path.dirname(out), exist_ok=True)
    with open(out, "w", encoding="utf-8") as f:
        json.dump(record, f, ensure_ascii=False, indent=2)
    print(f"\n证据写入：{out}")
    print("期望答案：计算 1351.00；'你好 hello' = 7 个字符")


if __name__ == "__main__":
    main()
