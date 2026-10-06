# labs/ch07-agentloop —— 自写 Agent Loop + 测试（U8 单元）

## 1. 出处与目标

- 母本：第 7 章《构建你的 Agent 框架》（`my_simple_agent.py` / `my_react_agent.py`）
- 本单元做两件事：
  1. **把阶段1 的三条实测结论落成一个可复用的 Agent Loop**（`agentloop.py`），并补上母本 chapter7 缺失的测试纪律（`test_agentloop.py`）；
  2. **排查并修复母本 chapter7 在框架 1.0.0 下的兼容问题**（`upstream-adapted/`），把「书里的代码跑不起来」定位到具体行。

## 2. 设计：循环里那些"失败要能归类"的取舍

| 设计点 | 来自哪次教训 | 具体做法 |
|---|---|---|
| 工具契约用原生 function calling | U3（原生 2489 token / 8.16 s，优于提示词+正则 3051 / 11.29 s） | `tool_schemas()` 直接把 schema 交给 SDK，不做正则解析 |
| 四类停止原因必须显式返回 | U5（v1 耗尽步数却只能返回 None） | `stop_reason ∈ {done, max_steps, budget, loop_guard, model_error}` |
| **预算闸放在发起调用之前** | U6（工具口径坑） + 本次第 1 版实现 | 第 1 版把预算判断写在"收尾之后"，等于多花一轮；改成循环开头先查预算 |
| 工具异常转文本回填 | U6（`count("keyword")=0` 被当真事实） | `call_tool()` 把 `TypeError`（参数不匹配）与工具内部异常分别转成可读文本，让模型能自己改 |
| 参数不是合法 JSON 也要能说清错在哪 | U5（参数解析坑） | 显式区分"参数不是 JSON 对象"，并把原始串回显给模型 |
| 原地打转要止损 | U6（react 那轮空转） | 同一组调用签名连续出现两次 → `loop_guard` 提前退出 |
| 可测性：模型调用可注入 | 本次 | `model_fn` 参数让测试塞假模型，离线零 token 跑完 11 个用例 |

## 3. 怎么跑

```bash
cd D:/code/hermes/ai-agent/labs/ch07-agentloop
uv venv .venv --python 3.11
uv pip install --python .venv/Scripts/python.exe pytest openai python-dotenv
export PYTHONIOENCODING=utf-8

.venv/Scripts/python.exe -m pytest -q test_agentloop.py              # 11 离线用例，0.05 s，零 token
export LLM_MODEL_ID=step-3.7-flash LLM_BASE_URL=https://api.stepfun.com/v1 LLM_API_KEY=$HERMES_CUSTOM_STEPFUN_API_KEY
AGENTLOOP_LIVE=1 .venv/Scripts/python.exe -m pytest -q test_agentloop.py   # +2 真实端点用例
```

## 4. 真实输出（2026-10-05 实测）

**自写 Agent Loop 的测试**

```
.venv/Scripts/python.exe -m pytest -q test_agentloop.py
11 passed, 2 skipped in 0.05s          ← 离线（假模型），零 token

AGENTLOOP_LIVE=1 ... test_agentloop.py
13 passed in 29.98s                   ← 含 2 条真实模型用例
```

用例分布（验收要求的"正常 / 异常 / 边界 + 3 条真实"）：

| 类别 | 用例 | 断言要点 |
|---|---|---|
| 正常 | `test_normal_one_tool_then_answer` | 1 轮工具 + 1 轮收尾，`tool_results == ["5"]` |
| 正常 | `test_two_tool_calls_in_one_step_are_both_executed` | 一步内两个调用都执行（U3 遗留的并行调用） |
| 正常 | `test_multi_step_dependency` | 后一步用到前一步结果（`["30"] → ["42"]`） |
| 异常 | `test_tool_raises_is_reported_and_loop_survives` | 工具抛异常 → 文本回填 → 循环继续并收尾 |
| 异常 | `test_unknown_tool_reported` / `test_bad_json_arguments_reported` | 未注册工具、坏 JSON 都要说清原因 |
| 异常 | `test_model_error_stops_cleanly` | 模型层异常 → `model_error`，**不产生假轨迹** |
| 边界 | `test_max_steps_exhausted` | 撞步数上限时返回 `max_steps`（不是 None 了事） |
| 边界 | `test_loop_guard_on_repeated_identical_call` | 重复同一调用 → 第 2 步止损 |
| 边界 | `test_budget_exhausted_before_next_call` | 预算闸前置：`tokens == 100` 且只跑了 1 步（**不再白花一轮**） |
| 边界 | `test_no_tools_registered_still_works` | 零工具时 `tools=None` 不崩 |
| 真实 | `test_live_dependency_chain` | 真实模型：137+245 → ×3，含 1146，工具调用 ≥2 轮 |
| 真实 | `test_live_no_hallucinated_tool` | 工具名不越界（只允许 add/multiply） |

**母本 chapter7 兼容性排查（`upstream-adapted/`，母本保持只读）**

| 版本 | 结果 | 说明 |
|---|---|---|
| 原始母本代码 + 框架 1.0.0 | `7 passed, 3 errors` | 见下方根因 |
| 打两处兼容补丁后 | **`7 passed`** | 4 个可运行测试文件全绿 |
| 剩下 2 个文件 | 仍失败：`my_plan_solve_agent` / `my_reflection_agent` **不存在** | 书里没附这两个实现文件（章节目录只有 simple / react / calculator / advanced_search） |

**根因（源码级，不是猜的）**：框架 1.0.0 的 `HelloAgentsLLM.invoke()` 返回 **`LLMResponse`（dataclass）**，而书里的代码按"它返回 str"来用：
- `Message(response, "assistant")` → `ValidationError: content Input should be a valid string`
- `re.search(..., response_text)` → `TypeError: expected string or bytes-like object`

补丁只做一件事——在两处解包 `.content`：

```python
def _text(resp):
    return resp.content if hasattr(resp, "content") else str(resp)
# ① self.add_message(Message(_text(response), "assistant"))
# ② response = _text(self.llm.invoke(messages, **kwargs))
```

（`LLMResponse.__str__` 返回 content，但 pydantic 校验和 `re` 都不走 `__str__`，所以必须显式解包。）

## 5. 结论

1. **"教材代码跑不起来"往往不是环境的错，而是 API 契约变了**：本次两行补丁 vs 一整套"环境重装/换版本"的折腾。定位手段是**看异常类型**——`ValidationError(content=LLMResponse)` 已经指明"你传了对象，它要字符串"。
2. **失败要归类**：把 `None` 换成 `stop_reason` 之后，"是模型没收尾、还是工具没返回、还是预算不够"一眼可分——这正是面试里"失败怎么排查"要的答案。
3. **预算闸必须是前置的**：第一版把判断放在收尾之后，等于每次超预算都多花一轮；补的用例（`tokens == 100` 且 1 步）把这个行为**锁进测试**，以后不会再退化。
4. **可测性是设计出来的**：`model_fn` 注入让 11 个用例 0.05 秒跑完、零 token；否则每个用例都要真调模型（2 条真实用例就花了 30 秒、约 8k token）。
