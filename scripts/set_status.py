#!/usr/bin/env python3
"""Set the research status of every candidate row of a scheme (or one candidate id).

  python3 scripts/set_status.py hdfc-2023 complete --note "all legs sourced"
  python3 scripts/set_status.py c0042 duplicate --note "same as hdfc-2023"
"""
import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import CANDIDATE_FIELDS, CANDIDATES, STATUSES, read_csv, write_csv  # noqa: E402


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("key", help="scheme id or candidate_id")
    ap.add_argument("status", choices=STATUSES)
    ap.add_argument("--note", default=None)
    ap.add_argument("--scheme", default=None, help="also re-assign the rows to this scheme id")
    a = ap.parse_args()
    rows = read_csv(CANDIDATES)
    hit = [r for r in rows if a.key in (r["scheme"], r["candidate_id"])]
    if not hit:
        sys.exit(f"no candidate with scheme or id {a.key!r}")
    for r in hit:
        r["status"] = a.status
        if a.note is not None:
            r["status_note"] = a.note
        if a.scheme:
            r["scheme"] = a.scheme
    write_csv(CANDIDATES, rows, CANDIDATE_FIELDS)
    print(f"{len(hit)} row(s) -> {a.status}")


if __name__ == "__main__":
    main()
