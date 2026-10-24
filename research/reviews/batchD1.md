# Batch D1 review (boss), 2026-10-24

Inputs reviewed:
- `research/results_batchD1.md` and registry rows D1-1 to D1-7
- `research/d1_select.py` and its git history
- the 7 modules and `strategies/_d1util.py`
- `bt1s.Context.m1` and `calendar()`, and `download_m1.py` (timestamp convention)
- `results/<id>_opt_stage1.csv` and `_opt_exits.csv`, including the gold_silver `*_prefix.csv` files
- `strategy_cards/usd_impulse_catchup.frozen.json`, with git history

I re-ran `d1_select.py` for all 7 ids without `--val` (IS columns only).

## Protocol checks

- **Selector committed before any grid.**
  - c414e82 (01:27:12) adds `research/d1_select.py` and the rule text.
  - `d1_select.py` is unchanged from c414e82 to HEAD.
  - The earliest D1 grid file is `reopen_gap_fade_opt_stage1.csv` (01:28:11), and every other D1
    grid is later (01:33 to 01:52). Verified.
- **Selector applied correctly, IS only.**
  - The selector prints VAL only with `--val`.
  - Re-running it reproduces all 7 reported finalists and exits: reopen (card), gold_silver (card),
    vr_kalman (fixed 1.5/3.0), tick (card), usd_impulse (fixed 2.0/2.0), common_factor (card) and
    riskoff (card).
  - The rule is the protocol's top-plateau rule with a template-neighbour check, which fixes the
    Batch C deviation.
- **Freeze before OOS.**
  - usd_impulse_catchup was frozen at 01:41:05, committed in 01c6bcd (01:41:41) with
    `oos_run: false`, and the OOS run was at 01:42:19.
  - The v3 hash 1e501d2caf57ac97 still matches. It covers `_d1util.py`, whose sha256[:16] is
    289fc7dab1b30ac0 and which is unchanged since d14606a.
- **Budget.** Stage 1 is ≤ 141 everywhere (maximum 135), and every count is reported. gold_silver
  counts both the pre-fix and post-fix grids (534). Good.
- **ICT/SMC:** none.

## New audit areas

**Cross-asset look-ahead: clean.**
- Data convention: `download_m1.py` stores Dukascopy BID candles with `ts` = minute start, and
  `ctx.m1` sets `close_sec = ts + 59`.
- Every module reads the cross-asset close at a minute-start index whose close is at or before the
  XAU decision second:
  - usd_impulse_catchup and riskoff_rebound read at the XAU 1m bar's own minute-start (same close
    second, t+59).
  - gold_silver_residual reads the 1m bar starting at 5m start + 240, which closes at the 5m bar's
    close_sec.
  - common_factor_residual reads the 1m bar starting at 15m start + 840, which closes at the 15m
    close_sec.
- Gaps and holidays in other markets: closes are forward-filled for at most 5 minutes (4 for
  gold_silver, 14 for common_factor), so missing data is NaN rather than stale.
  - W-window returns that span a NaN produce no signal.
  - common_factor needs ≥ 2 factor members present, and a missing residual adds 0.
  - USATECH and Brent closures (US holidays, the ICE break) therefore suppress signals rather than
    fabricate them.
