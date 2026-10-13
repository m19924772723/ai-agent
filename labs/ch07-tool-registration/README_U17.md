# labs/ch07-tool-registration · U17 扩展：框架内置工具实测

## 1. 目标

U7/U15 都看到框架自动注册 4 个内置工具但从未深究。U17 读源码 + 实测回答：**Skill / Task / TodoWrite / DevLog 各是什么、写到哪里、什么时候该用**。

## 2. 源码定位（hello-agents 1.0.0，tools/builtin/）

| 工具 | 文件 | 定位（源码 docstring 原文提炼） | 落盘位置 |
|---|---|---|---|
| Skill | `skill_tool.py` | 按需加载领域知识；渐进式披露（仅需要时加载完整技能）；作为 tool_result 注入不修改 system_prompt；支持 `$ARGUMENTS` 占位符 | 读 `skills/`（需要先有技能库） |
| Task | `task_tool.py` | 启动**子代理**处理子任务：上下文隔离（独立历史）、工具过滤（readonly/full/none）、摘要返回（避免污染主上下文）、可选轻量模型 | 无落盘（运行期） |
| TodoWrite | `todowrite_tool.py` | 任务列表管理：声明式覆盖（每次提交完整列表）、单线程强制（最多 1 个 in_progress）、自动 Recap | `memory/todos/` |
| DevLog | `devlog_tool.py` | 开发日志：结构化（category+content+metadata）、7 类目（decision/progress/issue/solution/refactor/test/performance）、支持过滤查询与摘要 | `memory/devlogs/` |

## 3. 实测（2026-10-13，ReActAgent，step-3.7-flash）

任务：把"调研并总结三个最常用的 Agent 评测指标"拆成待办（TodoWrite）、记一条日志说明原因（DevLog）、最后作答。

**调用序列**：`['TodoWrite', 'DevLog', 'DevLog']`（16.97 s）

**TodoWrite 落盘**（`memory/todos/todoList-20261013-101140.json`）：
3 步 pending 清单 + summary + stats（total 3 / pending 3）——结构化任务管理真实生效。

**DevLog 落盘**（`memory/devlogs/devlog-s-*.json`）：
1 条 `decision` 类目日志，含 content、metadata.tags、step——日志持久化真实生效。
（模型两次调用 DevLog 用了不同 category：development 和 decision，都被接受——category 校验宽松。）

**Skill 未被调用**：本任务不需要领域知识——符合设计（按需加载，不是每轮都查）。

**回答**：Success Rate（成功率）/ Task Completion Rate（任务完成率）/ Efficiency（效率），从效果/质量/效率三维评估——答案合理（延续第 12 章评测主题）。

## 4. 用途小结（什么时候该用哪个）

- **Skill**：Agent 需要领域专业知识时（"加载 pdf 技能再处理这个文档"）——对应第 7 章"让 Agent 拥有知识"；本仓库里我的 `notes/` 学习笔记可做成技能库供 agent 加载。
- **Task**：子任务需要隔离上下文时（长任务拆子代理、避免主上下文爆炸）——对应多 Agent 协作（第 15 章赛博小镇方向）。
- **TodoWrite**：多步任务必须显式管理进度时——让 Agent 自己维护清单，跨会话可恢复。
- **DevLog**：需要留下决策/问题/方案记录时——Agent 的开发过程审计（对应 U16 的 trace 证据思路）。

## 5. 复现

```bash
cd D:/code/hermes/ai-agent/labs/ch07-tool-registration
export LLM_API_KEY=$HERMES_CUSTOM_STEPFUN_API_KEY PYTHONIOENCODING=utf-8
.venv/Scripts/python.exe builtin_tools_probe.py
# → out/builtin_tools_run.json（调用序列+落盘核对）+ memory/todos/、memory/devlogs/（工具产物）
```
