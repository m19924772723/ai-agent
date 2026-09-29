# AI Agent 每日学习与实践计划（plan.md）

> 依据：本地母本 `D:\code\hello-agents`（Datawhale《从零开始构建智能体》，16 章正文 + 每章可运行代码 + 14 篇 Extra）
> 对齐：`D:\code\hermes\ai_pm\README.md` 的 W1–W18 进度看板（周次按**周三～周二**）
> 起点：2026-09-29（**本计划单元编号 U1、U2…**，不用 Day 编号——`ai_pm` 的 Day 1–6（09-23~09-28）属于「启动包 + L1 首轮」那条线，本计划从 09-29 起接，U1 = 09-29）｜滚动更新，**逐日表只写未来 2 周**，后面阶段按周给主题

## 0. 怎么用这份计划

1. **一天一个单元**，单元固定四步：定向读（10 min）→ 动手（25–35 min）→ 写笔记（10 min）→ 打卡（5 min）。
2. **验收列必须是能勾的动作**（跑通、输出对比、默写、讲 2 分钟），禁止「理解/掌握」这类空词。
3. **完成一个单元后**：`notes/YYYY-MM-DD.md` 记一条 → `progress.md` 章节打勾 → `tech-stack.md` 勾验收动作 → 有成品就归档 `results/YYYY-MM-DD/<成果名>/`。
4. **优先级**：`ai_pm` 主线项目任务 > 本计划单元。被挤掉的单元**不顺延堆积**，在周日复盘里合并或砍掉。
5. 本计划是「学 + 做」一对一：**每个单元必须落到 `labs/` 里一个能跑的东西**，只读不跑不算完成。

## 1. 时间轴总览（与 ai_pm 主线并行）

| 阶段 | 周次 | 日期 | ai_pm 主线 | 本计划学什么 | 阶段产出（可归档） |
|---|---|---|---|---|---|
| **阶段0 地基与范式** | W1–W2 | 09-23 ~ 10-06 | 启动包 + L1 首轮 | 第 1、3、4、7 章 + `code/chapter1`、`chapter4`、`chapter7` | 4 个 labs 实验 + 1 份范式对比表 |
| **L1 期：评测与观测** | W3–W4 | 10-07 ~ 10-20 | L1 三模板 + 导出 | 第 12 章 + 第 6、7 章余下 | L1 的 LLM-judge 对比 + langfuse 面板 + 框架对比表 |
| **L2 期：检索增强** | W5–W8 | 10-21 ~ 11-17 | L2 知识库问答 | **第 8 章全章**（`code/chapter8` 01–11） | RAG 管线实验 + ragas 评测报告（L2 作品的数字） |
| **L3 期：Agent 编排** | W9–W12 | 11-18 ~ 12-15 | L3 深度研究/浏览器 Agent | 第 4、7 章深挖 + 第 9、6、14、10 章 | 自写 Agent Loop + 上下文工程 + deepresearch 跑通 + 自建 MCP server |
| **评测与数据** | W13 | 12-16 ~ 12-22 | 评测集与复盘 | 第 12 章 02–09（BFCL / GAIA / LLM-judge / win-rate） | 1 个 benchmark 子集结果 + 自建 20 条评测数据 |
| **包装上线** | W14–W16 | 12-23 ~ 01-12 | 上线与作品集 | 第 13 章 + 第 5 章 + I 组安全 | Docker 化 + 端到端跑通 + 低代码三平台 demo |
| **缓冲补漏** | W17–W18 | 01-13 ~ 01-26 | 复盘与投递 | Extra01 面试题 + 未完成回补 | 面试问答清单（Agent 方向） |

> 低代码平台（第 5 章 Coze / Dify / n8n）和 Extra11 浏览器 Agent 是**穿插单元**，安排在假期或周末，不占工作日的动手时间。

> **依赖提醒（做 lab 前先看）**：第 1、4 章的代码是独立的（只需要 `openai` + `python-dotenv`）；**第 7、8、9、12 章的代码都 import `hello_agents`**，必须在 lab 的 venv 里装框架：
> ```bash
> uv pip install --python .venv/Scripts/python.exe hello-agents          # PyPI 最新 1.0.0，要求 Python ≥3.10
> ```
> 书里第 12 章 README 写的是 `hello-agents[evaluation]==0.2.3`（带评测工具的老版本）。**先装最新版跑**，如果示例报 API 不兼容，再退回书里钉的版本并在笔记里记一笔差异——这本身就是「框架演进」的一手素材。

