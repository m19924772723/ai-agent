"""U10 渲染端：把 summary.json 渲染成自包含单文件观测面板（panel.html）。

面板看什么（验收要求 ≥5 次调用的输入/输出/耗时/成本）：
  · 顶部 KPI：调用数 / 总 token / 平均耗时 / 失败数 / 成本口径
  · 表格：每次调用的 输入摘要 / 输出摘要 / 耗时 / prompt+completion token / 成本 / finish_reason
  · 失败行红色高亮；点行展开看完整输入输出

使用：.venv/Scripts/python.exe render.py   （读 out/summary.json → out/panel.html）
"""
import json
import os
from html import escape

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "out")


def cost_row(r, price):
    if r["tokens"].get("total") is None:
        return "—"
    if not price or price == "未定价":
        return "未定价"
    try:
        return f"¥{r['tokens']['total'] * float(price) / 1000:.4f}"
    except ValueError:
        return "未定价"


def render():
    s = json.load(open(os.path.join(OUT, "summary.json"), encoding="utf-8"))
    rows, price = s["rows"], s.get("price_per_1k_rmb", "未定价")

    cards = [
        ("调用次数", str(s["calls"])),
        ("总 token", f"{s['total_tokens']:,}"),
        ("平均耗时", f"{s['avg_latency_ms']} ms"),
        ("失败次数", str(s["failed"])),
        ("模型", s["model"]),
        ("成本口径", str(price)),
    ]
    cards_html = "".join(f'<div class="card"><div class="k">{k}</div><div class="v">{v}</div></div>'
                         for k, v in cards)

    trs = []
    for r in rows:
        cls = "fail" if r["finish_reason"] != "stop" else ""
        inp = escape(r["input"])
        outp = escape(r["output"][:120])
        cost = cost_row(r, price)
        trs.append(
            f'<tr class="{cls}"><td>{r["id"]}</td><td>{r["ts"]}</td>'
            f'<td class="inp">{inp[:60]}</td><td class="out">{outp}</td>'
            f'<td>{r["latency_ms"]:.0f} ms</td>'
            f'<td>P {r["tokens"]["prompt"]} / C {r["tokens"]["completion"]}</td>'
            f'<td>{cost}</td><td>{r["finish_reason"]}</td></tr>'
            f'<tr class="detail"><td colspan="8"><b>完整输入：</b>{inp}<br>'
            f'<b>完整输出：</b>{escape(r["output"])}</td></tr>')
    table = f"""
    <table id="tbl">
      <thead><tr><th>ID</th><th>时间</th><th>输入摘要</th><th>输出摘要</th>
      <th>耗时</th><th>Tokens(P/C)</th><th>成本</th><th>finish</th></tr></thead>
      <tbody>{''.join(trs)}</tbody>
    </table>"""

    html = f"""<!DOCTYPE html><html lang="zh"><head><meta charset="utf-8">
<title>Agent 调用观测面板 · {s['ts']}</title>
<style>
  :root {{ color-scheme: dark; }}
  * {{ box-sizing: border-box; }}
  body {{ font-family: "Segoe UI", "Microsoft YaHei", sans-serif; background: #0f1216;
         color: #d7dde4; margin: 0; padding: 24px; }}
  h1 {{ font-size: 20px; margin: 0 0 4px; }}
  .dim {{ color: #7a828c; font-size: 12px; margin-bottom: 16px; }}
  .cards {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(120px,1fr));
            gap: 10px; margin-bottom: 18px; }}
  .card {{ background: #171c22; border: 1px solid #232a33; border-radius: 10px; padding: 12px; }}
  .k {{ font-size: 12px; color: #7a828c; }} .v {{ font-size: 18px; font-weight: 600; margin-top: 4px; }}
  table {{ border-collapse: collapse; width: 100%; font-size: 13px; }}
  th {{ text-align: left; color: #9aa3ad; font-weight: 500; padding: 8px 10px; border-bottom: 1px solid #232a33; }}
  td {{ padding: 8px 10px; border-bottom: 1px solid #1a2027; vertical-align: top; }}
  td.inp {{ color: #c5cdd6; max-width: 220px; }} td.out {{ color: #8fd3a8; max-width: 260px; }}
  tr.fail td {{ background: #2a1719; color: #ff9c9c; }}
  tr.detail {{ display: none; background: #11161b; color: #aab4be; }}
  tr.detail td {{ white-space: pre-wrap; word-break: break-all; }}
  tr.detail.open {{ display: table-row; }}
  tbody tr.click {{ cursor: pointer; }}
</style></head><body>
<h1>Agent 调用观测面板</h1>
<div class="dim">{s['ts']} · 采集：collect.py → 渲染：render.py · 点击行展开完整输入输出</div>
<div class="cards">{cards_html}</div>
{table}
<script>
  const rows = document.querySelectorAll('#tbl tbody tr.click');
  rows.forEach(r => r.addEventListener('click', () => {{
    const d = r.nextElementSibling;
    if (d && d.classList.contains('detail')) d.classList.toggle('open');
  }}));
</script>
</body></html>"""
    body_rows = html  # noqa
    # 只给非 detail 行挂 click 类
    fixed = html.replace(
        '<tr class="fail"><td>',
        '<tr class="fail click"><td>').replace(
        '<tr><td>', '<tr class="click"><td>')
    # 避免误伤 detail 行（detail 行 td colspan=8）
    fixed = fixed.replace('<tr class="click"><td colspan', '<tr><td colspan')
    # 上面把 detail 的 class 去掉了，重新用 JS 恢复
    fixed = fixed.replace("</tbody>", "</tbody>")
    out_path = os.path.join(OUT, "panel.html")
    with open(out_path, "w", encoding="utf-8") as f:
        f.write(fixed)
    print(f"面板已生成：{out_path}（{len(rows)} 次调用）")


if __name__ == "__main__":
    render()