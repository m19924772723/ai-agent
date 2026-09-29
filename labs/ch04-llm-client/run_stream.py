"""U1 单元（2026-09-29）：跑通 OpenAI 兼容端点的流式调用，并采集真实指标。

出处：D:\\code\\hello-agents\\code\\chapter4\\llm_client.py（母本 HelloAgentsLLM.think 的流式写法）
本文件是它的最小复刻 + 指标采集，用来回答三个问题：
  1. 流式到底"流"了没有？（逐 chunk 到达时间：首字延迟 / chunk 数 / 最大间隔）
  2. 一次调用花多少 token、多快？（usage + 吞吐）
  3. 两个可用端点谁更快？（preset 循环：stepfun / deepseek）

端点复用 Hermes 已注入的环境变量（见 ../../software.md 第 2 节），不写死任何密钥。

运行：
  .venv/Scripts/python.exe run_stream.py              # 跑全部 preset
  .venv/Scripts/python.exe run_stream.py stepfun      # 只跑其中一个
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

SYSTEM = "你是助理，用中文回答，控制在 80 字以内。"
USER = "用一句话解释什么是 LLM 的流式输出。"
MESSAGES = [{"role": "system", "content": SYSTEM}, {"role": "user", "content": USER}]

# preset：key_env 为空表示用 LLM_API_KEY / HERMES_CUSTOM_STEPFUN_API_KEY
PRESETS = [
    {"name": "stepfun", "model": "step-3.7-flash", "base_url": "https://api.stepfun.com/v1",
     "key_env": "HERMES_CUSTOM_STEPFUN_API_KEY"},
    {"name": "deepseek", "model": "deepseek-flash", "base_url": "https://api.deepseek.com/v1",
     "key_env": "HERMES_CUSTOM_DEEPSEEK_API_KEY", "max_tokens": 2048},
]


def resolve_key(key_env: str) -> str | None:
    if key_env and os.getenv(key_env):
        return os.getenv(key_env)
    return os.getenv("LLM_API_KEY") or os.getenv("HERMES_CUSTOM_STEPFUN_API_KEY")


def call(preset: dict, with_usage: bool = True):
    """流式调用一次，采集逐 chunk 时间线。"""
    key = resolve_key(preset.get("key_env", ""))
    if not key:
        raise RuntimeError(f"缺少密钥：{preset.get('key_env') or 'LLM_API_KEY'}")
    client = OpenAI(api_key=key, base_url=preset["base_url"], timeout=int(os.getenv("LLM_TIMEOUT", "60")))

    kwargs = dict(model=preset["model"], messages=MESSAGES, temperature=0, stream=True)
    if with_usage:
        kwargs["stream_options"] = {"include_usage": True}
    if preset.get("max_tokens"):
        kwargs["max_tokens"] = preset["max_tokens"]

    t0 = time.perf_counter()
    times, parts, usage, reasoning = [], [], None, []
    stream = client.chat.completions.create(**kwargs)
    for chunk in stream:
        if getattr(chunk, "usage", None):
            usage = chunk.usage
        if not chunk.choices:
            continue
        d = chunk.choices[0].delta
        rc = getattr(d, "reasoning_content", None)
        if rc:
            reasoning.append(rc)
        if d.content:
            times.append(time.perf_counter() - t0)
            parts.append(d.content)
    total = time.perf_counter() - t0
    text = "".join(parts)

    if usage is None:  # 网关不支持 stream_options，退回一次非流式调用取用量
        r = client.chat.completions.create(
            model=preset["model"], messages=MESSAGES, temperature=0,
            **({"max_tokens": preset["max_tokens"]} if preset.get("max_tokens") else {}))
        usage = r.usage

    gaps = [round(b - a, 3) for a, b in zip(times, times[1:])]
    return {
        "ts": datetime.now().isoformat(timespec="seconds"),
        "preset": preset["name"],
        "model": preset["model"],
        "base_url": preset["base_url"],
        "prompt": USER,
        "output": text,
        "ttft_s": round(times[0], 3) if times else None,
        "total_s": round(total, 3),
        "chars": len(text),
        "delta_count": len(times),
        "max_gap_s": max(gaps) if gaps else None,
        "median_gap_s": round(statistics.median(gaps), 3) if gaps else None,
        "reasoning_streamed": bool(reasoning),
        "usage": None if usage is None else {
            "prompt_tokens": usage.prompt_tokens,
            "completion_tokens": usage.completion_tokens,
            "total_tokens": usage.total_tokens,
        },
        "finish_reason": None,
    }


def show(rec: dict):
    print(f"\n===== {rec['preset']} / {rec['model']} =====")
    print(f"输出：{rec['output']}")
    u = rec["usage"] or {}
    print(f"TTFT {rec['ttft_s']} s | 总耗时 {rec['total_s']} s | 输出 {rec['chars']} 字")
    print(f"流式增量：{rec['delta_count']} 个 delta 片段 | 中位间隔 {rec['median_gap_s']} s | 最大间隔 {rec['max_gap_s']} s")
    print(f"usage：prompt={u.get('prompt_tokens')} completion={u.get('completion_tokens')} total={u.get('total_tokens')}")
    if u.get("completion_tokens"):
        print(f"吞吐：{u['completion_tokens'] / rec['total_s']:.1f} tok/s（completion_tokens / 总耗时）")
    if rec["delta_count"] and rec["delta_count"] <= 1:
        print("⚠️ 只收到 1 个 delta：该端点/网关把响应整包下发，客户端看不到真正的逐字流")


def main():
    only = sys.argv[1] if len(sys.argv) > 1 else None
    records = []
    for preset in PRESETS:
        if only and preset["name"] != only:
            continue
        try:
            records.append(call(preset))
        except Exception as e:
            print(f"\n===== {preset['name']} 调用失败：{type(e).__name__}: {e}")
            records.append({"preset": preset["name"], "model": preset["model"],
                            "error": f"{type(e).__name__}: {e}"})
    for rec in records:
        if "error" in rec:
            print(f"\n===== {rec['preset']} 失败：{rec['error']}")
        else:
            show(rec)

    out = os.path.join(os.path.dirname(os.path.abspath(__file__)), "out", "usage.json")
    with open(out, "w", encoding="utf-8") as f:
        json.dump({"ts": datetime.now().isoformat(timespec="seconds"), "records": records},
                  f, ensure_ascii=False, indent=2)
    print(f"\n证据写入：{out}")


if __name__ == "__main__":
    main()
