# FP&A Copilot

**Quarterly variance analysis on real SEC filings — for any US public company.**

Pulls a company's actual quarterly numbers straight from SEC EDGAR, computes QoQ and YoY variance, and (optionally) writes an FP&A-style variance narrative in the voice of an analyst briefing a CFO. No fictional companies, no toy numbers — every figure is what the company actually filed.

### ▶ Live demo — [charveepat-fpa-copilot.streamlit.app](https://charveepat-fpa-copilot.streamlit.app)

Type any ticker (MSFT, AAPL, NVDA, …) and it pulls the real filings live. The public demo runs without an API key: the data, variance tables, and trend chart all work; the AI narrative is gated behind a key (below).

---

## What it demonstrates

**Structured grounding.** The model never touches raw filings and never does its own arithmetic. It's handed a pre-computed variance table and asked only to write the commentary, under an explicit rule that every number it cites must trace back to a cell in that table. This is the same division of labor a real FP&A team uses between the BI tool (does the math) and the analyst (writes the "why") — and it's what keeps the output auditable instead of a black box that might hallucinate a figure.

**No fake budget.** Public companies don't disclose internal plans, so there's no real "budget vs. actual." Rather than invent one, this uses the two baselines FP&A teams actually fall back on: quarter-over-quarter and year-over-year (the seasonality-safe one). Q4 isn't separately tagged in XBRL — 10-Ks report a 12-month duration, not 3 months — so it's derived as FY total minus Q1+Q2+Q3, the standard way analysts back into a "phantom" Q4.

## How it works

| File | Role |
|------|------|
| `edgar_quarterly.py` | Looks up the ticker's CIK, pulls the full XBRL company-facts JSON from SEC EDGAR (free, no API key — just a User-Agent header), extracts quarterly revenue, gross profit, R&D, SG&A, operating income, and net income, and computes QoQ/YoY variance in $ and %. |
| `narrative.py` | Feeds the *computed variance table* (never raw filings) to Claude with a strict grounding instruction, and asks for a CFO-briefing narrative: materiality-ordered bullets, each with the actual, the variance, and a clearly-labeled driver *inference*. |
| `app.py` | Streamlit UI — ticker input, actuals table, color-graded YoY/QoQ variance tables, a chronological trend chart, and the narrative generator. |

Verified live against real filings — e.g. MSFT Q3 FY2026 revenue $82.89B (+18.3% YoY), AAPL Q1 FY2026 revenue $143.76B (+40.3% QoQ, reflecting the holiday quarter) — all pulled live from EDGAR, nothing hardcoded.

## A real bug this caught

The prompt tells the model to state "YoY, or QoQ if YoY is n/a" — but the table builder originally encoded only YoY per cell. For a recent IPO with under four quarters of history (YoY undefined), the model had no QoQ to fall back on despite the prompt promising it. Found via CRCL (Circle, IPO June 2025): three recent quarters showed YoY n/a while real QoQ growth (+19.8%, +46.0%) never reached the model. Fixed by encoding QoQ per cell alongside YoY. `test_grounding.py` is a regression test for exactly this failure mode — it deliberately targets a low-history ticker, since a mature filer like MSFT can never exercise the fallback branch.

## Run locally

```bash
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
export ANTHROPIC_API_KEY=your_key_here   # optional — everything except the AI narrative works without it
.venv/bin/streamlit run app.py
```

Without a key, the data and variance tables work in full; the narrative section shows the exact grounded table that *would* be sent to the model, so you can see the grounding design even without generating commentary.

## Stack

Python · Streamlit · pandas · SEC EDGAR XBRL API · Anthropic Claude (`claude-haiku-4-5`) · Altair
