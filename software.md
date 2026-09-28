# AI Agent 开发 · 软件/工具清单（software.md）

> 建立：2026-09-28　「现状」列 = **本机 2026-09-28 实测**（有版本号才算已装）。
> 配套：要学什么看 `tech-stack.md`；要不要装判断标准与 ai_pm 一致：**当前阶段用得上才装**。

## 0. 使用规则（先读，违反任何一条都会踩坑）

1. **一切装到 D 盘**：工具链在 `D:\code\environment\`，项目依赖在项目自己的 `.venv\`；C 盘只留系统必需。
2. **缓存永远指向 `D:\code\environment\cache\`**：pip/npm/pnpm/uv 已全局配好（`PIP_CACHE_DIR`/`NPM_CONFIG_CACHE`/`UV_CACHE_DIR`）。新装任何工具先确认它的缓存目录不在 C 盘。
3. **不要往 Hermes 的 python 里装包**：`python` 指向 `D:\code\hermes\hermes-agent\venv\Scripts\python.exe`（3.11.16），那是 Hermes 运行环境，装包会污染它。**每个实验用 `uv venv` 建独立环境**：
   ```bash
   cd D:/code/hermes/ai-agent/labs/<实验名>
   uv venv .venv --python 3.11
   uv pip install --python .venv/Scripts/python.exe openai python-dotenv pydantic
   .venv/Scripts/python.exe xxx.py
   ```
4. 「已装」≠「能用」：第一次真实跑出结果后才把 `notes/` 里的记录勾掉。
5. 密钥不进仓库：`.env` 已被 `.gitignore` 排除；本机密钥从 **Hermes 进程环境变量**继承（见第 2 节）。

## 1. 现状总表（2026-09-28 实测）

| 软件 | 版本 | 位置 | 状态 |
|---|---|---|---|
| git | 2.55.0 | `D:\code\environment\Git` | ✅ 在用 |
| gh（GitHub CLI） | 2.100.0 | `D:\code\environment\gh` | ✅ 在用 |
| uv | 0.12.13 | `D:\code\environment\uv` | ✅ 在用（缓存已在 D） |
| Node.js / npm / pnpm | 24.19.0 / 11.17.0 / 11.19.0 | `D:\code\environment\nodejs` | ✅ 在用 |
| VS Code | 1.139.1 | 系统 | ✅ 在用 |
| Cursor | 3.17.21 | `C:\Users\1\AppData\Local\Programs\cursor` | ✅ 在用 |
| Claude Code / Codex | — | `D:\code\environment\claude-code` 等 | ✅ 在用 |
| ripgrep（rg） | 15.2.0 | WinGet | ✅ 在用（离线全文检索靠它） |
| ffmpeg | 9.0.1 | `D:\code\environment` | ✅ 在用 |
| Obsidian | — | `D:\code\environment\obsidian` | ✅ 在用 |
| Figma | — | `%LOCALAPPDATA%\Figma` | ✅ 已装 |
| Docker CLI | 29.7.2 | 系统 | ⚠️ **daemon 未启动 + compose 插件缺失**（见 F1，需修） |
| Ollama | — | — | ❌ 未装（G 组可选再装） |
| python 包（openai/mcp/fastapi/pydantic…） | — | Hermes venv 自带 | ⚠️ 不可用（规则3：不往里装） |

**尚缺的 Python 包**（都未装，按阶段补）：`langgraph`、`langchain`、`llama-index`、`chromadb`、`ragas`、`langfuse`、`deepeval`、`browser-use`、`playwright`、`markitdown`、`litellm`。
L1 项目 venv 里已有的经验包（可复用参考）：`streamlit`、`trafilatura`、`pymupdf`、`pytest`、`pandas`、`httpx`——**不要在系统里重复装，需要时在 lab venv 里按需装**。

## 2. 模型端点怎么接（复用 Hermes 已配好的，不新建账号）

Hermes 的 provider 配置（`D:\code\hermes\config.yaml`）已把密钥注入本终端环境变量，**教程代码直接继承，不用复制任何密钥**：

| provider | base_url | 模型 | OpenAI 兼容？ | 环境变量（已注入） |
|---|---|---|---|---|
| stepfun（首选） | `https://api.stepfun.com/v1` | `step-3.7-flash` | ✅ chat_completions | `HERMES_CUSTOM_STEPFUN_API_KEY` |
| deepseek 官方 | `https://api.deepseek.com/v1` | `deepseek-flash` | ✅ chat_completions | `HERMES_CUSTOM_DEEPSEEK_API_KEY` |
| 中转 xxyapi/tuoji/siyu 系 | 各自域名 | 各模型 | ❌ anthropic_messages 协议，教程代码用不了 | 先不用 |

在 `labs/<实验名>/.env` 里写（hello-agents 统一格式，见 `D:\code\hello-agents\code\chapter4\.env.example`）：

```bash
LLM_MODEL_ID=step-3.7-flash
LLM_BASE_URL=https://api.stepfun.com/v1
LLM_API_KEY=${HERMES_CUSTOM_STEPFUN_API_KEY}   # 或直接 export 后再跑，密钥不进文件
LLM_TIMEOUT=60
```

> 坑：推理模型（deepseek-flash 等）会先消耗推理 token，`max_tokens` 给 4096 可能截断出半句 JSON——L1 已实测，模板里给足（≥8192 或显式截断信号）。

## 3. 分组清单

### A. 阶段0 · 现在就接（本周 W1–W2）