## 2. 阶段0 逐日单元（09-29 ~ 10-06，8 天）

| 单元 | 学什么（出处） | 动手做什么 | 验收标准（勾掉才算完成） | 产出位置 | 依赖/时长 |
|---|---|---|---|---|---|
| **U1 · 09-29 二**<br>端点与环境打通 | `Extra-Chapter/Extra07-环境配置.md` + `code/chapter4/.env.example`、`llm_client.py` | 建 `labs/ch04-llm-client/`，`uv venv` + 装 openai/dotenv，用 stepfun 端点跑通**流式**调用并打印耗时 | ① 终端有流式输出；② 打印出耗时与 token 数；③ 笔记贴真实输出片段 | `labs/ch04-llm-client/` + `notes/2026-09-29.md` | stepfun key（已有）；60 min |
| **U2 · 09-30 三**<br>Agent 与工作流的边界 | 第 1 章《初识智能体》中文正文（选读核心节） | 写 300 字「L1 为什么用工作流而不是 Agent」，并列出 L1 里 3 个「加 Agent 反而更差」的点 | ① 不看稿能讲 2 分钟；② 举的 3 个点都能对应 L1 实际代码/流程；③ `tech-stack.md` A 组该行改「能用」 | `notes/2026-09-30.md` | 45 min |
| **U3 · 10-01 四**<br>工具调用闭环 | `code/chapter1/FirstAgentTest.py` | 复制成 `labs/ch01-toolcall/`，把外部搜索工具换成**自己写的**时间/计算工具，跑通多轮工具调用 | ① 模型连续 ≥2 轮调用自写工具并给出最终答案；② 笔记贴出 tool_call 原始 JSON；③ 无外部付费 API 依赖 | `labs/ch01-toolcall/` | stepfun 端点；75 min |
| **U4 · 10-02 五**<br>采样参数与结构化输出 | 第 3 章「采样参数」节 + L1 的 JSON 截断踩坑记录 | 用 pydantic 定义 schema；**故意**把 `max_tokens` 调小复现「JSON 断句」，再给足 token 修好，两次输出对比 | ① 两段真实输出并排对比；② 记录 `finish_reason`；③ `tech-stack.md`「结构化输出」= 能用 | `labs/ch03-sampling/` + `notes/` | 60 min |
| **U5 · 10-03 六**<br>手写 ReAct | 第 4 章经典范式 + `code/chapter4/ReAct.py`、`tools.py` | **不抄示例**，手写 20–40 行 ReAct 循环（思考→行动→观察），跑通一个需要 ≥2 步的任务 | ① 运行日志能看到 ≥2 轮 思考/行动/观察；② 能讲清它与「一次提示词输出 JSON」的区别 | `labs/ch04-react-min/` | U3、U4；90 min |
| **U6 · 10-04 日**<br>范式对比 + **周复盘** | `code/chapter4/Reflection.py`、`Plan_and_solve.py` | 各跑一遍（换成自己的小任务），做对比表：适用场景/成本/失败模式 | ① 对比表每格都有具体例子（不是形容词）；② 本周 `results/` 归档；③ 周日复盘写完 | `results/2026-10-04/范式对比/` | 90 min |
| **U7 · 10-05 一**<br>框架帮我做了什么 | 第 7 章正文前半 + `code/chapter7/my_simple_agent.py` | 先在 venv 里装 `hello-agents` 框架，跑通 `my_simple_agent.py`，画出 Agent / LLM / Tool / Memory 四者关系的类图 | ① 有一张类图（手画拍照也算）；② 能讲清「框架帮我做了什么」的 3 条；③ 笔记记下框架版本号 | `labs/ch07-simple-agent/` | 需装 hello-agents；75 min |
| **U8 · 10-06 二**<br>Agent 循环 + 测试 | 第 7 章 `my_react_agent.py` + `test_*.py` 写法 | 跑通 chapter7 的 pytest，给自己的 lab 补 3 个用例（正常/异常/边界） | ① pytest 全绿并贴输出；② 阶段0 复盘写进 notes；③ `tech-stack.md` A 组全部打勾 | `notes/2026-10-06.md` + `results/2026-10-06/阶段0复盘/` | 75 min |

