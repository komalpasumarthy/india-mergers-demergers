"""Shared paths and helpers. Standard library only."""
import csv
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
RAW = DATA / "raw"
EVENTS_DIR = DATA / "events"
CANDIDATES = DATA / "candidates.csv"
EVENTS_JSON = DATA / "events.json"
EVENTS_CSV = DATA / "events.csv"
PROGRESS_MD = ROOT / "PROGRESS.md"

CANDIDATE_FIELDS = [
    "candidate_id",     # c0001 ...
    "scheme",           # scheme id; the event file is data/events/<scheme>.json
    "kind_hint",        # MERGER | DEMERGER | UNKNOWN  (hint, not verified)
    "source_company",   # company that gives up shares (hint)
    "counterparty",     # company/companies whose shares are received (hint)
    "year_hint",        # approximate year the action took effect (hint)
    "nse_symbol",
    "bse_code",
    "isin",
    "ex_date_hint",     # ex/record date as listed by an exchange, if any
    "discovered_via",   # ;-separated: seed | bse-mergers-page | bse-corp-actions | nse-corp-actions | ...
    "refs",             # ;-separated URLs / purpose strings from the listings
    "status",           # pending | in_progress | complete | detected | skipped | duplicate
    "status_note",
]
STATUSES = ["pending", "in_progress", "complete", "detected", "skipped", "duplicate"]

# Normalised row format written by every fetch_* script (data/raw/<source>.csv).
RAW_FIELDS = ["source", "exchange", "scrip_code", "symbol", "isin", "company", "purpose",
              "counterparty", "ex_date", "record_date", "year_hint", "kind_hint", "scheme_hint",
              "url"]

ACTION_RE = re.compile(r"amalgamat|merger|demerg|de-merg|arrangement|spin[ -]?off|"
                       r"reconstruction|reorgani[sz]ation|scheme", re.I)
DEMERGER_RE = re.compile(r"demerg|de-merg|spin[ -]?off|hive", re.I)
MERGER_RE = re.compile(r"amalgamat|merger", re.I)

_STOP = {"ltd", "limited", "the", "and", "of", "co", "company", "corporation", "corp", "india",
         "industries", "pvt", "private", "&", "inc"}


def norm_name(name: str) -> str:
    s = re.sub(r"\(.*?\)", " ", name or "").lower()
    s = re.sub(r"[^a-z0-9 ]+", " ", s)
    return " ".join(t for t in s.split() if t not in _STOP)


def name_tokens(name: str) -> set:
    return set(norm_name(name).split())


def slug(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", norm_name(text)).strip("-")[:30].strip("-") or "unknown"


def read_csv(path: Path) -> list:
    if not path.exists():
        return []
    with path.open(newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def write_csv(path: Path, rows: list, fields: list) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fields, extrasaction="ignore")
        w.writeheader()
        for r in rows:
            w.writerow({k: r.get(k, "") for k in fields})


def load_json(path: Path):
    with path.open(encoding="utf-8") as f:
        return json.load(f)


def dump_json(path: Path, obj) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        json.dump(obj, f, indent=2, ensure_ascii=False)
        f.write("\n")


_DATE_FORMATS = ["%Y-%m-%d", "%d-%b-%Y", "%d %b %Y", "%d/%m/%Y", "%d-%m-%Y", "%d %B %Y",
                 "%d-%B-%Y", "%b %d, %Y", "%Y%m%d", "%d/%m/%y", "%d-%b-%y"]


def iso_date(text):
    """Best-effort conversion of exchange date strings to YYYY-MM-DD ('' if unknown)."""
    import datetime as _dt
    t = (text or "").strip().split("T")[0]
    if not t or t in ("-", "NA", "N.A."):
        return ""
    for fmt in _DATE_FORMATS:
        try:
            return _dt.datetime.strptime(t, fmt).date().isoformat()
        except ValueError:
            pass
    return ""
