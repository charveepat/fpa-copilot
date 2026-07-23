"""Real quarterly financials from SEC EDGAR, reshaped for FP&A variance analysis.

No internal "budget" system exists outside a company's four walls, so this
uses the two variance baselines real FP&A teams actually fall back on when
building a plan-vs-actual view from public data alone:
  - QoQ: this quarter vs. the immediately preceding quarter
  - YoY: this quarter vs. the same quarter last year (the seasonality-safe one)

Q4 isn't separately XBRL-tagged in a 10-K (annual filers report a 12-month
duration, not a 3-month one), so it's derived as FY total minus Q1+Q2+Q3 —
the standard trick analysts use to back into a "phantom" Q4.
"""

from __future__ import annotations

import json
import os
import time
from dataclasses import dataclass
from pathlib import Path

import requests

_CONTACT = os.environ.get("FPACOPILOT_CONTACT", "charveepatel00@gmail.com")
USER_AGENT = f"FPACopilot/0.1 ({_CONTACT})"
TICKERS_URL = "https://www.sec.gov/files/company_tickers.json"
FACTS_URL = "https://data.sec.gov/api/xbrl/companyfacts/CIK{cik:010d}.json"

CACHE_DIR = Path(__file__).resolve().parent / ".cache"
CACHE_DIR.mkdir(exist_ok=True)

LINE_ITEMS: dict[str, list[str]] = {
    "revenue": [
        "RevenueFromContractWithCustomerExcludingAssessedTax",
        "Revenues",
        "RevenueFromContractWithCustomerIncludingAssessedTax",
        "SalesRevenueNet",
    ],
    "cogs": ["CostOfRevenue", "CostOfGoodsAndServicesSold", "CostOfGoodsSold"],
    "gross_profit": ["GrossProfit"],
    "rd_expense": ["ResearchAndDevelopmentExpense"],
    "sga_expense": [
        "SellingGeneralAndAdministrativeExpense",
        "GeneralAndAdministrativeExpense",
    ],
    "sales_marketing_expense": ["SellingAndMarketingExpense"],
    "operating_income": ["OperatingIncomeLoss"],
    "net_income": ["NetIncomeLoss", "ProfitLoss"],
}


def _get(url: str) -> dict:
    resp = requests.get(url, headers={"User-Agent": USER_AGENT}, timeout=30)
    resp.raise_for_status()
    time.sleep(0.11)  # stay under SEC's 10 req/s fair-access limit
    return resp.json()


def lookup_cik(ticker: str) -> int:
    cache_path = CACHE_DIR / "tickers.json"
    if cache_path.exists() and time.time() - cache_path.stat().st_mtime < 7 * 86400:
        data = json.loads(cache_path.read_text())
    else:
        data = _get(TICKERS_URL)
        cache_path.write_text(json.dumps(data))
    ticker = ticker.upper()
    for entry in data.values():
        if entry["ticker"] == ticker:
            return int(entry["cik_str"])
    raise ValueError(f"Ticker {ticker!r} not found in SEC's company list")


def _fetch_facts(cik: int) -> dict:
    cache_path = CACHE_DIR / f"{cik}.json"
    if cache_path.exists() and time.time() - cache_path.stat().st_mtime < 86400:
        return json.loads(cache_path.read_text())
    data = _get(FACTS_URL.format(cik=cik))
    cache_path.write_text(json.dumps(data))
    return data


@dataclass(frozen=True)
class QuarterKey:
    fy: int
    fp: str  # "Q1", "Q2", "Q3", "Q4"

    def label(self) -> str:
        return f"{self.fp} FY{self.fy}"

    def sort_key(self) -> tuple:
        return (self.fy, {"Q1": 1, "Q2": 2, "Q3": 3, "Q4": 4}[self.fp])


def _duration_days(fact: dict) -> int:
    from datetime import date

    start = date.fromisoformat(fact["start"])
    end = date.fromisoformat(fact["end"])
    return (end - start).days