> **国庆假期提醒**：10-01~10-07 若出行，把 U3–U6 的**动手**单元整体挪到 10-08 之后；读的部分在路上做（本地 md 离线可读）。
> **单元进度**：U1 ✅ 完成（2026-09-29，见 `results/2026-09-29/端点流式调用打通/`）。

## 3. L1 期单元（10-07 ~ 10-20，主线是 L1 项目，本计划骑在它上面）

| 单元 | 学什么 | 动手做什么 → 验收 | 时长 |
|---|---|---|---|
| 10-07 ~ 10-08 | 第 12 章《智能体性能评估》正文 + `code/chapter12/01_basic_agent_example.py` | 给 L1 评测集加一个 **LLM-as-judge** 打分脚本，与现有规则匹配器对比一致性 → 输出对比表（谁更严、差在哪 3 例） | 2×60 min |
| 10-09 ~ 10-10 | Langfuse 官方文档快速上手 | 接入 L1 调用（云版免费额度）→ 面板里能看到 ≥5 次调用的输入/输出/耗时/成本 | 2×45 min |
| 10-11 ~ 10-12 | promptfoo 文档 | 对 L1 提示词 v1/v2 做一次 A/B → 产出对比报告（谁赢、差多少、样本量多少） | 2×60 min |
| 10-13 ~ 10-15 | 第 7 章后半 + `my_advanced_search.py`、`my_calculator_tool.py` | 把自己的 3 个工具注册进 chapter7 的框架跑通 → 截图/日志证明工具被正确选择 | 3×45 min |
| 10-16 ~ 10-18 | 第 6 章《框架开发实践》+ `code/chapter6/`（AgentScope / AutoGen / CAMEL） | 各跑 1 个 demo，做 3 行对比表（适用场景/上手难度/依赖体积） | 3×60 min |
| 10-19 ~ 10-20 | — | L1 期收口：补漏、`results/` 归档、`tech-stack.md` E 组打勾、写 2 周复盘 | 2×45 min |

## 4. L2 期 · 第 8 章为主线（10-21 ~ 11-17，每周一个主题）

| 周 | 日期 | 学什么（`code/chapter8/`） | 本周产出（可归档） |
|---|---|---|---|
| W5 | 10-21 ~ 10-27 | `01_MemoryTool_Basic_Operations`、`02_MemoryTool_Architecture`、`03_WorkingMemory_Implementation` | `labs/ch08-memory/`：记忆写入/读取/合并各 1 次真实运行日志 |
| W6 | 10-28 ~ 11-03 | `04_RAGTool_MarkItDown_Pipeline`、`05_RAGTool_Advanced_Search`、`06_Memory_Consolidation_Demo` | 用**自己的一份** PDF/URL 走完 解析→分块→检索，输出 3 种分块参数对比表 |
| W7 | 11-04 ~ 11-10 | `07_RAGTool_Intelligent_QA`、`08_Agent_Tool_Integration`、`10_RAG_Pipeline_Complete`、`11_Q&A_Assistant` | 跑通完整 RAG 管线并换成自己的语料，能回答 5 个预置问题（对/错都记录） |
| W8 | 11-11 ~ 11-17 | `09_Memory_Types_Deep_Dive` + ragas 文档 | **ragas 评测**：召回率 / 忠实度 / 相关性三指标 + ≥3 组参数前后对比 → L2 作品的数字证据 |
| 缓冲 | 11-16 ~ 11-17 | — | 补漏 + `results/` 归档 + 阶段复盘 |

## 5. L3 期 · 编排与协议（11-18 ~ 12-15，每周一个主题）

