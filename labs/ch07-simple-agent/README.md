# labs/ch07-simple-agent —— 框架帮我做了什么（U7 单元）

## 1. 出处

- 母本：第 7 章《构建你的 Agent 框架》前半 + `code/chapter7/my_simple_agent.py`（子类化 `SimpleAgent`）
- 框架：PyPI `hello-agents` **1.0.0**（`requires-python >=3.10`），与书里的 API 一致

## 2. 改了什么 / 为什么

| 项 | 母本 | 这里 | 为什么 |
|---|---|---|---|
| 目的 | 子类化演示 | **探针式**：不改框架，只调用公开 API，然后把它替我做掉的事逐条打印出来 | 要回答"框架帮我做了什么"，靠读源码不如靠观察它的行为 |
| 工具 | 自定义工具 | 框架自带 `CalculatorTool` + 自注册一个 `word_count` 函数工具 | 同时验证两条注册路径（`register_tool` / `register_function`） |
| 观测 | — | 读框架自己写的 **trace jsonl**（每步 tool_calls/usage） | 这是它的免费可观测性，也是我后面做评测的数据源 |

## 3. 怎么跑

```bash
cd D:/code/hermes/ai-agent/labs/ch07-simple-agent
uv venv .venv --python 3.11
uv pip install --python .venv/Scripts/python.exe hello-agents python-dotenv
export PYTHONIOENCODING=utf-8
.venv/Scripts/python.exe framework_probe.py
cat out/framework_run.json          # 本次运行记录
cat memory/traces/*.jsonl           # 框架自己写的轨迹（被 .gitignore 排除）
```

## 4. 真实输出（2026-10-04 实测，框架 1.0.0 + step-3.7-flash）

```
✅ 工具 'python_calculator' 已注册。
✅ 函数工具 'word_count' 已注册。
✅ 工具 'Skill' 已注册。   ✅ 工具 'Task' 已注册。
✅ 工具 'TodoWrite' 已注册。 ✅ 工具 'DevLog' 已注册。
框架版本：1.0.0｜已注册工具：['python_calculator', 'Skill', 'Task', 'TodoWrite', 'DevLog', 'word_count']
🧮 正在计算: (123+456)*7/3 → 计算结果: 1351.0
回答（7.02 s）：1. (123+456)*7/3 = 1351.00（保留两位小数）  2. '你好 hello' 共有 8 个字符
```

框架自己的 trace（`memory/traces/*.jsonl`）：

| 步 | tool_calls | usage（prompt / completion / total） |
|---|---|---|
| 1 | **2 个并行调用**：`python_calculator(input="(123+456)*7/3")` + `word_count(input="你好 hello")` | 1523 / 130 / **1653** |
| 2 | 0（收尾给答案） | 1619 / 122 / **1741** |
| 合计 | 2 步 | **3394 token**，7.02 s，status=success |

**框架"帮我做了什么"——三条（可验证的）**

1. **省掉了工具调用契约这一层**：我只写了两个工具函数和一句注册，框架自己把 schema 喂给模型、解析 `tool_calls`、执行、回填结果，并在**一步里并行执行了 2 个调用**（trace step1 显示 tool_calls=2）。这正好补上 U3 遗留问题：**该端点支持并行工具调用**，而框架已经内建处理。
2. **自带运行时状态与可观测性**：它自动创建了 `memory/{sessions,todos,devlogs,traces}`、`skills/`、`tool-output/` 目录，落盘 jsonl + html 轨迹（含每一步的 tool_calls 与 usage）。等价于送了一个轻量 Langfuse。**代价**：状态写在 CWD，必须 gitignore；且它会**自动注册 4 个内置工具**（Skill / Task / TodoWrite / DevLog），加上我的 2 个共 6 个 —— 工具 schema 本身就吃掉上下文（首轮 prompt 1523 token）。
3. **版本演进的方向是"原生工具调用"而不是"提示词拼接"**：1.0.0 里 `_get_enhanced_system_prompt()` 已不再把「可用工具」描述拼进 system prompt（返回的就是我的原句），说明工具契约改由原生 tool calling 承担——这与 U3 的结论（生产用原生工具调用）方向一致。

**类与数据的四件套关系（ASCII 图，取代手画）**

```
                 ┌───────────────────────────── SimpleAgent ─────────────────────────────┐
                 │  name / system_prompt / _history[]                                     │
                 │                                                                        │
   我提供的  ────▶│  llm: HelloAgentsLLM ──▶ chat.completions(tools=[...])  ──▶  模型      │
                 │        (model/base_url/key/temperature/max_tokens)                     │
                 │                                                                        │
   我注册的  ────▶│  tool_registry: ToolRegistry ──▶ execute_tool(name, args)              │
                 │        ├─ python_calculator（框架自带 CalculatorTool）                  │
                 │        ├─ word_count（我用 register_function 注册）                     │
                 │        └─ Skill / Task / TodoWrite / DevLog（框架自动注册）             │
                 │                                                                        │
   框架自己  ────▶│  memory/   sessions · todos · devlogs · traces(jsonl+html)             │
                 │  skills/   tool-output/                                                │
                 └────────────────────────────────────────────────────────────────────────┘
   一次 run 的循环：user → [模型输出 tool_calls] → 注册表执行（可并行）→ 结果回填 → 再次调用模型 → 收尾答案
```

MRO 实测：`SimpleAgent / ReActAgent / PlanSolveAgent / ReflectionAgent` **都直接继承 `Agent(ABC)`**，即四个范式在框架里是并列实现，不是层层继承——所以换范式=换类，不用重写工具层。

**一个自己踩的坑（判据也要被验证）**

第一版脚本里我把期望值手写成「`'你好 hello'` = **7** 个字符」，而正确答案是 **8**（你/好/空格/h/e/l/l/o）。模型答对了，是**我的判据错了**。已改成 `len("你好 hello")` 由代码计算——**期望值不能手写**，这跟 U4 学到的"数字必须来自真实输出"是同一件事的另一面：**判分脚本本身也得可验证**。