| 工具 | 干什么用 | 装到哪 | 怎么装 | 什么时候装 | 替代品/坑 |
|---|---|---|---|---|---|
| uv venv 工作流 | 所有实验的隔离环境 | lab 各自 `.venv` | 见规则3 四行命令 | 本周 | 别用 `pip install` 全局装 |
| openai + python-dotenv + pydantic | 教程代码的调用/配置/校验 | lab venv | `uv pip install --python .venv/Scripts/python.exe openai python-dotenv pydantic` | 本周 | — |
| jq（可选） | 终端 JSON 处理 | `D:\code\environment\bin` | 官网二进制放 bin | 本周 | 不装也能用 python -m json.tool |

### B. 阶段1 · L2 检索增强期（W5–W8 前装）

| 工具 | 干什么用 | 怎么装 | 坑 |
|---|---|---|---|
| chromadb | 本地向量库（入门用，零配置） | `uv pip install chromadb`（lab venv） | 先装这个，pgvector 等 L4 |
| llama-index（或 langchain 二选一） | RAG 框架 | `uv pip install llama-index` | 二选一即可，都装会乱 |
| markitdown | Office/PDF→Markdown 解析 | `uv pip install markitdown` | 与 trafilatura 互补 |
| ragas | RAG 评测（召回/忠实度） | `uv pip install ragas` | 依赖较多，装进独立 venv |
| langfuse（云端版） | 调用追踪/成本面板 | 网页注册 + `uv pip install langfuse` | 免费额度够学习 |
| promptfoo（可选） | 提示词 A/B | `npx promptfoo@latest`（Node 已就位） | 与 ai_pm 工具栈复用 |

### C. 阶段2 · L3 Agent 编排期（W9 前装）

| 工具 | 干什么用 | 怎么装 | 坑 |
|---|---|---|---|
| langgraph | 状态图编排（L3 主框架） | `uv pip install langgraph` | 需 Python 3.9+，OK |
| hello-agents 框架 | 母本自研框架，穿透表象 | `uv pip install hello-agents` | 见第7章；与 langgraph 可并存 |
| browser-use + playwright | 浏览器 Agent | `uv pip install browser-use playwright` + `playwright install chromium` | 首次下载浏览器较大，缓存别落 C 盘 |
| Firecrawl（可选） | 网页抓取 API | 网页注册 + SDK | 先用免费额度；本地抓取已有 trafilatura 兜底 |
| crewai / autogen（二选一对比） | 多 Agent 角色化 | `uv pip install crewai` | 只用来做框架对比表 |

### D. 横切 · 低代码平台（有空就玩）

| 平台 | 干什么用 | 怎么装 | 坑 |
|---|---|---|---|
| Coze | 网页搭 bot | 注册即用（网页） | 无需安装 |
| Dify | 自托管工作流+RAG | Docker Compose 一键 | **需先修 Docker（F1）**；嫌麻烦用官网云版 |
| n8n | 自动化工作流 | `npx n8n` 或 `npm i -g n8n` | Node 已就位 |

### E. 部署与观测（阶段3 / L4 前）

| 工具 | 干什么用 | 怎么装 | 坑 |
|---|---|---|---|
| **Docker Desktop 修复** | 容器化一切的先决条件 | 现状：CLI 29.7.2 已装，但 **daemon 没起 + compose 插件缺失**（`docker info` 连不上 `dockerDesktopLinuxEngine`）。需启动 Docker Desktop，必要时补装 compose 插件 | 本机是标准用户，Docker Desktop 若装失败只能引导手动装；Dify 等 docker 系工具都卡在这 |
| GitHub Actions | CI 自动测试 | 仓库已会配 | 与 ai_pm 三平台联动 |
| Vercel / Railway（可选） | 部署 FastAPI/前端 | 注册 + CLI | L4 再说 |

### F. 安全（阶段1 前）

| 工具 | 干什么用 | 怎么装 |
|---|---|---|
| OWASP LLM Top 10 | 通读标准 | 网页即可（不装软件） |
| LLM Guard / Guardrails AI（可选） | 输入过滤/输出护栏 | `uv pip install llm-guard guardrails-ai` |
| Microsoft Presidio | PII 脱敏 | `uv pip install presidio-analyzer`（含模型下载，注意缓存到 D） |

### G. 先不装（写了理由，不是忘了）

| 软件 | 为什么不装 |
|---|---|
| AnythingLLM / Open WebUI / LM Studio / Jan | PM「体验完整 RAG 产品」用，**不是 Agent 开发工具**；要体验时用 Dify 云版代替 |
| Ollama | 无网/隐私回退才需要；当前所有端点可用，阶段0 不装（G 组技术标「可选」） |
| RAGFlow / Langchain-Chatchat | Docker 未修好前装了也跑不起来；且 L2 首选 chromadb+llama-index，够用 |
| vLLM / SGLang / Kubernetes / GPUStack | 本机无 GPU 集群，是实习/生产向，研一下再说 |
| Metabase / Grafana | 数据看板是 L4 包装期的事，装早了吃灰 |
| Docker Compose 全家 | 见 E1：Docker daemon 修复前，所有 docker 系（Dify/n8n 自托管/RAGFlow）都延迟 |

## 4. 维护规则

- 每次新装工具：更新本表「现状」列 + 在当天 `notes/` 里记一条真实使用记录；
- 装之前对照 ai_pm 的《工具栈与信息源》和 `soft/` 清单，**能复用就不重装**；
- 「先不装」条目每季度复核一次，条件变了就上移；
- 本机实测状态以本表为准，怀疑失效就重新跑版本命令，不凭记忆。