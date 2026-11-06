# Filling rules (canonical — do not edit without updating schema/validate.py)

You are filling a JSON file of Indian stock-market MERGERS and DEMERGERS (NSE/BSE listed
companies). The file is loaded into a portfolio app as-is, so accuracy matters more than coverage.

## OUTPUT

Return ONLY one JSON object, no prose, in exactly this shape:

```json
{
  "events": [
    {
      "scheme": "...", "step": 1, "kind": "MERGER" | "DEMERGER",
      "source_ticker": "...", "source_isin": "...", "source_name": "...",
      "source_aliases": [],
      "source_continues": true | false,
      "ex_date": "YYYY-MM-DD", "record_date": "YYYY-MM-DD", "last_trading_date": "YYYY-MM-DD" | null,
      "status": "complete" | "detected",
      "terms_source": "...", "notes": "...",
      "legs": [
        {
          "target_ticker": "..." | null, "target_isin": "..." | null, "target_name": "...",
          "target_aliases": [],
          "instrument": "equity" | "preference",
          "ratio": "held:received",
          "cost_share_pct": number | null,
          "listing_date": "YYYY-MM-DD" | null,
          "face_value": number | null,
          "cash_per_share": number | null
        }
      ]
    }
  ]
}
```

## THE ONE RULE

Write ONE event per company that GIVES UP shares. Its "legs" are what its shareholders RECEIVE
(one leg per company or instrument received).

## FIELD RULES

* **scheme**: short lowercase id for the whole scheme, e.g. "hdfc-2023", "vedanta-2026". Every event
  of the same scheme uses the same id.
* **step**: 1. If one scheme happens in stages (company A merges into B, then B demerges C), number
  the stages 1, 2, 3 in the order they take effect.
* **kind**: "MERGER" if the source company stops existing; "DEMERGER" if it keeps trading after
  handing out shares of another company.
* **source_continues**: false for MERGER, true for DEMERGER.
* **source_ticker**: the NSE symbol (use the BSE scrip id only if never listed on NSE).
* **source_isin**: the 12-character ISIN (starts with INE). Always try to find it: it is how the
  app matches a company whose symbol later changed.
* **source_aliases / target_aliases**: other symbols the same company has used (old or new names),
  e.g. ["LTI", "LTIM"]. Empty list if none.
* **ex_date**: the EX-DATE, the first day the shares trade without the entitlement.
  Do NOT use the board approval date, NCLT approval date, appointed date or "effective date".
  India rule of thumb: from 27 Jan 2023 (T+1 settlement), ex-date = record date. Before that
  (T+2), ex-date = one trading day before the record date. Confirm on the NSE/BSE corporate-
  action listing when possible.
* **record_date**: the record date announced by the company.
* **last_trading_date**: MERGER only, the last day the source company's shares traded (usually the
  day before the ex-date). null for a DEMERGER.
* **ratio**: always "held:received", as announced: "25:42" means 42 new shares for every 25 held.
  Keep the announced numbers (e.g. "100:73"); decimals are allowed if that is how it was
  announced ("1:0.0687").
* **cost_share_pct**: the % of the source company's ORIGINAL COST OF ACQUISITION that moves to this
  leg, from the company's "apportionment of cost of acquisition" announcement (usually published
  for income-tax purposes after a demerger).
    * MERGER: the equity leg gets 100 (all the cost moves to the acquirer).
    * DEMERGER: each new company gets its published %, and the parent keeps the rest; the legs
      add up to LESS than 100 (e.g. ABLBL 24.32 → ABFRL keeps 75.68).
    * preference shares / bonds received: instrument "preference", cost_share_pct 0, unless the
      company published a cost split for them.
    * not published or not found: null (and then status must be "detected").
* **listing_date**: first trading day of a company that was NEWLY listed because of this event.
  null if the receiving company was already trading (e.g. a merger into an existing company).
* **target_ticker / target_isin**: null if the new company is not listed yet or not known.
* **face_value**: face value of the shares received, if stated.
* **cash_per_share**: cash paid per share HELD as part of the scheme (not cash for fractions). null if none.
* **status**: "complete" only if, for every equity leg, the ratio AND cost_share_pct are known and
  sourced. Otherwise "detected".
