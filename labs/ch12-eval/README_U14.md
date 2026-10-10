# labs/ch12-eval · U14 扩展：A/B 多轮复跑验证

> U13 完成了"单轮 A/B"，U14 回答"单轮的结论站得住吗"。
> 结论：**站不住，但多轮后站得住**。详见 `out/ab_5runs_report.md`。

## 为什么复跑（U14 的动机）

U13 单轮跑出「v2 锚点版 全对 12→15、严重度 15→19」，但当时 McNemar p=0.375 不显著。
疑点：temp=0 下模型输出仍有采样噪声，**单轮 A/B 的结果可能是噪声**。

## 做了什么

1. 同一 A/B（20 条真值 × 2 版提示词）用 `--no-cache` 复跑 4 轮（+U13 的 run1 共 5 轮，200 次真实调用）
2. 写 `analyze_ab_runs.py`：对 5 轮做**配对检验**（单侧，精确 t CDF），并生成 markdown 报告
3. 发现并修正了一个方法论错误（见下）

## 关键结果（2026-10-10 实测）

| | v1 纯口径 | v2 锚点版 | Δ |
|---|---|---|---|
| 严重度均值 | 15.4/20 | **18.8/20** | **+3.4（每轮都赢）** |
| 全对均值 | 13.8/20 | **15.4/20** | **+1.6（4/5 轮赢，1 轮平）** |
| 配对检验 | — | — | 严重度 t=8.50 p=0.0005 ✓；全对 t=3.14 p=0.018 ✓ |

类型/模块两版几乎无差 → 锚点只影响它教的那一维（严重度），且方向稳定。

## 方法论收获（本单元最重要的产出）

**单轮 A/B 会被噪声骗**：
- run1：v2 全对 +3（"锚点有效"）
- run2：v2 全对 +0（"锚点无效"）
- 5 轮合并：+1.6，配对检验显著

→ **评测/调优报告必须多次运行取分布 + 配对检验**，单次跑的数字（无论输赢）都不足以支撑改版决策。
这与 U1/U10 的教训同源：单次延迟/单次准确率都不可靠，要看分布。

## 文件

```
analyze_ab_runs.py          # 5 轮判分 + 配对检验 + 报告生成（可复现）
out/results_run{2..5}.json  # 4 轮复跑原始输出（run1 在 results.json）
out/ab_5runs_summary.json   # 逐轮判分 + 检验结果 JSON
out/ab_5runs_report.md      # 结论报告（可直接展示）
```

## 复现

```bash
cd D:/code/hermes/ai-agent/labs/ch12-eval
export LLM_API_KEY=$HERMES_CUSTOM_STEPFUN_API_KEY PYTHONIOENCODING=utf-8
for n in 2 3 4 5; do node_modules/.bin/promptfoo eval --output out/results_run$n.json --no-share --no-cache; done
.venv/Scripts/python.exe analyze_ab_runs.py
```
