"""U10 采集器：跑 6 次真实调用，记录每次调用的输入/输出/耗时/token，落成 JSONL。

可观测闭环 = 采集端（本文件）+ 渲染端（render.py）→ 面板 panel.html。
云端切换：若设置了 LANGFUSE_PUBLIC_KEY / LANGFUSE_SECRET_KEY / LANGFUSE_HOST，
则同一批调用会同步发给 Langfuse（trace 记录 + 异步，失败不影响本地采集）。

成本口径（诚实原则）：不编价格——token 数是成本代理；要换算钱的话设
STEPFUN_PRICE_PER_1K（元/每千 token 输入输出均价），不设则成本列显示"未定价"。
"""
import json
import os
import time
from datetime import datetime

from dotenv import load_dotenv
from openai import OpenAI

load_dotenv()

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "out")
os.makedirs(OUT, exist_ok=True)

MODEL = os.getenv("LLM_MODEL_ID") or "step-3.7-flash"
BASE_URL = os.getenv("LLM_BASE_URL") or "https://api.stepfun.com/v1"
KEY = os.getenv("LLM_API_KEY") or os.getenv("HERMES_CUSTOM_STEPFUN_API_KEY")
PRICE = os.getenv("STEPFUN_PRICE_PER_1K")  # 元/千 token；None = 未定价

# 6 条混合难度的反馈（取自 labs/ch12-eval 的评测集口径，保证有真值可对照）
SAMPLES = [
    "付款的时候页面直接闪退了，钱扣了订单没生成，重新登录也看不到订单记录，怎么办？",        # bug/高/支付
    "希望搜索页能支持按时间排序，现在最新发布的内容永远排不到前面。",                          # 需求/低/搜索
    "打开详情页白屏，刷新三次才好，第一次加载一直转圈。",                                     # bug/中/内容
    "登录后偶尔会自动退出，有时候看两篇文章就掉线了，体验很差。",                              # bug/高/登录
    "提交评价的时候一直转圈，最后提示保存失败，但评论其实已经写进去了。",                      # bug/中/其他
    "能不能加个夜间模式？晚上刷手机白底太刺眼了。",                                            # 需求/低/其他
]

SYSTEM = """你是用户反馈分类器。只输出 JSON，不要解释、不要 Markdown 代码块。
字段：{"类型": "bug|体验|需求", "严重度": "高|中|低", "模块": "支付|登录|搜索|列表|内容|其他"}
口径：类型=bug（功能坏了/报错/闪退/扣款异常）；体验（能用但慢/卡/难找）；需求（希望新增或改进）
严重度=高（涉及钱/登录/数据丢失/完全不可用）；中（主流程受阻）；低（不影响完成）"""


def call(cli, fb):
    t0 = time.perf_counter()
    r = cli.chat.completions.create(
        model=MODEL,
        messages=[{"role": "system", "content": SYSTEM}, {"role": "user", "content": fb}],
        temperature=0, max_tokens=2048)
    dt_ms = round((time.perf_counter() - t0) * 1000, 1)
    u = r.usage
    return {
        "input": fb, "output": (r.choices[0].message.content or "").strip(),
        "latency_ms": dt_ms, "finish_reason": r.choices[0].finish_reason,
        "tokens": {"prompt": u.prompt_tokens if u else None,
                   "completion": u.completion_tokens if u else None,
                   "total": u.total_tokens if u else None},
    }


def to_langfuse(row, i):
    """云版接入：有 LANGFUSE_* 环境变量才发（trace 记录在后台线程，失败静默）。"""
    try:
        from langfuse import Langfuse
    except ImportError:
        return None
    try:
        lf = Langfuse(
            public_key=os.getenv("LANGFUSE_PUBLIC_KEY"),
            secret_key=os.getenv("LANGFUSE_SECRET_KEY"),
            host=os.getenv("LANGFUSE_HOST", "https://cloud.langfuse.com"))
        t = lf.trace(name="ch12-observe", input=row["input"], output=row["output"],
                     metadata={"latency_ms": row["latency_ms"], "tokens": row["tokens"]})
        t.generation(name="collect", model=MODEL, input=row["input"], output=row["output"],
                     usage={"input": row["tokens"]["prompt"], "output": row["tokens"]["completion"]},
                     start_time=datetime.now(),
                     end_time=datetime.now().timestamp() + 0.001)
        lf.flush()
        print(f"  [{i}] Langfuse trace 已发送")
        return True
    except Exception as e:  # 云版故障不阻塞本地采集
        print(f"  [{i}] Langfuse 发送失败（已忽略）：{type(e).__name__}")
        return False


def main():
    if not KEY:
        raise SystemExit("缺少密钥：LLM_API_KEY / HERMES_CUSTOM_STEPFUN_API_KEY")
    cli = OpenAI(api_key=KEY, base_url=BASE_URL, timeout=90)
    rows, total_tokens, fails = [], 0, 0
    print(f"采集 {len(SAMPLES)} 次调用（{MODEL}）…")
    for i, fb in enumerate(SAMPLES, 1):
        row = call(cli, fb)
        row["id"] = f"C{i:02d}"
        row["ts"] = datetime.now().strftime("%H:%M:%S")
        row["model"] = MODEL
        rows.append(row)
        total_tokens += row["tokens"]["total"] or 0
        if row["finish_reason"] != "stop":
            fails += 1
        print(f"  {row['id']} {row['latency_ms']:>7.1f} ms  {row['tokens']['total']:>5} tok  {row['finish_reason']}  raw={row['output'][:40]!r}")
        if os.getenv("LANGFUSE_PUBLIC_KEY") and os.getenv("LANGFUSE_SECRET_KEY"):
            to_langfuse(row, i)
        else:
            print(f"  {row['id']} 未配 LANGFUSE_*，仅本地采集（云版接入就绪，配 key 即生效）")

    avg_ms = round(sum(r["latency_ms"] for r in rows) / len(rows), 1)
    summary = {
        "ts": datetime.now().isoformat(timespec="seconds"),
        "model": MODEL,
        "calls": len(rows),
        "total_tokens": total_tokens,
        "avg_latency_ms": avg_ms,
        "failed": fails,
        "price_per_1k_rmb": PRICE or "未定价",
        "rows": rows,
    }
    with open(os.path.join(OUT, "calls.jsonl"), "w", encoding="utf-8") as f:
        for r in rows:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
    with open(os.path.join(OUT, "summary.json"), "w", encoding="utf-8") as f:
        json.dump(summary, f, ensure_ascii=False, indent=2)
    print(f"\n完成：{len(rows)} 次调用 / {total_tokens} token / 平均 {avg_ms} ms / 失败 {fails}")
    print(f"数据：{OUT}/calls.jsonl + summary.json")


if __name__ == "__main__":
    main()