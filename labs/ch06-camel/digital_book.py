"""U20（第 18 天 · 2026-10-16）：CAMEL DigitalBookWriting demo（第 6 章框架实践③，收官对比表）。

母本参考：`references/hello-agents/code/chapter6/CAMEL/DigitalBookWriting.py`（62 行，双角色 RolePlaying）。

与已学的框架对比（本单元目的）：
  · AgentScope = MsgHub 消息路由 + pipeline（U18，狼人杀 10 调用/156MB）
  · AutoGen    = RoundRobin 轮转 + 终止条件（U19，软件团队 8 消息/59MB）
  · CAMEL      = **双角色 RolePlaying（RolePlaying 类，一问一答步进）**——本单元实测

适配：母本用 ModelPlatformType.QWEN（百炼），我们切到 **OPENAI_COMPATIBLE** 自定义端点（deepseek，
与 U19 同款：LLM_API_KEY/LLM_BASE_URL/LLM_MODEL 环境变量）。角色：作家(user) + 心理学家(assistant)，
任务：创作"拖延症心理学"短篇电子书（母本原文），回合上限 30，检测 CAMEL_TASK_DONE 结束。

运行：.venv/Scripts/python.exe digital_book.py
输出：out/camel_run.json（回合数/墙钟/消息数 + 协作文本）
"""
import json
import os
import time
from datetime import datetime

from camel.agents import ChatAgent
from camel.configs import ChatGPTConfig
from camel.models import BaseModelBackend, ModelFactory
from camel.societies import RolePlaying
from camel.types import ModelPlatformType


class StatsModel(BaseModelBackend):
    """统计包装器（U18 同款）：继承 BaseModelBackend（框架要求 isinstance 检查），
    实现抽象方法 _run/_arun 转发 inner，在 run() 后累计 token usage。"""

    def __init__(self, inner):
        # 先跑基类：此时 __setattr__ 里 inner 尚未存在 → 直接设自身（不转发）
        super().__init__(model_type=inner.model_type, model_config_dict=inner.model_config_dict)
        object.__setattr__(self, "inner", inner)
        object.__setattr__(self, "calls", 0)
        object.__setattr__(self, "prompt_tokens", 0)
        object.__setattr__(self, "completion_tokens", 0)

    def _run(self, *args, **kwargs):
        return self.inner.run(*args, **kwargs)

    def _arun(self, *args, **kwargs):
        return self.inner.arun(*args, **kwargs)

    def run(self, messages, response_format=None, tools=None):
        resp = self.inner.run(messages, response_format=response_format, tools=tools)
        self.calls += 1
        try:
            usage = getattr(resp, "usage", None)
            if usage is not None:
                self.prompt_tokens += getattr(usage, "prompt_tokens", 0) or 0
                self.completion_tokens += getattr(usage, "completion_tokens", 0) or 0
        except Exception:
            pass
        return resp

    @property
    def token_counter(self):
        return self.inner.token_counter

    def __getattr__(self, name):
        # 注意：必须用 object.__getattribute__ 取 inner，直接 self.inner 会再次触发 __getattr__ 递归
        return getattr(object.__getattribute__(self, "inner"), name)

    def __setattr__(self, name, value):
        if name in ("inner", "calls", "prompt_tokens", "completion_tokens"):
            object.__setattr__(self, name, value)
        else:
            try:
                inner = object.__getattribute__(self, "inner")
            except AttributeError:
                # 基类 __init__ 阶段（inner 未就位）→ 直接设自身
                object.__setattr__(self, name, value)
            else:
                setattr(inner, name, value)
from dotenv import load_dotenv

load_dotenv()

LLM_API_KEY = (os.getenv("LLM_API_KEY") or os.getenv("HERMES_CUSTOM_DEEPSEEK_API_KEY")
               or os.getenv("HERMES_CUSTOM_STEPFUN_API_KEY"))
LLM_BASE_URL = os.getenv("LLM_BASE_URL") or "https://api.deepseek.com"
LLM_MODEL = os.getenv("LLM_MODEL") or "deepseek-flash"

