#!/usr/bin/env python3
"""Pick the next schemes for research agents.

  python3 scripts/next_batch.py -n 5            # list next 5 pending schemes
  python3 scripts/next_batch.py -n 5 --claim    # ...and mark them in_progress
  python3 scripts/next_batch.py --prompt SCHEME # print the filled agent prompt for one scheme
Order: newest year first (better-documented, matters most to current portfolios).
"""
import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import CANDIDATE_FIELDS, CANDIDATES, ROOT, read_csv, write_csv  # noqa: E402

SHOW = ["candidate_id", "kind_hint", "source_company", "counterparty", "year_hint", "nse_symbol",
        "bse_code", "isin", "ex_date_hint", "discovered_via", "refs"]


def render_prompt(scheme, rows):
    tpl = (ROOT / "prompts" / "research_agent.md").read_text(encoding="utf-8")
    tpl = tpl.split("---", 1)[1] if "---" in tpl else tpl
    lines = []
    for r in rows:
        lines.append("- " + "; ".join(f"{k}={r[k]}" for k in SHOW if r.get(k)))
    return tpl.replace("{{scheme}}", scheme).replace("{{candidate_rows}}", "\n".join(lines)).strip()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("-n", type=int, default=5)
    ap.add_argument("--claim", action="store_true")
    ap.add_argument("--prompt", metavar="SCHEME")
    ap.add_argument("--retry-detected", action="store_true",
                    help="also pick schemes whose status is 'detected'")
    ap.add_argument("--skip-only-from", metavar="SOURCE",
                    help="ignore schemes discovered only via this source (e.g. nse-scheme-filings)")
    ap.add_argument("--write-prompts", metavar="DIR",
                    help="write DIR/prompt_<scheme>.md for each picked scheme")
    a = ap.parse_args()
    rows = read_csv(CANDIDATES)
    by_scheme = {}
    for r in rows:
        by_scheme.setdefault(r["scheme"], []).append(r)
    if a.prompt:
        if a.prompt not in by_scheme:
            sys.exit(f"unknown scheme {a.prompt!r}")
        print(render_prompt(a.prompt, by_scheme[a.prompt]))
        return
    want = {"pending"} | ({"detected"} if a.retry_detected else set())
    ready = [s for s, rs in by_scheme.items() if all(r["status"] in want for r in rs)
             and not (a.skip_only_from and all(r["discovered_via"] == a.skip_only_from
                                               for r in rs))]
    ready.sort(key=lambda s: (-int(by_scheme[s][0]["year_hint"] or 0), s))
    pick = ready[: a.n]
    for s in pick:
        print(s)
        if a.write_prompts:
            d = Path(a.write_prompts)
            d.mkdir(parents=True, exist_ok=True)
            (d / f"prompt_{s}.md").write_text(render_prompt(s, by_scheme[s]), encoding="utf-8")
    if a.claim:
        for r in rows:
            if r["scheme"] in pick:
                r["status"] = "in_progress"
        write_csv(CANDIDATES, rows, CANDIDATE_FIELDS)
        print(f"claimed {len(pick)} scheme(s)", file=sys.stderr)


if __name__ == "__main__":
    main()
