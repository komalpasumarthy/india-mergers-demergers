#!/usr/bin/env python3
"""Download BSE listings of mergers/demergers.

  pip install -r requirements.txt
  python3 scripts/fetch_bse.py mergers-page          # static list, names only (no dates)
  python3 scripts/fetch_bse.py corp-actions --from 2000 --to 2026

mergers-page  -> data/raw/bse_mergers_page.csv
    https://www.bseindia.com/static/about/acompany-mergers  (security code, company, reason).
    The table is hard-coded in the site's Angular JS bundle, so the script walks the bundle's
    chunks to the "app-acompany-mergers" component and reads the template's text literals.
corp-actions  -> data/raw/bse_corp_actions.csv
    The JSON API behind https://www.bseindia.com/corporates/corporate_act.aspx . Purpose text
    such as "Amalgamation", "Scheme of Arrangement", "Demerger" is kept; everything else
    (dividends, bonus, splits) is dropped. Raw responses saved to data/raw/bse_corp_actions_<year>.json.

NOTE: api.bseindia.com sits behind Akamai, which answers 403 to cloud/datacenter IPs; run
corp-actions from a residential connection. The API parameters are the ones the BSE corporate
action page sends (from its JS bundle); FIELD_MAP is unverified - check the saved JSON.
"""
import argparse
import datetime as dt
import json
import re
import sys
import time
from pathlib import Path

import requests

sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import ACTION_RE, RAW, RAW_FIELDS, iso_date, read_csv, write_csv  # noqa: E402

HEADERS = {
    "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) "
                  "Chrome/124.0 Safari/537.36",
    "Accept": "application/json, text/plain, */*",
    "Referer": "https://www.bseindia.com/",
    "Origin": "https://www.bseindia.com",
}
MERGERS_PAGES = ["https://www.bseindia.com/static/about/acompany-mergers.aspx",
                 "https://www.bseindia.com/static/about/a-merger.aspx"]
API = "https://api.bseindia.com/BseIndiaAPI/api/DefaultData/w"
FIELD_MAP = {
    "scrip_code": ["scrip_code", "SCRIP_CODE", "scripcode"],
    "symbol": ["short_name", "ShortName", "scrip_id"],
    "company": ["long_name", "LONG_NAME", "company_name", "short_name"],
    "purpose": ["Purpose", "purpose", "PURPOSE"],
    "ex_date": ["Ex_date", "exdate", "EX_DATE", "Ex_Date"],
    "record_date": ["RD_Date", "BCRD_FROM", "Record_Date", "record_date"],
}


def pick(row, keys):
    for k in keys:
        if row.get(k) not in (None, "", "-"):
            return str(row[k]).strip()
    return ""


JS_BASE = "https://www.bseindia.com/assets/includenew/js/"


def _bundle_chunks(sess, marker, limit=400):
    """BSE's site is an Angular app: page content lives in lazily loaded JS chunks. Walk the
    chunk graph from the page's main bundle and return the text of the chunk containing marker."""
    html = sess.get(MERGERS_PAGES[0], timeout=60).text
    todo = re.findall(r"(main-[A-Z0-9]+\.js|chunk-[A-Z0-9]+\.js)", html)
    seen = set()
    while todo and len(seen) < limit:
        name = todo.pop()
        if name in seen:
            continue
        seen.add(name)
        js = sess.get(JS_BASE + name, timeout=60).text
        if marker in js:
            return js, JS_BASE + name
        todo.extend(set(re.findall(r"chunk-[A-Z0-9]+\.js", js)) - seen)
    raise SystemExit(f"could not find {marker!r} in {len(seen)} BSE JS chunks")


