# Bank Peer Benchmarking Dashboards

**One bank in an eleven-bank peer group got worse in 2025. Every other bank got better.**

**Author:** Robert W Cellucci
**Stack:** Python 3 · SEC EDGAR XBRL REST API · Power BI (DAX, Power Query) · Excel
**Subject:** First Citizens BancShares (FCNCA) · **Peers:** MTB, FITB, HBAN, RF, KEY, CFG, ZION, WAL, EWBC, WBS

---

## The Finding

Between FY2024 and FY2025, **First Citizens BancShares was the only bank in its peer group whose return on assets declined.** ROA fell 28 basis points, from 1.24% to 0.96%. All ten peers improved.

The ranking consequence is severe. FCNCA entered 2024 as the **3rd most profitable bank of eleven** by ROA and exited 2025 as the **10th of eleven**. It did not lose ground because the peer set stood still — it lost ground because the peer set moved and FCNCA moved the other way.

| Bank | FY2024 ROA | FY2025 ROA | Change |
|---|---:|---:|---:|
| KEY | −0.09% | 0.99% | **+108 bp** |
| WBS | 0.97% | 1.19% | +22 bp |
| RF | 1.20% | 1.36% | +15 bp |
| ZION | 0.88% | 1.01% | +13 bp |
| CFG | 0.69% | 0.81% | +12 bp |
| EWBC | 1.53% | 1.65% | +11 bp |
| MTB | 1.24% | 1.34% | +9 bp |
| FITB | 1.09% | 1.18% | +9 bp |
| WAL | 0.97% | 1.04% | +7 bp |
| HBAN | 0.95% | 0.98% | +3 bp |
| **FCNCA** | **1.24%** | **0.96%** | **−28 bp** |

