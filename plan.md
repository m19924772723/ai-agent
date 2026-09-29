# AI Agent 每日学习与实践计划（plan.md）

> 依据：本地母本 `D:\code\hermes\ai-agent\references\hello-agents`（Datawhale《从零开始构建智能体》：16 章正文 + 每章可运行代码 + 14 篇 Extra）
> 编号：**本文档自有单元编号 U1、U2…**（U1 = 2026-09-29），不沿用任何其他目录的编号
> 节奏：一天一个单元（45–90 分钟），逐日表只保留**未来 2 周**，后面阶段按周给主题
> 边界：本目录自成一个学习线，**不与其他工作区交叉链接**；一切产出（笔记 / 实验 / 成果）都写在 `D:\code\hermes\ai-agent` 内
> **单元进度**：U1 ✅、U2 ✅（都在 2026-09-29 完成）｜下一个：U3（10-01，工具调用闭环）

## 0. 怎么用这份计划

1. **一天一个单元**，单元固定四步：定向读（10 min）→ 动手（25–35 min）→ 写笔记（10 min）→ 打卡（5 min）。
2. **验收列必须是能勾的动作**（跑通、输出对比、默写、讲 2 分钟），禁止「理解/掌握」这类空词。
3. **完成一个单元后**：`notes/YYYY-MM-DD.md` 记一条 → `progress.md` 章节打勾 → `tech-stack.md` 台账加一行 → 有成品就归档 `results/YYYY-MM-DD/<成果名>/`。
4. **被挤掉的单元不顺延堆积**：当周剩余单元里挑最重要的做，其余标「跳过」并写原因。
5. 本计划是「学 + 做」一对一：**每个单元必须落到 `labs/` 里一个能跑的东西**，只读不跑不算完成。

## 1. 阶段总览

| 阶段 | 单元区间 | 日期 | 学什么（母本） | 阶段产出（可归档） |
|---|---|---|---|---|
| **阶段1 地基与范式** | U1–U8 | 09-29 ~ 10-06 | 第 1、3、4、7 章 + `code/chapter1`、`chapter4`、`chapter7` | 4 个 labs 实验 + 1 份范式对比表 |
| **阶段2 评测与观测** | U9 起 | 10-07 ~ 10-20 | 第 12 章 + 第 6、7 章余下 | LLM-judge 对比 + 观测面板 + 框架对比表 |
| **阶段3 检索增强** | 每周 1 主题 | 10-21 ~ 11-17 | **第 8 章全章**（`code/chapter8` 01–11） | RAG 管线实验 + ragas 评测报告（召回/忠实度/相关性） |
| **阶段4 编排与协议** | 每周 1 主题 | 11-18 ~ 12-15 | 第 4、7 章深挖 + 第 9、6、14、10 章 | 自写 Agent Loop + 上下文工程 + deepresearch 跑通 + 自建 MCP server |
| **阶段5 交付与安全** | 每周 1 主题 | 12-16 ~ 01-26 | 第 12 章 02–09 + 第 13、5 章 + 安全组 | benchmark 子集结果 + 容器化 + 低代码三平台 demo + OWASP 笔记 |

> 低代码平台（第 5 章 Coze / Dify / n8n）和 Extra11 浏览器 Agent 是**穿插单元**，安排在假期或周末，不占工作日的动手时间。

> **依赖提醒（做 lab 前先看）**：第 1、4 章的代码是独立的（只需要 `openai` + `python-dotenv`）；**第 7、8、9、12 章的代码都 import `hello_agents`**，必须在 lab 的 venv 里装框架：
> ```bash
> uv pip install --python .venv/Scripts/python.exe hello-agents          # PyPI 最新 1.0.0，要求 Python ≥3.10
> ```
> 书里第 12 章 README 写的是 `hello-agents[evaluation]==0.2.3`（带评测工具的老版本）。**先装最新版跑**，如果示例报 API 不兼容，再退回书里钉的版本并在笔记里记一笔差异——这本身就是「框架演进」的一手素材。

