# US macro release calendar, 2025-01-01 to 2026-10-31

File: `us_macro_2025_2026.csv` (311 rows). Built 2026-10-24. Rows dated after that day are
**scheduled** releases, and their `note` starts with `SCHEDULED`.

Columns: `event, date_local, time_local (America/New_York), datetime_utc (ISO, DST-aware via zoneinfo),
source_url (primary source first, then the cross-check sources, separated by " | "), verified, note`.

## Counts

| event | rows | notes |
|---|---|---|
| NFP | 21 | Oct-2025 report not published |
| CPI | 21 | Oct-2025 CPI not published |
| PPI | 21 | Oct-2025 PPI not published as a separate release |
| JOLTS | 21 | Sep-2025 JOLTS not published as a separate release |
| PCE (Personal Income & Outlays) | 21 | includes scheduled 2026-10-29; Oct and Nov 2025 came out together on 2026-01-22 |
| GDP_advance | 8 | includes scheduled 2026-10-29; Q3-2025 advance cancelled (see below) |
| GDP_second | 6 | Q3-2025 second estimate cancelled |
| GDP_third | 7 | Q3-2025 "Updated Estimate" (2026-01-22) is counted as the third estimate |
| retail_sales | 22 | |
| jobless_claims | 89 | 7 releases skipped during the shutdown; includes scheduled 2026-10-29 |
| FOMC_statement | 15 | includes scheduled 2026-10-28; the 2025-08-22 notation vote is excluded |
| FOMC_minutes | 15 | includes the minutes of the Dec-2024 meeting, released 2025-01-08 |
| ISM_manufacturing | 22 | |
| ISM_services | 22 | |

All 311 rows have `verified=yes`: an official source plus at least one independent source agree on the date.
Release times come from the official source.

## Sources

Primary (official). We fetched each source in October 2026 and parsed the HTML. bls.gov blocked the
Chrome User-Agent but accepted a Safari User-Agent.

- **BLS** (NFP, CPI, PPI, JOLTS):
  - Monthly release calendars `https://www.bls.gov/schedule/YYYY/MM_sched.htm`, which give the actual date
    and time.
  - Archived release lists `https://www.bls.gov/bls/news-release/{empsit,cpi,ppi,jolts}.htm`.
  - Each row links its archived release, `news.release/archives/<code>_MMDDYYYY.htm`. Every BLS date
    appears in both lists.
- **BEA** (GDP, PCE): `https://www.bea.gov/news/schedule/full-2025` and `/full`. Each released row links its
  BEA news release.
- **Census** (retail sales): `https://www.census.gov/economic-indicators/calendar-listview-{2025,2026}.html`.
- **DOL/ETA** (weekly claims): the news-release archive at `oui.doleta.gov/unemploy/archive.asp` lists
  every published PDF as `press/YYYY/MMDDYY.pdf`. The page `claims_arch.asp` lists the holiday
  exceptions and states that no releases were published during the shutdown.
- **Federal Reserve** (FOMC): `https://www.federalreserve.gov/monetarypolicy/fomccalendars.htm` gives the
  meeting dates, statement press releases and "Released <date>" for the minutes. Statements and minutes
  both come out at 14:00 ET.
- **ISM** (PMIs): ISM's own press releases on PR Newswire
  (`prnewswire.com/news/institute-for-supply-management/`), which carry date and time stamps. The
  ismworld.org site is behind a captcha.

Independent cross-checks:

- **mql5.com economic calendar** (MetaQuotes). Event history pages give exact UTC timestamps.
- **Nasdaq economic calendar API** (`api.nasdaq.com/api/calendar/economicevents?date=`). This API has a
  quirk: querying date D+1 returns the events of ET-day D, and its `gmt` field is really fixed UTC-4. We
  confirmed this against all 15 FOMC-minutes dates. It has occasional holes, for example no data for
  2025-01-15 or 2026-10-14.
- **OMB PFEI schedules** for 2025 and 2026 (statspolicy.gov). These are the pre-shutdown planned dates.
  We used them only to confirm the *original* dates quoted in the notes.