| 周 | 日期 | 学什么 | 本周产出 |
|---|---|---|---|
| W9 | 11-18 ~ 11-24 | 第 4 章范式复习 + 第 7 章框架 | 自写 Agent Loop：工具注册 + 预算控制 + 终止条件，`labs/ch07-agent-loop/` |
| W10 | 11-25 ~ 12-01 | 第 9 章《上下文工程》`code/chapter9/01–06` | context builder（系统+记忆+检索+工具，含 token 预算计算）+ 跑通三日工作流 |
| W11 | 12-02 ~ 12-08 | 第 6 章 LangGraph + **第 14 章 `code/chapter14/helloagents-deepresearch`** | LangGraph 重写一个 agent；deepresearch 后端+前端本地跑通，生成 1 份研究报告 |
| W12 | 12-09 ~ 12-15 | 第 10 章《智能体通信协议》`code/chapter10/01–05`、`weather-mcp-server/` + Extra11 浏览器 Agent 起步 | 自建 MCP server 并被 Agent 成功调用（贴调用日志）；浏览器 Agent 完成 1 个网页动作 |
| 缓冲 | 12-14 ~ 12-15 | — | L3 收口：架构图 + 评测数字 + 复盘归档 |

## 6. 收尾期（12-16 ~ 01-26）

| 阶段 | 日期 | 学什么 | 产出 |
|---|---|---|---|
| W13 评测与数据 | 12-16 ~ 12-22 | 第 12 章 `02_bfcl_quick_start`、`03`、`05_gaia_quick_start`、`08_data_generation_llm_judge`、`09_win_rate` | 1 个 benchmark 子集结果 + 自建 20 条评测数据（LLM-judge 打分） |
| W14–W16 包装上线 | 12-23 ~ 01-12 | 第 13 章 `helloagents-trip-planner`（FastAPI+Vue 结构）+ Docker + I 组安全 + **第 5 章低代码三平台** | 端到端跑通 + 容器化成功 + Coze/Dify/n8n 各 1 个 demo + OWASP 10 条笔记 |
| W17–W18 缓冲补漏 | 01-13 ~ 01-26 | `Extra-Chapter/Extra01-面试问题总结.md` + `Extra01-参考答案.md` | Agent 方向面试问答清单（每题配自己的项目例子） |

## 7. 每天固定动作（贴在 `notes/` 里就够）

```text
① 10 min  定向读：rg -n "关键词" /d/code/hello-agents/docs/chapter*/   → 只看今天要用的那一段
② 25-35 min 动手：在 labs/<实验名>/ 里跑，改，再跑；粘贴真实输出
③ 10 min  写笔记：notes/YYYY-MM-DD.md 四块（概念/输出/面试话术/用进哪）
④ 5 min   打卡：progress.md 打勾 · tech-stack.md 打勾 · 有成品 → results/
```

**每周日额外 15 分钟**：复盘本周单元完成率 → 把下周 7 天单元补进本文件第 2/3 节 → `results/` 归档。

## 8. 调整与止损规则（触发就照做，不留情）

| 情况 | 动作 |
|---|---|
| 连续 2 天没做 | **不补**。当周剩下的单元里挑最重要 1 个做，其余标「跳过」并写原因 |
| 单个单元卡住 >1 小时 | 记进踩坑日志，标「跳过」，周日复盘再决定是否重排 |
| ai_pm 主线吃紧 | 本计划降级为「每周 3 个单元」，但 `progress.md` 不许长期空白 |
| 第 3 / 11 章数学推导看不懂 | 只读到「能解释现象」为止，标注「了解级」，不追推导 |
| 每 4 周检查 | 若 `tech-stack.md` 有超过 2 周没打勾的分组 → 说明计划定太满，砍条目 |

## 9. 维护规则

- 逐日表只保留**未来 2 周**，过期单元改成 `✅ 完成 / ⏭ 跳过` 并留一行结果（链接到 notes）；
- 章节内容、代码清单变化时，先看 `D:\code\hermes\ai_pm\docs\hello-agents-学习索引.md`，再改本文件；
- 本文件与 `progress.md`（章节打卡）、`tech-stack.md`（技术验收）、`results/`（成果归档）四者联动，改一处要同步另三处；
- 教材更新：`cd /d/code/hello-agents && git pull --depth 1 origin main` 后核对章节号是否变动。

*建立 2026-09-29｜下次滚动更新：2026-10-06（阶段0 复盘时）*