## 2. 阶段1 逐日单元（09-29 ~ 10-06，8 天）

| 单元 | 学什么（出处） | 动手做什么 | 验收标准（勾掉才算完成） | 产出位置 | 依赖/时长 |
|---|---|---|---|---|---|
| **U1 · 09-29 二**（✅ 已完成）<br>端点与环境打通 | `Extra-Chapter/Extra07-环境配置.md` + `code/chapter4/.env.example`、`llm_client.py` | 建 `labs/ch04-llm-client/`，`uv venv` + 装 openai/dotenv，跑通**流式**调用并采集 TTFT / token / 吞吐 | ① 终端有流式输出；② 打印耗时与 token；③ 笔记贴真实输出片段 | `labs/ch04-llm-client/` + `notes/2026-09-29.md` | 60 min（实际约 75） |
| **U2 · 09-30 三**（✅ 09-29 提前完成）<br>Agent 与工作流的边界 | 第 1 章《初识智能体》中文正文（选读核心节） | 写 300 字「一个自动化任务为什么用工作流而不是 Agent」，并列出 3 个「加 Agent 反而更差」的点 | ① 不看稿能讲 2 分钟；② 3 个点都能对应具体场景；③ 能说出什么条件下才值得上 Agent | `notes/2026-09-29.md`（U2 单元） | 45 min |
| **U3 · 10-01 四**<br>工具调用闭环 | `code/chapter1/FirstAgentTest.py` | 复制成 `labs/ch01-toolcall/`，把外部搜索工具换成**自己写的**时间/计算工具，跑通多轮工具调用 | ① 模型连续 ≥2 轮调用自写工具并给出最终答案；② 笔记贴出 tool_call 原始 JSON；③ 无外部付费 API 依赖 | `labs/ch01-toolcall/` | stepfun 端点；75 min |
| **U4 · 10-02 五**<br>采样参数与结构化输出 | 第 3 章「采样参数」节 | 用 pydantic 定义 schema；**故意**把 `max_tokens` 调小复现「JSON 断句」，再给足 token 修好，两次输出对比 | ① 两段真实输出并排对比；② 记录 `finish_reason`；③ 能解释推理 token 与输出 token 共用一个预算 | `labs/ch03-sampling/` + `notes/` | 60 min |
| **U5 · 10-03 六**<br>手写 ReAct | 第 4 章经典范式 + `code/chapter4/ReAct.py`、`tools.py` | **不抄示例**，手写 20–40 行 ReAct 循环（思考→行动→观察），跑通一个需要 ≥2 步的任务 | ① 运行日志能看到 ≥2 轮 思考/行动/观察；② 能讲清它与「一次提示词输出 JSON」的区别 | `labs/ch04-react-min/` | U3、U4；90 min |
| **U6 · 10-04 日**<br>范式对比 + **周复盘** | `code/chapter4/Reflection.py`、`Plan_and_solve.py` | 各跑一遍（换成自己的小任务），做对比表：适用场景/成本/失败模式 | ① 对比表每格都有具体例子（不是形容词）；② 本周 `results/` 归档；③ 周日复盘写完 | `results/2026-10-04/范式对比/` | 90 min |
| **U7 · 10-05 一**<br>框架帮我做了什么 | 第 7 章正文前半 + `code/chapter7/my_simple_agent.py` | 先在 venv 里装 `hello-agents` 框架，跑通 `my_simple_agent.py`，画出 Agent / LLM / Tool / Memory 四者关系的类图 | ① 有一张类图（手画拍照也算）；② 能讲清「框架帮我做了什么」的 3 条；③ 笔记记下框架版本号 | `labs/ch07-simple-agent/` | 需装 hello-agents；75 min |
| **U8 · 10-06 二**<br>Agent 循环 + 测试 | 第 7 章 `my_react_agent.py` + `test_*.py` 写法 | 跑通 chapter7 的 pytest，给自己的 lab 补 3 个用例（正常/异常/边界） | ① pytest 全绿并贴输出；② 阶段1 复盘写进 notes；③ 台账里阶段1 的验收动作全部勾掉 | `notes/2026-10-06.md` + `results/2026-10-06/阶段1复盘/` | 75 min |

