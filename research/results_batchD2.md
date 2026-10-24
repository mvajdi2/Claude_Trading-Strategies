# Batch D2 results: macro-calendar strategies (round-2 cards + academic macro shock)

Protocol: `evaluate.py` (staged harness). Screen at card defaults on IS, then the staged IS search:
stage 1 = full sorted PARAMS grid with the card's own exit (≤ 141 combos), stage 2 = all 53 exit
templates on the top-3 plateau settings (n_IS ≥ 60). Then a single VAL look at one finalist, freeze,
commit, and a single OOS run. Costs: cTrader model (spread max($0.10, 0.3×Dukascopy) at each second,
$0.03 slippage, $0.07/oz commission), 1 s fill latency. DD = max equity drawdown at 0.5 % risk per
trade, compounding.

## Selection rule (committed on its own before any D2 grid was run)

Applied identically to every D2 strategy that gets a grid, by `research/d2_select.py` (a copy of the
D1 selector; IS columns only):

1. **Finalist setting** = the stage-1 (card-exit) setting with the highest plateau score, i.e. the
   harness's median IS PF(R) over the setting and its sorted ±1 neighbours that have n_IS ≥ 60,
   among settings with n_IS ≥ 60. Ties: the higher own IS PF(R).
2. **Exit**: among the 53 stage-2 templates of that setting, a template is eligible if the median
   IS PF(R) of its template neighbours is ≥ 1.30 (neighbours: same family; ±1 step in sl with the
   rest fixed; ±1 step in the final tp with tp1/f1/be fixed; trail family ±1 step in sl and in
   trail; the template itself excluded). The best eligible template replaces the card exit only if
   its IS PF(R) is higher than the card exit's (by > 0.005). Ties: the lower sl, then the card exit.
3. **VAL**: the single finalist's VAL row is the strategy's only VAL look.
4. **Freeze + single OOS** only if the finalist has IS PF(R) ≥ 1.30 **and** VAL PF ≥ 1.30.
   Never re-tune after OOS.
5. Strategies whose natural frequency cannot reach n_IS ≥ 60 at any setting get no stage 2 and no
   finalist: reported as "ineligible by trade count" (X7).
6. Controls are **not** in the search grid and never choose anything: the placebo run (same rules at
   matched non-release times), the card's `mode=break` / `large_mode=follow` controls, and the cost
   sensitivity runs. They are run once on the IS-selected finalist (or at defaults when there is no
   finalist) and reported next to it.
7. Pre-declared scope by card (from the batch plan, before any result was seen):
   - `month_end_fix`, `comex_expiry`: screen + sign check + placebo only (≈ 12–24 events/yr), no grid,
     no freeze.
   - `macro_shock`: NFP+CPI only (card restriction) gives ≤ ~22 IS events → X7; screen, at most a small
     card-exit grid (≤ 12 rows, counted), placebo, no stage 2, no freeze.
   - `release_bracket`: the finalist is also reported under `bt1s.STRESS` and under raw Dukascopy
     spreads (`bt1s.Cost(sp_k=1.0, sp_min=0.0)`), IS and (at the single VAL look) VAL; these runs
     never select anything.
   - Long/short splits are reported for every finalist.

## Calendar conventions (`strategies/_d2util.py`)

The real calendar (`ctx.calendar()`, `data/calendar/us_macro_2025_2026.csv`) has columns
`event, date_local, time_local, datetime_utc, source_url, verified, note` and no tier column. Rows whose
note starts with `SCHEDULED` are dropped. Tiers are defined in the module (researcher choice):

| Tier | Events |
|---|---|
| 1 | NFP, CPI, FOMC_statement |
| 2 | PCE, GDP_advance, GDP_second, GDP_third, retail_sales, PPI, ISM_manufacturing, ISM_services, JOLTS |
| claims | jobless_claims (kept separate; joins an event set only where a card names 08:30 releases) |
| excluded | FOMC_minutes (no data surprise; only used to exclude placebo days) |

Releases sharing one timestamp are merged into one event whose type is the highest-tier member
(order NFP > CPI > FOMC_statement > PCE > GDP_advance > retail_sales > PPI > ISM_manufacturing >
ISM_services > JOLTS > GDP_second > GDP_third > jobless_claims). Shutdown cancellations simply have no
row; merged/shifted releases are used at their actual recorded time. Release times are New-York local
and the calendar's UTC column is DST-aware. The FOMC press conference (14:30 ET on statement days) is
not in the file; where a card needs it, it is derived as statement time + 30 min.

