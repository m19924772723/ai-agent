"""U9 评测集：20 条用户反馈 + 人工标注真值（评测对象是"结构化抽取"任务）。

设计要点（延续 U6 的"真值判分"纪律）：
  · 每条样本：feedback（用户原话）+ 三个结构化字段的真值（类型 / 严重度 / 模块）
  · 真值 = 我先按**冻结的口径**人工标注，再由代码校验一遍格式与分布（避免手写出错，见 U7 的教训）
  · 口径（冻结，写进 PROMPT 与 judge 评分标准，三处必须一致）：
      类型：bug（功能坏了/报错/闪退/白屏/扣款异常）
            体验（能用但慢/卡/难找/无提示）
            需求（希望新增/改进能力）
      严重度：高（涉及钱、登录、数据丢失或完全不可用）
              中（主流程可用但明显受阻）
              低（不影响完成，仅体验或锦上添花）
      模块：支付 / 登录 / 搜索 / 列表 / 内容 / 其他
  · 额外留 3 条"口径边界样本"（模糊表达），用来暴露"人和模型都容易分歧"的地方——
    LLM-as-judge 的价值恰恰在这类样本上，而不是在确定答案上（见笔记 §2 的推理）

运行：python make_dataset.py    # 生成 dataset.json 并打印分布与自检结果
"""
import json
import os
from collections import Counter

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "dataset.json")

TYPES = ("bug", "体验", "需求")
SEVERITIES = ("高", "中", "低")
MODULES = ("支付", "登录", "搜索", "列表", "内容", "其他")

# (id, 用户原话, 类型, 严重度, 模块, 是否边界样本)
SAMPLES = [
    ("S01", "付款的时候页面直接闪退了，钱扣了订单没生成", "bug", "高", "支付", False),
    ("S02", "商品列表加载特别慢，滑一次要等三四秒", "体验", "中", "列表", False),
    ("S03", "登录一直提示验证码错误，换浏览器也一样", "bug", "高", "登录", False),
    ("S04", "搜索转圈好几秒才出结果，等得心累", "体验", "中", "搜索", False),
    ("S05", "希望搜索页能支持按时间排序", "需求", "低", "搜索", False),
    ("S06", "订单列表翻页到第二页就卡住不动了", "bug", "中", "列表", False),
    ("S07", "打开详情页白屏，刷新三次才好", "bug", "中", "内容", False),
    ("S08", "退款提交后没有任何提示，不知道成功没有", "体验", "中", "支付", False),
    ("S09", "首页图片加载很慢，半天不出图", "体验", "中", "内容", False),
    ("S10", "能不能加一个导出 Excel 的按钮", "需求", "低", "其他", False),
    ("S11", "支付成功后没收到通知，客服入口也找不到", "体验", "中", "支付", False),
    ("S12", "建议把常用功能放到首页，现在要点三层", "需求", "低", "内容", False),
    ("S13", "账号在另一台手机登录后，这台就被踢出去了，希望提示一下", "需求", "低", "登录", True),
    ("S14", "搜索结果里混进了很多不相关的内容，翻半天找不到想要的", "体验", "中", "搜索", True),
    ("S15", "优惠券明明还没过期，结算时却说不可用", "bug", "高", "支付", True),
    ("S16", "列表里的商品图片和标题对不上，看着像串了", "bug", "中", "列表", True),
    ("S17", "希望能自定义消息通知的时间段，晚上别推送", "需求", "低", "其他", False),
    ("S18", "登录后偶尔会自动退出，一天要重新登录好几次", "bug", "高", "登录", False),
    ("S19", "详情页文字排版在手机上很难读，字号忽大忽小", "体验", "低", "内容", False),
    ("S20", "提交评价时一直转圈，最后提示保存失败", "bug", "中", "其他", False),
]

INSTRUCTION = "把下面的用户反馈归入三个字段，只输出 JSON。"
FIELD_SPEC = {
    "类型": list(TYPES),
    "严重度": list(SEVERITIES),
    "模块": list(MODULES),
}


def build():
    rows = []
    for sid, text, t, sev, mod, edge in SAMPLES:
        assert t in TYPES and sev in SEVERITIES and mod in MODULES, sid
        assert len(text) >= 8, sid
        rows.append({"id": sid, "feedback": text, "true": {"类型": t, "严重度": sev, "模块": mod},
                     "edge_case": edge})
    return rows


def self_check(rows):
    """真值也要被验证（U7 的教训：判据本身会错）。"""
    problems = []
    for r in rows:
        if not r["feedback"].strip():
            problems.append(f"{r['id']}: 空文本")
        for k, v in r["true"].items():
            if k == "类型" and v not in TYPES:
                problems.append(f"{r['id']}: 类型非法 {v}")
            if k == "严重度" and v not in SEVERITIES:
                problems.append(f"{r['id']}: 严重度非法 {v}")
            if k == "模块" and v not in MODULES:
                problems.append(f"{r['id']}: 模块非法 {v}")
    ids = [r["id"] for r in rows]
    if len(set(ids)) != len(ids):
        problems.append("id 有重复")
    return problems


def main():
    rows = build()
    problems = self_check(rows)
    payload = {
        "name": "反馈结构化抽取评测集 v1",
        "created": "2026-10-06",
        "size": len(rows),
        "task": INSTRUCTION,
        "rubric": FIELD_SPEC,
        "labels": {k: {"type": "closed_set", "options": v} for k, v in FIELD_SPEC.items()},
        "samples": rows,
    }
    with open(OUT, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)

    print(f"已写入 {OUT}｜样本 {len(rows)} 条（边界样本 {sum(r['edge_case'] for r in rows)} 条）")
    print("自检：", "通过" if not problems else problems)
    for k in ("类型", "严重度", "模块"):
        c = Counter(r["true"][k] for r in rows)
        print(f"  {k} 分布：{dict(c)}")


if __name__ == "__main__":
    main()
