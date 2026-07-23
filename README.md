# FP&A Copilot

Quarterly variance analysis on **real SEC XBRL data** for any US public company, with an
AI-generated variance narrative in the voice of an FP&A analyst briefing a CFO. No fictional
companies, no toy numbers — every figure is what the company actually filed with the SEC.

## What it demonstrates

This is a level-up of an earlier FP&A Variance Narrator script into a deployed, interactive
tool. The concept: **structured grounding**. The model never touches raw filings and never
does its own arithmetic — it's handed a pre-computed variance table and asked only to write
commentary from it, with an explicit rule that every number it cites must come from the table.
This is the same division of labor real FP&A teams use between their BI tool (does the math)
and their analyst (writes the "why"), and it's what keeps the AI's output auditable instead of
being a black box that might hallucinate a number.

It also solves a real problem: **there's no public "budget" for a public company** — internal
plans aren't disclosed. So instead of faking one, this uses the two baselines FP&A teams
actually fall back on when no budget is available: quarter-over-quarter and year-over-year
(the seasonality-safe one). Q4 isn't separately reported in XBRL (10-Ks report a 12-month
duration, not 3 months), so it's derived as FY total minus Q1+Q2+Q3 — the standard trick
analysts use to back into a "phantom" Q4.

## How it works

1. **`edgar_quarterly.py`** — looks up a ticker's CIK, pulls the full XBRL company-facts JSON
   from SEC EDGAR (free, no API key, just a User-Agent header), and extracts quarterly
   revenue, gross profit, R&D, SG&A, operating income, and net income. Computes QoQ and YoY
   $ and % variance for each line item.
2. **`narrative.py`** — feeds the computed variance table (not raw filings) to Claude
   (`claude-haiku-4-5`) with a strict grounding instruction, and asks for a CFO-briefing-style
   narrative: materiality-ordered bullets, each with the actual, the variance, and a clearly
   labeled *inference* about the driver (flagged as inference, since the model has no access
   to management commentary — it's reasoning from numbers only).
3. **`app.py`** — Streamlit UI: ticker input, actuals table, color-graded YoY/QoQ variance
   tables, a trendline chart, and a button to generate the narrative.

Verified live against real MSFT and AAPL filings — e.g. MSFT Q3 FY2026 revenue $82.89B
(+18.3% YoY), AAPL Q1 FY2026 revenue $143.76B (+15.7% YoY, +40.3% QoQ reflecting the holiday
quarter) — all pulled live from EDGAR, not hardcoded.

**Grounding fix (2026-07-14):** the prompt tells Claude to state "YoY (or QoQ if YoY is n/a)",
but `rows_to_markdown_table()` only ever encoded YoY per cell — for a recent IPO with < 4
quarters of history (YoY undefined), Claude had no QoQ data to fall back on despite the prompt
promising it. Caught via CRCL (real IPO, June 2025): 3 of 3 recent quarters had YoY n/a while
real QoQ growth (+19.8%, +46.0%) never reached the model. Fixed by including QoQ per cell
alongside YoY. `test_grounding.py` is a regression test for this specific failure mode — it
deliberately targets a low-history ticker rather than MSFT/AAPL, since happy-path tickers can't
exercise the fallback branch.

## Running locally

```bash
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
export ANTHROPIC_API_KEY=your_key_here   # optional — data/variance table works without it
.venv/bin/streamlit run app.py
```

Without an API key, the data and variance tables still work in full; only the "Generate
narrative" button is disabled (it tells you why instead of failing silently).

## To push this to GitHub

```bash
cd /Users/charveepatel/Claude/fpa-copilot
git init
git add .
git commit -m "FP&A Copilot: real-data quarterly variance analysis + AI narrative"
gh repo create fpa-copilot-sec-variance --public --source=. --remote=origin
git push -u origin main
```

(Suggested repo name: `fpa-copilot-sec-variance`.)

## Deploying (free — Streamlit Community Cloud)

1. Push the repo to GitHub (above).
2. Go to [share.streamlit.io](https://share.streamlit.io), sign in with GitHub, click "New app."
3. Point it at this repo, branch `main`, file `app.py`.
4. In the app's "Secrets" settings, add:
   ```
   ANTHROPIC_API_KEY = "your_key_here"
   ```
5. Deploy — you get a public `*.streamlit.app` URL, a clickable resume/portfolio link.
