"""U9 评测执行：同一份预测结果，用「规则判分」与「LLM-as-judge」两套打分器各评一遍。

目的（对应 plan.md U9 验收）：
  ① 20 条评测集 → 规则判分与 LLM-as-judge 的一致性对比（谁更严、差在哪几例）
  ② 给出可复现的数字，而不是"感觉模型还行"

流程：
  1) 用冻结口径的提示词，对 dataset.json 的 20 条反馈跑一次结构化抽取 → predictions.json（缓存，重跑不重复花钱）
  2) 规则判分：逐字段精确匹配（口径是闭集，这是最客观的基线）
  3) LLM-as-judge：把"反馈原文 + 模型预测 + 人工真值 + 评分标准"给裁判模型，让它逐字段判对错并说明理由
  4) 对比两者的一致率 + 分歧明细

运行：
  .venv/Scripts/python.exe run_eval.py            # 全部（首次会调用 20+20 次模型）
  .venv/Scripts/python.exe run_eval.py --judge-only   # 只重跑裁判（用已有 predictions.json）
"""
import argparse
import json
import os
import re
import sys
import time
from collections import Counter
from datetime import datetime

from dotenv import load_dotenv
from openai import OpenAI

load_dotenv()

HERE = os.path.dirname(os.path.abspath(__file__))
DS = os.path.join(HERE, "dataset.json")
PRED = os.path.join(HERE, "out", "predictions.json")
JUDGED = os.path.join(HERE, "out", "judged.json")

MODEL = os.getenv("LLM_MODEL_ID") or "step-3.7-flash"
BASE_URL = os.getenv("LLM_BASE_URL") or "https://api.stepfun.com/v1"
KEY = os.getenv("LLM_API_KEY") or os.getenv("HERMES_CUSTOM_STEPFUN_API_KEY")

FIELD_ORDER = ("类型", "严重度", "模块")

# 冻结的口径 —— 必须与 dataset.json 的 rubric 一致（三处同源：数据、抽取提示词、judge 评分标准）
RUBRIC_TEXT = """类型：bug（功能坏了/报错/闪退/白屏/扣款异常）；体验（能用但慢/卡/难找/无提示）；需求（希望新增或改进能力）
严重度：高（涉及钱、登录、数据丢失或完全不可用）；中（主流程可用但明显受阻）；低（不影响完成，仅体验或锦上添花）
模块：支付 / 登录 / 搜索 / 列表 / 内容 / 其他"""

EXTRACT_SYSTEM = f"""你是用户反馈分类器。只输出 JSON，不要解释、不要 Markdown 代码块。
字段：{{"类型": "...", "严重度": "...", "模块": "..."}}

分类口径（必须严格遵守）：
{RUBRIC_TEXT}"""

JUDGE_SYSTEM = f"""你是严格的评测裁判。逐字段判断「模型预测」与「人工真值」是否一致。
评分口径（与标注口径完全一致）：
{RUBRIC_TEXT}

对每个字段给出：
  verdict: "一致" 或 "不一致"
  reason: 一句话说明（若不一致，指出按口径应该是哪个、模型为什么错）
最后给 overall: "全对" 或 "有错"。
只输出 JSON：{{"类型": {{"verdict": "...", "reason": "..."}}, "严重度": {{...}}, "模块": {{...}}, "overall": "..."}}"""


def client():
    if not KEY:
        sys.exit("缺少密钥：LLM_API_KEY / HERMES_CUSTOM_STEPFUN_API_KEY")
    return OpenAI(api_key=KEY, base_url=BASE_URL, timeout=int(os.getenv("LLM_TIMEOUT", "90")))


def chat(cli, system, user, max_tokens=4096):
    r = cli.chat.completions.create(model=MODEL, messages=[
        {"role": "system", "content": system}, {"role": "user", "content": user}],
        temperature=0, max_tokens=max_tokens)
    u = r.usage
    return (r.choices[0].message.content or "").strip(), (u.total_tokens if u else 0), r.choices[0].finish_reason


