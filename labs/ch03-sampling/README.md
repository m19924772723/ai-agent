# labs/ch03-sampling —— 采样参数与结构化输出（U4 单元）

## 1. 出处

- 母本：`references/hello-agents/docs/chapter3/第三章 大语言模型基础.md` 的 **3.2.1 提示工程 →（1）模型采样参数**（Temperature / Top-k / Top-p 的原理与适用区间）与（4）上下文示例里的 JSON 输出约束。
- 本实验把「采样参数怎么影响结构化抽取」变成可复现数据，并顺手验证端点对 `response_format=json_object` 的支持。

## 2. 改了什么 / 为什么

| 项 | 母本 | 这里 | 为什么 |
|---|---|---|---|
| 任务 | 情感分类 / 翻译示例 | **长文 → 结构化 JSON**（title / key_points / tags / todos），用 **pydantic** 定义 schema 并强校验 | 与真实产品里的抽取任务同构；pydantic 让"格式对不对"变成可判定的布尔值 |
| 参数实验 | 只讲原理区间 | **5 组对照**：小预算(64)/足额(8192)/高温(1.2)/流式+小预算/json_object | U4 的验收要求"故意调小复现断句"+记录 `finish_reason` |
| 推理 token | 未涉及 | 对比 `completion_tokens` 与**可见输出字符数** | 解释"推理 token 与输出 token 共用一个预算" |
| 遗留问题 | — | 顺带验证流式响应能否拿到 `finish_reason`（U1 未解决项） | 生产上要靠它做截断判断 |

## 3. 怎么跑

```bash
cd D:/code/hermes/ai-agent/labs/ch03-sampling
uv venv .venv --python 3.11
uv pip install --python .venv/Scripts/python.exe openai python-dotenv pydantic
export PYTHONIOENCODING=utf-8
.venv/Scripts/python.exe run_sampling.py     # 5 组，约 35 s
cat out/sampling.json                        # 每组完整记录
```

## 4. 真实输出（2026-10-01 实测，step-3.7-flash，输入文章 216 字 / prompt 245 token）

| run | 配置 | finish_reason | pydantic | completion tokens | 可见输出 | 耗时 |
|---|---|---|---|---|---|---|
| run1 | max_tokens=64, temp=0 | **length** | ❌ `Invalid JSON: EOF while parsing a value at line 1 column 0` | 64 | **0 字符** | 4.04 s |
| run2 | max_tokens=8192, temp=0 | stop | ✅ | 1423 | 329 字符 | 9.84 s |
| run3 | max_tokens=8192, temp=1.2 | stop | ✅（但内容漂） | 1646 | 338 字符 | 10.82 s |
| run4 | max_tokens=64, temp=0, **流式** | **length**（拿到了） | ❌ 同上 | 64 | **0 字符** | 1.84 s |
| run5 | max_tokens=8192, temp=0, `response_format=json_object` | stop | ✅ | **905** | 263 字符 | 9.38 s |

**run2 vs run3（同为足额预算，只差温度）**

| 字段 | run2（temp=0） | run3（temp=1.2） |
|---|---|---|
| title | 2026年9月内部知识库问答升级落地 | 团队推动内部知识库问答从能用升级至敢用 |
| tags | 内部知识库 / 问答系统优化 / 检索升级 / 用户体验提升（4 个） | 内部知识库 / 混合检索 / 问答系统优化（3 个） |
| todos[3] | 解决知识库人工维护不足导致的答案噪音问题 | 建立知识库内容更新维护机制，避免无人维护文档成为答案噪音 |

**五条结论**

1. **`max_tokens` 是"推理 + 输出"的总预算，不是输出上限**：给 64 时，64 个 token 全被推理吃掉，客户端拿到的是**空字符串**（不是半句 JSON），`finish_reason=length`。这就是"模型返回空内容"的真因——不是模型不听话，是预算不够它先想完。
2. **`finish_reason` 是显式的截断信号，且流式也能拿到**（run4 在最后一个 chunk 的 `choices[0].finish_reason` 里就是 `length`）→ **U1 的遗留问题（流式下拿不到 finish_reason）关闭**。生产里必须把它当错误分支，而不是靠"JSON 解析失败"去反推。
3. **温度影响的是内容稳定性，不是格式合法性**：temp=1.2 时 pydantic 依然通过，但标题、标签数量（4→3）、待办措辞全变 → **结构化输出 ≠ 可复现输出**。评测、抽取、数据入库这类任务必须低温；温度留给创意类。
4. **`response_format={"type":"json_object"}` 这个端点支持，而且省 token**：run5 用 905 token 完成同一任务，比 run2 的 1423 少 **36%**，输出也更短（263 vs 329 字符）——约束解码让模型少"啰嗦"。结构化抽取应默认开它。
5. **推理 token 是大头**：run2 的 1423 completion token 里，可见输出只占约 250 token，**其余 ~82% 都是没下发的推理**。这直接解释了 U1 里"TTFT ≈ 总耗时"和"3 次工具调用烧 2489 token"——预算要按"推理 + 输出"估。
