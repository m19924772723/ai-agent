"""U4（第 4 天 · 2026-10-01）：采样参数与结构化输出。

目标（plan.md U4 的验收）：
  ① 两段真实输出并排对比（截断 vs 正常）
  ② 记录 finish_reason
  ③ 能解释"推理 token 与输出 token 共用一个预算"
附带解决 U1 的遗留问题：流式响应里 finish_reason 到底拿不拿得到。

做法：同一个"长文 → 结构化 JSON"任务，跑 5 组配置，全部用 pydantic 校验：
  run1  max_tokens=64   temp=0    非流式  → 预期：JSON 断在半句，finish_reason=length
  run2  max_tokens=8192 temp=0    非流式  → 预期：通过校验，finish_reason=stop
  run3  max_tokens=8192 temp=1.2  非流式  → 同样的输入，看高温度下结果漂不漂
  run4  max_tokens=64   temp=0    流式    → 只为验证：流式能不能拿到 finish_reason
  run5  max_tokens=8192 temp=0    非流式 + response_format=json_object → 端点是否支持

运行：.venv/Scripts/python.exe run_sampling.py
"""
import json
import os
import sys
import time
from datetime import datetime
from typing import List

from dotenv import load_dotenv
from openai import OpenAI
from pydantic import BaseModel, Field, ValidationError

load_dotenv()

MODEL = os.getenv("LLM_MODEL_ID") or "step-3.7-flash"
BASE_URL = os.getenv("LLM_BASE_URL") or "https://api.stepfun.com/v1"
KEY = os.getenv("LLM_API_KEY") or os.getenv("HERMES_CUSTOM_STEPFUN_API_KEY") or os.getenv("HERMES_CUSTOM_DEEPSEEK_API_KEY")

ARTICLE = """2026 年 9 月，团队把内部知识库问答从"能用"推到"敢用"：第一步把检索从纯关键词换成混合检索，
召回率从 41% 提到 68%；第二步给答案加了引用来源，用户投诉"胡说"的比例从 12% 降到 3%；
第三步做了 20 条离线评测集，每次改提示词都跑一遍，避免改好一个场景又坏了两个。
下一步计划是把评测集扩到 100 条，并接入线上埋点观察真实提问分布。
风险点：知识库内容更新依赖人工，没人维护的文档会变成答案里的噪音。"""

SYSTEM = """你是长文结构化的提取器。只输出 JSON，不要解释、不要 Markdown 代码块。
JSON 字段：
- title: 字符串，一句话标题（不超过 30 字）
- key_points: 字符串数组，3 条要点，每条不超过 40 字
- tags: 字符串数组，2-4 个标签
- todos: 字符串数组，0-3 条待办事项"""


class Article(BaseModel):
    title: str = Field(min_length=2, max_length=60)
    key_points: List[str] = Field(min_length=3)
    tags: List[str] = Field(min_length=2)
    todos: List[str] = Field(default_factory=list)


def client():
    if not KEY:
        sys.exit("缺少密钥：LLM_API_KEY / HERMES_CUSTOM_STEPFUN_API_KEY / HERMES_CUSTOM_DEEPSEEK_API_KEY")
    return OpenAI(api_key=KEY, base_url=BASE_URL, timeout=int(os.getenv("LLM_TIMEOUT", "90")))


def validate(raw: str):
    """把响应文本丢给 pydantic，返回 (是否通过, 结果或错误, 提取到的 JSON 片段)。"""
    s = raw.strip()
    if "```" in s:                     # 去掉可能的代码块围栏
        s = s.replace("```json", "").replace("```", "").strip()
    frag = s[s.find("{"): s.rfind("}") + 1] if "{" in s else ""
    try:
        return True, Article.model_validate_json(frag).model_dump(), frag
    except ValidationError as e:
        errs = [f"{'.'.join(str(x) for x in er['loc'])}: {er['msg']}" for er in e.errors()[:3]]
        return False, "校验失败 → " + "；".join(errs), frag
    except Exception as e:
        return False, f"解析失败 → {type(e).__name__}: {e}", frag


