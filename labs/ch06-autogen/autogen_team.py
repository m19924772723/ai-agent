"""U19（第 17 天 · 2026-10-15）：AutoGen 多智能体软件开发团队 demo（第 6 章 AutoGenDemo）。

母本参考：`references/hello-agents/code/chapter6/AutoGenDemo/autogen_software_team.py`
  （AutoGen 0.7：AssistantAgent + RoundRobinGroupChat + TextMentionTermination + Console）

适配点：OpenAIChatCompletionClient 切到 stepfun OpenAI 兼容端点（LLM_BASE_URL/LLM_MODEL_ID/LLM_API_KEY）。
任务缩小（母本是"比特币价格应用"，需要 streamlit/requests/plotly 全家桶且对话很长）：
  让四角色团队协作写一个"两点欧氏距离函数"，走 需求→实现→审查→验收 完整链路，控制 token。

采集：总调用次数 / token / 墙钟耗时 / 每轮消息，供三框架对比表（AgentScope vs AutoGen vs CAMEL）。

运行：.venv/Scripts/python.exe autogen_team.py
"""
import asyncio
import json
import os
import time
from datetime import datetime

from autogen_agentchat.agents import AssistantAgent, UserProxyAgent
from autogen_agentchat.conditions import TextMentionTermination
from autogen_agentchat.teams import RoundRobinGroupChat
from autogen_ext.models.openai import OpenAIChatCompletionClient
from dotenv import load_dotenv

load_dotenv()

# 端点选择：stepfun 配额已耗尽（402，2026-10-15 实测）→ 默认切 deepseek（与 U18 AgentScope 同款）
MODEL = os.getenv("LLM_MODEL_ID") or "deepseek-flash"
BASE_URL = os.getenv("LLM_BASE_URL") or "https://api.deepseek.com"
KEY = (os.getenv("LLM_API_KEY") or os.getenv("HERMES_CUSTOM_DEEPSEEK_API_KEY")
       or os.getenv("HERMES_CUSTOM_STEPFUN_API_KEY"))

TASK = (
    "请团队协作完成一个小任务：写一个 Python 函数 distance(p1, p2) 计算二维平面上两点的欧氏距离，"
    "返回 float。要求：产品经理先拆需求，工程师写实现，审查员审查并给出一个改进建议，"
    "用户代理最后验收并回复结束词。代码控制在 20 行以内。"
)


async def main():
    if not KEY:
        raise SystemExit("缺少密钥：LLM_API_KEY / HERMES_CUSTOM_STEPFUN_API_KEY")
    llm = OpenAIChatCompletionClient(
        model=MODEL, api_key=KEY, base_url=BASE_URL, temperature=0,
        # AutoGen 0.7 对非 OpenAI 标准模型必须显式给 model_info（否则报 "model_info is required"）
        model_info={
            "vision": False, "function_calling": True, "json_output": True,
            "family": "step", "structured_output": False, "multiple_system_messages": True,
        })
    print("=" * 70)
    print(f"AutoGen 版本：请见 pip show｜模型 {MODEL}｜端点 {BASE_URL}")
    print(f"团队：ProductManager / Engineer / CodeReviewer / UserProxy（RoundRobin，max_turns=8）")
    print("=" * 70)

    t0 = time.perf_counter()
    def auto_accept(_prompt, _cancellation_token=None):
        """UserProxy 的无头模式：模拟用户验收通过（AutoGen 0.7 需要 input_func，否则交互等待 stdin）。"""
        return "TERMINATE"

    msgs = []
    async for event in (RoundRobinGroupChat(
        participants=[AssistantAgent(name="ProductManager", model_client=llm, system_message="拆需求，回复'请工程师开始实现'"),
                      AssistantAgent(name="Engineer", model_client=llm, system_message="写代码，回复'请代码审查员检查'"),
                      AssistantAgent(name="CodeReviewer", model_client=llm, system_message="审查，回复'请用户代理验收'"),
                      UserProxyAgent(name="UserProxy", description="验收后回复 TERMINATE", input_func=auto_accept)],
        termination_condition=TextMentionTermination("TERMINATE"), max_turns=8
    )).run_stream(task=TASK):
        src = getattr(event, "source", "?")
        content = getattr(event, "content", None)
        if content:
            msgs.append({"source": src, "content": str(content)})
            print(f"\n[{src}]")
            print(str(content)[:250])
        if getattr(event, "type", "") == "TaskResult":
            pass
    wall = round(time.perf_counter() - t0, 1)
    print("\n" + "=" * 70)
    print(f"墙钟耗时：{wall} s｜消息数：{len(msgs)}")

    # 结果落盘
    record = {
        "ts": datetime.now().isoformat(timespec="seconds"),
        "framework": "AutoGen",
        "model": MODEL,
        "base_url": BASE_URL,
        "task": TASK,
        "agents": ["ProductManager", "Engineer", "CodeReviewer", "UserProxy"],
        "max_turns": 8,
        "wall_seconds": wall,
        "message_count": len(msgs),
        "messages": msgs,
    }
    out = os.path.join(os.path.dirname(os.path.abspath(__file__)), "out", "autogen_run.json")
    os.makedirs(os.path.dirname(out), exist_ok=True)
    with open(out, "w", encoding="utf-8") as f:
        json.dump(record, f, ensure_ascii=False, indent=2)
    print(f"证据写入：{out}")


if __name__ == "__main__":
    asyncio.run(main())