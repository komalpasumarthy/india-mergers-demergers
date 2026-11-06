#!/usr/bin/env python3
"""Merge every listing in data/raw/*.csv into data/candidates.csv.

Existing candidate rows (and their research status) are preserved; new listings either enrich a
matching candidate (same company, year within +-1) or become a new `pending` candidate.
Rows whose purpose does not look like a merger/demerger/scheme are ignored.

  python3 scripts/build_candidates.py            # all raw files
  python3 scripts/build_candidates.py --dry-run  # show what would change
"""
import argparse
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


def find_match(cands, r, year, ex):
    """Best existing candidate for a listing row: same ISIN/symbol/code or similar name, year
    within +-1. Prefers an identical ex-date, then the same year."""
    hits = []
    for c in cands:
        if c["status"] == "duplicate":
            continue
        cy = c["year_hint"]
        year_ok = not year or not cy or abs(int(year) - int(cy)) <= 1
        if not year_ok:
            continue
        ids_equal = any(r.get(rk) and r.get(rk) == c.get(ck) for rk, ck in
                        (("isin", "isin"), ("symbol", "nse_symbol"), ("scrip_code", "bse_code")))
        names = [c["source_company"]] + c["source_company"].split(" / ")
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
    for path in sorted(RAW.glob("*.csv")):
        for r in read_csv(path):
            purpose = r.get("purpose", "")
            if r.get("source") != "seed" and not ACTION_RE.search(purpose):
                ignored += 1
                continue
            year = year_of(r)
            kind = r.get("kind_hint") or ("DEMERGER" if DEMERGER_RE.search(purpose) else
                                          "MERGER" if MERGER_RE.search(purpose) else "UNKNOWN")
            ref = "; ".join(x for x in (r.get("url", ""), purpose.replace(";", ",")) if x)
            ex = iso_date(r.get("ex_date", "")) or iso_date(r.get("record_date", ""))
            if r.get("source") == "seed":
                # seed rows are already curated into schemes: add once, never fuzzy-merge
                if any(c["scheme"] == r["scheme_hint"] and c["source_company"] == r["company"]
                       for c in cands):
                    continue
                c = None
            else:
                c = find_match(cands, r, year, ex)
            if c and r["source"] in c["discovered_via"].split(";") and ref and ref in c["refs"]:
                continue  # this exact listing was merged on an earlier run
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
            next_id += 1
            added += 1
    cands.sort(key=lambda c: c["candidate_id"])
    print(f"added {added}, enriched {enriched}, ignored {ignored} non-scheme rows; "
          f"total {len(cands)} candidates")
    if not a.dry_run:
        write_csv(CANDIDATES, cands, CANDIDATE_FIELDS)


if __name__ == "__main__":
    main()
