# Batch D2 review (boss), 2026-10-24

Inputs reviewed:
- `research/results_batchD2.md` and registry rows D2-1 to D2-7
- `research/d2_select.py` and its git history
- `strategies/_d2util.py` and the 7 modules
- `results/batchD2_screen*.txt` and `batchD2_controls{1,2,3}.txt`
- `results/<id>_opt_stage1.csv`, `_opt_exits.csv` and `_optimise.txt`
- the git snapshots 4dec099, e3efc99 and e26c8de, and the amended D2 commit 47ab608

Nothing was frozen and no OOS data was simulated for any D2 id.

## Protocol checks

- **Selection rule committed before the grids: verified.**
  - 5e2a6ea (01:32:58) adds `research/d2_select.py` with the tier definitions and the pre-declared
    scope by card.
  - The file is unchanged from 5e2a6ea to HEAD.
  - The first D2 output is `batchD2_screen.txt` (01:37:28), and the first grid is
    `post_release_revert_opt_stage1.csv` (01:37:57). All other grids are later (01:40 to 01:56).
- **Module code against the grids.**
  - The modules first appear in the WIP snapshot 4dec099 (01:52:47). That is after the
    post_release, range_crush, bracket and macro_shock grids, but before the pre_release_drift grid
    (01:56:35).
  - Between 4dec099 and HEAD, only `pre_release_drift.py` changed. That was the documented
    `.T`-clash / pre-data-days fix, in e3efc99 (01:54:49), before its grid.
  - The amended commit 47ab608 does not change module content.
  - The PARAMS keys, including the `event_set` pooling values, are visible as columns in each
    stage-1 CSV, so they were present when each grid ran.
- **Budget.** Stage 1 is ≤ 141, and the totals per idea are ≤ 300 (655 grid rows over 5 ideas, all
  counted). The controls are not in any search. Good.
- **ICT/SMC:** none.

## Points the coordinator asked about

**(a) Calendar join and timing: clean.**
- Events sit at the calendar's verified UTC second (DST-aware `datetime_utc`). Rows marked SCHEDULED
  are dropped, and same-timestamp releases are merged by priority.
- Per module:
  - **post_release_revert:** R0 uses mid(T+s0) − mid(T−60), and the decision is at T+s0+delay
    (≥ T+s0). The stop extreme covers [T, decision]. ATR is from the last 1m bar closed by T−1. med20
    uses prior events only (`prior_stat`, exclusive).
  - **release_range_crush:** the initial range covers [T, T+899]. The first decision is at the close
    of the bar ending T+20 min. PV uses the bars T..T+4 min, and rv10 includes only closed bars.
  - **release_bracket:** the pre-range covers [T−900, T−5], and the impulse and spread are taken at
    T+s1 (the decision second). The sd and spread medians use prior events.
  - **macro_shock:** the decision is at T+899, using p15 = mid(T+899).
  - **pre_release_drift:** the cross-asset 1m bars start at b−60 and close at b−1, before the
    decision b. The 5m ATR comes from a bar with `close_sec` ≤ the decision.
  - **month_end_fix:** USD2 uses bars closing at t−1 and t−3601. The USA500 month-to-date return runs
    to the prior business day.
  - **comex_expiry:** the 5-day rally uses prior daily closes plus the mid at entry. Expiry dates
    follow the CME rule and are calendar-known.
- range_crush caveat (no look-ahead): its one-per-side / stop-after-stop-out state machine is driven
  by the *native* exit path. Under exit templates the real exits differ. That is an inconsistency,
  not a leak: later entries depend only on exits that have already happened.
- 1 s fill latency is optimistic at release seconds. release_bracket was also shown under STRESS and
  raw Dukascopy spreads (PF 0.45 and 0.58), and it loses in all three.

**(b) VAL printed for settings that did not qualify.** No influence on any decision.
- Every grid finalist failed IS PF(R) 1.30 *before* VAL was read: post_release_revert 0.88,
  range_crush 1.03. Every other id was ineligible by trade count, or screen-only by pre-declaration.
- No grid was changed after any optimise output.
- The one pre-grid change (post_release_revert, point d) followed a screen whose 4 trades were all
  in IS. That screen printed no VAL row, because VAL had 0 trades.
- range_crush's VAL PF 1.45 and comex's VAL PF 6.05 (5 trades) were correctly ignored.
- The disclosure is honest.