- Same-second synchronous use of the cross-asset close is implementable in a cBot (subscribe to the
  other symbol's bars, with 1 s execution latency).
- Rolling statistics:
  - `clock_baseline` uses the pivot by day with `shift(1)`, i.e. prior days only.
  - The beta and correlation windows use daily sums with `shift(1)`.
  - riskoff's pooled z uses the prior 20 days.
  - The common_factor trend-decile filter uses the previous day's rank.
- Scheduled release times may be used before they happen, because the calendar is published in
  advance. `near_release` windows are fine.

**gold_silver_residual exit bug and full rerun: accepted.**
- The defect was genuine. `abs(S) <= S_out` with S_out = 0 practically never fires (no target).
  With S_out > 0 it also missed a jump straight through the band. The fix (`side*S >= -S_out` =
  crossing) is what the card means.
- VAL handling:
  - The pre-fix finalist's VAL (PF 1.29) was seen.
  - The rerun used the same pre-committed rule, selected the same setting, kept the card exit, and
    was rejected **on IS** (PF(R) 1.12) before VAL could matter.
  - No decision used VAL. The post-fix VAL row should not have been printed, but it is harmless.
- The strategy is closed.
- The silver-leg diagnostic (+4.3 bp gold leg, −15.4 bp silver leg) shows the spread did not
  converge. That is a good, honest diagnostic.

**common_factor_residual gap-blanking fix at screen: accepted.**
- It is a genuine defect: NaN returns across the daily break blanked C for Zwin bars, so Z was
  finite on only 60 % of bars.
- It was fixed before any grid, and only the fixed version was optimised.
- The screen prints a VAL row by harness design (true in every batch). The fix was motivated by Z
  coverage, not by VAL.
- Rejected on IS (PF(R) 1.01).

**Grid recalibrations away from card thresholds: justified by trade count, not a disguised peek.**
- **reopen_gap_fade.** g_min 0.1/0.2 were added because the card's 0.3–1.0 gives only 7–30 IS+VAL
  trades. That is a count argument, made on IS counts only.
  - The search still kept 0.3/0.5/1.0.
  - The finalist (g_min 0.1) fails IS (PF(R) 0.90), and the follow control also loses (0.76).
  - A recalibration that ends in an IS rejection cannot be a peek that helped.
- **tick_intensity_follow.** imb_min was moved from 0.2–0.45 to 0.1–0.2, based on the IMB
  *distribution* (sd 0.097; |IMB| ≥ 0.3 in 0.2 % of bars). The card default still gives only
  8 trades.
  - That is an outcome-free calibration, and it is disclosed.
  - The finalist fails IS (0.77), and the zero-cost run (PF(R) 1.16) shows the pre-cost edge is
    below cost, consistent with T3.

**News filters with the self-defined TIER1: acceptable.**
- The calendar is verified, and the tier-1 set (NFP, CPI, PPI, FOMC, retail sales, GDP advance, PCE,
  ISM×2, JOLTS) is a reasonable, standard choice.
- It was fixed in the helper before the grids and is covered by the hash. It was not tuned: it is
  not a PARAMS key.
- The "all events" filter for the 1m strategies is the conservative choice.

**riskoff_rebound long-only observation: must not be revived.**
- The IS long subset (53 trades, PF(R) 2.02) and the long-only benchmark (59 trades, 1.93) are below
  60 trades. The long side's VAL (28 trades, PF 0.93) has been seen and fails.
- Any "riskoff_long" id would be selected on IS subsets plus seen VAL. It is closed.

**USA500 not tested as the risk proxy: acceptable, and no rerun.**
- It is documented (the data arrived after the run).
- S&P 500 versus Nasdaq-100 as a risk proxy is not a *materially different* idea, since the two are
  highly correlated.
- riskoff's VAL has been seen, so adding the variant now would mean a second VAL look.

**reopen_gap_fade session timing (note).** Decisions after the 22:00/23:00 UTC reopen are held to
`exit_utc` of the *next* date. That is inside the new trading session, consistent with the
23:00→21:00 session convention (as with asian_drift). No position is carried across a daily close.

## Per-strategy verdicts

### common_factor_residual — ACCEPT (reject on IS)
The code is causal and the gap fix is correct. Finalist (EntryZ 1.5, Zwin 16, ExitZ 0.3, 3 members,
card exit): IS PF(R) 1.01 on 371 trades. No template is eligible.

### usd_impulse_catchup — ACCEPT (OOS FAIL, final)
- Causal: the leader close is at the same close second, the beta, correlation and sd come from prior
  days, and the spread gate is causal.
- The finalist (XAGUSD leader, W 30, k 4, hold 30; fixed sl 2/tp 2) was selected by the committed
  rule: plateau 1.14, template neighbour median 1.725, IS PF(R) 1.76. VAL PF 2.13 on 22 trades.
- OOS: 12 trades, PF 0.25, so it would fail the n ≥ 25 gate even if profitable. Stress PF 0.25.
- Robustness: 1.11 (1.38 numeric only), below the 2.0 gate.
- The random-side benchmark (95th percentile 1.24) shows the IS edge was beyond chance in IS. It did
  not generalise.
- Final.

### gold_silver_residual — ACCEPT (reject on IS after the bug-fix rerun)
See above. The finalist is a grid corner (N 24, S_in 3.0, w 1.0). IS PF(R) 1.12.

### riskoff_rebound — ACCEPT (reject on IS)
Causal: the stabilisation bar closes after the trigger, the stop low is from t to the decision
second, and the window high is from t−W to t. Finalist (mirror on): IS PF(R) 1.23. The long-only
subset is closed (see above).

### reopen_gap_fade — ACCEPT (reject on IS)
Causal: the break type is known at the reopen, the per-minute spread medians use closed minutes,
the baseline comes from previous reopens, and the ATR is from before the break. Finalist IS PF(R)
0.90. The follow control also loses. The card's thresholds give too few trades.

### tick_intensity_follow — ACCEPT (reject on IS)
Causal: the decision is at the close of the persistence bar, the baselines come from prior days, and
the news check is at the decision second. IS PF(R) 0.77, with a sub-cost pre-cost edge.

### vr_kalman_regime — ACCEPT (reject at VAL)
Causal: the Kalman level, rolling sd and VR all use past bars, and the exits are evaluated at closed
bars with an exit fill 1 s later. Finalist (corner q 12, band 0.25, z 2.5; fixed 1.5/3.0): IS PF(R)
1.66, VAL PF 0.79. Its single VAL look is final. The regime-gate benchmark is reported, which is
good practice.

## Summary table

| Strategy | Verdict | One-line reason |
|---|---|---|
| common_factor_residual | ACCEPT (reject on IS) | gap fix correct; IS PF(R) 1.01 |
| usd_impulse_catchup | ACCEPT (OOS FAIL, final) | committed rule, freeze before OOS; OOS 12 trades, PF 0.25 |
| gold_silver_residual | ACCEPT (reject on IS) | genuine exit bug, full rerun under the same rule; IS PF(R) 1.12 |
| riskoff_rebound | ACCEPT (reject on IS) | IS PF(R) 1.23; long-only subset not to be revived |
| reopen_gap_fade | ACCEPT (reject on IS) | count-justified g_min; IS PF(R) 0.90; follow control also loses |
| tick_intensity_follow | ACCEPT (reject on IS) | distribution-based imb_min; edge below costs |
| vr_kalman_regime | ACCEPT (reject at VAL) | IS PF(R) 1.66, VAL PF 0.79 |

## Instructions for the Batch D1 agent

**ACCEPT – no further work.** No reruns, no new ids, and no further VAL or OOS looks.

Documentation only, in `results_batchD1.md`:
1. Add one line saying that riskoff long-only and a USA500-proxy variant are closed: VAL has been
   seen, and the variant is not materially different.
2. gold_silver_residual: note that the post-fix VAL row was printed although the finalist failed IS,
   and that it informed no decision.

For D2 (macro releases):
- Keep the same discipline: a selector committed before the grids, the plateau rule, and VAL only
  through `--val` for IS-qualified finalists.
- Release-time joins must use the calendar's scheduled `sec`, and post-release bars must have
  `close_sec` ≤ the decision second.
- Trade-count eligibility (X7) will bind for monthly releases. NFP and CPI give about 12 events a
  year each, so pooling across release types is needed to reach 60 IS trades. That pooling must be
  decided before the grid.
