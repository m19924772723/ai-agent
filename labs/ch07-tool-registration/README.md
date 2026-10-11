# labs/ch07-tool-registration —— 把我的 3 个工具注册进框架（U15 单元）

## 1. 出处与目标

- 母本：第 7 章后半 `my_advanced_search.py`（多源搜索工具，依赖 Tavily/SerpAPI 密钥——我们不装）、`my_calculator_tool.py`（ToolRegistry 注册函数）
- 验收：**自己的 3 个工具**注册进 hello-agents 框架跑通 → 日志证明工具被正确选择
- 我的工具 = U3 的三件套（`labs/ch01-toolcall/run_tools.py`，零外部依赖）：
  `get_current_time`（零参）· `calculate`（1 参）· `hours_until`（1 参）

## 2. 任务设计

一次提问必须**依次调用全部 3 个工具**，缺一个都答不全：
> "现在几点？帮我算一下 (137+85)*12 等于几？再告诉我距离 2026-11-01 00:00 还有多少小时？"

## 3. 怎么跑

```bash
cd D:/code/hermes/ai-agent/labs/ch07-tool-registration
uv venv .venv --python 3.11
uv pip install --python .venv/Scripts/python.exe hello-agents python-dotenv
export LLM_API_KEY=$HERMES_CUSTOM_STEPFUN_API_KEY PYTHONIOENCODING=utf-8
.venv/Scripts/python.exe register_my_tools.py
# 证据 → out/my_tools_run.json；框架 trace → memory/traces/*.jsonl
```

## 4. 实测结果（2026-10-11，step-3.7-flash，temp=0）

```
回答（12.69 s）：
现在是 **2026年10月11日 13:26:32**（北京时间）。
**(137+85)×12 = 2664**
距离 **2026-11-01 00:00** 还有约 **490.56 小时**。
```

**trace 工具调用证据（框架 memory/traces/ 提取）：**

| step | 工具 | 参数 | 结果 | 成功 |
|---|---|---|---|---|
| 1 | get_current_time | {"input": "现在几点"} | 2026-10-11 13:26:32 (UTC+08) | ✅ |
| 1 | calculate | {"input": "(137+85)*12"} | (137+85)*12 = 2664 | ✅ |
| 1 | hours_until | {"input": "2026-11-01 00:00"} | 距今 490.56 小时 | ✅ |

模型在**同一轮（step1）并行发起 3 个 tool_call**，框架逐个执行并回填，step2 汇总成最终答案。
**期望核对**：2664 ✓；工具全部成功 = True ✓。

## 5. U15 踩坑（比结果更值钱）

1. **框架 1.0.0 零参函数兼容问题**（与 U8 的 LLMResponse 同源：框架 API 与"常规用法"有缝隙）：
   `ToolRegistry.execute_tool()` 对函数工具是 `func(input_text)` **位置式传参**——零参函数必炸
   `takes 0 positional arguments but 1 was given`。
   → 修复：`tool_adapter()` 按 `inspect.signature` 自适应——0 参函数丢弃框架硬塞的参数。
2. **"答案对、工具错"的隐性失败**：第一版运行时 get_current_time 实际失败，但最终答案里的时间
   是从 `hours_until` 成功返回里的"现在 13:15"**间接凑出来的**——光看最终答案根本发现不了。
   → 教训：接入框架必须逐工具核对执行结果，不能只看 agent 回答。
3. **证据要从 trace 拿**：`agent.get_history()` 只保留 user/assistant 最终对话，工具调用中间过程
   在框架自带的 `memory/traces/*.jsonl`（事件字段是 `event` 不是 `type`；写盘有缓冲，读前 sleep 0.5s）。

## 6. 结论

- 自己的工具进框架：**注册两条路都通**（register_function 用于函数、register_tool 用于类实例），
  框架自动把工具描述拼进 system prompt（首轮 1614 prompt token）
- 我的三件套从"裸 SDK 手动循环"（U3）升级到"框架托管循环"（U15），同一批工具两套玩法都验证过
- 框架自动带 4 个内置工具（Skill/Task/TodoWrite/DevLog）+ 熔断器（连续失败自动禁用工具）
