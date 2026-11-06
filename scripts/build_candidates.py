#!/usr/bin/env python3
"""Merge every listing in data/raw/*.csv into data/candidates.csv.

Existing candidate rows (and their research status) are preserved; new listings either enrich a
matching candidate (same company, year within +-1) or become a new `pending` candidate.
Rows whose purpose does not look like a merger/demerger/scheme are ignored.

  python3 scripts/build_candidates.py            # all raw files
  python3 scripts/build_candidates.py --dry-run  # show what would change
"""
import argparse
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import (ACTION_RE, CANDIDATE_FIELDS, CANDIDATES, DEMERGER_RE, MERGER_RE, RAW,  # noqa
                    iso_date, name_tokens, read_csv, slug, write_csv)


def add_list(cell, value):
    vals = [v for v in cell.split(";") if v]
    for v in value.split(";"):
        if v and v not in vals:
            vals.append(v)
    return ";".join(vals)


def year_of(r):
    for k in ("ex_date", "record_date"):
        d = iso_date(r.get(k, ""))
        if d:
            return d[:4]
    return (r.get("year_hint") or "").strip()[:4]


def similar(a, b):
    ta, tb = name_tokens(a), name_tokens(b)
    if not ta or not tb:
        return False
    inter = len(ta & tb)
    return inter / min(len(ta), len(tb)) >= 0.75 and inter / max(len(ta), len(tb)) >= 0.5


WOS_RE = re.compile(r"wholly[\s-]*owned\s+subsidiar", re.I)
# A scheme filing is made 1-2 years before it takes effect: match it to candidates whose
# effective year is from one year before to three years after the filing year.
YEAR_WINDOW = {"nse-scheme-filings": (-1, 3)}


def kind_of(purpose):
    d, m = bool(DEMERGER_RE.search(purpose)), bool(MERGER_RE.search(purpose))
    return "MIXED" if d and m else "DEMERGER" if d else "MERGER" if m else "UNKNOWN"


def similar_any_party(r, c):
    """The filer must be one of the candidate's parties (source or counterparty)."""
    parties = (c["source_company"].split(" / ") + c["counterparty"].split(" / ")
               + [c["source_company"], c["counterparty"]])
    return any(similar(r["company"], p) for p in parties if p)