There is no consensus/actual data. Where a card needs "surprise size", the proxy is gold's own realised
initial reaction (the first seconds/minutes move, scaled by the history of the same quantity on prior
events, or by pre-release volatility), stated per strategy.

Placebo (control): every event is moved to the same New-York clock time on a matched weekday with no
calendar release of any kind on that day (offsets tried in order −7, +7, −1, +1, −2, +2 calendar days;
US holidays excluded). The event type label is kept, so history-based scalings behave the same way.

Other conventions: `unit` = the native stop distance; explicit 20:55 UTC flat (20:45 where the card
says so); no PARAMS key that only changes sl/tp; numeric PARAMS sorted ascending, categorical keys
last.

## Results

No D2 strategy qualified for a freeze (IS PF(R) ≥ 1.30 and VAL PF ≥ 1.30), so **no OOS run was made** and
no frozen card exists for D2. OOS data was never simulated for any D2 id. Raw outputs:
`results/batchD2_screen.txt`, `results/batchD2_screen2.txt`, `results/batchD2_controls{1,2,3}.txt`,
`results/<id>_optimise.txt`, `results/<id>_opt_stage1.csv`, `results/<id>_opt_exits.csv`.

### Summary table (IS-selected setting; VAL = the single final look; OOS not run)

| Strategy | Combos (stage 1 + stage 2) | IS-selected setting | IS n / WR / PF / PF(R) / DD% / tr/wk | VAL n / WR / PF / PF(R) / DD% | OOS | Placebo (same rules, matched no-release days) | Verdict |
|---|---|---|---|---|---|---|---|
| post_release_revert | 108 + 106 = 214 | s0 300 s, delay 0, q_max 1.25, r_min 0.0, card exit (plateau 0.72) | 60 / 70.0 / 0.96 / 0.88 / 3.10 / 1.26 | 27 / 63.0 / 0.73 / 0.73 / 2.99 | – | IS n41 PF 0.59 PF(R) 0.63; VAL n25 PF 0.69 | REJECT (IS PF(R) < 1.3) |
| pre_release_drift | 108 + 0 = 108 | none: max n_IS 42 (all_t12) | defaults: 2 trades; best n ≥ 30 row PF(R) 0.83 | – | – | all_t12/d2/z0.5/v1: real IS PF(R) 0.64 vs placebo 1.25 | INELIGIBLE (trade count, X7); no edge |
| release_range_crush | 54 + 159 = 213 | tol 0.0, crush 0.7, w_min 0.5, event_set t1card_t2, card exit (stop IR ext ∓ 0.25W, target IR mid; plateau 1.03) | 95 / 48.4 / 1.02 / 1.03 / 7.24 / 1.91 | 42 / 52.4 / 1.45 / 1.56 / 2.98 | – | IS n48 PF 0.71 PF(R) 0.49; VAL n27 PF 0.66 | REJECT (IS PF(R) < 1.3) |
| release_bracket | 108 + 0 = 108 | none: max n_IS 44 (event_set all) | defaults: 16 / 31.3 / 0.66 / 0.52 / 2.96 / 0.51; stage-1 median PF(R) 0.69 | defaults: 4 trades | – | 1 placebo trade (no PR breakouts on quiet days) | INELIGIBLE (trade count, X7); negative IS |
| macro_shock | 12 + 0 = 12 | none (≤ 14 IS trades at any setting) | defaults (s 1.0, NFP+CPI, 1 h): 10 / 40.0 / 0.49 / 0.41 / 2.33 / 0.27 | 5 / 40.0 / 0.42 / 0.54 | – | IS n9 PF 2.01 (placebo beats real) | INELIGIBLE (X7); sign wrong |
| month_end_fix | screen + 5 sign variants | defaults (m_min 2 %, 15:00 London, both legs) | 16 / 18.8 / 0.55 / 0.56 / 5.13 / 0.41 | 4 / 25.0 / 0.27 / 0.28 | – | IS n12 PF 0.11 | REJECT (no sign support; pre-declared screen only) |
| comex_expiry | screen + 5 sign variants | defaults (expiry+fnd, r5_min 0.5, short 08:20→13:35 NY) | 8 / 25.0 / 0.35 / 0.35 / 1.57 / 0.21 | 5 / 40.0 / 6.05 / 3.30 / 0.55 | – | placebo days (7–9 bd before month end): IS n19 PF 1.66 | REJECT (does not beat placebo; IS sign against card) |