* **terms_source**: the URL(s) that state the ratio, the cost split and the dates. Prefer, in order:
  the company's stock-exchange filings (NSE/BSE announcements, scheme document, cost-apportionment
  letter), the NSE/BSE corporate-action pages, then reputable news. Name what each URL gave,
  e.g. "Cost: <url>; ratio and record date: <url>".
* **notes**: anything a reviewer should know (conflicting sources, fractional shares paid in cash,
  dates that differ between NSE and BSE, a rename that happened at the same time).

## HOW TO FILL EACH SHAPE

1. Merger into an existing listed company (HDFC → HDFC Bank): one event, kind MERGER,
   one equity leg to the acquirer, cost_share_pct 100, listing_date null.
2. Two or more companies merging into a NEW company (OCL + Dalmia Bharat → new Dalmia Bharat):
   one MERGER event per company that disappears, same scheme, each with a leg to the new company
   (each leg cost_share_pct 100, listing_date = the new company's first trading day).
3. Demerger into one new company (ABFRL → ABLBL): one DEMERGER event, one leg, the published cost %.
4. Demerger into several companies (Vedanta 2026 → 4 companies): one DEMERGER event with one leg
   per new company.
5. Demerger into an EXISTING listed company (Kesoram's cement business → UltraTech shares): one
   DEMERGER event, the leg is the existing company, listing_date null.
6. Merger paying shares of more than one company: one MERGER event, one leg per company, cost %s
   adding up to 100.
7. Shares plus preference shares/bonds (Cairn → Vedanta): an equity leg (cost 100) plus a leg with
   instrument "preference" (cost 0).
8. Multi-stage scheme: one event per stage, same scheme, step 1, 2, 3…

Skip pure renames (same company, new name/symbol, no share exchange). Put the old symbol in the
aliases of the relevant event instead, if one exists.

## NEVER GUESS

* Do not invent ISINs, ratios, percentages or dates. If you cannot find a value with a source,
  use null, set status "detected", and say what is missing in notes.
* If two sources disagree, use the company's own filing and record the conflict in notes.
* Do not convert the ratio direction: it is always held:received.

## CHECK BEFORE ANSWERING

* One event per company giving up shares; legs = what is received.
* MERGER ⇒ source_continues false and equity legs' cost_share_pct sum to 100.
* DEMERGER ⇒ source_continues true and equity legs' cost_share_pct sum to less than 100.
* ex_date is the ex-date (not the effective/appointed date); dates are YYYY-MM-DD.
* status "complete" only when every equity leg has a ratio and a cost_share_pct with a source.
* Valid JSON, no comments, no trailing commas.

## EXAMPLES

```json
{"events": [
 {"scheme": "hdfc-2023", "step": 1, "kind": "MERGER",
  "source_ticker": "HDFC", "source_isin": "INE001A01036",
  "source_name": "Housing Development Finance Corporation Ltd", "source_aliases": [],
  "source_continues": false, "ex_date": "2023-07-13", "record_date": "2023-07-13",
  "last_trading_date": "2023-07-12", "status": "complete",
  "terms_source": "Ratio and record date: <url>", "notes": "",
  "legs": [{"target_ticker": "HDFCBANK", "target_isin": "INE040A01034", "target_name": "HDFC Bank Ltd",
            "target_aliases": [], "instrument": "equity", "ratio": "25:42", "cost_share_pct": 100,
            "listing_date": null, "face_value": 1, "cash_per_share": null}]},
 {"scheme": "abfrl-2025", "step": 1, "kind": "DEMERGER",
  "source_ticker": "ABFRL", "source_isin": "INE647O01011",
  "source_name": "Aditya Birla Fashion and Retail Ltd", "source_aliases": [],
  "source_continues": true, "ex_date": "2025-05-22", "record_date": "2025-05-22",
  "last_trading_date": null, "status": "complete",
  "terms_source": "Cost: <company cost-apportionment pdf> (ABFRL 75.68%, ABLBL 24.32%); ratio and dates: <url>",
  "notes": "",
  "legs": [{"target_ticker": "ABLBL", "target_isin": null, "target_name": "Aditya Birla Lifestyle Brands Ltd",
            "target_aliases": [], "instrument": "equity", "ratio": "1:1", "cost_share_pct": 24.32,
            "listing_date": "2025-06-23", "face_value": 10, "cash_per_share": null}]}
]}
```