*(KeyCorp's outlier gain is not organic operating improvement — it reflects recovery from a FY2024 net loss of −$161M tied to securities repositioning. It is included for completeness, but the finding does not depend on it: set KeyCorp aside and all nine remaining peers still improved.)*

### The second half of the finding

The profitability decline did not come with a matching reduction in balance-sheet risk. It came with the opposite.

| Metric | FY2024 | FY2025 |
|---|---:|---:|
| FCNCA equity multiplier (Assets / Equity) | 10.06x | 10.33x |
| Peer mean equity multiplier (10 peers, FCNCA excluded) | 10.14x | 9.43x |
| FCNCA leverage rank (1 = most levered, of 11) | 6th | 3rd |

The peer group **deleveraged** through 2025 — the mean equity multiplier across the ten peers fell 0.71x. FCNCA levered up slightly. So over a single fiscal year, FCNCA moved from the middle of the pack on leverage to the third most levered bank in the group, while simultaneously falling from third to tenth on returns.

Peer averages throughout this project exclude the subject bank, so that FCNCA is never being compared against a mean it is inside of. For reference, the all-eleven mean equity multiplier is 10.14x → 9.52x; the direction and conclusion are unchanged, but the ten-peer figure is the one the dashboard reports and the one used here.

**Returns down, relative leverage up.** That is the quadrant a credit analyst screens for, and it is visible in twelve months of two balance-sheet line items and one income-statement line item.

The cross-sectional relationship supports the same reading: leverage and ROA are negatively correlated across the peer group in both years (r = −0.18 in FY2024, r = −0.36 in FY2025). In this sample, leverage is not buying returns.

---

## Dashboards

### Power BI — Core Dashboard

The subject-versus-peers view. KPI cards report FCNCA's absolute metric alongside its position in the peer distribution, so a single glance answers both "what is it" and "is that good."

![Core Dashboard — FCNCA total assets, ROA versus peer average, equity multiplier, and peer ranks, with an ROA-versus-leverage scatter](images/core_dashboard.png)

The scatter on the right plots equity multiplier against ROA for all eleven banks, with FCNCA isolated by the `is_subject` flag (dark marker). This is the visual that carries the finding: FCNCA sits right of center on leverage without a corresponding position on returns.

### Power BI — Year to Year Financials

The same measures re-pointed at a single-company drill, so any peer can be inspected on the same basis rather than only in aggregate.

![Year to Year Financials page — per-company drill with fiscal year and ticker slicers](images/financials_year_to_year_dashboard.png)

Shown here: Citizens Financial Group (CFG), FY2024 — 0.69% ROA, peer rank 10 of 11. The peer rank measure responds to the slicer selection rather than being hardcoded to the subject bank, which is what makes the page reusable across all eleven tickers.

### Excel — Head-to-Head Scorecard

A two-column comparison that pits FCNCA against any peer selected from a dropdown, for any fiscal year.

![Excel Scorecard comparing HBAN against FCNCA for FY2024 across assets, equity, liabilities, net income, ROA, and leverage ratio](images/Scorecard.png)

### Excel — Interactive Wide Table

The full peer set, both years, with computed ratio columns, conditional formatting, slicers, and a year-over-year net income comparison chart.

![Bank Financials Wide pivot table with leverage ratio and ROA columns, conditional formatting, slicers, and a net income bar chart](images/Bank_Financials_wide_image.png)

---

## Repository Structure

```
├── pull_bank_financials.py                                  # SEC EDGAR XBRL extraction pipeline
├── source/bank_financials_long.csv                          # Pipeline output — 88 rows, tidy long format
├── bank_peer_scorecard.xlsx                                 # Excel layer: Scorecard, wide pivot, source table
├── Regional Bank Peer Benchmarking Dashboard (Power BI).pbix
├── images/                                                  # Dashboard screenshots used in this README
├── LICENSE                                                  # MIT
└── README.md
```

---

## The Data Pipeline

`pull_bank_financials.py` pulls four concepts — Assets, Liabilities, Equity, and Net Income — for eleven tickers across the two most recent fiscal years, directly from the SEC's XBRL `companyfacts` REST API. It resolves each ticker to a zero-padded 10-digit CIK, requests the full facts payload, and filters down to annual figures.

The interesting engineering is in the filtering, because raw XBRL is not clean.

### Problem 1: There is no single universal tag per concept

Shareholders' equity is reported under either `StockholdersEquity` or `StockholdersEquityIncludingPortionAttributableToNoncontrollingInterest`. Net income has at least three plausible tags. A single-tag pull silently drops filers.

The script defines an **ordered fallback list** per concept and merges lowest-priority first, so higher-priority tags overwrite:

```python
CONCEPT_TAGS = {
    "Assets":      ["Assets"],
    "Liabilities": ["Liabilities"],
    "Equity":      ["StockholdersEquityIncludingPortionAttributableToNoncontrollingInterest",
                    "StockholdersEquity"],
    "NetIncome":   ["NetIncomeLoss", "ProfitLoss",
                    "NetIncomeLossAvailableToCommonStockholdersBasic"],
}
```

This achieves 100% coverage — 88 of 88 expected company-year-concept cells populated, zero gaps.

Two things to be precise about, because they are easy to overstate. First, the ordering means a filer that reports **both** equity tags resolves to the NCI-inclusive one; the split observed in the output is therefore partly a consequence of this priority order, not purely a statement about filer behavior. Second, in practice the fallbacks were barely exercised: all 22 net income values resolved from `NetIncomeLoss`, and no company-year needed the second or third tag. The fallback list is insurance that did not have to pay out on this peer set. Both points are revisited under Limitations.

### Problem 2: The same fiscal year appears more than once

A 10-K reports both the current year and the prior year as a comparative. Restatements and amended filings add further duplicates. Pulling naively yields multiple conflicting values for the same period.

Two deduplication passes handle this. `deduplicate_by_end_date` keeps only the **most recently filed** value for each distinct period end, so restatements win over originals. `deduplicate_same_year` then guards against fiscal-year changes and stub periods by keeping the latest `end_date`, tie-broken by filing date.

### Problem 3: Annual versus quarterly windows

Duration-type facts carry start and end dates. `is_annual_window` computes the span and keeps only periods of 350–380 days, which excludes quarterly and transition-period facts that would otherwise contaminate the net income series. Instant-type facts (Assets, Equity) carry no start date and pass through.

### Problem 4: Missing liabilities

Some filers omit a total `Liabilities` tag entirely. When Assets and Equity are both present, `add_derived_liabilities` computes the difference and writes it with `source_tag = "derived_Assets_minus_Equity"` — **flagged in the output**, not silently imputed, so any downstream consumer can filter derived values out.

For this peer set the fallback did not fire: all 22 company-year Liabilities values resolved from the `Liabilities` tag directly. It is defensive code, and the output confirms it was not needed here.

### Validation: the balance sheet has to balance

Before writing the CSV, `sanity_check` verifies **Assets = Liabilities + Equity** for every company-year and prints any discrepancy over 1%.

```
FCNCA FY2024: Assets=223,720,000,000 vs L+E=223,720,000,000 (diff 0.00%)
```

Across all 22 company-years the maximum observed discrepancy is **0.00062%** (6.2 × 10⁻⁶ expressed as a fraction), attributable to rounding at the reporting-unit level. This is the check that catches a bad pull before it reaches Power BI, where a wrong number looks exactly as authoritative as a right one.

---

## Power BI Model

A two-table star schema rather than a flat import, which is what makes the peer-relative measures possible.

| Table | Role | Key columns |
|---|---|---|
| `DIM_Company` | Dimension | `company`, `ticker`, `is_subject` |
| `Facts` | Fact table | `fiscal_year`, concept values |

The `is_subject` boolean flag on the dimension is the design decision that does the most work. It lets a single measure compute a peer average that **excludes the subject bank**, rather than comparing FCNCA against an average that FCNCA is inside of. Verified: the dashboard's FY2024 peer average of 0.95% matches the mean of the ten non-FCNCA banks (0.945%), not the eleven-bank mean (0.972%).

### Measures

| Measure | Purpose |
|---|---|
| `Total Assets` | Subject bank asset base |
| `ROA %` | Net income ÷ assets |
| `Equity Multiplier` | Assets ÷ equity |
| `Peer Avg ROA` | Mean ROA across peers, subject excluded |
| `Peer Rank` | Descending rank on ROA % within the fiscal year |
| `Peer Rank (Equity Multiplier)` | Descending rank on leverage within the fiscal year |

Ranks are computed within the fiscal-year filter context, so switching the year slicer re-ranks the entire group rather than returning a stale ordering. Ranks are taken across all eleven banks — the subject is excluded from *averages*, not from *rankings*, since a rank of "3rd of 11" is only meaningful if the subject is one of the eleven.

---

## Excel Layer

The Excel workbook is deliberately built on the same long-format CSV, not a pre-pivoted extract, so the lookup logic has to do real work.

| Sheet | Purpose |
|---|---|
| **Scorecard** | Head-to-head comparison: selected peer versus FCNCA for a selected fiscal year |
| **bank_financials_wide_full** | PivotTable over the full peer set with computed ratio columns, slicers, and a net income chart |
| **bank_financials_long** | The pipeline output as an Excel Table — the single source both sheets read from |

### Three-condition lookup without a helper column

Pulling one value out of tidy long data requires matching on ticker **and** fiscal year **and** concept simultaneously. Standard `VLOOKUP` and `XLOOKUP` handle one criterion. The Scorecard uses boolean multiplication inside `MATCH` to build a composite key on the fly:

```excel
=INDEX(bank_financials_long[value],
   MATCH(1,
     (bank_financials_long[ticker]      = B$3) *
     (bank_financials_long[fiscal_year] = $B$2) *
     (bank_financials_long[concept]     = IF($A4="NetIncomeLoss","NetIncome",$A4)),
   0))
```

Each comparison returns a TRUE/FALSE array; multiplying them coerces to 1/0 and yields 1 only on the row satisfying all three conditions. The nested `IF` reconciles the display label (`NetIncomeLoss`, the XBRL tag name) with the stored concept value (`NetIncome`) so the row labels can stay filing-accurate without breaking the match.

The ROA and Leverage Ratio rows run the same lookup twice and divide, so the ratios are derived live from the long table rather than from the displayed cells above them — the two rows are independent of each other and of any manual entry.

The fiscal year in `B2` is driven by a data-validation list; the peer ticker in `B3` is driven by a second data-validation list sourced from the `ticker` column of the long table. The entire scorecard — including derived ROA and leverage ratio — recalculates on a single cell change. See Known Issues for a caveat on how that second list is currently defined.

### Wide table

The PivotTable is built over the `bank_financials_long` table (88 records) and carries `IFERROR`-wrapped ratio columns (`=IFERROR(B6/C6,"")`) so that a missing denominator produces a blank rather than `#DIV/0!` polluting the conditional formatting scale. Row and column grand totals are suppressed, since a grand total of a ratio column would be meaningless. Slicers on `fiscal_year` and `company` filter both the table and the linked net income chart together.

---

## Limitations

Stated plainly, because each one bounds what the finding can claim.

**ROA uses year-end assets, not average assets.** Standard practice is to divide net income by *average* assets over the period, since income is earned across the year while the balance sheet is a point-in-time snapshot. This dashboard uses period-end assets. For a bank growing assets, that understates ROA slightly. The bias is consistent across all eleven banks and both years, so relative comparisons and rank orderings hold — but the absolute ROA figures are not directly comparable to a bank's published ROA.

**Four banks resolve to an NCI-inclusive equity tag, and the resulting bias runs toward the conclusion.** HBAN, RF, WAL, and WBS resolve to `StockholdersEquityIncludingPortionAttributableToNoncontrollingInterest`; the other seven, including FCNCA, resolve to `StockholdersEquity`. NCI-inclusive equity is the larger figure, so those four banks' equity multipliers are biased marginally *downward*, which pulls the peer mean down and therefore makes FCNCA look marginally *more* levered relative to peers than a like-for-like comparison would.

Noting that FCNCA uses the plain tag is not sufficient defense, because the finding is relative. The finding survives a direct sensitivity test instead: stripping an assumed noncontrolling interest of 1% and then 3% of reported equity from all four banks — well above typical NCI levels for regional bank holding companies — leaves FCNCA's leverage rank at 6th in FY2024 and 3rd in FY2025 in both cases, and leaves the peer mean falling year over year in both cases. The ranking result is not an artifact of tag selection.

Year-over-year comparisons within any single bank are unaffected regardless, since each bank resolves to the same tag in both years.

**FY2024 figures are comparative-period restatements.** All 88 rows come from a single accession per ticker — the FY2025 10-K. FY2024 values are the prior-year comparatives as restated in that filing, not the figures originally published in the FY2024 10-K. This is the correct choice for consistency, but it is not "what the market saw in early 2025."

**No income-statement decomposition.** The pipeline pulls net income as a single line. It can establish *that* FCNCA's returns fell while peers' rose; it cannot establish *why*. Net interest margin compression, credit provisioning, non-interest expense, and one-time items are all candidate drivers, and separating them would require pulling the full income statement.

**Accounting leverage, not regulatory capital.** Assets ÷ Equity is not Tier 1, is not risk-weighted, and says nothing about asset quality. This is a screening ratio, not a capital adequacy assessment.

**Small sample, short window.** Eleven banks, two fiscal years. The negative leverage-to-ROA correlation (r = −0.18 and −0.36) is directionally consistent with the broader 242-bank sample in the companion [Bank Leverage & Efficiency Dashboard](https://github.com/robertwcellucci/Bank-Leverage-Efficiency-Dashboard) project (r = −0.30), but at n = 11 it is not independently significant.

---

## Reproducing

```bash
pip install requests
python3 pull_bank_financials.py
```

The SEC requires a descriptive `User-Agent` header identifying the requester and a contact method; requests without one are throttled or blocked. Update `HEADERS` in the script before running. The script sleeps 0.2s between tickers to stay under the SEC's rate limit.

Output is written to `bank_financials_long.csv` in the working directory; the tracked copy in this repository sits at `source/bank_financials_long.csv`. Both the Excel workbook and the Power BI model read from that file — refresh the Power Query connection and the workbook's source table to update the dashboards.

To retarget the analysis at a different subject bank, change `SUBJECT` and `PEERS` at the top of the script, then update the `is_subject` flag in `DIM_Company` and re-point the Scorecard's `B3` data validation (see Known Issues).

---

## Data Source

U.S. Securities and Exchange Commission, XBRL `companyfacts` API — `https://data.sec.gov/api/xbrl/companyfacts/CIK##########.json`. Form types restricted to 10-K and 10-K/A. All figures as filed; no manual adjustments.

---

## License

MIT — see [LICENSE](LICENSE).
