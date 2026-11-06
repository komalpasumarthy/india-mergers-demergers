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
2. Research this scheme on the web. Source priority:
   1. Company filings on NSE (`nsearchives.nseindia.com/corporate/...`) and BSE
      (`bseindia.com/xml-data/corpfiling/...`): scheme document, record-date intimation,
      allotment / listing intimation, **cost-of-acquisition apportionment letter**.
   2. NSE / BSE corporate-action listings and exchange notices/circulars
      ("Amalgamation of …", "Scheme of Arrangement …", "Listing of new securities …").
   3. The company's investor-relations page (cost apportionment is often only there).
   4. Reputable news (Economic Times, Business Standard, Moneycontrol, Livemint) only to locate
      the primary filing or when nothing primary exists — say so in `notes`.
3. Find the ISINs (NSE/BSE quote pages, NSDL ISIN search, filings). Never invent one.
4. If the hint is wrong (e.g. it was a pure rename, the source company was unlisted, the
   scheme was withdrawn, or shareholders received nothing), do NOT write an event; report
   `skipped` with the reason.
5. Write the result to `data/events/{{scheme}}.json` as `{"events": [...]}` (all events of this
   scheme, all steps). Use exactly the scheme id `{{scheme}}`.
6. Run `python3 scripts/validate.py data/events/{{scheme}}.json` and fix every error.
7. Update the candidate rows:
   `python3 scripts/set_status.py {{scheme}} <complete|detected|skipped> --note "<short reason>"`
   (`complete` only if every event in the file has status "complete").
8. Reply with ONE short line: `{{scheme}}: <status> — <what is missing, if anything>`.
   Do not paste the JSON back; it is in the file.

Do not edit any other scheme's file, `data/events.json` or `PROGRESS.md` — the orchestrator
rebuilds those.
