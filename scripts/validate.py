#!/usr/bin/env python3
"""Validate event files against prompts/filling_rules.md.

Usage:
  python3 scripts/validate.py                    # every file in data/events/ + data/events.json
  python3 scripts/validate.py data/events/x.json # specific files
Exit code 1 if any ERROR. WARN lines are advisory.
"""
import datetime as dt
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import EVENTS_DIR, EVENTS_JSON  # noqa: E402

EVENT_KEYS = ["scheme", "step", "kind", "source_ticker", "source_isin", "source_name",
              "source_aliases", "source_continues", "ex_date", "record_date",
              "last_trading_date", "status", "terms_source", "notes", "legs"]
LEG_KEYS = ["target_ticker", "target_isin", "target_name", "target_aliases", "instrument",
            "ratio", "cost_share_pct", "listing_date", "face_value", "cash_per_share"]
ISIN_RE = re.compile(r"^IN[A-Z0-9]{9}[0-9]$")
RATIO_RE = re.compile(r"^\d+(\.\d+)?:\d+(\.\d+)?$")
SCHEME_RE = re.compile(r"^[a-z0-9]+(-[a-z0-9]+)*$")
T1_START = dt.date(2023, 1, 27)


def isin_checksum_ok(isin: str) -> bool:
    digits = "".join(str(int(c, 36)) for c in isin[:-1])
    total = 0
    for i, d in enumerate(reversed(digits)):
        n = int(d) * (2 if i % 2 == 0 else 1)
        total += n // 10 + n % 10
    return (10 - total % 10) % 10 == int(isin[-1])


def parse_date(v, where, errs, nullable=True):
    if v is None:
        if not nullable:
            errs.append(f"{where}: must not be null")
        return None
    if not isinstance(v, str):
        errs.append(f"{where}: must be a YYYY-MM-DD string")
        return None
    try:
        d = dt.date.fromisoformat(v)
        if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", v):
            raise ValueError
    except ValueError:
        errs.append(f"{where}: invalid date {v!r}")
        return None
    if not dt.date(2000, 1, 1) <= d <= dt.date.today() + dt.timedelta(days=400):
        errs.append(f"{where}: date {v} outside 2000..next year")
    return d


def check_isin(v, where, errs, warns):
    if v is None:
        return
    if not isinstance(v, str) or not ISIN_RE.match(v):
        errs.append(f"{where}: invalid ISIN {v!r}")
    elif not isin_checksum_ok(v):
        errs.append(f"{where}: ISIN {v} fails its check digit")
    elif not v.startswith("INE"):
        warns.append(f"{where}: ISIN {v} does not start with INE")