> **国庆假期提醒**：10-01~10-07 若出行，把 U3–U6 的**动手**单元整体挪到 10-08 之后；读的部分在路上做（本地 md 离线可读）。

## 3. 阶段2 评测与观测（10-07 ~ 10-20）

| 单元 | 学什么 | 动手做什么 → 验收 | 时长 |
|---|---|---|---|
| U9 ~ U10 | 第 12 章《智能体性能评估》正文 + `code/chapter12/01_basic_agent_example.py` | 建一份 20 条的小评测集，写 **LLM-as-judge** 打分脚本，与规则匹配器对比一致性 → 输出对比表（谁更严、差在哪 3 例） | 2×60 min |
| U11 ~ U12 | Langfuse 官方文档快速上手 | 把 lab 的调用接入观测面板（云版免费额度）→ 面板里能看到 ≥5 次调用的输入/输出/耗时/成本 | 2×45 min |
| U13 ~ U14 | promptfoo 文档 | 对同一提示词的两版做一次 A/B → 产出对比报告（谁赢、差多少、样本量多少） | 2×60 min |
| U15 ~ U17 | 第 7 章后半 + `my_advanced_search.py`、`my_calculator_tool.py` | 把自己的 3 个工具注册进 chapter7 的框架跑通 → 日志证明工具被正确选择 | 3×45 min |
| U18 ~ U20 | 第 6 章《框架开发实践》+ `code/chapter6/`（AgentScope / AutoGen / CAMEL） | 各跑 1 个 demo，做 3 行对比表（适用场景/上手难度/依赖体积） | 3×60 min |
| U21 ~ U22 | — | 阶段2 收口：补漏、`results/` 归档、台账打勾、写 2 周复盘 | 2×45 min |

## 4. 阶段3 检索增强 · 第 8 章为主线（10-21 ~ 11-17）

| 周 | 日期 | 学什么（`code/chapter8/`） | 本周产出（可归档） |
|---|---|---|---|
| 第 1 周 | 10-21 ~ 10-27 | `01_MemoryTool_Basic_Operations`、`02_MemoryTool_Architecture`、`03_WorkingMemory_Implementation` | `labs/ch08-memory/`：记忆写入/读取/合并各 1 次真实运行日志 |
| 第 2 周 | 10-28 ~ 11-03 | `04_RAGTool_MarkItDown_Pipeline`、`05_RAGTool_Advanced_Search`、`06_Memory_Consolidation_Demo` | 用**自己的一份** PDF/URL 走完 解析→分块→检索，输出 3 种分块参数对比表 |
| 第 3 周 | 11-04 ~ 11-10 | `07_RAGTool_Intelligent_QA`、`08_Agent_Tool_Integration`、`10_RAG_Pipeline_Complete`、`11_Q&A_Assistant` | 跑通完整 RAG 管线并换成自己的语料，回答 5 个预置问题（对/错都记录） |
| 第 4 周 | 11-11 ~ 11-17 | `09_Memory_Types_Deep_Dive` + ragas 文档 | **ragas 评测**：召回率 / 忠实度 / 相关性三指标 + ≥3 组参数前后对比 |
| 缓冲 | 11-16 ~ 11-17 | — | 补漏 + `results/` 归档 + 阶段复盘 |

## 5. 阶段4 编排与协议（11-18 ~ 12-15）

