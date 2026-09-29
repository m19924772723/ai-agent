"""U2 实验：同一个「字段抽取」任务，用**工作流**和**Agent**两条路径各跑一遍，量出成本/延迟/稳定性差异。

为什么要做：U2 的结论是「字段固定的批处理该用工作流」，但那是判断，不是证据。这个脚本把它变成数字。

设计
----
任务：把 12 条中文用户反馈抽成三列 —— 类型 / 严重度 / 模块。
路径 A 工作流：关键词规则写死，确定性，零 token。
路径 B Agent：每条一次 LLM 调用，要求输出 JSON（同一 schema）。

度量（全部真实采集）
  · 成本：token 合计（来自 usage 字段）
  · 延迟：整批耗时 + 单条均值
  · 格式稳定性：JSON 解析成功率
  · 结果稳定性：同一批输入跑**两遍**，两遍完全一致的条数（Agent 独有，工作流恒为 12/12）
  · 交叉一致率：Agent 结果与工作流规则结果一致的条数（参考值，不判定谁更"对"）

运行：.venv/Scripts/python.exe run_compare.py
"""
import json
import os
import statistics
import sys
import time
from datetime import datetime

from dotenv import load_dotenv
from openai import OpenAI

load_dotenv()

MODEL = os.getenv("LLM_MODEL_ID") or "deepseek-flash"
BASE_URL = os.getenv("LLM_BASE_URL") or "https://api.deepseek.com/v1"
KEY = os.getenv("LLM_API_KEY") or os.getenv("HERMES_CUSTOM_DEEPSEEK_API_KEY")
PASSES = 2

# ---------------- 测试数据（合成，12 条） ----------------
SAMPLES = [
    "付款的时候页面直接闪退了，钱扣了订单没生成",
    "希望搜索页能支持按时间排序，现在翻半天找不到最新的",
    "登录一直提示验证码错误，换浏览器也一样",
    "列表加载特别慢，滑一次要等三四秒",
    "能不能加一个导出 Excel 的按钮，我要给领导做周报",
    "退款申请提交后没有任何提示，不知道成功没有",
    "搜索关键词没结果时页面是空白的，很难用",
    "账号在另一台手机上登录后，这台就被踢出去了，希望提示一下",
    "订单列表翻页到第二页就卡住不动了",
    "支付成功后没收到通知，客服入口也找不到",
    "建议把常用的功能放到首页，现在要点三层",
    "内容列表里的图片加载失败，全是碎图标",
]

# ---------------- 路径 A：工作流（规则写死） ----------------
TYPE_RULES = [
    ("bug", ("崩溃", "闪退", "报错", "打不开", "卡住", "加载失败", "没生成", "空白")),
    ("需求", ("希望", "建议", "能不能", "加一个", "支持")),
    ("体验", ("慢", "难用", "找不到", "等", "卡")),
]
SEV_RULES = [
    ("高", ("闪退", "崩溃", "无法", "打不开", "没生成", "钱扣")),
    ("中", ("慢", "卡", "超时", "没有提示", "加载失败")),
    ("低", ()),
]
MODULE_RULES = [
    ("支付", ("支付", "付款", "退款", "订单", "钱")),
    ("登录", ("登录", "验证码", "账号")),
    ("搜索", ("搜索", "关键词", "检索")),
    ("列表", ("列表", "翻页", "排序", "加载")),
    ("内容", ("图片", "内容", "首页")),
]


def _match(text, rules, default):
    for label, kws in rules:
        if any(k in text for k in kws):
            return label
    return default


def extract_workflow(text):
    return {
        "类型": _match(text, TYPE_RULES, "体验"),
        "严重度": _match(text, SEV_RULES, "低"),
        "模块": _match(text, MODULE_RULES, "其他"),
    }


# ---------------- 路径 B：Agent（一次调用一条） ----------------
SYSTEM = (
    "你是用户反馈分类器。把用户反馈归入三类字段，只输出 JSON，不要任何解释。\n"
    '格式：{"类型": "bug|需求|体验", "严重度": "高|中|低", "模块": "支付|登录|搜索|列表|内容|其他"}'
)


