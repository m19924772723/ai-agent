# Git 推送记录台账（ai-agent 学习线）

> 仓库：`D:\code\hermes\ai-agent`（本地）｜远程：GitHub `m19924772723/ai-agent`（public）
> 身份：m19924772723 / m19924772723@163.com｜SSH key：`C:/Users/1/.ssh/id_ed25519_gh`
> 维护：每次推送后更新本文件；当前 HEAD = `0ef85ae`（2026-10-17）
> 查询命令：`git log --oneline`｜`git ls-remote origin -h refs/heads/main`

## 一、总体状态

| 项 | 值 |
|---|---|
| 提交总数 | 31 |
| 已推送 | 31（全部） |
| 远程 HEAD | `97efeb6`（与本地一致） |
| 工作区 | 干净（0 未提交） |

## 二、提交明细（新→旧）

| # | 提交 | 日期 | 类型 | 内容 |
|---|---|---|---|---|
| 31 | `97efeb6` | 10-18 | feat | U22 CAMEL token 采集（StatsModel 包装器：5 轮/36.3s/11 调用/16722 tokens）+ 三框架成本列收官 + 周日复盘 7/7 ✅ |
| 30 | `0ef85ae` | 10-17 | docs | U21 阶段2 收口复盘：12 单元全 ✅ 核对 + 四线沉淀 + 三条跨单元规律；补 progress 第 6 章 CAMEL 行 |
| 29 | `356d4a1` | 10-16 | docs | U20 章节行同步：CAMEL demo 已跑通，三框架对比表收官 |
| 28 | `aab9b60` | 10-16 | feat | U20 CAMEL 双角色电子书协作（7 轮/84.6s/产出含实证引用）+ 三框架对比表收官 |
| 27 | `9c1db6f` | 10-15 | docs | U19 章节行同步：AutoGen 已跑通（CAMEL 待 U20） |
| 26 | `624016a` | 10-15 | feat | U19 AutoGen 四角色软件团队 demo（8 消息/46.7s，代码验证 5.0✓）+ 三坑（402 静默/TERMINATE 文本/UserProxy 无头） |
| 25 | `9489fe0` | 10-14 | feat | U18 AgentScope 狼人杀 demo（4 人 1 轮：10 调用/10129+1797 token/46.6s，判定全对） |
| 24 | `4f9a0b5` | 10-13 | feat | U17 框架内置 4 工具实测（Skill/Task/TodoWrite/DevLog 落盘）+ 第 7 章收尾 |
| 23 | `2fe5ab4` | 10-12 | feat | U16 工具调用链（hours_until→calculate 强依赖，trace 校验 3 项全过）+ SimpleAgent/ReActAgent 差异 |
| 22 | `3c6ab4e` | 10-11 | feat | U15 3 个工具注册进框架 + 修零参函数兼容 + "答案对工具错"隐性失败 |
| 21 | `27502fe` | 10-10 | feat | U14 提示词 A/B 5 轮复跑（200 次调用）+ 配对检验（严重度 p=0.0005） |
| 20 | `d9af09e` | 10-09 | feat | U13 promptfoo A/B（严重度 15→19、全对 12→15）+ Thinking 兼容性踩坑 |
| 19 | `05aa64b` | 10-08 | feat | U10 观测闭环（6 次调用五要素 + HTML 面板）+ Langfuse 云版接入就绪 |
| 18 | `e10f17c` | 10-06 | feat | U9 20 条评测集 + 规则判分/judge 一致性 + 负样本背书 |
| 17 | `fc3f355` | 10-05 | feat | U8 自写 Agent Loop + 13 用例 + 母本 chapter7 兼容修复 + 阶段1 复盘 |
| 16 | `c2ea3fe` | 10-04 | feat | U7 框架探针（工具契约/运行时/并行 tool_calls）+ 周复盘 |
| 15 | `c90deae` | 10-02 | feat | U5 手写 ReAct + 对照组实证（解析层三坑，token 4688→3181） |
| 14 | `a5d85f8` | 10-01 | feat | U4 采样参数 5 组对照（max_tokens 预算/流式 finish_reason/json_object 省 36%） |
| 13 | `57fd2e9` | 09-30 | feat | U3 工具调用闭环（自写工具 + 双契约对比 2489 vs 3051 token） |
| 12 | `b4a0987` | 09-30 | docs | 明确"一天一个单元"纪律（第 3 天起严格） |
| 11 | `77c0967` | 09-29 | docs | 计划按天次重排（第 1 天 = 2026-09-28 周一） |
| 10 | `0f57a19` | 09-29 | feat | U2 补完动手实测（工作流 vs Agent：0.2ms/0 token vs 70.5s/5809 token） |
| 9 | `54c1639` | 09-29 | feat | U2 第 1 章边界（300 字论述 + 3 反例 + 判断清单） |
| 8 | `85b613a` | 09-29 | refactor | 母本移入本目录 references/hello-agents（自包含） |
| 7 | `9464f20` | 09-29 | refactor | 独立化：去掉 ai_pm 耦合，阶段改 1-5 自编号 |
| 6 | `4b84cfe` | 09-29 | chore | .env.example 允许入库（含密钥的 .env 仍排除） |
| 5 | `34ea388` | 09-29 | feat | U1 跑通两端点流式调用（TTFT/token/吞吐实测） |
| 4 | `9c40808` | 09-29 | docs | plan.md 每日学习与实践计划 |
| 3 | `96b9497` | 09-28 | feat | results/ 每日成果归档体系 + 首条成果 |
| 2 | `447782b` | 09-28 | docs | tech-stack.md 技术验收表 + software.md 软件清单 |
| 1 | `66042f8` | 09-28 | init | 学习目录 init（README + notes 模板 + progress 打卡表 + labs 约定） |

## 三、推送历史事件（踩坑与重试）

| 日期 | 事件 | 处置 |
|---|---|---|
| 10-06 | GitHub 服务端 `Internal Server Error`（推送 e10f17c 时连续失败 6 次） | 本地提交完好；隔 45s+ 重试 3 次仍失败；10-08 网络恢复后一次推上 |
| 10-15 | push 时 `Connection reset by 20.205.243.160` | 本地提交完好；重试 3 次，第 3 次成功 |
| 10-16 | 网络不稳，ls-remote 核对 4 次有 2 次超时 | 重试核对，最终确认远程 = 本地 |

> 通用处置原则（教训）：**GitHub 远端故障时本地提交永远完好，不修改任何代码，隔一段时间重试即可**；推送成功以 `git ls-remote origin` 与本地 HEAD 一致为准。

## 四、维护规则

- 每完成一个单元（feat 提交）→ 推送 → 在本表追加一行，更新"总体状态"数字与 HEAD。
- 只记录**已推送**的提交；本地有未推送的用 ⚠️ 标注。
- 推送核对命令：
  ```bash
  git log --oneline          # 本地提交
  git ls-remote origin -h refs/heads/main | cut -c1-40   # 远程 HEAD
  git rev-parse HEAD         # 本地 HEAD
  git status --porcelain     # 工作区（空=干净）
  ```