def find_match(cands, r, year, ex):
    """Best existing candidate for a listing row: same ISIN/symbol/code or similar name, year
    within +-1. Prefers an identical ex-date, then the same year."""
    hits = []
    for c in cands:
        if c["status"] == "duplicate":
            continue
        cy = c["year_hint"]
        lo, hi = YEAR_WINDOW.get(r.get("source"), (-1, 1))
        year_ok = not year or not cy or lo <= int(cy) - int(year) <= hi
        if not year_ok:
            continue
        ids_equal = any(r.get(rk) and r.get(rk) == c.get(ck) for rk, ck in
                        (("isin", "isin"), ("symbol", "nse_symbol"), ("scrip_code", "bse_code")))
        names = c["source_company"].split(" / ") + [c["source_company"]]
        if r.get("source") == "nse-scheme-filings":
            # Each filing is its own scheme: never merge two filings together, and never
            # attach an internal (wholly-owned subsidiary) scheme to a public one.
            if c["discovered_via"].split(";")[0] == "nse-scheme-filings" or WOS_RE.search(
                    r.get("purpose", "")):
                continue
            # the filer may be the acquirer: match on the companies named in the scheme text
            text = name_tokens(r.get("purpose", ""))
            if any(name_tokens(n) and len(name_tokens(n) & text) / len(name_tokens(n)) >= 0.75
                   and similar_any_party(r, c) for n in names):
                hits.append(c)
            continue
        if ids_equal or any(similar(r["company"], n) for n in names):
            hits.append(c)
    if not hits:
        return None
    hits.sort(key=lambda c: (not (ex and c["ex_date_hint"] == ex), c["year_hint"] != year))
    return hits[0]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args()
    cands = read_csv(CANDIDATES)
    next_id = max([int(c["candidate_id"][1:]) for c in cands] or [0]) + 1
    schemes = {c["scheme"] for c in cands}
    added = enriched = ignored = 0
    seen_refs = {x for c in cands for x in c["refs"].split(" || ") if x}
    # seed first (curated groupings), then listings with dates, then filings
    order = {"seed_knowledge.csv": 0, "bse_mergers_page.csv": 1, "nse_corp_actions.csv": 2,
             "bse_corp_actions.csv": 2, "nse_scheme_filings.csv": 3}
    for path in sorted(RAW.glob("*.csv"), key=lambda p: (order.get(p.name, 9), p.name)):
        for r in read_csv(path):
            purpose = r.get("purpose", "")
            if r.get("source") != "seed" and not ACTION_RE.search(purpose):
                ignored += 1
                continue
            year = year_of(r)
            kind = r.get("kind_hint") or kind_of(purpose)
            # one ref per listing row; includes the company so the exact row is recognisable
            ref = f"[{r['source']}] {r['company']}: {purpose.replace(';', ',').replace('||', '/')}"
            if r.get("url"):
                ref += f" <{r['url']}>"
            if ref in seen_refs:
                continue  # merged on an earlier run
            seen_refs.add(ref)
            ex = iso_date(r.get("ex_date", "")) or iso_date(r.get("record_date", ""))
            if r.get("source") == "seed":
                # seed rows are already curated into schemes: add once, never fuzzy-merge
                if any(c["scheme"] == r["scheme_hint"] and c["source_company"] == r["company"]
                       for c in cands):
                    continue
                c = None
            else:
                c = find_match(cands, r, year, ex)
            if c:
                c["discovered_via"] = add_list(c["discovered_via"], r["source"])
                if ref and ref not in c["refs"]:
                    c["refs"] = (c["refs"] + " || " + ref) if c["refs"] else ref
                for rk, ck in (("symbol", "nse_symbol"), ("scrip_code", "bse_code"),
                               ("isin", "isin"), ("counterparty", "counterparty")):
                    if r.get(rk) and not c[ck]:
                        c[ck] = r[rk]
                if ex and not c["ex_date_hint"]:
                    c["ex_date_hint"] = ex
                if year and not c["year_hint"]:
                    c["year_hint"] = year
                enriched += 1
                continue
            scheme = r.get("scheme_hint") or f"{slug(r['company'])}-{year or 'unknown'}"
            base, k = scheme, 2
            while scheme in schemes and not r.get("scheme_hint"):
                scheme, k = f"{base}-{k}", k + 1
            schemes.add(scheme)
            cands.append({
                "candidate_id": f"c{next_id:04d}", "scheme": scheme, "kind_hint": kind,
                "source_company": r["company"], "counterparty": r.get("counterparty", ""),
                "year_hint": year,
                "nse_symbol": r.get("symbol", "") if r.get("exchange") != "BSE" else "",
                "bse_code": r.get("scrip_code", ""), "isin": r.get("isin", ""),
                "ex_date_hint": ex, "discovered_via": r["source"], "refs": ref,
                "status": "pending", "status_note": "",
            })
            if WOS_RE.search(purpose):
                cands[-1]["status"] = "skipped"
                cands[-1]["status_note"] = ("auto-wos: scheme with a wholly-owned subsidiary, usually "
                                            "no shares to public holders; re-open if shares issued")
            next_id += 1
            added += 1
    cands.sort(key=lambda c: c["candidate_id"])
    print(f"added {added}, enriched {enriched}, ignored {ignored} non-scheme rows; "
          f"total {len(cands)} candidates")
    if not a.dry_run:
        write_csv(CANDIDATES, cands, CANDIDATE_FIELDS)


if __name__ == "__main__":
    main()
