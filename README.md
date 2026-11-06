# India mergers & demergers (NSE / BSE), 2000 → today

A curated, source-cited dataset of share-exchange corporate actions — **mergers
(amalgamations)** and **demergers** — of companies listed on NSE and BSE, in the exact JSON
format a portfolio app loads to adjust holdings and cost basis.

Accuracy over coverage: every value is either sourced or `null`, and an event is `complete`
only when every equity leg has a sourced ratio and cost split.

## Repository layout

| Path | What it is |
|---|---|
| `data/events.json` | **The deliverable.** `{"events": [...]}` built from `data/events/` by `scripts/merge_events.py`. |
| `data/events.csv` | Same data, one row per leg (spreadsheet view). |
| `data/events/<scheme>.json` | One file per scheme, written by one research agent. The source of truth. |
| `data/candidates.csv` | Master list of every merger/demerger found (one row per company giving up shares), with research status. |
| `data/raw/` | Normalised listings from each discovery source (`seed_knowledge.csv`, `bse_*.csv`, `nse_*.csv`). |
| `PROGRESS.md` | Generated progress report (counts by status/year, per-scheme table). |
| `prompts/filling_rules.md` | **The specification** for every field. |
| `prompts/research_agent.md` | Prompt template for a per-scheme research agent. |
| `schema/events.schema.json` | JSON Schema (structure). |
| `scripts/validate.py` | Enforces the schema **and** the cross-field rules (cost sums, status, dates, ISIN check digits). |
| `docs/sources.md` | Discovery and research sources. |

## Event format (summary)

One event per company that **gives up** shares; its `legs` are what its shareholders
**receive**. Full rules: [`prompts/filling_rules.md`](prompts/filling_rules.md).

```json
{"scheme": "hdfc-2023", "step": 1, "kind": "MERGER",
 "source_ticker": "HDFC", "source_isin": "INE001A01036", "source_name": "Housing Development Finance Corporation Ltd",
 "source_aliases": [], "source_continues": false,
 "ex_date": "2023-07-13", "record_date": "2023-07-13", "last_trading_date": "2023-07-12",
 "status": "complete", "terms_source": "Ratio and record date: <url>", "notes": "",
 "legs": [{"target_ticker": "HDFCBANK", "target_isin": "INE040A01034", "target_name": "HDFC Bank Ltd",
           "target_aliases": [], "instrument": "equity", "ratio": "25:42", "cost_share_pct": 100,
           "listing_date": null, "face_value": 1, "cash_per_share": null}]}
```

Key rules: `ratio` is always `held:received`; `ex_date` is the ex-date (= record date from
27 Jan 2023, one trading day earlier before that), never the appointed/effective date;
merger equity legs' `cost_share_pct` sum to 100, demerger legs to < 100.

## Workflow

### Phase 1 — build the candidate list  ✅ done (BSE corporate actions still to add)

Current list: **1,823 candidate rows** — 174 seed, 241 BSE mergers page, 163 NSE corporate
actions, 1,078 NSE scheme filings as their own rows (plus listings merged into existing rows),
167 auto-skipped wholly-owned-subsidiary schemes. See [`PROGRESS.md`](PROGRESS.md).

```bash
pip install -r requirements.txt
```

```bash
python3 scripts/fetch_bse.py mergers-page
```

```bash
python3 scripts/fetch_bse.py corp-actions --from 2000
```

```bash
python3 scripts/fetch_nse.py --from 2000
```

```bash
python3 scripts/fetch_nse.py --schemes
```

```bash
python3 scripts/build_candidates.py
```

```bash
python3 scripts/progress.py
```

`build_candidates.py` is idempotent: it keeps existing rows and their status, enriches matches
(same company, year ±1) and appends new ones as `pending`. A candidate's `scheme` groups the
rows that belong to one scheme (e.g. both companies in a merger of equals, or each stage of a
multi-stage scheme). Fix groupings by editing `scheme` in `candidates.csv` or with
`scripts/set_status.py <id> duplicate`.

### Phase 2 — research, one agent per scheme  ⏳ not started

An orchestrator session loops:

1. `python3 scripts/next_batch.py -n 5 --claim` → next 5 pending schemes (newest first), marked `in_progress`.
2. For each scheme, start a **fresh** agent with `python3 scripts/next_batch.py --prompt <scheme>`.
   One agent per scheme keeps context small; agents are discarded after writing their file.
3. Each agent writes `data/events/<scheme>.json`, runs `scripts/validate.py` on it, and
   sets the status with `scripts/set_status.py <scheme> complete|detected|skipped`.
4. Orchestrator: `python3 scripts/validate.py`, `python3 scripts/merge_events.py`,
   `python3 scripts/progress.py`, commit, repeat.

`python3 scripts/next_batch.py --retry-detected` re-queues `detected` schemes for another pass.

### Candidate statuses

`pending` → `in_progress` → `complete` (all legs sourced) | `detected` (event written, something
missing) | `skipped` (not a share-exchange event: pure rename, unlisted source, withdrawn, no
consideration) | `duplicate`.

## Checks

```bash
python3 scripts/validate.py
```

```bash
python3 -m unittest discover tests
```

## Caveats

- Many NSE scheme filings are internal reorganisations, withdrawn schemes or re-filings of the
  same scheme; agents mark those `skipped` / `duplicate`. Auto-skipped rows carry the note
  `auto-wos` and can be re-opened with `scripts/set_status.py <id> pending`.
- `data/raw/seed_knowledge.csv` is a hand-compiled starting list. Its names, years and
  groupings are **hints, not data**; research agents verify or reject each one.
- BSE's corporate-actions API (`api.bseindia.com`) refuses cloud/datacenter IPs (Akamai 403);
  `fetch_bse.py corp-actions` must be run from a residential connection. The NSE scripts and
  the BSE mergers page work from anywhere.
- NSE corporate actions list few mergers (the merged company stops trading); mergers come mostly
  from the BSE mergers page, NSE scheme filings and the seed list.
