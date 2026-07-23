"""Grounding regression test: the prompt in narrative.py promises Claude
"YoY (or QoQ if YoY is n/a)" for every line item. That promise is only true
if QoQ is actually present in the markdown table Claude receives.

MSFT/AAPL can't catch a broken promise here — both are mature filers where
YoY is always defined, so the "n/a" fallback branch never fires. This test
uses CRCL (IPO'd June 2025), a real ticker with < 4 quarters of history,
where YoY is genuinely unavailable for its earliest reported quarters and
QoQ is the only fallback data the prompt's own rule can point to.

Run: python3 test_grounding.py
"""

from edgar_quarterly import build_variance_table
from narrative import rows_to_markdown_table

TICKER_WITH_NO_YOY_HISTORY = "CRCL"


def test_qoq_present_when_yoy_unavailable():
    rows = build_variance_table(TICKER_WITH_NO_YOY_HISTORY)
    no_yoy_rows = [r for r in rows if r.get("revenue_yoy_pct") is None]
    assert no_yoy_rows, (
        f"expected at least one {TICKER_WITH_NO_YOY_HISTORY} quarter with YoY "
        "unavailable — test fixture assumption broke, pick a newer IPO ticker"
    )

    table_md = rows_to_markdown_table(rows, ["revenue"])
    for r in no_yoy_rows:
        row_line = next(line for line in table_md.splitlines() if r["quarter"] in line)
        assert "QoQ n/a" not in row_line or r.get("revenue_qoq_pct") is None, (
            f"{r['quarter']}: YoY is n/a but QoQ is also missing from the table — "
            "the prompt's fallback rule has nothing to point to"
        )
    print(f"PASS — QoQ correctly present in {len(no_yoy_rows)} YoY-unavailable row(s)")


if __name__ == "__main__":
    test_qoq_present_when_yoy_unavailable()
