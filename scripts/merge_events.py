#!/usr/bin/env python3
"""Combine data/events/<scheme>.json into data/events.json (the app file) and data/events.csv
(one row per leg, for spreadsheets). Run after agents finish a batch."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import EVENTS_CSV, EVENTS_DIR, EVENTS_JSON, dump_json, load_json, write_csv  # noqa
from validate import validate_file  # noqa: E402

LEG_COLS = ["target_ticker", "target_isin", "target_name", "target_aliases", "instrument", "ratio",
            "cost_share_pct", "listing_date", "face_value", "cash_per_share"]
EVENT_COLS = ["scheme", "step", "kind", "source_ticker", "source_isin", "source_name",
              "source_aliases", "source_continues", "ex_date", "record_date", "last_trading_date",
              "status", "terms_source", "notes"]


def main():
    events, bad = [], []
    for p in sorted(EVENTS_DIR.glob("*.json")):
        errs, _ = validate_file(p, expect_scheme=True)
        if errs:
            bad.append(p.name)
            continue
        events.extend(load_json(p)["events"])
    events.sort(key=lambda e: (e.get("ex_date") or "9999", e["scheme"], e["step"],
                               e["source_ticker"]))
    dump_json(EVENTS_JSON, {"events": events})
    rows = []
    for e in events:
        for i, leg in enumerate(e["legs"]):
            r = {k: e.get(k) for k in EVENT_COLS}
            r.update({k: leg.get(k) for k in LEG_COLS})
            r["leg"] = i + 1
            for k in ("source_aliases", "target_aliases"):
                r[k] = "|".join(r[k] or [])
            rows.append({k: ("" if v is None else v) for k, v in r.items()})
    write_csv(EVENTS_CSV, rows, EVENT_COLS + ["leg"] + LEG_COLS)
    print(f"merged {len(events)} event(s) into {EVENTS_JSON.name} / {EVENTS_CSV.name}")
    if bad:
        print("SKIPPED (fix with validate.py):", ", ".join(bad))
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
