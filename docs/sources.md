# Sources

Where the candidate list comes from and where research agents look for terms. Status column
says whether a script exists for it.

## Discovery (building `data/candidates.csv`)

| Source | What it gives | Dates? | Script |
|---|---|---|---|
| Seed list (`data/raw/seed_knowledge.csv`) | ~170 well-known schemes 2000-2026, hand-compiled as a starting point. **Unverified hints**: names/years may be wrong. | year only | built in |
| BSE mergers list — https://www.bseindia.com/static/about/acompany-mergers.aspx and https://www.bseindia.com/static/about/a-merger.aspx | Company, scrip code, company it merged into (long history, mostly older) | no | `fetch_bse.py mergers-page` |
| BSE corporate actions — https://www.bseindia.com/corporates/corporate_act.aspx | Purpose (Amalgamation / Scheme of Arrangement / Demerger), ex-date, record date. Incomplete. | yes | `fetch_bse.py corp-actions` |
| NSE corporate actions — https://www.nseindia.com/companies-listing/corporate-filings-actions | Symbol, ISIN, subject, ex-date, record date | yes | `fetch_nse.py` |
| BSE draft schemes / NOC under Reg. 37 — https://www.bseindia.com/corporates/NOCUnder.aspx | Every scheme of arrangement filed with BSE (incl. ones that never completed) | filing date | not yet |
| NSE scheme of arrangement filings — https://www.nseindia.com/companies-listing/corporate-filings-scheme-document | Same for NSE | filing date | not yet |
| BSE notices / circulars — https://www.bseindia.com/markets/MarketInfo/NoticesCirculars.aspx (search "Amalgamation", "Scheme of Arrangement", "Listing of equity shares of … pursuant to") | Record date, ratio, suspension/last trading day, new listings | yes | not yet |
| NSE circulars — https://www.nseindia.com/resources/exchange-communication-circulars (Listing / CMTR) | Same for NSE, plus symbol changes | yes | not yet |
| Broker mirrors of exchange circulars, e.g. https://www.angelone.in/announcements/circulars | Searchable copies of "[BSE] Amalgamation of …" notices | yes | not yet |
| SEBI — observation letters on draft schemes (https://www.sebi.gov.in → Filings) | Scheme pipeline (2017+) | letter date | not yet |
| Wikipedia, news archives ("List of mergers and acquisitions in India") | Large schemes, older years | varies | manual |

Exchange listings overlap; `build_candidates.py` merges rows for the same company/year into one
candidate and records every source in `discovered_via`.

## Terms (used by research agents)

In order of preference (see `prompts/filling_rules.md`):

1. Company filings — `https://nsearchives.nseindia.com/corporate/<SYMBOL>_<timestamp>_*.pdf`,
   `https://www.bseindia.com/xml-data/corpfiling/AttachHis/<uuid>.pdf`: scheme document, record
   date intimation, allotment, **cost of acquisition apportionment**.
2. Exchange corporate-action pages and notices.
3. Company investor-relations pages (cost apportionment often only here, under "Demerger" /
   "Shareholder information" / "Income tax").
4. Reputable news, only to locate primary documents, noted in `notes`.

ISINs: NSE/BSE quote pages, NSDL ISIN search (https://nsdl.co.in/master_search.php),
filings. `validate.py` checks the ISIN check digit.