def extract_agent(client, text):
    t0 = time.perf_counter()
    resp = client.chat.completions.create(
        model=MODEL,
        messages=[{"role": "system", "content": SYSTEM}, {"role": "user", "content": text}],
        temperature=0,
        max_tokens=2048,
    )
    dt = time.perf_counter() - t0
    raw = (resp.choices[0].message.content or "").strip()
    ok, parsed = False, None
    try:
        s = raw[raw.find("{"): raw.rfind("}") + 1]
        parsed = json.loads(s)
        ok = all(k in parsed for k in ("类型", "严重度", "模块"))
    except Exception:
        pass
    u = resp.usage
    return {
        "ok": ok,
        "result": parsed,
        "raw": raw[:200],
        "latency_s": round(dt, 3),
        "prompt_tokens": u.prompt_tokens if u else 0,
        "completion_tokens": u.completion_tokens if u else 0,
        "total_tokens": u.total_tokens if u else 0,
    }


def same(a, b):
    return bool(a) and bool(b) and a == b


def main():
    if not KEY:
        sys.exit("缺少密钥：LLM_API_KEY 或 HERMES_CUSTOM_DEEPSEEK_API_KEY")

    # ---- 路径 A ----
    t0 = time.perf_counter()
    wf = [extract_workflow(t) for t in SAMPLES]
    wf_ms = (time.perf_counter() - t0) * 1000

    # ---- 路径 B：跑两遍 ----
    client = OpenAI(api_key=KEY, base_url=BASE_URL, timeout=int(os.getenv("LLM_TIMEOUT", "60")))
    passes = []
    for p in range(PASSES):
        rows = [extract_agent(client, t) for t in SAMPLES]
        passes.append(rows)
        print(f"[pass {p+1}] 完成 {len(rows)} 条，JSON 成功 {sum(r['ok'] for r in rows)}/{len(rows)}")

    p1, p2 = passes[0], passes[1]
    agent_tokens = sum(r["total_tokens"] for rs in passes for r in rs)
    agent_secs = sum(r["latency_s"] for rs in passes for r in rs)
    agent_lat = [r["latency_s"] for rs in passes for r in rs]
    json_ok = sum(r["ok"] for rs in passes for r in rs)
    self_consistent = sum(same(a["result"], b["result"]) for a, b in zip(p1, p2))
    cross_consistent = sum(
        same(r["result"], dict(zip(("类型", "严重度", "模块"), (w["类型"], w["严重度"], w["模块"]))))
        for r, w in zip(p1, wf)
    )

    summary = {
        "ts": datetime.now().isoformat(timespec="seconds"),
        "model": MODEL,
        "base_url": BASE_URL,
        "samples": len(SAMPLES),
        "passes": PASSES,
        "workflow": {"total_ms": round(wf_ms, 1), "tokens": 0,
                     "avg_ms": round(wf_ms / len(SAMPLES), 2)},
        "agent": {"json_ok": json_ok, "json_ok_total": len(SAMPLES) * PASSES,
                  "total_tokens": agent_tokens,
                  "avg_tokens": round(agent_tokens / (len(SAMPLES) * PASSES), 1),
                  "total_s": round(agent_secs, 2),
                  "avg_s": round(statistics.mean(agent_lat), 2),
                  "max_s": round(max(agent_lat), 2),
                  "self_consistent": self_consistent},
        "cross_consistent_with_rules": cross_consistent,
        "workflow_detail": wf,
        "agent_pass1": p1,
        "agent_pass2": p2,
    }

    print("\n" + "=" * 60)
    print(f"任务：{len(SAMPLES)} 条反馈 → 类型/严重度/模块  |  模型：{MODEL}")
    print(f"路径A 工作流 : 整批 {wf_ms:.1f} ms（{wf_ms/len(SAMPLES):.2f} ms/条）  token 0")
    print(f"路径B Agent  : 整批 {agent_secs:.2f} s（{statistics.mean(agent_lat):.2f} s/条，最慢 {max(agent_lat):.2f} s）")
    print(f"               token 合计 {agent_tokens}（{agent_tokens/(len(SAMPLES)*PASSES):.1f}/条），JSON 成功 {json_ok}/{len(SAMPLES)*PASSES}")
    print(f"结果稳定性   : 两遍完全一致 {self_consistent}/{len(SAMPLES)}（工作流恒为 {len(SAMPLES)}/{len(SAMPLES)}）")
    print(f"与规则交叉一致率: {cross_consistent}/{len(SAMPLES)}（参考值，不代表谁更对）")
    print(f"倍率         : 延迟 {agent_secs / (wf_ms/1000):.0f}×  成本 0 → {agent_tokens} token")

    out = os.path.join(os.path.dirname(os.path.abspath(__file__)), "out", "compare.json")
    os.makedirs(os.path.dirname(out), exist_ok=True)
    with open(out, "w", encoding="utf-8") as f:
        json.dump(summary, f, ensure_ascii=False, indent=2)
    print(f"\n证据写入：{out}")


if __name__ == "__main__":
    main()