**(c) event_set pooling "from event counts only", committed after the grids: acceptable.**
- The keys were present at grid time (they are columns in the stage-1 CSVs). Git cannot prove the
  *motivation* was counts only.
- No verdict depends on it: every pooled setting is below n_IS 60 (pre_release_drift ≤ 42,
  release_bracket ≤ 44) or below IS PF(R) 1.30 (range_crush t1card_t2, 1.03).
- For the future, commit the module files with their PARAMS together with the selector, before any
  grid.

**(d) post_release_revert grid moved after the default screen: count-based, not a peek.**
- The card grid is q_max [0.5, 0.75, 1.0] and r_min [0.5, 1.0, 2.0]. The module uses
  [0.75, 1.0, 1.25] and [0.0, 0.5, 1.0].
- The default screen gave 4 trades in 22 months, against the card's ~60–90 trades a year. All 4 were
  IS trades and no VAL row existed.
- The scale argument is documented: ATR14(1m) ≈ $2.4 against a median |R0| ≈ $3, so the two filters
  are nearly exclusive.
- Even after widening, the best plateau is 0.72 and the finalist's IS PF(R) is 0.88. A widening that
  ends below breakeven cannot be a helpful peek.

**(e) Bug fixes before the grids: accepted.**
- pre_release_drift: the fixes are the `.T` attribute clash (the column was renamed `rt`) and the
  removal of pre-data days from the z-score baseline. Both are genuine and in e3efc99, before its
  grid.
- month_end_fix: screen only, no grid. Its pre-screen fixes are documented in the report and affect
  no selection.

**(f) Placebo design and conclusions: good design, correct conclusions.**
- Design: the same NY clock time on a matched no-release weekday (±7, ±1, ±2 days; holidays
  excluded), keeping the type label so that history-based scalings behave the same.
  month_end_fix uses one week earlier, and comex_expiry uses 7–9 business days before month end.
  Controls are run once on the finalist or on the defaults, and never select anything.
- Conclusions:
  - The placebo *beating* the real signal (macro_shock: 9 trades, PF 2.01; comex: 19 trades,
    PF 1.66) is small-sample noise. It shows there is no event-specific effect in the card's
    direction.
  - It is **not** a tradable inverse edge. Nobody should build a "placebo-day" strategy from it,
    since those numbers include VAL-free IS but tiny n, and they were not part of any search.
  - post_release_revert and range_crush beat their placebos, so there is some event-specific mean
    reversion, but they are about breakeven after costs in IS.
  - All of this is stated correctly in the report.

**Harness recommendation (protect future batches): yes, change the default VAL printing.**
1. `evaluate.screen`: report IS only by default. Add a `--val` flag.
2. `evaluate.optimise`: print IS columns only in the console table. Write the VAL columns to a
   separate file (`results/<id>_opt_val.csv`) that only the selector's `--val` path reads, after
   the finalist is fixed.
3. Optional: record each `--val` read (id, timestamp, finalist params) in `results/val_looks.log`.
   That makes "one VAL look per strategy" auditable from the repo.

## Per-strategy verdicts

| Strategy | Verdict | Reason |
|---|---|---|
| post_release_revert | ACCEPT (reject on IS) | count-justified grid; plateau 0.72; finalist IS PF(R) 0.88; beats placebo but net negative; the large-move follow control also loses |
| pre_release_drift | ACCEPT (ineligible, X7) | the card's E10 set is not in the calendar; max 42 IS trades; real 0.64 vs placebo 1.25 |
| release_range_crush | ACCEPT (reject on IS) | IS PF(R) 1.03 (DD 7.2 %); beats placebo (0.49) and the break control (0.81); VAL 1.45 correctly ignored |
| release_bracket | ACCEPT (ineligible, X7) | max 44 IS trades; defaults lose under base, stress and raw spread |
| macro_shock | ACCEPT (ineligible, X7) | ≤ 14 IS trades (NFP+CPI); continuation sign wrong; 4 h control fails VAL |
| month_end_fix | ACCEPT (reject, pre-declared screen) | no sign support; placebo also negative |
| comex_expiry | ACCEPT (reject, pre-declared screen) | IS sign against the card; does not beat placebo |

## Instructions for the Batch D2 agent

**ACCEPT – no further work.** No reruns, no new ids, no VAL or OOS looks.

For the coordinator (harness): apply the VAL-printing changes above before any further batch.

---