def run(cli, name, max_tokens, temperature, stream=False, json_mode=False):
    kwargs = dict(model=MODEL, messages=[{"role": "system", "content": SYSTEM},
                                         {"role": "user", "content": ARTICLE}],
                  temperature=temperature, max_tokens=max_tokens)
    if json_mode:
        kwargs["response_format"] = {"type": "json_object"}
    rec = {"run": name, "max_tokens": max_tokens, "temperature": temperature,
           "stream": stream, "json_mode": json_mode}
    t0 = time.perf_counter()
    try:
        if stream:
            chunks, finish = [], None
            resp = cli.chat.completions.create(**kwargs, stream=True,
                                               stream_options={"include_usage": True})
            usage = None
            for ch in resp:
                if getattr(ch, "usage", None):
                    usage = ch.usage
                if not ch.choices:
                    continue
                if ch.choices[0].finish_reason:
                    finish = ch.choices[0].finish_reason
                if ch.choices[0].delta and ch.choices[0].delta.content:
                    chunks.append(ch.choices[0].delta.content)
            raw = "".join(chunks)
            rec.update(finish_reason=finish, usage=None if usage is None else usage.model_dump())
        else:
            resp = cli.chat.completions.create(**kwargs)
            raw = resp.choices[0].message.content or ""
            rec.update(finish_reason=resp.choices[0].finish_reason,
                       usage=None if resp.usage is None else resp.usage.model_dump())
    except Exception as e:
        rec.update(error=f"{type(e).__name__}: {e}", seconds=round(time.perf_counter() - t0, 2))
        return rec, "", False, str(e)

    ok, result, frag = validate(raw)
    u = rec.get("usage") or {}
    rec.update(seconds=round(time.perf_counter() - t0, 2), ok=ok, result=result,
               raw_chars=len(raw), raw_tail=raw[-160:],
               completion_tokens=u.get("completion_tokens"),
               prompt_tokens=u.get("prompt_tokens"),
               json_fragment_chars=len(frag))
    return rec, raw, ok, result


def main():
    cli = client()
    print(f"模型：{MODEL}｜端点：{BASE_URL}\n" + "=" * 70)
    plan = [
        ("run1 小预算(64)", dict(max_tokens=64, temperature=0)),
        ("run2 足额(8192)", dict(max_tokens=8192, temperature=0)),
        ("run3 高温(1.2)", dict(max_tokens=8192, temperature=1.2)),
        ("run4 流式+小预算", dict(max_tokens=64, temperature=0, stream=True)),
        ("run5 json_object", dict(max_tokens=8192, temperature=0, json_mode=True)),
    ]
    recs = []
    for name, kw in plan:
        rec, raw, ok, result = run(cli, name, **kw)
        recs.append(rec)
        print(f"\n--- {name} ---")
        if "error" in rec:
            print(f"  调用失败：{rec['error'][:160]}")
            continue
        u = rec.get("usage") or {}
        print(f"  finish_reason={rec['finish_reason']}｜pydantic={'通过' if ok else '失败'}"
              f"｜completion_tokens={u.get('completion_tokens')}｜visible_chars={rec['raw_chars']}"
              f"｜{rec['seconds']} s")
        print(f"  输出尾部 160 字：{rec['raw_tail']!r}")
        if ok:
            print(f"  解析结果：title={result['title'][:30]}｜要点 {len(result['key_points'])} 条"
                  f"｜标签 {result['tags']}｜待办 {len(result['todos'])} 条")
        else:
            print(f"  {result}")

    out = os.path.join(os.path.dirname(os.path.abspath(__file__)), "out", "sampling.json")
    os.makedirs(os.path.dirname(out), exist_ok=True)
    with open(out, "w", encoding="utf-8") as f:
        json.dump({"ts": datetime.now().isoformat(timespec="seconds"), "model": MODEL,
                   "article_chars": len(ARTICLE), "runs": recs}, f, ensure_ascii=False, indent=2)
    print(f"\n证据写入：{out}")


if __name__ == "__main__":
    main()