TASK_PROMPT = """创作一本关于"拖延症心理学"的短篇电子书，目标读者是对心理学感兴趣的普通大众。
要求：
1. 内容科学严谨，基于实证研究
2. 语言通俗易懂，避免过多专业术语
3. 包含实用的改善建议和案例分析
4. 篇幅控制在300-500字（本实验简化版：引言+一个核心章节+总结即可）
5. 结构清晰，包含引言、核心章节和总结

请尽快完成任务，单轮输出控制在200字内。"""


def main():
    if not LLM_API_KEY:
        raise SystemExit("缺少密钥：LLM_API_KEY / HERMES_CUSTOM_DEEPSEEK_API_KEY")

    # CAMEL 0.2.75：自定义 OpenAI 兼容端点用 OPENAI_COMPATIBLE 平台（官方文档做法）
    inner = ModelFactory.create(
        model_platform=ModelPlatformType.OPENAI_COMPATIBLE_MODEL,
        model_type=LLM_MODEL,
        url=LLM_BASE_URL,
        api_key=LLM_API_KEY,
        model_config_dict=ChatGPTConfig(temperature=0.2, max_tokens=2048).as_dict(),
    )
    model = StatsModel(inner)  # 统计包装（U18 同款）

    print("=" * 70)
    print(f"CAMEL｜模型 {LLM_MODEL}｜端点 {LLM_BASE_URL}")
    print(f"协作任务：拖延症心理学短篇电子书（母本原文，篇幅按实验简化）")
    print("=" * 70)

    role_play_session = RolePlaying(
        assistant_role_name="心理学家",
        user_role_name="作家",
        task_prompt=TASK_PROMPT,
        model=model,
    )

    chat_turn_limit, n = 30, 0
    input_msg = role_play_session.init_chat()
    transcript = []

    t0 = time.perf_counter()
    done = False
    while n < chat_turn_limit:
        n += 1
        try:
            assistant_response, user_response = role_play_session.step(input_msg)
        except Exception as e:
            print(f"第 {n} 轮异常：{type(e).__name__}: {e}")
            break
        u_content = user_response.msg.content
        a_content = assistant_response.msg.content
        transcript.append({"turn": n, "作家": str(u_content), "心理学家": str(a_content)})
        print(f"\n--- 第 {n} 轮 ---")
        print(f"[作家] {str(u_content)[:150]}")
        print(f"[心理学家] {str(a_content)[:150]}")

        if "CAMEL_TASK_DONE" in str(u_content):
            print("✅ 任务完成（CAMEL_TASK_DONE）")
            done = True
            break
        input_msg = assistant_response.msg

    wall = round(time.perf_counter() - t0, 1)
    print(f"\n总共进行了 {n} 轮协作对话｜墙钟 {wall} s｜完成标志：{done}")
    print(f"LLM 调用 {model.calls} 次｜prompt {model.prompt_tokens} + completion {model.completion_tokens} = {model.prompt_tokens + model.completion_tokens} tokens")

    record = {
        "ts": datetime.now().isoformat(timespec="seconds"),
        "framework": "CAMEL",
        "model": LLM_MODEL,
        "base_url": LLM_BASE_URL,
        "roles": {"user": "作家", "assistant": "心理学家"},
        "task": TASK_PROMPT,
        "turns": n,
        "wall_seconds": wall,
        "task_done": done,
        "llm_calls": model.calls,
        "tokens": {"prompt": model.prompt_tokens, "completion": model.completion_tokens,
                   "total": model.prompt_tokens + model.completion_tokens},
        "transcript": transcript,
    }
    out = os.path.join(os.path.dirname(os.path.abspath(__file__)), "out", "camel_run.json")
    os.makedirs(os.path.dirname(out), exist_ok=True)
    with open(out, "w", encoding="utf-8") as f:
        json.dump(record, f, ensure_ascii=False, indent=2)
    print(f"证据写入：{out}")


if __name__ == "__main__":
    main()