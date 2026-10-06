"""自写最小 Agent Loop（U8 / 第 8 天）——把阶段1 学到的三条经验落成代码。

设计取自此前的实测结论：
  · U3：工具契约用**原生 function calling**（schema 交给 SDK），不用提示词+正则
  · U5：解析与循环必须能区分"模型跑偏"和"工具失败"，并且失败要能回填给模型
  · U6：失败模式要能归类（预算耗尽 / 步数上限 / 工具报错 / 原地打转），不能只返回 None

对外只有一个类 AgentLoop，两个入口：
  · register(name, fn, description, parameters)  注册工具
  · run(user_input) -> RunResult                 跑一轮，返回答案 + 轨迹 + 成本 +停止原因

为了**可测**：模型调用走注入的 `model_fn`（离线测试塞假模型），不注入时才用真端点。
"""
from __future__ import annotations

import json
import time
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional

DONE, MAX_STEPS, BUDGET, LOOP_GUARD = "done", "max_steps", "budget", "loop_guard"


@dataclass
class Step:
    index: int
    content: str = ""
    tool_calls: List[Dict[str, Any]] = field(default_factory=list)
    tool_results: List[str] = field(default_factory=list)
    tokens: int = 0


@dataclass
class RunResult:
    answer: Optional[str]
    stop_reason: str
    steps: List[Step]
    tokens: int
    seconds: float
    error: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "answer": self.answer,
            "stop_reason": self.stop_reason,
            "steps": [{"index": s.index, "content": s.content,
                       "tool_calls": s.tool_calls, "tool_results": s.tool_results,
                       "tokens": s.tokens} for s in self.steps],
            "tokens": self.tokens,
            "seconds": self.seconds,
            "error": self.error,
        }


class AgentLoop:
    def __init__(self, *, model_fn: Optional[Callable] = None, client=None, model: str = "",
                 system_prompt: str = "", max_steps: int = 6, max_tokens: int = 20000,
                 temperature: float = 0.0):
        self.model_fn = model_fn
        self.client = client
        self.model = model
        self.system_prompt = system_prompt
        self.max_steps = max_steps
        self.max_tokens = max_tokens
        self.temperature = temperature
        self.tools: Dict[str, Dict[str, Any]] = {}

    # ---------------- 工具注册 ----------------
    def register(self, name: str, fn: Callable, description: str = "",
                 parameters: Optional[Dict[str, Any]] = None) -> "AgentLoop":
        self.tools[name] = {
            "fn": fn,
            "schema": {"type": "function", "function": {
                "name": name,
                "description": description or name,
                "parameters": parameters or {"type": "object", "properties": {}},
            }},
        }
        return self

    def tool_schemas(self) -> List[Dict[str, Any]]:
        return [t["schema"] for t in self.tools.values()]

    def call_tool(self, name: str, args: Dict[str, Any]) -> str:
        """执行工具：任何异常都转成可回填的文本，不让循环崩掉。"""
        if name not in self.tools:
            return f"错误：工具 {name} 不存在。可用工具：{list(self.tools)}"
        try:
            return str(self.tools[name]["fn"](**(args or {})))
        except TypeError as e:            # 参数对不上
            return f"错误：工具 {name} 参数不匹配（{e}）"
        except Exception as e:            # 工具内部异常
            return f"错误：工具 {name} 执行失败（{type(e).__name__}: {e}）"

    # ---------------- 跑一轮 ----------------
    def _model_call(self, messages: List[Dict[str, Any]]) -> Dict[str, Any]:
        """统一成 {'content','tool_calls','tokens'} 三种形态，方便离线假模型注入。"""
        if self.model_fn is not None:
            return self.model_fn(messages, self.tool_schemas())
        if self.client is None:
            raise RuntimeError("既没有 model_fn 也没有 client，无法调用模型")
        resp = self.client.chat.completions.create(
            model=self.model, messages=messages, tools=self.tool_schemas() or None,
            temperature=self.temperature,
        )
        msg = resp.choices[0].message
        usage = getattr(resp, "usage", None)
        return {
            "content": msg.content or "",
            "tool_calls": [{"id": c.id, "name": c.function.name, "arguments": c.function.arguments}
                           for c in (msg.tool_calls or [])],
            "tokens": getattr(usage, "total_tokens", 0) if usage else 0,
        }

    def run(self, user_input: str) -> RunResult:
        messages: List[Dict[str, Any]] = []
        if self.system_prompt:
            messages.append({"role": "system", "content": self.system_prompt})
        messages.append({"role": "user", "content": user_input})

        steps: List[Step] = []
        total_tokens = 0
        t0 = time.perf_counter()
        last_signature = None
        stop_reason, answer, error = MAX_STEPS, None, None

        for i in range(1, self.max_steps + 1):
            # 终止条件 0（前置预算闸）：预算已耗尽就不再发起新调用，避免"越界那一轮"白花钱
            if total_tokens >= self.max_tokens:
                stop_reason = BUDGET
                answer = steps[-1].content if steps else None
                break
            try:
                out = self._model_call(messages)
            except Exception as e:
                error = f"{type(e).__name__}: {e}"
                stop_reason = "model_error"
                break

            tokens = int(out.get("tokens") or 0)
            total_tokens += tokens
            step = Step(index=i, content=out.get("content", ""), tokens=tokens)
            calls = out.get("tool_calls") or []

            # 终止条件 1：模型不再调工具 → 收敛
            if not calls:
                answer = out.get("content") or ""
                stop_reason = DONE
                steps.append(step)
                break

            # 终止条件 2：原地打转（同一组调用连续出现两次）
            signature = json.dumps([[c.get("name"), c.get("arguments")] for c in calls],
                                   ensure_ascii=False, sort_keys=True)
            if signature == last_signature:
                steps.append(step)
                stop_reason = LOOP_GUARD
                answer = out.get("content") or ""
                break
            last_signature = signature

            messages.append({"role": "assistant", "content": step.content,
                             "tool_calls": [{"id": c.get("id") or f"call_{i}",
                                             "type": "function",
                                             "function": {"name": c.get("name"),
                                                          "arguments": c.get("arguments")}}
                                            for c in calls]})
            for c in calls:
                try:
                    args = json.loads(c.get("arguments") or "{}")
                    if not isinstance(args, dict):     # 模型偶尔给数组/字符串
                        raise ValueError("arguments 不是 JSON 对象")
                except Exception as e:
                    result = f"错误：参数不是合法 JSON（{e}）；收到的是 {c.get('arguments')!r}"
                else:
                    result = self.call_tool(c.get("name"), args)
                step.tool_calls.append({"name": c.get("name"), "arguments": c.get("arguments")})
                step.tool_results.append(result)
                messages.append({"role": "tool", "tool_call_id": c.get("id") or f"call_{i}",
                                 "content": result})
            steps.append(step)

            # 终止条件 3：单轮就冲破预算（后置兜底；前置闸在下一轮开始时生效）
            if total_tokens >= self.max_tokens and stop_reason != DONE:
                stop_reason = BUDGET
                answer = step.content or None
                break

        seconds = round(time.perf_counter() - t0, 3)
        return RunResult(answer=answer, stop_reason=stop_reason, steps=steps,
                         tokens=total_tokens, seconds=seconds, error=error)
