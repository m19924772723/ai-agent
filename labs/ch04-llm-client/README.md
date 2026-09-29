# labs/ch04-llm-client —— 跑通 OpenAI 兼容端点的流式调用（U1 单元）

## 1. 出处

- 母本：`D:\code\hermes\ai-agent\references\hello-agents\code\chapter4\llm_client.py`（`main@8c57a6c`）+ 同目录 `.env.example`
- 第 4 章 4.1 节的 `HelloAgentsLLM.think()`：流式调用 OpenAI 兼容接口的最小实现

## 2. 改了什么 / 为什么

| 母本写法 | 这里 | 为什么 |
|---|---|---|
| 只打印流式内容 | 采集**逐 chunk 到达时间线** | 「流式到底流了没有」不能靠感觉——要看 TTFT、delta 片段数、最大间隔 |
| 不记录用量 | 采集 `usage`（prompt/completion/total）并落 `out/usage.json` | 面试要数字；下次调优要有基线 |
| 单一端点 | preset 循环：stepfun + deepseek 两家 | 一次实验拿到横向对比，顺便验证「换端点不改业务代码」 |
| 流式失败就报错 | `stream_options` 不被支持时自动退回、再退一次非流式取用量 | 网关实现差异很大，实验脚本要能自己降级 |

## 3. 怎么跑

```bash
cd D:/code/hermes/ai-agent/labs/ch04-llm-client
uv venv .venv --python 3.11            # 已是 D 盘解释器：D:\code\environment\uv\python
uv pip install --python .venv/Scripts/python.exe openai python-dotenv
export PYTHONIOENCODING=utf-8
.venv/Scripts/python.exe run_stream.py            # 两家都跑
.venv/Scripts/python.exe run_stream.py stepfun    # 只跑一家
```

密钥不必写进文件：脚本按 `LLM_API_KEY` → `HERMES_CUSTOM_STEPFUN_API_KEY` 顺序取（Hermes 终端已注入）。

## 4. 真实输出（2026-09-29 实测）

| 端点 / 模型 | TTFT | 总耗时 | 输出 | delta 片段 | prompt tk | completion tk | 吞吐 |
|---|---|---|---|---|---|---|---|
| stepfun / `step-3.7-flash` | 5.387 s | 5.454 s | 68 字 | 11 | 43 | 280 | 51.3 tok/s |
| deepseek / `deepseek-flash` | 2.804 s | 2.911 s | 46 字 | 31 | 56 | 97 | 33.3 tok/s |

（完整 JSON 证据：`out/usage.json`；两次运行的原始记录都在里面）

**三个结论**

1. **TTFT ≈ 总耗时**（5.39 vs 5.45 / 2.80 vs 2.91）：可见 token 几乎是在最后一段批量到达的，说明对**推理模型**来说，流式省不下"首字之前的推理时间"——它救的是长答案的后续等待。
2. **completion_tokens 远大于可见输出**：stepfun 68 个汉字 ≈ 45–70 token，实测记账 280 —— 差额是**没下发给客户端的推理 token**；deepseek 同理（46 字 / 97 tk）。这正是 L1 出现"JSON 断在半句"的根因：**推理 token 与输出 token 共用同一个预算**。
3. **两家延迟差一倍**（5.4 s vs 2.9 s），换端点不用改一行业务代码——只要 base_url/model/key 走配置。

**初始疑惑与排查过程**：第一版脚本打印出「TTFT 5.14 s / 总耗时 5.14 s」，怀疑是脚本把 TTFT 记错（记成了最后一个 delta）。加逐 chunk 时间线后确认不是 bug：`delta_count=11`、最大间隔 58 ms，是**响应确实后段批量到达**，脚本只是如实记录。
