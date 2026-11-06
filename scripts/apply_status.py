#!/usr/bin/env python3
"""Apply research results written by agents to data/candidates.csv.

Each agent writes data/status/<scheme>.json:
  {"scheme": "...", "status": "complete|detected|skipped|duplicate", "note": "...",
   "duplicate_of": "<other scheme>" (optional)}
Agents never edit candidates.csv directly (many run in parallel); the orchestrator runs this.
A status file whose scheme has an event file with errors is reported and not applied.
"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import CANDIDATE_FIELDS, CANDIDATES, DATA, EVENTS_DIR, read_csv, write_csv  # noqa
from validate import validate_file  # noqa: E402

STATUS_DIR = DATA / "status"


def main():
    rows = read_csv(CANDIDATES)
    by_scheme = {}
    for r in rows:
        by_scheme.setdefault(r["scheme"], []).append(r)
    applied = 0
    for p in sorted(STATUS_DIR.glob("*.json")):
        try:
            st = json.loads(p.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            print(f"BAD {p.name}: {exc}")
            continue
        scheme = st.get("scheme") or p.stem
        status = st.get("status")
        if scheme not in by_scheme or status not in ("complete", "detected", "skipped",
                                                     "duplicate"):
            print(f"BAD {p.name}: unknown scheme or status {status!r}")
            continue
        ev = EVENTS_DIR / f"{scheme}.json"
        if status in ("complete", "detected"):
            if not ev.exists():
                print(f"BAD {p.name}: status {status} but no {ev.name}")
                continue
            errs, _ = validate_file(ev, expect_scheme=True)
            if errs:
                print(f"BAD {p.name}: {ev.name} has {len(errs)} validation error(s)")
                continue
        note = st.get("note", "")
        if st.get("duplicate_of"):
            note = f"duplicate of {st['duplicate_of']}; {note}".strip("; ")
        for r in by_scheme[scheme]:
            if (r["status"], r["status_note"]) != (status, note):
                r["status"], r["status_note"] = status, note
                applied += 1
    write_csv(CANDIDATES, rows, CANDIDATE_FIELDS)
    print(f"applied {applied} row update(s)")


if __name__ == "__main__":
    main()
