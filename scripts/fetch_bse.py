#!/usr/bin/env python3
"""Download BSE listings of mergers/demergers.

  pip install -r requirements.txt
  python3 scripts/fetch_bse.py mergers-page          # static list, names only (no dates)
  python3 scripts/fetch_bse.py corp-actions --from 2000 --to 2026

mergers-page  -> data/raw/bse_mergers_page.csv
    https://www.bseindia.com/static/about/acompany-mergers.aspx  (company, scrip code, merged
    into). Every table on the page is parsed generically; columns are mapped by header text.
corp-actions  -> data/raw/bse_corp_actions.csv
    The JSON API behind https://www.bseindia.com/corporates/corporate_act.aspx . Purpose text
    such as "Amalgamation", "Scheme of Arrangement", "Demerger" is kept; everything else
    (dividends, bonus, splits) is dropped. Raw responses saved to data/raw/bse_corp_actions_<year>.json.

NOTE: written without network access to BSE from the authoring environment. The API URL and
field names below are the ones the BSE website uses as far as known; check the saved JSON on the
first run and adjust API / FIELD_MAP if BSE has changed them.
"""
import argparse
import datetime as dt
import json
import re
import sys
import time
from pathlib import Path

import requests
from bs4 import BeautifulSoup

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


def mergers_page():
    out = []
    for url in MERGERS_PAGES:
        r = requests.get(url, headers=HEADERS, timeout=60)
        if r.status_code != 200:
            print(f"{url}: HTTP {r.status_code}")
            continue
        soup = BeautifulSoup(r.text, "html.parser")
        for table in soup.find_all("table"):
            rows = table.find_all("tr")
            if len(rows) < 2:
                continue
            header = [c.get_text(" ", strip=True).lower() for c in rows[0].find_all(["th", "td"])]

            def col(*words):
                for i, h in enumerate(header):
                    if any(w in h for w in words):
                        return i
                return None
            ci_name = col("company", "name")
            ci_code = col("code", "scrip")
            ci_into = col("merged", "amalgamat", "with", "into", "transferee")
            if ci_name is None:
                continue
            for tr in rows[1:]:
                cells = [c.get_text(" ", strip=True) for c in tr.find_all("td")]
                if len(cells) <= ci_name or not cells[ci_name]:
                    continue
                get = (lambda i: cells[i] if i is not None and i < len(cells) else "")
                out.append(dict(source="bse-mergers-page", exchange="BSE",
                                scrip_code=re.sub(r"\D", "", get(ci_code)),
                                company=cells[ci_name], counterparty=get(ci_into),
                                purpose="Amalgamation (BSE mergers list)", url=url))
        print(f"{url}: {len(out)} rows so far")
    path = RAW / "bse_mergers_page.csv"
    write_csv(path, out, RAW_FIELDS)
    print(f"wrote {path}")


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