def _extract_concept(facts: dict, tags: list[str]) -> dict[QuarterKey, float]:
    us_gaap = facts.get("facts", {}).get("us-gaap", {})
    for tag in tags:
        concept = us_gaap.get(tag)
        if not concept:
            continue
        units = concept.get("units", {}).get("USD", [])

        quarterly: dict[QuarterKey, float] = {}
        annual: dict[int, float] = {}
        for fact in units:
            if "start" not in fact or "end" not in fact:
                continue
            days = _duration_days(fact)
            fy = fact.get("fy")
            fp = fact.get("fp")
            if fy is None:
                continue
            if 80 <= days <= 100 and fp in ("Q1", "Q2", "Q3") and fact["form"] in ("10-Q", "10-Q/A"):
                key = QuarterKey(fy, fp)
                # later filings (restatements) overwrite earlier ones for the same key
                quarterly[key] = fact["val"]
            elif days >= 355 and fact["form"] in ("10-K", "10-K/A"):
                annual[fy] = fact["val"]

        # derive Q4 = FY - (Q1 + Q2 + Q3), only when all three quarters are present
        for fy, fy_total in annual.items():
            q1 = quarterly.get(QuarterKey(fy, "Q1"))
            q2 = quarterly.get(QuarterKey(fy, "Q2"))
            q3 = quarterly.get(QuarterKey(fy, "Q3"))
            if q1 is not None and q2 is not None and q3 is not None:
                quarterly[QuarterKey(fy, "Q4")] = fy_total - q1 - q2 - q3

        if quarterly:
            return quarterly
    return {}


def get_quarterly_financials(ticker: str) -> dict[str, dict[QuarterKey, float]]:
    """Returns {line_item: {QuarterKey: value}} using real SEC XBRL data."""
    cik = lookup_cik(ticker)
    facts = _fetch_facts(cik)
    return {name: _extract_concept(facts, tags) for name, tags in LINE_ITEMS.items()}


def build_variance_table(ticker: str, num_quarters: int = 8) -> list[dict]:
    """One row per quarter (most recent `num_quarters`), each line item with
    QoQ and YoY variance in $ and %."""
    data = get_quarterly_financials(ticker)
    revenue = data["revenue"]
    if not revenue:
        raise ValueError(f"No quarterly revenue data found for {ticker} on EDGAR")

    all_quarters = sorted(revenue.keys(), key=lambda k: k.sort_key())
    recent = all_quarters[-num_quarters:]

    rows = []
    for i, q in enumerate(recent):
        row = {"quarter": q.label(), "fy": q.fy, "fp": q.fp}
        for line_item, series in data.items():
            val = series.get(q)
            row[line_item] = val

            # QoQ: previous entry in the full sorted series (may be earlier
            # than `recent` if this is the first row we're displaying)
            idx_all = all_quarters.index(q)
            prev_q = all_quarters[idx_all - 1] if idx_all > 0 else None
            prev_val = series.get(prev_q) if prev_q else None
            row[f"{line_item}_qoq_abs"] = (val - prev_val) if (val is not None and prev_val) else None
            row[f"{line_item}_qoq_pct"] = (
                (val - prev_val) / abs(prev_val) if (val is not None and prev_val) else None
            )

            # YoY: same fp, fy - 1
            prior_year_key = QuarterKey(q.fy - 1, q.fp)
            py_val = series.get(prior_year_key)
            row[f"{line_item}_yoy_abs"] = (val - py_val) if (val is not None and py_val) else None
            row[f"{line_item}_yoy_pct"] = (
                (val - py_val) / abs(py_val) if (val is not None and py_val) else None
            )
        rows.append(row)
    return rows


if __name__ == "__main__":
    import sys

    ticker = sys.argv[1] if len(sys.argv) > 1 else "MSFT"
    rows = build_variance_table(ticker, num_quarters=6)
    for r in rows:
        rev = r.get("revenue")
        yoy = r.get("revenue_yoy_pct")
        qoq = r.get("revenue_qoq_pct")
        rev_s = f"${rev/1e9:.2f}B" if rev else "n/a"
        yoy_s = f"{yoy*100:+.1f}%" if yoy is not None else "n/a"
        qoq_s = f"{qoq*100:+.1f}%" if qoq is not None else "n/a"
        print(f"{r['quarter']:>10}  revenue={rev_s:>10}  YoY={yoy_s:>8}  QoQ={qoq_s:>8}")