| 周 | 日期 | 学什么 | 本周产出 |
|---|---|---|---|
| 第 1 周 | 11-18 ~ 11-24 | 第 4 章范式复习 + 第 7 章框架 | 自写 Agent Loop：工具注册 + 预算控制 + 终止条件，`labs/ch07-agent-loop/` |
| 第 2 周 | 11-25 ~ 12-01 | 第 9 章《上下文工程》`code/chapter9/01–06` | context builder（系统+记忆+检索+工具，含 token 预算计算）+ 跑通三日工作流 |
| 第 3 周 | 12-02 ~ 12-08 | 第 6 章 LangGraph + **第 14 章 `code/chapter14/helloagents-deepresearch`** | LangGraph 重写一个 agent；deepresearch 后端+前端本地跑通，生成 1 份研究报告 |
| 第 4 周 | 12-09 ~ 12-15 | 第 10 章《智能体通信协议》`code/chapter10/01–05`、`weather-mcp-server/` + Extra11 浏览器 Agent 起步 | 自建 MCP server 并被 Agent 成功调用（贴调用日志）；浏览器 Agent 完成 1 个网页动作 |
| 缓冲 | 12-14 ~ 12-15 | — | 阶段收口：架构图 + 评测数字 + 复盘归档 |

## 6. 阶段5 交付与安全（12-16 ~ 01-26）

| 阶段 | 日期 | 学什么 | 产出 |
|---|---|---|---|
| 评测与数据 | 12-16 ~ 12-22 | 第 12 章 `02_bfcl_quick_start`、`03`、`05_gaia_quick_start`、`08_data_generation_llm_judge`、`09_win_rate` | 1 个 benchmark 子集结果 + 自建 20 条评测数据（LLM-judge 打分） |
| 包装上线 | 12-23 ~ 01-12 | 第 13 章 `helloagents-trip-planner`（FastAPI+Vue 结构）+ Docker + 安全组 + **第 5 章低代码三平台** | 端到端跑通 + 容器化成功 + Coze/Dify/n8n 各 1 个 demo + OWASP 10 条笔记 |
| 缓冲补漏 | 01-13 ~ 01-26 | `Extra-Chapter/Extra01-面试问题总结.md` + `Extra01-参考答案.md` | Agent 方向面试问答清单（每题配自己的实验例子） |

## 7. 每天固定动作（贴在 `notes/` 里就够）

```text
① 10 min  定向读：rg -n "关键词" /d/code/hermes/ai-agent/references/hello-agents/docs/chapter*/   → 只看今天要用的那一段
② 25-35 min 动手：在 labs/<实验名>/ 里跑，改，再跑；粘贴真实输出
③ 10 min  写笔记：notes/YYYY-MM-DD.md 四块（概念/输出/面试话术/落点）
④ 5 min   打卡：progress.md 打勾 · tech-stack.md 台账加一行 · 有成品 → results/
```

**每周日额外 15 分钟**：复盘本周单元完成率 → 把下周 7 天单元补进本文件第 2/3 节 → `results/` 归档。

## 8. 调整与止损规则（触发就照做，不留情）

| 情况 | 动作 |
|---|---|
| 连续 2 天没做 | **不补**。当周剩下的单元里挑最重要 1 个做，其余标「跳过」并写原因 |
| 单个单元卡住 >1 小时 | 记进踩坑日志，标「跳过」，周日复盘再决定是否重排 |
| 其他事情吃紧 | 本计划降级为「每周 3 个单元」，但 `progress.md` 不许长期空白 |
| 第 3 / 11 章数学推导看不懂 | 只读到「能解释现象」为止，标注「了解级」，不追推导 |
| 每 4 周检查 | 若台账超过 2 周没有新增行 → 说明计划定太满，砍条目 |

## 9. 维护规则

- 逐日表只保留**未来 2 周**，过期单元改成 `✅ 完成 / ⏭ 跳过` 并留一行结果（链接到 notes）；
- 章节内容、代码清单变化时，以母本 `D:\code\hermes\ai-agent\references\hello-agents` 实际文件为准再改本文件；
- 本文件与 `progress.md`（章节打卡）、`tech-stack.md`（技术验收 + 台账）、`results/`（成果归档）四者联动，改一处要同步另三处；
- 教材更新：`cd /d/code/hermes/ai-agent/references/hello-agents && git pull --depth 1 origin main` 后核对章节号是否变动。

*建立 2026-09-29｜下次滚动更新：2026-10-06（阶段1 复盘时）*