# Overall conclusion across all batches (A, B, C, D1, D2), for the final report

1. **No strategy passes.**
   - No idea meets every gate on unseen data: WR > 75 %, PF > 3, DD < 5 % at 0.5 % risk, ≥ 100
     IS+VAL and ≥ 25 OOS trades, stress PF > 2, and neighbourhood median PF > 2.
   - Under the honesty clause the deliverable is the frontier, and `research/ctrader_candidates.md`
     should say **"no candidates"**.
2. **Coverage.**
   - Round 1 (A/B/C): 33 ideas. Round 2: D1 has 7 cross-asset, statistical and microstructure ideas,
     and D2 has 7 macro-calendar ideas, including macro_shock, which was skipped in C.
   - That is 47 ideas in all, with ICT/SMC excluded as the user instructed.
   - Outcomes:
     - **Reached OOS (7 frozen ids, all FAIL):** asian_range_breakout, london_range_ny_break,
       ib_fade_ny, bb_pinbar_fade, ema_pullback_adx, avwap_london, usd_impulse_catchup.
     - **Ineligible by trade count:** idnr4, raschke_8020, fomc_drift, pre_release_drift,
       release_bracket, macro_shock.
     - **Screen-only rejects:** month_end_fix and comex_expiry.
     - **Everything else:** rejected on IS (best IS PF(R) < 1.3) or at its single VAL look.
3. **OOS frontier** (profitable, but far from WR 75 / PF 3):

   | Id | OOS PF | OOS WR | OOS trades |
   |---|---|---|---|
   | asian_range_breakout | 2.11 | 69 % | 16 |
   | ib_fade_ny | 1.88 | 53 % | 32 |
   | avwap_london | 1.56 | 46 % | 61 |

   The remaining frozen ids lost out of sample:
   - ema_pullback_adx: PF 0.99 at WR 80 %
   - bb_pinbar_fade: PF 0.52
   - london_range_ny_break: PF 0.47
   - usd_impulse_catchup: PF 0.25 on 12 trades
4. **What the evidence says.**
   - High WR on XAUUSD intraday appears only with scalp-plus-break-even exits (tp1 = 0.25–0.5R).
     There, PF depends on rare runners and collapses out of sample.
   - The time-of-day effects (Asian drift, day-session TSMOM, PM-fix follow) are 2025 bull-trend
     beta: they equal a long-daytime benchmark in IS and reverse in 2026.
   - Calendar effects: the round-number levels equal their placebo, and the month-end, COMEX-expiry
     and macro-shock effects fail their placebo or sign checks. The release-driven mean reversion
     that beats its placebo is about breakeven after costs.
   - Cross-asset lead-lag (silver, USD, Nasdaq) and microstructure (tick intensity) edges are small
     before costs and vanish after cTrader costs. usd_impulse_catchup beat chance in IS but failed
     OOS.
   - Every candidate degraded from June 2026 onwards, which matches the registry's prior
     observation.
5. **Process integrity.**
   - Every OOS freeze was committed before its single OOS run, and no strategy was re-tuned after
     OOS.
   - Selection rules were committed before the grids from D1 onwards. Finalists were chosen on IS
     columns, with plateau and neighbour checks.
   - The harness defects found in review were fixed:
     - card exits not searched;
     - random subsampling;
     - list-order neighbours;
     - helper files missing from the freeze hash;
     - plateau ranking with n_IS < 60;
     - the `exit` column collision.
   - The remaining documented deviations change no verdict: Batch C's top-PF(R) finalist rule,
     VAL seen before the audit for asian_drift and pre-fix for gold_silver_residual, and default VAL
     printing (D2). The recommended harness change is to hide VAL by default.
6. **Recommendation to the user.**
   - Report the frontier honestly, and do not loosen the gates or move the splits without explicit
     approval.
   - The joint WR > 75 % and PF > 3 requirement implies an average win at least as large as the
     average loss at a 75 % hit rate. None of the 47 intraday XAUUSD ideas came close after
     realistic costs.
   - If the user wants to continue, the options are:
     - (a) relax the gates explicitly, starting from ib_fade_ny and avwap_london, which would need
       fresh, untouched data because their OOS has been used;
     - (b) accept lower-WR, positive-expectancy profiles (PF 1.5–2) for live paper monitoring only;
     - (c) bring materially new information (consensus/actual macro data for true surprises,
       order-book or futures volume data) through the full pipeline as new ideas.