Screen at card defaults (IS): post_release_revert 4 trades (PF(R) 0.59); release_range_crush 41 trades PF(R) 0.43;
release_bracket 16 trades PF(R) 0.52; macro_shock 10 trades PF(R) 0.41; pre_release_drift 2 trades.

### Long/short splits (finalists / defaults)

| Strategy | IS long n / PF / PF(R) | IS short n / PF / PF(R) | VAL long | VAL short |
|---|---|---|---|---|
| post_release_revert (finalist) | 28 / 0.55 / 0.59 | 32 / 1.60 / 1.24 | 15 / 0.43 | 12 / 1.28 |
| release_range_crush (finalist) | 43 / 1.14 / 1.30 | 52 / 0.91 / 0.85 | 15 / 1.39 | 27 / 1.50 |
| release_bracket (defaults) | 11 / 0.82 / 0.64 | 5 / 0.39 / 0.32 | 3 / all wins | 1 / win |
| macro_shock (defaults) | 8 / 0.46 / 0.21 | 2 / 0.55 / 1.90 | 4 / 0.12 | 1 / win |
| pre_release_drift (all_t12, d2, z0.5, v1) | 26 / 0.80 / 0.58 | 16 / 0.91 / 0.75 | 11 / 1.31 | 11 / 0.38 |
| month_end_fix (defaults) | 8 / 1.06 / 1.18 | 8 / 0.08 / 0.04 | 2 / 0.89 | 2 / 0.00 |
| comex_expiry (defaults, short only) | – | 8 / 0.35 / 0.35 | – | 5 / 6.05 |

### Per-strategy notes

**post_release_revert** (card r2-post-release-small-surprise-revert). Events: all 08:30 ET releases (incl. claims)
plus 10:00 ET tier-1/2, FOMC days skipped; 219 events in the whole file (~115 IS). Surprise proxy = gold's own
reaction R0 = mid(T+s0) − mid(T−60 s), scaled by the median |R0| of the previous 20 same-type events (pooled when
< 20). Grid deviation (from signal counts, before any grid): ATR14(1m) ≈ $2.4 against a median |R0| ≈ $3, so the
card's two filters were almost mutually exclusive (4 trades in 22 months at defaults); r_min 2.0 → 0.0 and
q_max 0.5 → 1.25 so that n_IS ≥ 60 is reachable. Even so, only two stage-1 settings reach n_IS ≥ 60, the best
plateau is 0.72, and no stage-2 template had a neighbour median ≥ 1.30 (best single template 1.52, scalp+BE,
ineligible). The `large_mode=follow` control (continuation after large reactions) also loses (IS PF 0.85).
The real fade beats its placebo (0.96 vs 0.59 IS PF) but is still net negative. Rejected on IS.

**pre_release_drift** (card r2-pre-release-drift-10et). The card's E10 set (Conference Board, existing/pending
home sales, industrial production) is absent from the verified calendar, so E10 = the two ISM releases
(~22 IS events). Widened sets (ISM+JOLTS, all 10:00 ET, + all 08:30 tier-1/2) top out at 42 IS trades. USA500 votes
use USA500IDXUSD 1m BID bars (downloaded during the batch). Ineligible by trade count; where n is largest the
signal underperforms its own placebo (IS PF(R) 0.64 vs 1.25). A bug found during the screen (DataFrame `.T`
attribute clash, plus pre-data days in the z-score baseline) was fixed before the grid; the screen numbers above
are after the fix.

**release_range_crush** (card r2-post-release-range-crush-fade). Tier-1 card set (NFP, CPI, PCE, GDP advance,
retail sales, FOMC statement + press conference at +30 min) gives ≤ 56 IS trades; the t1card_t2 widening (adds
PPI, ISM, JOLTS, GDP 2nd/3rd) reaches 95. The finalist breaks even on IS (PF(R) 1.03, DD 7.2 %) and is rejected on IS
despite VAL PF 1.45 (VAL is never used to select). Placebo is clearly worse (IS PF(R) 0.49) and the `mode=break`
control loses (IS PF(R) 0.81), so there is some event-specific mean reversion, but it does not survive costs in IS.

**release_bracket** (card r2-release-bracket-impulse). Impulse at T+s1 vs mid(T−5 s), sd from the previous 24 events,
must clear the 15-min pre-range; spread filter vs the median release-second spread of the previous 20 events.
Even with claims added (event_set all) the filters leave ≤ 44 IS trades. Ineligible by trade count. Cost
sensitivity at defaults (IS, 16 trades): base PF 0.66, `bt1s.STRESS` PF 0.45, raw Dukascopy spread
(`Cost(sp_k=1.0, sp_min=0.0)`) PF 0.58. The first-seconds capture loses even before the optimistic part of the fill model.

