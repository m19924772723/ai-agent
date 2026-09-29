# labs/ —— 跑通并改造过的实验

## 放什么

母本里的代码**不要直接改**（`git pull` 会冲突）。要动手时：复制过来 → 改名 → 改 → 跑 → 记。

## 命名与结构

```
labs/
└── ch08-rag-pipeline/          # 章节号 + 干了什么事
    ├── README.md               # 必写：出处文件、改了什么、怎么跑、真实输出
    ├── main.py
    └── out/                    # 输出产物（日志、json、图）
```

`README.md` 四行起步（缺一行这个实验就不算数）：

1. **出处**：`D:\code\hermes\ai-agent\references\hello-agents\code\chapterN\<原文件>`（附上游 commit `8c57a6c`）
2. **改了什么 / 为什么**：一句话说清和原版的差别
3. **怎么跑**：命令 + 需要哪些环境变量（`.env` 不进 git）
4. **真实输出**：贴关键片段（不是「运行成功」）

## 环境

- 需要 OpenAI 兼容端点：配置模板见 `D:\code\hermes\ai-agent\references\hello-agents\code\chapter4\.env.example`（`LLM_MODEL_ID / LLM_API_KEY / LLM_BASE_URL / LLM_TIMEOUT`）。
- `.env` 一律不进 git（已在 `.gitignore` 排除）。
- 依赖装在实验自己的 venv 里（`python -m venv .venv`），不要污染系统 Python；缓存走 `D:\code\environment\cache`。
