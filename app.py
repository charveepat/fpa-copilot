"""FP&A Copilot — real quarterly variance analysis + AI narrative for any US public company."""

from __future__ import annotations

import os

import pandas as pd
import streamlit as st

from edgar_quarterly import build_variance_table
from narrative import generate_variance_narrative

LINE_ITEMS = [
    "revenue",
    "gross_profit",
    "rd_expense",
    "sga_expense",
    "operating_income",
    "net_income",
]

st.set_page_config(page_title="FP&A Copilot", page_icon="📊", layout="wide")

st.title("📊 FP&A Copilot")
st.caption(
    "Quarterly variance analysis on real SEC XBRL data — no fictional companies, "
    "no toy numbers. Every figure here is what the company actually filed."
)

with st.sidebar:
    st.header("Company")
    ticker = st.text_input("Ticker", value="MSFT").strip().upper()
    num_quarters = st.slider("Quarters to show", min_value=4, max_value=12, value=6)
    st.markdown("---")
    st.markdown(
        "**Variance baselines used** (no internal budget exists for public "
        "companies, so this mirrors what FP&A teams fall back on):\n"
        "- **QoQ** — vs. immediately prior quarter\n"
        "- **YoY** — vs. same quarter last year (seasonality-safe)"
    )
    st.markdown("---")
    api_key_present = bool(os.environ.get("ANTHROPIC_API_KEY"))
    if api_key_present:
        st.success("ANTHROPIC_API_KEY found — AI narrative enabled")
    else:
        st.warning("No ANTHROPIC_API_KEY set — data/variance table still works, narrative disabled")

if not ticker:
    st.stop()

try:
    with st.spinner(f"Pulling {ticker}'s real quarterly filings from SEC EDGAR..."):
        rows = build_variance_table(ticker, num_quarters=num_quarters)
except Exception as e:
    st.error(f"Couldn't load {ticker}: {e}")
    st.stop()

df = pd.DataFrame(rows).set_index("quarter")

st.subheader(f"{ticker} — Actuals ($)")
actuals_cols = [li for li in LINE_ITEMS if li in df.columns]
st.dataframe(
    df[actuals_cols].style.format(lambda v: f"${v/1e9:,.2f}B" if pd.notna(v) else "n/a"),
    use_container_width=True,
)

st.subheader("YoY Variance (%)")
yoy_cols = [f"{li}_yoy_pct" for li in actuals_cols]
yoy_df = df[[c for c in yoy_cols if c in df.columns]].rename(
    columns=lambda c: c.replace("_yoy_pct", "")
)
st.dataframe(
    yoy_df.style.format(lambda v: f"{v*100:+.1f}%" if pd.notna(v) else "n/a")
    .background_gradient(cmap="RdYlGn", axis=None, vmin=-0.3, vmax=0.3),
    use_container_width=True,
)

st.subheader("QoQ Variance (%)")
qoq_cols = [f"{li}_qoq_pct" for li in actuals_cols]
qoq_df = df[[c for c in qoq_cols if c in df.columns]].rename(
    columns=lambda c: c.replace("_qoq_pct", "")
)
st.dataframe(
    qoq_df.style.format(lambda v: f"{v*100:+.1f}%" if pd.notna(v) else "n/a")
    .background_gradient(cmap="RdYlGn", axis=None, vmin=-0.15, vmax=0.15),
    use_container_width=True,
)

st.line_chart(df[["revenue", "operating_income", "net_income"]] / 1e9)

st.subheader("AI Variance Narrative")
if st.button("Generate narrative for latest quarter", type="primary"):
    try:
        with st.spinner("Writing variance commentary..."):
            narrative = generate_variance_narrative(ticker, rows, actuals_cols)
        st.markdown(narrative)
    except RuntimeError as e:
        st.warning(str(e))