def _template_rows(js, component):
    """Rows of the hard-coded <table> in an Angular component template: each row is the list of
    text literals t(n,"...") between consecutive "tr" element openings."""
    seg = js[js.index(component):]
    nxt = seg.find("selectors:", 50)
    seg = seg if nxt < 0 else seg[:nxt]
    parts = re.split(r'[(,]\d+,"tr"\)', seg)[1:]
    for part in parts:
        cells = [re.sub(r"\\(.)", r"\1", c).strip()
                 for c in re.findall(r't\(\d+,"((?:[^"\\]|\\.)*)"\)', part)]
        if cells:
            yield cells


def mergers_page():
    """BSE 'Company Mergers' list (security code, company, reason). No dates on the page."""
    sess = requests.Session()
    sess.headers.update(HEADERS)
    js, src = _bundle_chunks(sess, "app-acompany-mergers")
    out = []
    for cells in _template_rows(js, "app-acompany-mergers"):
        if cells[0].lower().startswith("security code"):
            continue
        code = cells[0] if re.fullmatch(r"\d{6}", cells[0]) else ""
        rest = cells[1:] if code else cells
        if len(rest) < 2:
            print("skipping odd row:", cells)
            continue
        name, reason = rest[0], " ".join(rest[1:])
        m = re.search(r"(?:amalgamat\w*|merg\w*)\s+(?:with|into)\s+(.*)", reason, re.I)
        out.append(dict(source="bse-mergers-page", exchange="BSE", scrip_code=code, company=name,
                        counterparty=(m.group(1).strip(" .") if m else ""),
                        purpose=reason, kind_hint="MERGER",
                        url=MERGERS_PAGES[0].replace(".aspx", "")))
    path = RAW / "bse_mergers_page.csv"
    write_csv(path, out, RAW_FIELDS)
    print(f"parsed {len(out)} rows from {src}; wrote {path}")


def corp_actions(y0, y1, sleep):
    path = RAW / "bse_corp_actions.csv"
    keep = {(r["scrip_code"], r["purpose"], r["ex_date"]): r for r in read_csv(path)}
    s = requests.Session()
    s.headers.update(HEADERS)
    for year in range(y0, y1 + 1):
        params = {"Fdate": f"{year}0101", "TDate": f"{year}1231", "Purposecode": "",
                  "ddlcategorys": "E", "ddlindustrys": "", "scripcode": "", "segment": "0",
                  "strSearch": "S"}
        r = s.get(API, params=params, timeout=90)
        if r.status_code != 200:
            print(f"{year}: HTTP {r.status_code}")
            continue
        data = r.json()
        rows = data if isinstance(data, list) else data.get("Table", data.get("data", []))
        (RAW / f"bse_corp_actions_{year}.json").write_text(json.dumps(rows, indent=1))
        n = 0
        for row in rows:
            rec = {k: pick(row, v) for k, v in FIELD_MAP.items()}
            if not ACTION_RE.search(rec["purpose"]):
                continue
            rec.update(source="bse-corp-actions", exchange="BSE",
                       ex_date=iso_date(rec["ex_date"]) or rec["ex_date"],
                       record_date=iso_date(rec["record_date"]) or rec["record_date"],
                       url=f"https://www.bseindia.com/stock-share-price/x/x/{rec['scrip_code']}/corp-actions/")
            keep[(rec["scrip_code"], rec["purpose"], rec["ex_date"])] = rec
            n += 1
        print(f"{year}: {len(rows)} corporate actions, {n} scheme-related")
        time.sleep(sleep)
    write_csv(path, sorted(keep.values(), key=lambda r: (r["ex_date"], r["scrip_code"])), RAW_FIELDS)
    print(f"wrote {path} ({len(keep)} rows). Next: python3 scripts/build_candidates.py")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("what", choices=["mergers-page", "corp-actions"])
    ap.add_argument("--from", dest="y0", type=int, default=2000)
    ap.add_argument("--to", dest="y1", type=int, default=dt.date.today().year)
    ap.add_argument("--sleep", type=float, default=1.0)
    a = ap.parse_args()
    if a.what == "mergers-page":
        mergers_page()
    else:
        corp_actions(a.y0, a.y1, a.sleep)


if __name__ == "__main__":
    main()