- **Wikipedia**. The 2025 shutdown ran Oct 1 to Nov 12, 2025. Two further lapses came in 2026: Jan 31 to
  Feb 3 and Feb 14 to Apr 30.
- **tradingeconomics** for the upcoming claims release.

Rule for `verified=yes`: the official date matches mql5 or Nasdaq (or both) on the same ET day. Where a
cross-check's clock time disagrees, the row's note says so.

## Shutdown effects: actual dates recorded, cancellations

- **Oct 1 to Nov 12, 2025 shutdown**:
  - NFP: the Sep report came out 2025-11-20 instead of 10-03. The Oct report was **not published**; Oct
    establishment data came out with the Nov report on 2025-12-16.
  - CPI: Sep came out 2025-10-24 instead of 10-15. **Oct CPI not published.** Nov came out 2025-12-18
    instead of 12-10.
  - PPI: Sep came out 2025-11-25 instead of 10-16. **Oct PPI not published separately.** Nov came out
    2026-01-14 and Dec on 2026-01-30.
  - JOLTS: **Sep not published separately.** Oct came out 2025-12-09.
  - PCE: Sep came out 2025-12-05 at 10:00 instead of 10-31. Oct and Nov came out **combined** on
    2026-01-22 at 10:00.
  - GDP Q3-2025: the **advance (orig. 2025-10-30) and second (orig. 11-26) estimates were cancelled**. An
    "Initial Estimate" came out 2025-12-23 and is recorded as `GDP_advance` with a note. An "Updated
    Estimate" came out 2026-01-22 and is recorded as `GDP_third`.
  - GDP Q4-2025: advance 2026-02-20 (PFEI had 01-29), second 03-13, third 04-09.
  - Retail sales: Sep came out 11-25, Oct 12-16, Nov 2026-01-14, Dec 02-10 and Jan 03-06, against
    mid-month originals.
  - Weekly claims: **the 7 Thursday releases from 2025-10-02 to 2025-11-13 were not published.** DOL posted
    the data later, and releases resumed on 2025-11-20.
- **Jan 31 to Feb 3, 2026 lapse**: Jan NFP came out 2026-02-11 (PFEI had 02-06). Jan CPI came out 02-13
  (PFEI had 02-11). Dec JOLTS came out 02-05.
- FOMC meetings, FOMC minutes and ISM were not affected.

Cancelled releases do **not** appear as rows; they are listed in the notes of the next actual release
and here.

## Holiday shifts (verified against the DOL archive filenames, mql5 and Nasdaq)

Jobless claims came out on a Wednesday on these dates:

| date | reason |
|---|---|
| 2025-01-08 | Thu 2025-01-09 national day of mourning for President Carter |
| 2025-06-18 | Juneteenth |
| 2025-11-26 | Thanksgiving |
| 2025-12-24 | Christmas |
| 2025-12-31 | New Year |

There were no other non-Thursday releases in the window. DOL's next listed exception is 2026-11-25,
which is outside the window.

## Known gaps and caveats

- mql5 has errors on some dates; the official source is used in all of them:
  - ISM services on 2025-10-05 (a Sunday) and 2026-04-03. ISM and Nasdaq give 2025-10-03 and 2026-04-06.
  - The UTC hour for 2025-11-20 and 11-25 (EDT offset applied after the DST change).
  - It has no history entry for the 2025-12-18 CPI.
- Nasdaq clock times are sometimes a minute or a few minutes off, for example 13:29Z. Dates are what count.
- Rows marked `SCHEDULED` (2026-10-28 FOMC; 2026-10-29 GDP advance, PCE and claims) come from schedules
  and could still move.
- Out of scope: the FOMC press conference (always 14:30 ET on statement days) and the 2025-08-22 notation
  vote, which approved the Statement on Longer-Run Goals and had no rate decision. Also out of scope:
  ADP, UMich, Empire/Philly, regional Fed surveys and the 2025 benchmark revision.
- The build scripts and raw downloads were kept in a scratch directory and are not committed. Rebuild by
  re-fetching the sources above.