def parse_json(text):
    s = text.strip().replace("```json", "").replace("```", "").strip()
    frag = s[s.find("{"): s.rfind("}") + 1] if "{" in s else ""
    try:
        return json.loads(frag), None
    except Exception as e:
        return None, f"{type(e).__name__}: {e}"


# ---------------------------------------------------------------- 1) 抽取
def extract_all(cli, ds):
    rows, tokens = [], 0
    for s in ds["samples"]:
        txt, tk, fin = chat(cli, EXTRACT_SYSTEM, s["feedback"], max_tokens=2048)
        tokens += tk
        obj, err = parse_json(txt)
        pred = None if obj is None else {k: obj.get(k) for k in FIELD_ORDER}
        rows.append({"id": s["id"], "feedback": s["feedback"], "true": s["true"],
                     "pred": pred, "raw": txt[:300], "finish_reason": fin, "parse_error": err})
        print(f"  {s['id']} pred={pred} err={err}")
    return rows, tokens


# ---------------------------------------------------------------- 2) 规则判分
def rule_grade(rows):
    out = []
    for r in rows:
        detail = {}
        for k in FIELD_ORDER:
            pred = (r["pred"] or {}).get(k)
            detail[k] = {"verdict": "一致" if pred == r["true"][k] else "不一致",
                         "reason": f"真值={r['true'][k]}，预测={pred}"}
        out.append({"id": r["id"], "detail": detail,
                    "overall": "全对" if all(v["verdict"] == "一致" for v in detail.values()) else "有错"})
    return out


# ---------------------------------------------------------------- 3) LLM-as-judge
def judge_all(cli, rows):
    out, tokens, fails = [], 0, 0
    for r in rows:
        if r["pred"] is None:
            out.append({"id": r["id"], "detail": {}, "overall": "有错", "note": "预测解析失败，裁判跳过"})
            fails += 1
            continue
        user = (f"反馈原文：{r['feedback']}\n\n"
                f"人工真值：{json.dumps(r['true'], ensure_ascii=False)}\n"
                f"模型预测：{json.dumps(r['pred'], ensure_ascii=False)}")
        txt, tk, fin = chat(cli, JUDGE_SYSTEM, user)
        tokens += tk
        obj, err = parse_json(txt)
        if obj is None:
            fails += 1
            out.append({"id": r["id"], "detail": {}, "overall": "有错", "note": f"裁判输出无法解析：{err}"})
        else:
            detail = {k: obj.get(k, {}) for k in FIELD_ORDER}
            out.append({"id": r["id"], "detail": detail,
                        "overall": obj.get("overall") or ("全对" if all(
                            str(detail[k].get("verdict", "")).strip() == "一致" for k in FIELD_ORDER) else "有错")})
    return out, tokens, fails


