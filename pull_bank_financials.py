"""
Pulls Assets, Liabilities, Stockholders Equity, and Net Income (with fallback tags) 
from the most recent two fiscal years for FCNCA and its peer group.
Outputs the results into a long-format CSV file.

Run: python3 pull_bank_financials.py
Requires: pip install requests
"""

import csv
import time
from datetime import date
import requests

# ==========================================
# CONFIGURATION
# ==========================================

# SEC requires a descriptive User-Agent identifying you and a contact method.
# Requests without one get throttled or blocked.
HEADERS = {"User-Agent": "Robert Cellucci robertwcellucci@protonmail.com"}

# Target company and its peer group
SUBJECT = "FCNCA"
PEERS = ["MTB", "FITB", "HBAN", "RF", "KEY", "CFG", "ZION", "WAL", "EWBC", "WBS"]
TICKERS = [SUBJECT] + PEERS

# Mapping of standard concepts to their possible SEC XBRL tags (in order of preference)
CONCEPT_TAGS = {
    "Assets": ["Assets"],
    "Liabilities": ["Liabilities"], 
    "Equity": ["StockholdersEquityIncludingPortionAttributableToNoncontrollingInterest", "StockholdersEquity"],
    "NetIncome": ["NetIncomeLoss", "ProfitLoss", "NetIncomeLossAvailableToCommonStockholdersBasic"],
}

ALLOWED_FORMS = ("10-K", "10-K/A")
OUTPUT_PATH = "bank_financials_long.csv"


# ==========================================
# API HELPER FUNCTIONS
# ==========================================

def get_cik(ticker: str) -> str:
    """Fetches the 10-digit Central Index Key (CIK) for a given ticker."""
    url = "https://www.sec.gov/files/company_tickers.json"
    response = requests.get(url, headers=HEADERS)
    response.raise_for_status()
    
    ticker_data = response.json()
    ticker_upper = ticker.upper()
    
    for entry in ticker_data.values():
        if entry["ticker"] == ticker_upper:
            # The SEC API requires a zero-padded 10-digit CIK
            return str(entry["cik_str"]).zfill(10)
            
    raise ValueError(f"Ticker '{ticker}' not found in SEC ticker map.")


def get_company_facts(cik: str) -> dict:
    """Pulls all available XBRL company facts for a given CIK from the SEC API."""
    results = None
    try:
        cik_padded = str(cik).zfill(10)
        url = f"https://data.sec.gov/api/xbrl/companyfacts/CIK{cik_padded}.json"
        response = requests.get(url, headers=HEADERS)
        response.raise_for_status()
        results = response.json()
    except requests.HTTPError as error:
        print(f"Skipping CIK {cik}: {error}")
        
    return results


# ==========================================
# DATA PROCESSING FUNCTIONS
# ==========================================

def is_annual_window(entry: dict) -> bool:
    """Checks if the reporting period represents a full fiscal year (roughly 350-380 days)."""
    if "start" not in entry:
        return True
        
    start_date = date.fromisoformat(entry["start"])
    end_date = date.fromisoformat(entry["end"])
    days_in_period = (end_date - start_date).days
    
    return 350 <= days_in_period <= 380


def get_raw_records_for_tag(facts_json: dict, tag: str, require_fiscal_year: bool, taxonomy: str = "us-gaap") -> list[dict]:
    """Extracts raw financial records for a specific XBRL tag."""
    try:
        units = facts_json["facts"][taxonomy][tag]["units"]
    except (KeyError, TypeError):
        return []

    records = []
    for entries in units.values():  # This is almost always "USD"
        for entry in entries:
            if entry.get("form") not in ALLOWED_FORMS:
                continue
            if require_fiscal_year and entry.get("fp") != "FY":
                continue
            if not is_annual_window(entry):
                continue
                
            records.append({
                "source_tag": tag,
                "value": entry.get("val"),
                "end_date": entry.get("end"),
                "filed": entry.get("filed"),
                "accn": entry.get("accn"),
                "sec_fy": entry.get("fy"),
            })
            
    return records


def deduplicate_by_end_date(records: list[dict]) -> list[dict]:
    """
    Keeps only the most recently filed value for each distinct end_date.
    This handles restatements or later 10-Ks re-reporting last year's balance.
    """
    best_records: dict[str, dict] = {}
    for record in records:
        key = record["end_date"]
        # Overwrite if we haven't seen this date, or if this record was filed later
        if key not in best_records or record["filed"] > best_records[key]["filed"]:
            best_records[key] = record
            
    return list(best_records.values())


def extract_concept_records(facts_json: dict, concept: str) -> list[dict]:
    """
    Extracts records for a broad concept (e.g., 'Equity') by checking fallback tags.
    Tags earlier in the CONCEPT_TAGS list take priority for the same period.
    """
    tag_priority = CONCEPT_TAGS[concept]
    merged_records: dict[str, dict] = {}
    
    # Process lowest priority first, so higher-priority tags overwrite them
    for tag in reversed(tag_priority):
        records = get_raw_records_for_tag(facts_json, tag, require_fiscal_year=True)
        if not records:
            records = get_raw_records_for_tag(facts_json, tag, require_fiscal_year=False)
            
        records = deduplicate_by_end_date(records)
        
        for record in records:
            merged_records[record["end_date"]] = record

    formatted_output = []
    for end_date, record in merged_records.items():
        record["concept"] = concept
        record["fiscal_year"] = int(end_date[:4])  # Derive year from the real period end
        formatted_output.append(record)
        
    return formatted_output


