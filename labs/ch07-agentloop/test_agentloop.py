"""AgentLoop 的测试（U8 验收：正常 / 异常 / 边界 各一组 + 3 条真实模型用例）。

前半段离线（注入假模型，零 token、可重复）；后半段打真端点跑 3 条真实用例。
运行：
  pytest -q test_agentloop.py              # 只跑离线用例（-m "not live"）
  AGENTLOOP_LIVE=1 pytest -q test_agentloop.py   # 含真实端点用例
"""
from __future__ import annotations

import json
import os

import pytest

from agentloop import BUDGET, DONE, LOOP_GUARD, MAX_STEPS, AgentLoop

# ------------------------------------------------------------------ 假模型工具
class FakeModel:
    """按剧本返回工具调用；剧本用完就返回最终答案。"""

    def __init__(self, script, final="最终答案", tokens=100):
        self.script = list(script)
        self.final = final
        self.tokens = tokens
        self.seen = []

    def __call__(self, messages, tools):
        self.seen.append(json.loads(json.dumps(messages, ensure_ascii=False)))
        assert tools and tools[0]["function"]["name"], "工具 schema 必须传下去"
        if self.script:
            calls = self.script.pop(0)
            return {"content": "", "tool_calls": calls, "tokens": self.tokens}
        return {"content": self.final, "tool_calls": [], "tokens": self.tokens}


def make_loop(script, final="最终答案", **kw):
    loop = AgentLoop(model_fn=FakeModel(script, final), max_steps=kw.pop("max_steps", 6), **kw)
    loop.register("add", lambda a, b: f"{int(a) + int(b)}", "两数相加",
                  {"type": "object", "properties": {"a": {"type": "integer"}, "b": {"type": "integer"}},
                   "required": ["a", "b"]})
    loop.register("boom", lambda: 1 / 0, "必定报错的工具")
    return loop


# ================================ 正常路径
def test_normal_one_tool_then_answer():
    loop = make_loop([[{"id": "c1", "name": "add", "arguments": '{"a": 2, "b": 3}'}]], final="结果是 5")
    r = loop.run("算 2+3")
    assert r.stop_reason == DONE and r.answer == "结果是 5"
    assert len(r.steps) == 2                                  # 一轮工具 + 一轮收尾
    assert r.steps[0].tool_results == ["5"]
    assert r.steps[0].tool_calls[0]["name"] == "add"


def test_two_tool_calls_in_one_step_are_both_executed():
    loop = make_loop([[{"id": "c1", "name": "add", "arguments": '{"a": 1, "b": 1}'},
                       {"id": "c2", "name": "add", "arguments": '{"a": 2, "b": 2}'}]])
    r = loop.run("两个加法")
    assert r.steps[0].tool_results == ["2", "4"]              # 一个模型输出里的两个调用都执行
    assert r.stop_reason == DONE


def test_multi_step_dependency():
    """后一步依赖前一步：模型第二轮拿第一轮结果继续算。"""
    script = [
        [{"id": "c1", "name": "add", "arguments": '{"a": 10, "b": 20}'}],
        [{"id": "c2", "name": "add", "arguments": '{"a": 30, "b": 12}'}],
    ]
    loop = make_loop(script, final="42")
    r = loop.run("先 10+20，再加 12")
    assert [s.tool_results for s in r.steps[:-1]] == [["30"], ["42"]]
    assert r.answer == "42"


# ================================ 异常路径
def test_tool_raises_is_reported_and_loop_survives():
    loop = make_loop([[{"id": "c1", "name": "boom", "arguments": "{}"}]], final="我改用别的方式")
    r = loop.run("调用会炸的工具")
    assert "执行失败" in r.steps[0].tool_results[0]            # 异常被转成文本回填
    assert r.answer == "我改用别的方式" and r.stop_reason == DONE


def test_unknown_tool_reported():
    loop = make_loop([[{"id": "c1", "name": "nope", "arguments": "{}"}]])
    r = loop.run("调用不存在的工具")
    assert "不存在" in r.steps[0].tool_results[0]
    assert r.stop_reason == DONE


def test_bad_json_arguments_reported():
    loop = make_loop([[{"id": "c1", "name": "add", "arguments": '{"a": 1, "b": 2'}]])
    r = loop.run("参数是坏 JSON")
    assert "不是合法 JSON" in r.steps[0].tool_results[0]


