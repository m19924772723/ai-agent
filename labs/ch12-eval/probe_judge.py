"""U9 补充探针：裁判的"敏感度"验证 —— 故意注入错误预测，看打分器抓不抓得住。

为什么必须做：主实验里规则判分与 LLM 裁判 **100% 一致**（20/20 条、字段正确率逐项相同）。
一致有两种可能：① 两套打分器都准；② 裁判只会点头（对什么都没意见）。
本探针把 20 条里的 3 条**故意改错**（真值不变），再看：
  · 规则判分：应 100% 抓到（它是精确匹配，属于对照组）
  · LLM 裁判：如果也全部抓到 → 说明它真的在比对；如果漏 → 说明"一致率"是虚的

运行：.venv/Scripts/python.exe probe_judge.py
"""
import json
import os
import sys

from run_eval import FIELD_ORDER, client, judge_all, rule_grade

HERE = os.path.dirname(os.path.abspath(__file__))
PRED = os.path.join(HERE, "out", "predictions.json")
OUT = os.path.join(HERE, "out", "judge_probe.json")

# 注入的错误：id → 把哪个字段改成什么（改的都是"看起来合理但按口径不对"的值）
INJECT = {
    "S01": {"严重度": "中"},    # 真值 高（涉及钱）→ 改成 中，考它认不认"涉及钱=高"
    "S05": {"类型": "体验"},    # 真值 需求（"希望支持"是新增能力）→ 改成 体验
    "S07": {"模块": "其他"},    # 真值 内容（详情页）→ 改成 其他
}


def main():
    rows = json.load(open(PRED, encoding="utf-8"))["rows"]
    corrupted = []
    for r in rows:
        r = dict(r)                                   # 浅拷贝，不动原文件
        if r["id"] in INJECT:
            r["pred"] = {**(r["pred"] or {}), **INJECT[r["id"]]}
            r["injected"] = INJECT[r["id"]]
        corrupted.append(r)

    rule = rule_grade(corrupted)
    cli = client()
    print("裁判复核中（只判 3 条被改动的样本即可，但为一致性仍全跑）…")
    judged, tokens, fails = judge_all(cli, corrupted)

    # 只看注入过的那 3 条
    report = []
    for r, ru, ju in zip(corrupted, rule, judged):
        if "injected" not in r:
            continue
        caught_rule = [k for k in FIELD_ORDER if ru["detail"][k]["verdict"] == "不一致"]
        caught_judge = [k for k in FIELD_ORDER
                        if str(ju["detail"].get(k, {}).get("verdict", "")).strip() == "不一致"]
        report.append({
            "id": r["id"], "feedback": r["feedback"],
            "真值": r["true"], "被改成": r["pred"], "注入": r["injected"],
            "规则抓到字段": caught_rule, "裁判抓到字段": caught_judge,
            "裁判理由": {k: ju["detail"].get(k, {}).get("reason", "") for k in caught_judge},
        })

    print("\n" + "=" * 70)
    print("注入 3 条错误预测后的检测结果：")
    for x in report:
        ok_r = "✅" if x["规则抓到字段"] else "❌"
        ok_j = "✅" if x["裁判抓到字段"] else "❌"
        print(f"\n[{x['id']}] {x['feedback'][:34]}…")
        print(f"  真值={x['真值']} → 被改成 {x['注入']}")
        print(f"  规则 {ok_r} 抓到 {x['规则抓到字段']}")
        print(f"  裁判 {ok_j} 抓到 {x['裁判抓到字段']}")
        for k, why in x["裁判理由"].items():
            print(f"    · {k}: {why}")

    hit_r = sum(1 for x in report if x["规则抓到字段"])
    hit_j = sum(1 for x in report if x["裁判抓到字段"])
    print(f"\n检出率：规则 {hit_r}/3｜裁判 {hit_j}/3（裁判本轮 tokens={tokens}，解析失败 {fails}）")
    json.dump({"ts": __import__("datetime").datetime.now().isoformat(timespec="seconds"),
               "injected": INJECT, "report": report,
               "detected": {"rule": hit_r, "judge": hit_j, "total": 3},
               "judge_tokens": tokens, "judge_parse_failures": fails},
              open(OUT, "w", encoding="utf-8"), ensure_ascii=False, indent=2)
    print(f"证据写入：{OUT}")


if __name__ == "__main__":
    if not os.path.exists(PRED):
        sys.exit("先跑 run_eval.py 生成 predictions.json")
    main()
