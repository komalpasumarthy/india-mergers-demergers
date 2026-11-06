#!/usr/bin/env python3
"""Download NSE equity corporate actions and keep merger/demerger/scheme rows.

  pip install -r requirements.txt
  python3 scripts/fetch_nse.py --from 2000 --to 2026
Writes data/raw/nse_corp_actions.csv (normalised RAW_FIELDS) and the untouched API responses to
data/raw/nse_corp_actions_<year>.json (git-ignored) so the field mapping can be checked.

NSE's JSON API needs the cookies set by its home page and a browser-like User-Agent; it is
rate-limited, so the script sleeps between calls. Endpoint (as used by the NSE website,
Corporate Filings -> Corporate Actions):
  https://www.nseindia.com/api/corporates-corporateActions?index=equities&from_date=DD-MM-YYYY&to_date=DD-MM-YYYY
NOTE: written without network access to NSE from the authoring environment; verify the field
names on the first run (see the saved JSON) and adjust FIELD_MAP if needed.
"""
import argparse
import datetime as dt
import json
import sys
import time
from pathlib import Path

import requests

sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import ACTION_RE, RAW, RAW_FIELDS, iso_date, read_csv, write_csv  # noqa: E402

BASE = "https://www.nseindia.com"
API = BASE + "/api/corporates-corporateActions"
HEADERS = {
    "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) "
                  "Chrome/124.0 Safari/537.36",
    "Accept": "application/json, text/plain, */*",
    "Accept-Language": "en-US,en;q=0.9",
    "Referer": BASE + "/companies-listing/corporate-filings-actions",
}
# normalised field -> candidate keys in the NSE response (first present wins)
FIELD_MAP = {
    "symbol": ["symbol"], "company": ["comp", "companyName", "company"], "isin": ["isin"],
    "purpose": ["subject", "purpose"], "ex_date": ["exDate", "ex_date"],
    "record_date": ["recDate", "recordDate", "record_date"],
}
OUT = RAW / "nse_corp_actions.csv"


def pick(row, keys):
    for k in keys:
        if row.get(k) not in (None, "", "-"):
            return str(row[k]).strip()
    return ""


def session():
    s = requests.Session()
    s.headers.update(HEADERS)
    s.get(BASE, timeout=30)
    s.get(HEADERS["Referer"], timeout=30)
    return s


def fetch_range(s, start, end):
    params = {"index": "equities", "from_date": start.strftime("%d-%m-%Y"),
              "to_date": end.strftime("%d-%m-%Y")}
    for attempt in range(4):
        r = s.get(API, params=params, timeout=60)
        if r.status_code == 200:
            data = r.json()
            return data if isinstance(data, list) else data.get("data", [])
        time.sleep(2 ** (attempt + 1))
        s = session()
    r.raise_for_status()
    return []


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--from", dest="y0", type=int, default=2000)
    ap.add_argument("--to", dest="y1", type=int, default=dt.date.today().year)
    ap.add_argument("--sleep", type=float, default=1.5)
    a = ap.parse_args()
    s = session()
    keep = {(r["symbol"], r["purpose"], r["ex_date"]): r for r in read_csv(OUT)}
    for year in range(a.y0, a.y1 + 1):
        raw_year = []
        for q in range(4):  # quarterly windows keep responses small
            start = dt.date(year, 3 * q + 1, 1)
            end = (dt.date(year, 3 * q + 4, 1) - dt.timedelta(days=1)) if q < 3 \
                else dt.date(year, 12, 31)
            if start > dt.date.today():
                break
            rows = fetch_range(s, start, end)
            raw_year.extend(rows)
            time.sleep(a.sleep)
        (RAW / f"nse_corp_actions_{year}.json").write_text(json.dumps(raw_year, indent=1))
        n = 0
        for row in raw_year:
            rec = {k: pick(row, v) for k, v in FIELD_MAP.items()}
            if not ACTION_RE.search(rec["purpose"]):
                continue
            rec.update(source="nse-corp-actions", exchange="NSE",
                       ex_date=iso_date(rec["ex_date"]) or rec["ex_date"],
                       record_date=iso_date(rec["record_date"]) or rec["record_date"],
                       url=f"{BASE}/get-quotes/equity?symbol={rec['symbol']}")
            keep[(rec["symbol"], rec["purpose"], rec["ex_date"])] = rec
            n += 1
        print(f"{year}: {len(raw_year)} corporate actions, {n} scheme-related")
    write_csv(OUT, sorted(keep.values(), key=lambda r: (r["ex_date"], r["symbol"])), RAW_FIELDS)
    print(f"wrote {OUT} ({len(keep)} rows). Next: python3 scripts/build_candidates.py")


if __name__ == "__main__":
    main()
