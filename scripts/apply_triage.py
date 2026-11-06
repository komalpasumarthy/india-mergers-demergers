#!/usr/bin/env python3
"""Apply triage verdicts (data/triage/out_*.json) for filing-only candidates.

verdict "skip"     -> status skipped, note "triage: <reason>" (only if still pending)
verdict "research" -> stays pending; fills kind_hint / counterparty if they were unknown.
"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import CANDIDATE_FIELDS, CANDIDATES, DATA, read_csv, write_csv  # noqa: E402


def main():
    rows = read_csv(CANDIDATES)
    by_id = {r["candidate_id"]: r for r in rows}
    n = {"skip": 0, "research": 0, "missing": 0}
    for p in sorted((DATA / "triage").glob("out_*.json")):
        for t in json.loads(p.read_text(encoding="utf-8")):
            r = by_id.get(t.get("candidate_id"))
            if not r:
                n["missing"] += 1
                continue
            if r["status"] != "pending":
                continue
            if t.get("verdict") == "skip":
                r["status"] = "skipped"
                r["status_note"] = "triage: " + (t.get("reason") or "")
                n["skip"] += 1
            else:
                if r["kind_hint"] in ("", "UNKNOWN") and t.get("kind_hint"):
                    r["kind_hint"] = t["kind_hint"]
                if not r["counterparty"] and t.get("counterparty"):
                    r["counterparty"] = t["counterparty"]
                n["research"] += 1
    write_csv(CANDIDATES, rows, CANDIDATE_FIELDS)
    print(n)


if __name__ == "__main__":
    main()
