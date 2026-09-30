# labs/ch01-toolcall —— 自写工具 + 多轮工具调用闭环（U3 单元）

## 1. 出处

- 母本：`references/hello-agents/code/chapter1/FirstAgentTest.py`（第 1 章 1.3「5 分钟实现第一个智能体」）
- 母本用的是**提示词约定 `Thought/Action` 格式 + 自己写正则解析**，工具依赖 wttr.in（天气）和 Tavily（搜索）两个外部接口。

## 2. 改了什么 / 为什么

| 项 | 母本 | 这里 | 为什么这么改 |
|---|---|---|---|
| 工具 | `get_weather`（wttr.in）+ `get_attraction`（Tavily，要 API key） | `get_current_time` / `hours_until` / `calculate`（**全自写、零外部依赖**） | U3 验收要求「无外部付费 API 依赖」；本地工具结果可复现，不会被限流干扰 |
| 调用契约 | 只有一条路：提示词 + 正则 | **两条路各跑一遍**：`mode=native`（OpenAI 原生 function calling）+ `mode=prompt`（母本那条路） | 「工具调用契约靠什么保证」是本章最值得量化的点：靠框架的 schema，还是靠模型自觉守格式 |
| 轮数控制 | `for i in range(5)` 硬编码 | `MAX_ROUNDS=6` + 每轮记录 `tool_calls` 原始 JSON | 要把「多轮」变成可核对的证据（每轮调了谁、参数是什么） |
| 任务 | 查天气 → 推荐景点 | 查时间 → 算间隔 → 乘 7（**后一步依赖前一步结果**） | 故意让依赖串起来，否则模型可能一轮就把三件事都"猜"完，测不出多轮闭环 |

## 3. 怎么跑

```bash
cd D:/code/hermes/ai-agent/labs/ch01-toolcall
uv venv .venv --python 3.11
uv pip install --python .venv/Scripts/python.exe openai python-dotenv
export PYTHONIOENCODING=utf-8
.venv/Scripts/python.exe run_tools.py            # 两种模式都跑
.venv/Scripts/python.exe run_tools.py native     # 只跑原生 function calling
```

密钥不落地：按 `LLM_API_KEY` → `HERMES_CUSTOM_STEPFUN_API_KEY` → `HERMES_CUSTOM_DEEPSEEK_API_KEY` 取。

## 4. 真实输出（2026-09-30 实测，step-3.7-flash）

任务：① 现在北京时间 ② 到 2026-10-07 00:00 还有多少小时 ③ 该小时数 ×7

```
[原生 function calling] 轮数 4｜工具调用 3 次｜8.16 s｜2489 token｜解析失败 0
  第1轮 raw={"id": "chatcmpl-tool-96ea0b8dedfcfa15", "type": "function",
             "function": {"name": "get_current_time", "arguments": "{}"}}
  第2轮 raw={"id": "chatcmpl-tool-9852275a239fe0b1", "type": "function",
             "function": {"name": "hours_until", "arguments": "{\"target\": \"2026-10-07 00:00\"}"}}
  第3轮 raw={"id": "chatcmpl-tool-bf0cf01328cb3ffd", "type": "function",
             "function": {"name": "calculate", "arguments": "{\"expression\": \"156.85 * 7\"}"}}
  最终答案：① 2026-09-30 11:09 ② 156.85 小时 ③ 1097.95 小时

[母本风格 提示词+正则] 轮数 4｜工具调用 3 次｜11.29 s｜3051 token｜解析失败 0
  第1轮 raw_text=Action: get_current_time()
  第2轮 raw_text=Action: hours_until(target="2026-10-07 00:00")
  第3轮 raw_text=Action: calculate(expression="156.85 * 7")
  最终答案：① 2026-09-30 11:09 ② 156.85 小时 ③ 156.85 × 7 = 1097.95
```

（逐轮原始记录与完整答案：`out/run.json`）

**四条结论**

1. **多轮闭环成立且真的是"依赖链"**：时间 → 间隔 → 乘法三次调用顺序依赖，参数里带着上一步的结果（`156.85 * 7`），说明模型不是背答案，而是拿工具返回值往下算。
2. **原生 function calling 更省更稳**：同样 3 次调用、同样正确答案，native 用 2489 token / 8.16 s，母本风格用 3051 token / 11.29 s（**-18% token、-28% 延迟**）；native 的调用是结构化的 `{id, name, arguments(JSON 字符串)}`，可以直接程序化校验，母本风格的 `Action: hours_until(target="...")` 只能靠正则硬解。
3. **契约的"脆弱点"在哪**：正则那条路这次没失败（解析失败 0/4），但它的成立前提是**模型每次都乖乖写引号和括号**——一旦写成 `target=2026-10-07 00:00`（无引号）或换行，我的 `re` 就漏参。native 则把参数放在 JSON 字符串里，解析交给 SDK。**所以生产上用原生工具调用，提示词解析只当兜底。**
4. **成本随轮数线性上涨**：3 次工具调用就烧掉 2489 token，因为每一轮都要把历史（含工具返回）重发一遍。这是 Agent 成本曲线的起点——呼应 U1 的 token 预算与 U2 的成本意识。

> 补充：`calculate` 用 `ast` 白名单做安全求值（只允许数字与运算符），比母本示例里"直接拼提示词让模型算"更可靠：算术交给代码，模型只负责决定**算哪个式子**。
