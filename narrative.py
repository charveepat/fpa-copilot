"""Turns computed variance numbers into FP&A-style written commentary.

The model never sees raw filings or does its own arithmetic — it's handed a
pre-computed variance table and writes the narrative, the same division of
labor a real FP&A team uses between the model (Excel/BI tool) and the analyst
(commentary). This keeps every number in the write-up traceable back to a
cell you can point to.
"""

from __future__ import annotations

import os

import anthropic

MODEL = "claude-haiku-4-5"


def _fmt_money(v: float | None) -> str:
    if v is None:
        return "n/a"
    sign = "-" if v < 0 else ""
    v = abs(v)
    if v >= 1e9:
        return f"{sign}${v/1e9:.2f}B"
    return f"{sign}${v/1e6:.1f}M"


def _fmt_pct(v: float | None) -> str:
    return f"{v*100:+.1f}%" if v is not None else "n/a"


def rows_to_markdown_table(rows: list[dict], line_items: list[str]) -> str:
    header = "| Quarter | " + " | ".join(li.replace("_", " ").title() for li in line_items) + " |"
    sep = "|---" * (len(line_items) + 1) + "|"
    lines = [header, sep]
    for r in rows:
        cells = [r["quarter"]]
        for li in line_items:
            val = _fmt_money(r.get(li))
            yoy = _fmt_pct(r.get(f"{li}_yoy_pct"))
            qoq = _fmt_pct(r.get(f"{li}_qoq_pct"))
            cells.append(f"{val} (YoY {yoy}, QoQ {qoq})")
        lines.append("| " + " | ".join(cells) + " |")
    return "\n".join(lines)


def generate_variance_narrative(ticker: str, rows: list[dict], line_items: list[str]) -> str:
    """Calls Claude to write the variance commentary. Requires ANTHROPIC_API_KEY."""
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        raise RuntimeError(
            "ANTHROPIC_API_KEY not set. Add it to your environment or .env file to "
            "generate the AI narrative — the data and variance table above work without it."
        )

    table_md = rows_to_markdown_table(rows, line_items)
    latest = rows[-1]

    prompt = f"""You are an FP&A analyst writing the variance commentary section of a
quarterly business review for {ticker}. Below is a table of real actual results
(sourced from SEC filings) with QoQ and YoY variance already computed.

{table_md}

Write a variance narrative for the most recent quarter ({latest['quarter']}) in the
voice of an FP&A analyst briefing a CFO. Rules:
- Every number you cite MUST come from the table above. Do not invent, round
  differently than shown, or infer numbers not present in the table.
- Structure: 3-5 bullet points, each covering one line item, ordered by
  materiality (largest dollar variance first).
- For each bullet: state the actual, the YoY (or QoQ if YoY is n/a) variance
  in both $ and %, and one plausible, clearly-labeled driver hypothesis
  (e.g. "consistent with continued Azure/cloud demand" for a tech company) —
  flag driver commentary as inference, not fact, since you don't have access
  to management commentary.
- Close with one "watch item" — the metric most worth monitoring next quarter
  and why, based on the trend in the table.
- No preamble, no "Here is the narrative:" — start directly with the bullets.
"""

    client = anthropic.Anthropic(api_key=api_key)
    response = client.messages.create(
        model=MODEL,
        max_tokens=800,
        messages=[{"role": "user", "content": prompt}],
    )
    return response.content[0].text
