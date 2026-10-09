"""U13 A/B 判分与对比报告：读 promptfoo results.json，按 U9 真值判分两版提示词。

promptfoo 输出结构（--output results.json）：
  results: [{prompt: {label}, vars, output, metadata, ...}, ...]  每 (prompt × test) 一条
本脚本：解析每条的 output JSON → 与 metadata.true 逐字段比对 → 汇总两版对比表。

运行：.venv/Scripts/python.exe analyze_ab.py
"""
import json
import os
import re
from collections import Counter

HERE = os.path.dirname(os.path.abspath(__file__))
RES = os.path.join(HERE, "out", "results.json")
REPORT = os.path.join(HERE, "out", "ab_report.json")
FIELDS = ("类型", "严重度", "模块")

def parse_output(raw):
    if raw is None:
        return None, "empty"
    # 实测 step-3.7-flash 会对部分请求下发 `Thinking: ...` 前缀/尾缀文本；Thinking 文本里可能含花括号
    # → 不能 `{`..`}` 切片，改为在每个 `{` 位置尝试 raw_decode，取第一个合法对象
    s = re.sub(r"^```(?:json)?\s*|\s*```$", "", str(raw), flags=re.S).strip()
    dec = json.JSONDecoder()
    for m in re.finditer(r"\{", s):
        try:
            obj, _ = dec.raw_decode(s[m.start():])
            if isinstance(obj, dict):
                return {k: obj.get(k) for k in FIELDS}, None
        except json.JSONDecodeError:
            continue
    return None, "no-json-in-output"

def main():
    data = json.load(open(RES, encoding="utf-8"))
    rv = data.get("results", data)
    # v3 格式：results 是 dict {version, prompts, results(数组), stats}；老格式：results 直接是数组
    if isinstance(rv, dict) and isinstance(rv.get("results"), list):
        # promptId → 可读短标签（v1-纯口径版 / v2-锚点版）
        id2label = {}
        for p in rv.get("prompts", []):
            pid = p.get("id")
            raw = p.get("raw", "")
            id2label[pid] = "v2-锚点版" if "fewshot" in raw else "v1-纯口径版"
        rows = rv["results"]
    else:
        rows = rv
        id2label = {}
    # 按 prompt label 分组
    groups = {}
    for r in rows:
        pr = r.get("prompt")
        if isinstance(pr, dict):
            label = pr.get("label") or pr.get("raw") or "?"
            label = "v2-锚点版" if "fewshot" in label else ("v1-纯口径版" if "plain" in label else label[:20])
        else:
            label = id2label.get(str(pr), str(pr)[:40]) if pr else "?"
        groups.setdefault(label, []).append(r)

    report = {"samples": len(next(iter(groups.values()))) if groups else 0, "versions": {}}
    per = []
    for label, items in groups.items():
        v = {"全对": 0, "字段正确": Counter(), "解析失败": 0, "错例": []}
        for it in items:
            meta = it.get("metadata") or {}
            # v3 输出格式：真实输出在 response.output（顶层 output 字段在本版本不存在）
            if it.get("output") is None and isinstance(it.get("response"), dict):
                it["output"] = it["response"].get("output")
            true = meta.get("true") or {}
            out, err = parse_output(it.get("output"))
            if out is None:
                v["解析失败"] += 1
                continue
            wrong = {k: (out.get(k), true.get(k)) for k in FIELDS if out.get(k) != true.get(k)}
            if wrong:
                v["错例"].append({"id": meta.get("id"), "feedback": (it.get("vars") or {}).get("feedback", "")[:40],
                                  "wrong": wrong})
            else:
                v["全对"] += 1
            for k in FIELDS:
                if out.get(k) == true.get(k):
                    v["字段正确"][k] += 1
            per.append({"version": label, "id": meta.get("id"), "pred": out, "true": true,
                        "wrong": wrong, "err": err})
        v["字段正确"] = {k: f"{v['字段正确'][k]}/{len(items)}" for k in FIELDS}
        report["versions"][label] = v

    # 逐条差异：哪几条两版都错/只有 v1 错/只有 v2 错
    by_id = {}
    for p in per:
        by_id.setdefault(p["id"], {})[p["version"]] = p
    ids = sorted(by_id)
    diff_rows = []
    b_only, a_only = 0, 0  # v2 独占错、v1 独占错（McNemar 用）
    for i in ids:
        vs = by_id[i]
        keys = list(vs)
        if len(keys) < 2:  # 某版解析失败未入 per → 无法对比，跳过
            continue
        w1, w2 = bool(vs.get(keys[0], {}).get("wrong")), bool(vs.get(keys[1], {}).get("wrong"))
        if w1 != w2:
            better = keys[1] if (w1 and not w2) else keys[0]
            if w1 and not w2:
                b_only += 1   # v2 对、v1 错
            else:
                a_only += 1   # v1 对、v2 错
            diff_rows.append({"id": i, "feedback": vs[keys[0]].get("feedback", "")[:50],
                              "v1_wrong": vs.get(keys[0], {}).get("wrong", {}),
                              "v2_wrong": vs.get(keys[1], {}).get("wrong", {}),
                              "better": better})
    # McNemar（配对）：仅 v1 错 vs 仅 v2 错；样本 <25 用二项精确检验
    n_disc, chi, p_mc = 0, None, None
    if (b_only + a_only) > 0 and (b_only + a_only) < 25:
        from math import comb
        n_disc = b_only + a_only
        k_min = min(b_only, a_only)
        p_mc = 2 * sum(comb(n_disc, k) for k in range(0, k_min + 1)) / (2 ** n_disc)
    report["差异检验"] = {"v2_仅对": b_only, "v1_仅对": a_only, "不一致对数": n_disc,
                        "McNemar_p(双尾)": round(p_mc, 4) if p_mc is not None else None,
                        "说明": "p<0.05 才认为两版有显著差异（20 条小样本通常不够）"}
    report["关键差异"] = diff_rows

    json.dump(report, open(REPORT, "w", encoding="utf-8"), ensure_ascii=False, indent=2)

    print("=" * 70)
    print(f"样本 {report['samples']} 条 × {len(groups)} 版提示词\n")
    for label, v in report["versions"].items():
        name = "v2 锚点版" if "v2-锚点版" in label else ("v1 纯口径版" if "v1-纯口径版" in label else label[:20])
        print(f"[{name}] 全对 {v['全对']}/{report['samples']} | 类型 {v['字段正确']['类型']} | "
              f"严重度 {v['字段正确']['严重度']} | 模块 {v['字段正确']['模块']} | 解析失败 {v['解析失败']}")
    print("\n两版表现不同的样本（谁赢）：")
    for d in diff_rows[:12]:
        print(f"  {d['id']} {d['feedback']}… → 赢家 {d['better']}")
    print(f"\n完整报告：{REPORT}")

if __name__ == "__main__":
    main()
