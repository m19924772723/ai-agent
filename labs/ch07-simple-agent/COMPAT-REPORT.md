# U8 证据：母本 chapter7 在框架 1.0.0 下的兼容性排查

## 一、原始状态（母本代码 + hello-agents 1.0.0 + step-3.7-flash）

```
cd D:/code/hermes/ai-agent/references/hello-agents/code/chapter7
LLM_MODEL_ID=step-3.7-flash LLM_BASE_URL=https://api.stepfun.com/v1 LLM_API_KEY=$HERMES_CUSTOM_STEPFUN_API_KEY
<python 3.11 venv> -m pytest -q --continue-on-collection-errors
```
```
7 passed, 3 warnings, 3 errors in 32.13s
ERROR test_plan_solve_agent.py
ERROR test_reflection_agent.py
ERROR test_simple_agent.py - pydantic ValidationError ...
```

## 二、三条错误分开看

| 文件 | 错误 | 根因 | 可修否 |
|---|---|---|---|
| `test_simple_agent.py` | `pydantic ValidationError: content Input should be a valid string, input_type=LLMResponse` | 1.0.0 的 `llm.invoke()` 返回 `LLMResponse`（dataclass），书里当 str 用 | ✅ 已修 |
| `test_react_agent.py`（同源第二处） | `TypeError: expected string or bytes-like object` | 同上，`re.search` 收到 `LLMResponse` | ✅ 已修 |
| `test_plan_solve_agent.py` | `ModuleNotFoundError: my_plan_solve_agent` | **书里没附该文件**（chapter7 目录只有 simple / react / calculator / advanced_search） | ❌ 无法修（缺件） |
| `test_reflection_agent.py` | `ModuleNotFoundError: my_reflection_agent` | 同上 | ❌ 无法修（缺件） |

## 三、修复方式（两处解包，最小改动）

```python
def _text(resp):
    """兼容 hello-agents 1.0.0：llm.invoke() 返回 LLMResponse，不是 str。"""
    return resp.content if hasattr(resp, "content") else str(resp)
```
- `my_simple_agent.py`：3 处 `Message(<resp>, ...)` + 3 处 `invoke(...)` 解包
- `my_react_agent.py`：2 处 `Message(<resp>, ...)` + 1 处 `invoke(...)` 解包

## 四、修复后

```
<python 3.11 venv> -m pytest -q --continue-on-collection-errors \
    test_simple_agent.py test_react_agent.py test_my_calculator.py test_advanced_search.py
```
```
7 passed, 4 warnings in 107.20s (0:01:47)
```

> 注：`test_plan_solve_agent.py` / `test_reflection_agent.py` 仍未通过——**因为那两个实现文件在教材里就不存在**，属已知缺件，不是环境或版本问题。
> 这两行补丁同时说明：`LLMResponse.__str__` 虽然返回 content，但 pydantic 校验与 `re` 都不会走 `__str__`，所以必须显式解包。

## 五、母本未被改动

母本目录 `git status --porcelain` = **0 改动**；改动只发生在 lab 的副本 `labs/ch07-simple-agent/upstream-adapted/`。