def validate_event(e, where, errs, warns):
    if not isinstance(e, dict):
        errs.append(f"{where}: event must be an object")
        return
    for k in EVENT_KEYS:
        if k not in e:
            errs.append(f"{where}: missing key {k!r}")
    for k in e:
        if k not in EVENT_KEYS:
            errs.append(f"{where}: unknown key {k!r}")
    kind = e.get("kind")
    if not isinstance(e.get("scheme"), str) or not SCHEME_RE.match(e.get("scheme", "")):
        errs.append(f"{where}: scheme must be a lowercase id like 'hdfc-2023'")
    if not isinstance(e.get("step"), int) or isinstance(e.get("step"), bool) or e.get("step", 0) < 1:
        errs.append(f"{where}: step must be an integer >= 1")
    if kind not in ("MERGER", "DEMERGER"):
        errs.append(f"{where}: kind must be MERGER or DEMERGER")
    if not e.get("source_ticker"):
        errs.append(f"{where}: source_ticker required")
    if not e.get("source_name"):
        errs.append(f"{where}: source_name required")
    check_isin(e.get("source_isin"), f"{where}.source_isin", errs, warns)
    if e.get("source_isin") is None:
        warns.append(f"{where}: source_isin is null")
    for k in ("source_aliases",):
        if not isinstance(e.get(k), list) or not all(isinstance(x, str) for x in e.get(k, [])):
            errs.append(f"{where}: {k} must be a list of strings")
    sc = e.get("source_continues")
    if kind == "MERGER" and sc is not False:
        errs.append(f"{where}: MERGER requires source_continues false")
    if kind == "DEMERGER" and sc is not True:
        errs.append(f"{where}: DEMERGER requires source_continues true")

    ex = parse_date(e.get("ex_date"), f"{where}.ex_date", errs)
    rd = parse_date(e.get("record_date"), f"{where}.record_date", errs)
    ltd = parse_date(e.get("last_trading_date"), f"{where}.last_trading_date", errs)
    if kind == "DEMERGER" and e.get("last_trading_date") is not None:
        errs.append(f"{where}: last_trading_date must be null for a DEMERGER")
    if kind == "MERGER" and e.get("last_trading_date") is None:
        warns.append(f"{where}: MERGER without last_trading_date")
    if ex and rd:
        if ex > rd:
            errs.append(f"{where}: ex_date {ex} is after record_date {rd}")
        if rd >= T1_START and ex != rd:
            warns.append(f"{where}: T+1 era (record date {rd}) but ex_date != record_date")
        if rd < T1_START and ex == rd:
            warns.append(f"{where}: T+2 era but ex_date == record_date (expected one trading day earlier)")
        if (rd - ex).days > 5:
            warns.append(f"{where}: ex_date is {(rd - ex).days} days before record_date")
    if ex and ltd and ltd >= ex:
        errs.append(f"{where}: last_trading_date {ltd} must be before ex_date {ex}")

    if not isinstance(e.get("terms_source"), str):
        errs.append(f"{where}: terms_source must be a string")
    elif "http" not in e["terms_source"]:
        (errs if e.get("status") == "complete" else warns).append(
            f"{where}: terms_source has no URL")
    if not isinstance(e.get("notes"), str):
        errs.append(f"{where}: notes must be a string")

    legs = e.get("legs")
    if not isinstance(legs, list) or not legs:
        errs.append(f"{where}: legs must be a non-empty list")
        return
    equity_costs, incomplete = [], False
    for j, leg in enumerate(legs):
        lw = f"{where}.legs[{j}]"
        if not isinstance(leg, dict):
            errs.append(f"{lw}: leg must be an object")
            continue
        for k in LEG_KEYS:
            if k not in leg:
                errs.append(f"{lw}: missing key {k!r}")
        for k in leg:
            if k not in LEG_KEYS:
                errs.append(f"{lw}: unknown key {k!r}")
        if not leg.get("target_name"):
            errs.append(f"{lw}: target_name required")
        check_isin(leg.get("target_isin"), f"{lw}.target_isin", errs, warns)
        if not isinstance(leg.get("target_aliases"), list):
            errs.append(f"{lw}: target_aliases must be a list")
        inst = leg.get("instrument")
        if inst not in ("equity", "preference"):
            errs.append(f"{lw}: instrument must be equity or preference")
        ratio = leg.get("ratio")
        if ratio is None:
            incomplete = True
        elif not isinstance(ratio, str) or not RATIO_RE.match(ratio):
            errs.append(f"{lw}: ratio must look like 'held:received', got {ratio!r}")
        elif any(float(x) == 0 for x in ratio.split(":")):
            errs.append(f"{lw}: ratio has a zero side")
        cost = leg.get("cost_share_pct")
        if cost is not None and (not isinstance(cost, (int, float)) or isinstance(cost, bool)
                                 or not 0 <= cost <= 100):
            errs.append(f"{lw}: cost_share_pct must be a number 0..100 or null")
            cost = None
        if inst == "equity":
            if cost is None:
                incomplete = True
            else:
                equity_costs.append(cost)
        if inst == "preference" and cost not in (None, 0):
            warns.append(f"{lw}: preference leg with non-zero cost {cost} (ok only if published)")
        parse_date(leg.get("listing_date"), f"{lw}.listing_date", errs)
        if ex and leg.get("listing_date"):
            ld = dt.date.fromisoformat(leg["listing_date"]) if re.fullmatch(
                r"\d{4}-\d{2}-\d{2}", leg["listing_date"]) else None
            if ld and ld < ex:
                warns.append(f"{lw}: listing_date {ld} before ex_date {ex}")
        for k in ("face_value", "cash_per_share"):
            v = leg.get(k)
            if v is not None and (not isinstance(v, (int, float)) or isinstance(v, bool) or v < 0):
                errs.append(f"{lw}: {k} must be a non-negative number or null")

    if not incomplete and equity_costs:
        total = round(sum(equity_costs), 4)
        if kind == "MERGER" and abs(total - 100) > 0.01:
            errs.append(f"{where}: MERGER equity cost_share_pct sums to {total}, expected 100")
        if kind == "DEMERGER" and not total < 100:
            errs.append(f"{where}: DEMERGER equity cost_share_pct sums to {total}, must be < 100")
    if e.get("status") not in ("complete", "detected"):
        errs.append(f"{where}: status must be complete or detected")
    elif e.get("status") == "complete" and incomplete:
        errs.append(f"{where}: status 'complete' but an equity leg lacks ratio or cost_share_pct")


def validate_file(path: Path, expect_scheme: bool):
    errs, warns = [], []
    try:
        text = path.read_text(encoding="utf-8")
        doc = json.loads(text)
    except (OSError, json.JSONDecodeError) as exc:
        return [f"{path}: cannot parse JSON: {exc}"], []
    if not isinstance(doc, dict) or set(doc) != {"events"} or not isinstance(doc["events"], list):
        return [f"{path}: top level must be exactly {{\"events\": [...]}}"], []
    seen = set()
    for i, e in enumerate(doc["events"]):
        where = f"{path.name}#{i}"
        if isinstance(e, dict):
            where += f"({e.get('scheme')}/{e.get('step')}/{e.get('source_ticker')})"
            key = (e.get("scheme"), e.get("step"), e.get("source_ticker"))
            if key in seen:
                errs.append(f"{where}: duplicate scheme/step/source_ticker")
            seen.add(key)
            if expect_scheme and e.get("scheme") != path.stem:
                errs.append(f"{where}: scheme {e.get('scheme')!r} != file name {path.stem!r}")
        validate_event(e, where, errs, warns)
    if expect_scheme:
        steps = sorted({e.get("step") for e in doc["events"] if isinstance(e, dict)
                        and isinstance(e.get("step"), int)})
        if steps and steps != list(range(1, len(steps) + 1)):
            errs.append(f"{path.name}: steps {steps} are not numbered 1..n")
    return errs, warns


def main(argv):
    paths = [Path(p) for p in argv] or sorted(EVENTS_DIR.glob("*.json")) + [EVENTS_JSON]
    n_err = n_warn = 0
    for p in paths:
        errs, warns = validate_file(p, expect_scheme=p.parent.resolve() == EVENTS_DIR.resolve())
        for m in errs:
            print("ERROR", m)
        for m in warns:
            print("WARN ", m)
        n_err += len(errs)
        n_warn += len(warns)
    print(f"{len(paths)} file(s), {n_err} error(s), {n_warn} warning(s)")
    return 1 if n_err else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