**macro_shock** (card academic-macro-shock-15m-drift). NFP+CPI only (card restriction): ≤ 14 IS trades at any of the
12 grid rows. Continuation after the 15-min shock loses (IS PF 0.49), and its placebo does better (IS PF 2.01, n9).
A 4 h hold (control) is IS PF 1.45 but VAL PF 0.14. Ineligible; the continuation sign is not supported.

**month_end_fix** (card r2-month-end-fix-hedge-flow). Uses USA500IDXUSD month-to-date return. 11 IS month-ends pass the
USD-shock filter at m_min 0. Leg 1 (pre-fix follow) IS PF 1.07 (n8) is noise-level, leg 2 (post-fix fade) IS PF 0.08.
The placebo (same weekday one week earlier) is also negative. No sign support. Pre-declared screen only.

**comex_expiry** (card r2-comex-expiry-pressure). Expiry dates by the CME rule (checked against the published Jan 28 and
Mar 26 2025 expiries; 2025-12-24 may be 12-23 under a repeated holiday shift, one event). The short rule loses in IS
(PF 0.35, n8), and the placebo days 7–9 business days before month end do better (IS PF 1.66, n19). VAL (PF 6.05, n5)
is too small to mean anything and cannot be used to select. Rejected as a calendar effect.

### Conclusion

None of the 7 macro-calendar ideas qualifies. The two event-specific effects that beat their placebo
(post_release_revert, release_range_crush) are about breakeven after realistic costs in IS. The rest are
ineligible by trade count (pre_release_drift, release_bracket, macro_shock) or fail their sign/placebo check
(month_end_fix, comex_expiry). With ~120 usable release timestamps a year, after the event filters every card
except range-crush falls below the 60-IS-trade bar, so a WR > 75 / PF > 3 strategy on ≥ 100 IS+VAL trades cannot
come from this calendar alone. No frozen cards; no OOS looks used.

### Protocol disclosures (in reply to the supervisor's D2 guidance)

1. **Selection rule.** Committed on its own in 5e2a6ea (`research/d2_select.py`, a copy of the D1 plateau rule, plus
   the tier definitions and the pre-declared scope by card) **before any D2 grid was run**. The selections above
   are the output of that script, reading IS columns only.
2. **VAL visibility.** This deviates from "print VAL only for IS-qualified finalists", and I am stating it
   plainly. VAL was shown for settings that did not qualify on IS:
   - `evaluate.py screen` prints VAL at the card defaults. This is a harness default, as in earlier batches.
   - `optimise` prints the VAL columns of its IS top-15 rows.
   - I ran `d2_select.py --val` and the control script for the two IS-failing finalists (post_release_revert,
     release_range_crush).
   No decision used any VAL number: both finalists failed the IS PF(R) ≥ 1.30 bar before VAL was read, and
   nothing was frozen.
3. **Calendar join / causality.** Events sit at the calendar's verified release seconds (`sec` from the DST-aware
   `datetime_utc`). Every decision uses only data up to its own decision second:
   - The 1s mid at second T+s is that second's close, and the engine fills at the next second's close.
   - 1m bars are used only when `close_sec` ≤ the decision second.
   - Cross-asset 1m bars are used only when they close by the decision second.
   - ATR comes from the last bar closed before T.
4. **Pooling across release types.** The tier definitions and the merge rule were committed before the grids
   (5e2a6ea). The per-strategy `event_set` pooling keys (release_range_crush t1card_t2, release_bracket t12/all,
   pre_release_drift ISM_JOLTS/all10/all_t12) were written into the modules before any grid was run, based on
   event counts only. However, the module files were committed **after** the grids (in the results commit), so
   git does not prove they came first. The post_release_revert grid change (r_min 2.0 → 0.0 and q_max 0.5 → 1.25)
   was made after its screen run at the defaults (4 trades). It was based on signal counts and filter scales, not
   on P&L, and it is documented in the module docstring. No pooling or grid change was made after any grid
   result. No verdict depends on these points: every pooled setting is either below n_IS 60 or below IS PF(R) 1.30.
5. **Combos counted:** 214 + 108 + 213 + 108 + 12 = 655 grid rows across the 5 gridded ideas (each ≤ 300). There
   were also 2 screen-only ideas, and control runs (placebo, follow/break, cost, sign variants) are not part of
   any search.
