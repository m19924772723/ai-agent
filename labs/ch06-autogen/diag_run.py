"""U19 诊断：为什么 autogen_team.py 的 run_stream 立即返回 0 消息？

怀疑：RoundRobinGroupChat.run_stream 在 asyncio 环境下的事件/异常被吞。
本文件用母本 Console 方式 + 一个最小 team 复现，打印每一步。
"""
import asyncio
import os

from autogen_agentchat.agents import AssistantAgent
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


async def main():
    llm = OpenAIChatCompletionClient(
        model=MODEL, api_key=KEY, base_url=BASE_URL, temperature=0,
        model_info={"vision": False, "function_calling": True, "json_output": True,
                    "family": "step", "structured_output": False, "multiple_system_messages": True})
    print("llm 创建 OK（跳过单次调用诊断，直接跑 team）")

    pm = AssistantAgent(name="ProductManager", model_client=llm,
                        system_message="你是产品经理，拆需求后回复'请工程师开始实现'。")
    eng = AssistantAgent(name="Engineer", model_client=llm,
                         system_message="你是工程师，写代码后回复'请代码审查员检查'。")
    team = RoundRobinGroupChat(
        participants=[pm, eng],
        termination_condition=TextMentionTermination("TERMINATE"),
        max_turns=3)
    print("\nteam 创建 OK，启动 run_stream…")
    try:
        async for event in team.run_stream(task="写一个返回 42 的 Python 函数。"):
            print("事件:", type(event).__name__, "| source:", getattr(event, "source", "?"),
                  "| content:", str(getattr(event, "content", ""))[:80])
    except Exception as e:
        import traceback
        print(f"run_stream 异常: {type(e).__name__}: {e}")
        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(main())