def test_model_error_stops_cleanly():
    def broken(messages, tools):
        raise ConnectionError("模拟网络中断")

    loop = AgentLoop(model_fn=broken)
    r = loop.run("随便问问")
    assert r.stop_reason == "model_error" and "ConnectionError" in r.error
    assert r.answer is None and len(r.steps) == 0             # 不产生假轨迹


# ================================ 边界路径
def test_max_steps_exhausted():
    """模型一直调工具、从不收尾 → 撞步数上限，且必须带停因返回。"""
    script = [[{"id": f"c{i}", "name": "add", "arguments": json.dumps({"a": i, "b": 1})}]
              for i in range(10)]
    loop = make_loop(script, max_steps=3)
    r = loop.run("没完没了")
    assert r.stop_reason == MAX_STEPS and len(r.steps) == 3 and r.answer is None


def test_loop_guard_on_repeated_identical_call():
    """同一组调用重复出现 → 判定原地打转，提前止损。"""
    call = [{"id": "c1", "name": "add", "arguments": '{"a": 1, "b": 1}'}]
    loop = make_loop([call, call, call], final="不该走到这里")
    r = loop.run("重复同一个调用")
    assert r.stop_reason == LOOP_GUARD and len(r.steps) == 2


def test_budget_exhausted_before_next_call():
    """预算闸是**前置**的：花完预算后不再发起新调用（每轮假模型报 100 token，上限 100）。"""
    call = [{"id": "c1", "name": "add", "arguments": '{"a": 1, "b": 1}'}]
    loop = make_loop([call, call], max_tokens=100)
    r = loop.run("预算很小")
    assert r.stop_reason == BUDGET and r.tokens == 100 and len(r.steps) == 1


def test_no_tools_registered_still_works():
    """一个工具都没注册时不能崩（tools=None 传下去要合法）。"""
    loop = AgentLoop(model_fn=lambda m, t: {"content": "我没有工具也能答", "tool_calls": [], "tokens": 5})
    r = loop.run("你好")
    assert r.stop_reason == DONE and r.answer == "我没有工具也能答"


# ================================ 真实端点（可选）
LIVE = os.getenv("AGENTLOOP_LIVE") == "1"
live = pytest.mark.skipif(not LIVE, reason="设 AGENTLOOP_LIVE=1 才跑真实端点")


def _live_loop():
    from openai import OpenAI
    from dotenv import load_dotenv
    load_dotenv()
    model = os.getenv("LLM_MODEL_ID") or "step-3.7-flash"
    base = os.getenv("LLM_BASE_URL") or "https://api.stepfun.com/v1"
    key = os.getenv("LLM_API_KEY") or os.getenv("HERMES_CUSTOM_STEPFUN_API_KEY")
    if not key:
        pytest.skip("缺少密钥")
    loop = AgentLoop(client=OpenAI(api_key=key, base_url=base, timeout=90), model=model,
                     system_prompt="需要计算时必须调用工具，不要心算。", max_steps=5, max_tokens=20000)
    loop.register("add", lambda a, b: f"{int(a) + int(b)}", "两数相加（整数）",
                  {"type": "object", "properties": {"a": {"type": "integer"}, "b": {"type": "integer"}},
                   "required": ["a", "b"]})
    loop.register("multiply", lambda a, b: f"{int(a) * int(b)}", "两数相乘（整数）",
                  {"type": "object", "properties": {"a": {"type": "integer"}, "b": {"type": "integer"}},
                   "required": ["a", "b"]})
    return loop


@live
def test_live_dependency_chain():
    """真实模型：两数相加再用结果相乘 —— 必须出现 ≥2 轮工具调用。"""
    r = _live_loop().run("先算 137 + 245，再把结果乘以 3，告诉我最终数字。")
    assert r.stop_reason == DONE, r.stop_reason
    assert "1146" in (r.answer or ""), r.answer
    assert sum(len(s.tool_calls) for s in r.steps) >= 2


@live
def test_live_no_hallucinated_tool():
    """真实模型：问一个工具做不到的事，应正常收尾而不是乱编工具名。"""
    r = _live_loop().run("请用 add 工具算 5+7，然后告诉我今天是星期几（这个不用工具）。")
    assert r.stop_reason in (DONE, LOOP_GUARD), r.stop_reason
    names = {c["name"] for s in r.steps for c in s.tool_calls}
    assert names <= {"add", "multiply"}, names