# ---------------------------------------------------------------- 4) 对比
def compare(rows, rule, judged):
    cmp_rows, same, diff, strict = [], 0, [], {"规则更严": 0, "裁判更严": 0}
    for r, ru, ju in zip(rows, rule, judged):
        ru_pass = sum(1 for k in FIELD_ORDER if ru["detail"][k]["verdict"] == "一致")
        ju_pass = sum(1 for k in FIELD_ORDER
                      if str(ju["detail"].get(k, {}).get("verdict", "")).strip() == "一致") if ju["detail"] else 0
        agree = (ru_pass == ju_pass)
        same += agree
        if not agree:
            diff.append({"id": r["id"], "feedback": r["feedback"][:40],
                         "true": r["true"], "pred": r["pred"],
                         "规则": f"{ru_pass}/3 字段一致", "裁判": f"{ju_pass}/3 字段一致",
                         "裁判理由": {k: ju["detail"].get(k, {}).get("reason", "") for k in FIELD_ORDER
                                      if str(ju["detail"].get(k, {}).get("verdict", "")).strip() == "不一致"}})
            if ru_pass > ju_pass:
                strict["裁判更严"] += 1
            else:
                strict["规则更严"] += 1
        cmp_rows.append({"id": r["id"], "规则字段一致数": ru_pass, "裁判字段一致数": ju_pass,
                         "一致": agree})
    return cmp_rows, same, diff, strict


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--judge-only", action="store_true")
    args = ap.parse_args()

    ds = json.load(open(DS, encoding="utf-8"))
    cli = client()
    os.makedirs(os.path.dirname(PRED), exist_ok=True)
    total_tokens = 0

    if args.judge_only and os.path.exists(PRED):
        rows = json.load(open(PRED, encoding="utf-8"))["rows"]
        print(f"复用已有预测：{len(rows)} 条")
    else:
        print(f"抽取中（{len(ds['samples'])} 条）…")
        t0 = time.perf_counter()
        rows, tk = extract_all(cli, ds)
        total_tokens += tk
        json.dump({"ts": datetime.now().isoformat(timespec="seconds"), "model": MODEL,
                   "tokens": tk, "rows": rows}, open(PRED, "w", encoding="utf-8"),
                  ensure_ascii=False, indent=2)
        print(f"抽取完成，{time.perf_counter() - t0:.1f} s，tokens={tk}")

    rule = rule_grade(rows)
    print("裁判打分中…")
    judged, tk2, fails = judge_all(cli, rows)
    total_tokens += tk2

    cmp_rows, same, diff, strict = compare(rows, rule, judged)

    # 统计
    def field_acc(grades):
        acc = Counter()
        for g in grades:
            for k in FIELD_ORDER:
                if g["detail"].get(k, {}).get("verdict") == "一致":
                    acc[k] += 1
        return {k: f"{acc[k]}/{len(grades)}" for k in FIELD_ORDER}

    overall_rule = sum(1 for g in rule if g["overall"] == "全对")
    overall_judge = sum(1 for g in judged if g["overall"] == "全对")
    result = {
        "ts": datetime.now().isoformat(timespec="seconds"),
        "model": MODEL, "judge_model": MODEL, "samples": len(rows),
        "tokens": {"extract": json.load(open(PRED, encoding="utf-8")).get("tokens", 0) if os.path.exists(PRED) else 0,
                   "judge": tk2, "total": total_tokens},
        "rule": {"全对条数": overall_rule, "字段正确": field_acc(rule)},
        "judge": {"全对条数": overall_judge, "字段正确": field_acc(judged), "裁判解析失败": fails},
        "agreement": {"一致条数": same, "一致率": f"{same}/{len(rows)}", "严格性": strict},
        "diffs": diff,
        "per_sample": cmp_rows,
        "predictions": [{"id": r["id"], "pred": r["pred"], "true": r["true"],
                         "parse_error": r["parse_error"]} for r in rows],
    }
    json.dump(result, open(JUDGED, "w", encoding="utf-8"), ensure_ascii=False, indent=2)

    print("\n" + "=" * 70)
    print(f"样本 {len(rows)}｜模型 {MODEL}｜tokens 合计 {total_tokens}")
    print(f"规则判分：全对 {overall_rule}/{len(rows)}｜字段正确 {result['rule']['字段正确']}")
    print(f"LLM裁判 ：全对 {overall_judge}/{len(rows)}｜字段正确 {result['judge']['字段正确']}")
    print(f"两者一致：{same}/{len(rows)} 条（一致率 {same/len(rows):.0%}）｜严格性差异 {strict}")
    print(f"分歧明细见：{JUDGED}")
    for d in diff[:6]:
        print(f"  [{d['id']}] {d['feedback']}… 规则={d['规则']} 裁判={d['裁判']} 真值={d['true']} 预测={d['pred']}")


if __name__ == "__main__":
    main()
