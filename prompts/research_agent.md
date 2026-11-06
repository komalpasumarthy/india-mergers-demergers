# Research-agent prompt (one agent per scheme)

The orchestrator fills the `{{…}}` placeholders from `data/candidates.csv` (see
`python3 scripts/next_batch.py --prompt`) and starts ONE fresh agent per scheme. A fresh agent per
scheme keeps each context small; once an agent has written its file it is discarded.

---

You are researching ONE corporate action for the repository `india-mergers-demergers`.

**Scheme id:** `{{scheme}}`
**Candidate rows (hints only — unverified, may be wrong or incomplete):**

{{candidate_rows}}

## Your task

1. Read `prompts/filling_rules.md` — it is the specification. Follow it exactly.
2. Research this scheme on the web (WebSearch, WebFetch; `curl` works for exchange PDFs —
   download into your scratchpad and read them with `pdftotext -layout file.pdf -`).
   Source priority:
   1. Company filings on NSE (`nsearchives.nseindia.com/corporate/...`) and BSE
      (`bseindia.com/xml-data/corpfiling/...`): scheme document, record-date intimation,
      allotment / listing intimation, **cost-of-acquisition apportionment letter**.
   2. NSE / BSE corporate-action listings and exchange notices/circulars
      ("Amalgamation of …", "Scheme of Arrangement …", "Listing of new securities …").
      NSE corporate actions for one company (works from this machine):
      `curl -s -A "Mozilla/5.0" -H "Referer: https://www.nseindia.com/" "https://www.nseindia.com/api/corporates-corporateActions?index=equities&symbol=<SYMBOL>"`
   3. The company's investor-relations page (cost apportionment is often only there).
   4. Reputable news (Economic Times, Business Standard, Moneycontrol, Livemint) only to locate
      the primary filing or when nothing primary exists — say so in `notes`.
3. Find the ISINs (NSE/BSE quote pages, filings, NSE API above). Never invent one; null is fine.
4. Decide whether this is an event at all. Write NO event file if: it is a pure rename; the
   company giving up shares was never listed (e.g. a private or wholly-owned subsidiary merging
   into its listed parent, so public holders receive nothing); the scheme was withdrawn,
   rejected or never took effect; or holders received nothing (e.g. bank write-off). Then the
   status is `skipped`. If it is the same scheme as another candidate you were told about, the
   status is `duplicate`.
5. Otherwise write `data/events/{{scheme}}.json` as `{"events": [...]}` (all events of this
   scheme, all steps), using exactly the scheme id `{{scheme}}`. If the candidate rows turn out
   to describe a different scheme than the hint, research the real one and say so in `notes`.
6. Run `python3 scripts/validate.py data/events/{{scheme}}.json` and fix every ERROR.
7. Write `data/status/{{scheme}}.json`:
   `{"scheme": "{{scheme}}", "status": "complete|detected|skipped|duplicate", "note": "<one line: what is missing, or why skipped>"}`
   (`complete` only if every event in the file has status "complete"; add `"duplicate_of"` if a duplicate).
8. Reply with ONE short line: `{{scheme}}: <status> — <note>`. Do not paste the JSON back.

Work only in your own two files. Do not edit `data/candidates.csv`, `data/events.json`,
`PROGRESS.md` or any other scheme's files — many agents run in parallel; the orchestrator
merges results. Do not run git. Be efficient: a few targeted searches and the key filings,
not an exhaustive survey. Accuracy over coverage: null + "detected" beats a guess.
