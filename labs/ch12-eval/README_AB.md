# U13 A/B：严重度要不要加 few-shot 锚点？（在 labs/ch12-eval 内扩展）

> 复用 U9 的 20 条真值评测集（`dataset.json`），A/B 的唯一变量 = 提示词里要不要加"严重度示例锚点"。
> 结果文件：`out/results.json`（promptfoo 原始输出）、`out/ab_report.json`（判分报告）。

## 一、两版提示词（system 消息，user=反馈原文）

- **v1 纯口径版**（`prompts/v1_severity_plain.yaml`）：纯口径描述，与 U9 实验完全一致
- **v2 锚点版**（`prompts/v2_severity_fewshot.yaml`）：v1 + 高/中/低 各 3 个示例锚点

## 二、怎么跑（真实输出复现）

```bash
cd D:/code/hermes/ai-agent/labs/ch12-eval
export LLM_API_KEY=$HERMES_CUSTOM_STEPFUN_API_KEY PYTHONIOENCODING=utf-8

# 1) 运行 A/B：2 prompts × 20 tests = 40 次真实调用（--no-cache 保证不读旧缓存）
node_modules/.bin/promptfoo eval --output out/results.json --no-share --no-cache

# 2) 判分 + 对比报告（读 results.json → ab_report.json）
.venv/Scripts/python.exe analyze_ab.py
```

## 三、结论（2026-10-09 实测，step-3.7-flash，temperature=0）

| 版本 | 全对 | 类型 | 严重度 | 模块 |
|---|---|---|---|---|
| v1 纯口径版 | 12/20 | 19/20 | **15/20** | 17/20 |
| v2 锚点版 | **15/20** | 19/20 | **19/20** | 17/20 |

- 严重度正确率 **15→19**，全对 **12→15**；类型/模块无变化
- 5 条不一致样本：S08、S13、S18、S19 是 **v2 对 v1 错**（如 S08「退款没提示」v1 判低、v2 按锚点判中✓）；S15 是 **v1 对 v2 错**
- **统计检验**：McNemar p=0.375（20 条小样本，差异不显著，只能作趋势）
- **一句话**：加锚点显著改善了严重度维度（+4 条），但 20 条样本不到统计显著；方向值得在更大评测集上确认

**踩坑记录（本 lab 最值钱的产出）**
1. step-3.7-flash 会把推理文本 `Thinking: ...` 带进输出 content——promptfoo 默认把提示词当 user 消息时尤其严重（v1 一发就 38/40 transform 失败）
2. promptfoo v0.124 的 results.json 是 **v3 格式**：`results` 是 dict、真实输出在 `response.output` 而非顶层 `output`、`prompt` 是原始字符串
3. 推理模型场景：**提示词要放 system、不要当 user 消息**，否则模型会"边想边说"挤掉正式输出