def get_most_recent_two_fiscal_years(records: list[dict]) -> set:
    """Anchors on 'Assets' to determine the two most recent fiscal years reported."""
    asset_years = {record["fiscal_year"] for record in records if record["concept"] == "Assets"}
    sorted_years = sorted(asset_years, reverse=True)
    return set(sorted_years[:2])


def deduplicate_same_year(records: list[dict]) -> list[dict]:
    """
    Safety net: If a fiscal year changes or stub periods exist, keep the record 
    with the latest end_date (tie-broken by filed date).
    """
    best_records: dict[tuple, dict] = {}
    for record in records:
        key = (record["fiscal_year"], record["concept"])
        
        is_newer = False
        if key in best_records:
            current_best = (best_records[key]["end_date"], best_records[key]["filed"])
            candidate = (record["end_date"], record["filed"])
            if candidate > current_best:
                is_newer = True
                
        if key not in best_records or is_newer:
            best_records[key] = record
            
    return list(best_records.values())


def add_derived_liabilities(records: list[dict]) -> list[dict]:
    """
    Fallback: If Assets and Equity exist but Liabilities is missing, 
    compute it (Assets - Equity) and flag it as derived.
    """
    records_by_year: dict = {}
    for record in records:
        records_by_year.setdefault(record["fiscal_year"], {})[record["concept"]] = record

    derived_records = []
    for fiscal_year, concepts in records_by_year.items():
        if "Liabilities" in concepts:
            continue
            
        assets = concepts.get("Assets")
        equity = concepts.get("Equity")
        
        if assets and equity:
            derived_records.append({
                "fiscal_year": fiscal_year,
                "concept": "Liabilities",
                "source_tag": "derived_Assets_minus_Equity",
                "value": assets["value"] - equity["value"],
                "end_date": assets["end_date"],
                "filed": assets["filed"],
                "accn": None,
                "sec_fy": None,
            })
            
    return records + derived_records


def sanity_check(rows: list[dict]) -> None:
    """
    Ensures Assets loosely equal Liabilities + Equity for every company-year.
    Flags discrepancies greater than 1% to catch bad pulls before they hit Excel/PowerBI.
    """
    data_by_key: dict[tuple, dict] = {}
    for row in rows:
        data_by_key.setdefault((row["ticker"], row["fiscal_year"]), {})[row["concept"]] = row

    print("\n--- Balance sheet reconciliation check ---")
    
    for (ticker, fiscal_year), values in sorted(data_by_key.items(), key=lambda kv: (kv[0][0], str(kv[0][1]))):
        assets = values.get("Assets")
        liabilities = values.get("Liabilities")
        equity = values.get("Equity")
        
        if not all([assets, liabilities, equity]):
            found_concepts = [key for key, val in values.items() if val]
            print(f"{ticker} FY{fiscal_year}: MISSING a required concept -- have {found_concepts}")
            continue
            
        asset_val = assets["value"]
        liab_val = liabilities["value"]
        equity_val = equity["value"]
        
        diff_pct = abs(asset_val - (liab_val + equity_val)) / asset_val
        
        flag = "  <-- CHECK" if diff_pct > 0.01 else ""
        derived_note = "  (Liabilities derived)" if liabilities["source_tag"].startswith("derived") else ""
        
        print(f"{ticker} FY{fiscal_year}: Assets={asset_val:,} vs L+E={liab_val + equity_val:,} "
              f"(diff {diff_pct:.2%}){flag}{derived_note}")


# ==========================================
# MAIN EXECUTION
# ==========================================

def pull_company_data(ticker: str) -> list[dict]:
    """Executes the full extraction and processing pipeline for a single ticker."""
    print(f"Fetching {ticker}...")
    cik = get_cik(ticker)
    facts = get_company_facts(cik)
    
    if facts is None:
        return []

    company_name = facts.get("entityName", ticker)
    all_records: list[dict] = []

    # 1. Extract records using fallback tags
    for concept in CONCEPT_TAGS:
        concept_records = extract_concept_records(facts, concept)
        if not concept_records:
            print(f"  ! {ticker}: no data found for concept '{concept}' under any fallback tag")
        all_records.extend(concept_records)

    # 2. Deduplicate, filter to recent years, and derive missing liabilities
    all_records = deduplicate_same_year(all_records)
    target_years = get_most_recent_two_fiscal_years(all_records)
    all_records = [record for record in all_records if record["fiscal_year"] in target_years]
    all_records = add_derived_liabilities(all_records)

    # 3. Flag any completely missing data
    retrieved_concepts = {(record["fiscal_year"], record["concept"]) for record in all_records}
    for fiscal_year in target_years:
        for concept in CONCEPT_TAGS:
            if (fiscal_year, concept) not in retrieved_concepts:
                print(f"  ! {ticker} FY{fiscal_year}: MISSING {concept} after all fallbacks")

    # 4. Append metadata to each record
    for record in all_records:
        record["company"] = company_name
        record["cik"] = cik
        record["ticker"] = ticker

    return all_records


def main():
    all_rows: list[dict] = []
    
    for ticker in TICKERS:
        rows = pull_company_data(ticker)
        if not rows:
            print(f"  ! No data pulled for {ticker} -- check manually.")
            
        all_rows.extend(rows)
        time.sleep(0.2)  # Stay comfortably under SEC's rate limit

    sanity_check(all_rows)

    fieldnames = [
        "company", "cik", "ticker", "fiscal_year", "concept", 
        "value", "source_tag", "end_date", "filed", "accn", "sec_fy"
    ]
    
    with open(OUTPUT_PATH, "w", newline="", encoding="utf-8") as file:
        writer = csv.DictWriter(file, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(all_rows)

    print(f"\nWrote {len(all_rows)} rows to {OUTPUT_PATH}")


if __name__ == "__main__":
    main()
