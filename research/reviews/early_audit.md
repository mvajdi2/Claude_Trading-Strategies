# Early code audit (boss), 2026-10-23

Scope: every module in `strategies/` that existed at audit time (ignoring `test_orb.py`), plus the
shared helpers `batcha_util.py` (A) and `_bxutil.py` (B). This is a code audit only. Results files
were looked at only to check the protocol (how `optimise` was run). No OOS numbers exist yet and none
were looked at. Strategy files were not modified.

Method: read each module against its card(s) in `research/cards/*.yaml` and against the engine
(`bt1s.run`) and evaluator (`evaluate.py`) semantics. Then ran one Python process at a time to count
IS signals at the card defaults (and some variants): trades per week, long/short split, UTC hours of
the decision seconds, DST behaviour and decisions placed after the 21:00 UTC flat.

Verdicts are about the **code** (look-ahead, card fidelity, DST, frequency). Section X lists the
**cross-cutting protocol problems** that apply to every batch. Every agent must apply X1 to X5 to
every strategy, whatever its per-strategy verdict.

---

## X. Cross-cutting findings (send to all three agents)

**X1. The card's own exit is never tested in `optimise` when `EXIT_UNIT=True`.**
`evaluate.optimise` builds `exits` only from `EXIT_TEMPLATES` (fixed / scalp_be / trail). The native
`sl/tp/hold` the module returns is never in the grid. The cards' defining exits are therefore never
optimised. For the time-exit cards (last30, first_last_hh, asian_drift, pmfix, fomc_drift, tsmom_day,
Williams, Crabel, IDNR4) that is the disaster stop plus time exit with no target. For the
structural-target cards it is the opposite side of the range (fakeout, mp_80pct), the BB mid
(bb_pinbar), VWAP (vwap_sd_fade), the IB mid (ib_extension fade) or the prior swing
(holy_grail). They appear only in the single `screen` run.
→ Instruction: evaluate the native exit as an explicit exit option in the IS search, and count it
toward the grid.

**X2. Grids are randomly subsampled, which leaves no plateau or neighbourhood evidence.** With
53 templates, every module's `|PARAMS| × 53` is far above 300. Some examples: asian_range_breakout
72×53 = 3,816; last30 48×53 = 2,544; level_sweep 27×53 = 1,431. `optimise` then draws 300 at random
(about 8 to 20% coverage). `results/*_opt.csv` already shows this, for example
asian_range_breakout_opt.csv with 300 rows of 3,816. A random 8% sample cannot show a plateau, and
the "check the neighbours in `_opt.csv`" step is impossible.
→ Instruction (staged IS search, total ≤ 300 counted):
  (a) Stage 1: the full PARAMS grid with the **native exit only**. Run it with `EXIT_UNIT=False`,
      or with a small driver that calls `bt1s.run` on `visible(signals)`. Save it as
      `results/<id>_opt_stage1.csv`, because a second `optimise` call overwrites `<id>_opt.csv`.
  (b) Stage 2: take the 1 to 3 best IS settings **on a plateau** from stage 1. Run all 53 templates
      on each with a driver (`evaluate.apply_exit` + `bt1s.run`) and save to
      `results/<id>_opt_exits.csv`.
  (c) Report the total count (stage 1 + stage 2) per idea. Reduce PARAMS so that the total is
      ≤ 300.
  Do **not** collapse PARAMS to single values in the module to get stage 2. `robustness()` needs
  the full grids (see X3).

**X3. `robustness()` uses list positions, but PARAMS lists are in "default first" order.**
`evaluate.robustness` takes neighbours `grid[i-1], grid[i+1]` by list position. Every module puts
the card default first, because `screen` uses `v[0]`. So the "±1-step" neighbours are wrong. Example
from last30: `k: [0.5, 0.0, 0.25, 1.0]`. The neighbour of 0.5 becomes 0.0 only, and the neighbours of
0.25 become 0.0 and 1.0. Categorical switches also become "neighbours" (mode break↔retest,
fade↔follow, rng_filter, first_window, profile), which makes the robustness gate meaningless for
them.
→ Instruction: after `screen` (already done) and **before** `optimise` or `freeze`, put every
numeric PARAMS list in ascending order. The values stay the same, so the opt CSVs stay valid. For
structural switches that define different strategies, freeze each variant as its own id or list the
switch last and say so: `london_range_ny_break.mode`, `pmfix/fomc_drift.direction_mode`,
`ib_extension_ny.mode`, `avwap_london.mode`, `round_level.direction`. In the batch report, also give
the neighbourhood median computed **without** the categorical keys.

**X4. Parameters that the exit templates silently turn into no-ops.** `apply_exit` overwrites
`sl/tp/tp1/f1/be/trail` with multiples of `unit`. Any PARAMS key that only changes those columns
therefore creates duplicate rows that count toward the 300. Examples: `ema_pullback_adx.exit_mode`
and `.stop_atr` (unit = ATR), and `vwap_cross_mtf.stop_atr`. A related problem: some modules set
`unit = ATR` where the card stop is structural (holy_grail, ema_pullback_adx, vwap_cross_mtf,
pdh_pdl_breakout). Every template then throws away the card's structural stop.
→ Instruction: remove such keys from PARAMS. Where the card stop is structural, set `unit` = the
native stop distance (R), so that templates scale the card's stop.

**X5. Exits at the "close" and the 21:00 boundary.** The engine flattens at 20:59:59 UTC. During
EDT that is the last minute before the daily break, when spreads blow out. Cards ask for 20:55 (or
20:45). The "close" variants hand this to the engine with `hold = 12h/16h/22h/24h`: last30, pmfix,
first_last_hh, fomc_drift, tsmom_day, ema_pullback_adx, supertrend_rsi, vwap_cross_mtf and
avwap_london.
→ Instruction: compute the exit at the card's time (20:55 or 20:45 UTC) explicitly in `hold`. Also,
the engine moves any decision at or after 20:59:59 UTC to the **next** UTC day's 21:00 flat. That is
correct for entries in the 23:00 to 24:00 UTC hour that belong to the next trading day (Williams
ref_open=23, tsmom session_start=0, asian_drift's 23:59:59). For any *same-session* signal it would
be an overnight hold. Every module must guarantee that same-session signals have
`sec % 86400 < 75540` (20:59 UTC). See holy_grail.

**X6. Freeze integrity for the shared helpers.** `freeze` hashes only `strategies/<id>.py`. Batch A
imports `batcha_util.py` and Batch B imports `_bxutil.py`. Their hashes are not covered.
→ Instruction: put the sha256 of the helper file in the freeze `note`, and do not edit a helper
after any strategy that imports it has been frozen. A material change needs a new helper file.

**X7. Trade-count gate is out of reach for some cards (report, don't tune).** The gate needs
≥ 100 IS+VAL and ≥ 25 OOS trades. Cards with a published frequency of 2 to 4 per month (IDNR4,
Raschke 80-20) or 8 per year (FOMC) cannot get there. A 300-combination search on about 30 IS trades
only manufactures overfit.
→ Instruction: for these, run `screen` and at most a small native-exit grid. Report them as
"ineligible by trade count" unless an honest variant raises the count, such as `require_inside=False`
or `cond="oops"`. Do not freeze one only to "use" an OOS run.

---

## Batch A: breakouts and session ranges

Present: asian_range_breakout, crabel_orb_stretch, idnr4_breakout, williams_vol_breakout, ny_orb,
london_range_ny_break, pdh_pdl_breakout, ib_extension_ny, plus `batcha_util.py`.
Not yet present: bbkc_squeeze, noise_area_momentum, shanghai_open. These will be audited in the
batch review.

Helper `batcha_util.py`: clean. `first_touch` decides on the 1s high/low of the touching second, and
the engine fills at the next second (mid-based, so slightly conservative for stop orders). It skips
the day when both sides touch inside one second. `prev_rows` strictly uses `index < td`.
`vol_state_pct` uses the previous day's realised variance. `local_sec` is DST-correct. One caveat:
the trading day is 23:00 to 21:00 UTC all year, so in EDT the real 22:00 to 23:00 UTC reopen hour is
left out of daily bars and of the Williams "day open". This is consistent and has no look-ahead.
Note it in the report.

## asian_range_breakout — REDO
Findings:
- Look-ahead: none. The range is complete at `range_end`, the vol state and ATR come from prior
  days, the 05:59:59 placement check uses the mid, and fills use the 1s touch.
- **Signal frequency is far below the card because the USD range filter is stale.** The default
  `rng_filter="usd"` (3 to 20 USD) is the vendor's 300 to 2000 points, set when gold was near $2000.
  In IS 2025 the median 00:00 to 06:00 range is **$25.0**, 62% of days are > $20, and the 10th to
  90th percentiles are $11.5 to $53. The defaults give **95 IS trades = 1.9/wk** against the card's
  ~0.8/day (≈4/wk). The filter keeps only the quietest 38% of days, which is a selection bias.
  `rng_filter="pct"` gives 3.7/wk and "none" gives 4.2/wk.
- `vol_state="top"` combined with the USD cap is self-contradictory (high-vol days have wide
  ranges). It gives **9 IS trades**, with the first one on 2025-06-06.
- Card variants not covered: `stop_mode=midpoint` (cards 1 and 3; the 0.5×unit templates
  approximate it), the asian window 23:00 to 06:00 and 01:00 to 07:00 (card 3; `U.at` already
  supports h ≥ 23), flat at 21:00 with 2.5R and BE at 1.5R (card 2; `flat_h` is fixed at 16), and the
  card-1 spread filter (> 0.35 at placement).
- Stop and target are distances from the fill (the next second after the touch), not from the level.
  The difference is small for stop entries, so this is acceptable.
Instructions (IS only):
1. Replace the `rng_filter` grid with scale-free filters: `["pct", "atr", "none"]`, with pct = 0.3 to
   1.6% (card 2) and atr = 0.2 to 1.0 × ATR14(D) (card 3). Remove or rescale "usd".
2. Re-test `vol_state` ∈ {all, midtop, top} with the pct/atr filters only. Report the IS n for each.
3. Add `range_start: [0, 23, 1]` (paired with `range_end` 6/7 as in card 3) and `flat_h: [16, 21]`.
   Keep the grid within X2 after trimming the low-value keys (for example `cutoff`).
4. Report long and short legs separately (card 2 note on bull drift).
5. Apply X1 to X3 and rerun. The existing `asian_range_breakout_opt.csv` was made with the stale
   filter and 8% random coverage, so it must not be used for selection.

## crabel_orb_stretch — ACCEPT
Findings: faithful to the card. OR = 07:00 to 07:00+N UTC. The stretch is a rolling mean of prior
days' min(H−O, O−L) over 07:00 to 12:00, read through `prev_rows`, so it is known before the day.
The NR4/NR7 filter is on the prior 23:00 to 21:00 day. The ATR15 is taken from the last 15m bar that
closed before the OR end. The OR-width filter is ≤ 4×ATR15. Stop = opposite OR side, capped at
1.5×ATR15. Flat 12:00. No look-ahead. The card fixes the London open at 07:00 UTC, so that is not a
DST issue. Missing from PARAMS: `stretch_mult` 2.0 and `stretch_lookback` 5 (minor). There is also
the card's target variant 1.0×(OR width + stretch), which the fixed templates roughly span.
Instructions: X1 to X3 only. Optional: add a DST-aware 08:00 London OR start as an IS variant.

## idnr4_breakout — ACCEPT (code); see X7
Findings: the inside-day, NR-n and HV filters all come from the prior day through `prev_rows`.
Orders run from 01:00 to 18:00 UTC with a placement-inside check. The SAR re-entry is the first
touch of the opposite level after the first fill, valid until 18:00, with its stop at the original
entry level, as the card says. No look-ahead. The card expects 2 to 4 setups a month, so even with
SAR the IS+VAL count will be well below 100.
Instructions: X7. Report `require_inside=False` (NR-only) as the frequency-raising variant. Do not
run a 300-combination search on about 30 trades.

## williams_vol_breakout — ACCEPT
Findings: faithful. R comes from prior days, the open is the first 1m bar at or after the reference
time (within 30 min), the OCO uses 1s touches, and the flat is at 20:55. No look-ahead. `k_stop` is
fixed at 0.5, while the card grid is 0.3, 0.5, 1.0. The templates (sl 0.5 to 2.0 × R) cover all but
0.3. In EDT the "23:00 day open" is one hour after the real 22:00 UTC reopen (see the helper caveat).
Instructions: X1 to X3. Optional: add an `ref_open="ny1800"` DST-aware variant (the real reopen).

## ny_orb — ACCEPT
Findings: the OR at 09:30 NY is DST-aware (`local_sec`). Entry is the first closed entry_tf bar
beyond the OR before the cutoff. The width filter uses the last 15m ATR closed before the OR end.
Exit is 15:00 NY. No look-ahead. `target_x`/`stop_x` are singletons, and the templates cover the
card grid.
Instructions: X1 to X3. Optional: skip NYSE holidays and half-days (no 09:30 cash open).

## london_range_ny_break — REDO
Findings: break mode. The London range [start, 12:00) is complete before the first 30m bar
(12:30 to 12:59:59). BB(20,2) and ATR use closed 30m bars. The range filter is ≤ 2.5×ATR30 at 12:00.
Retest mode. Displacement uses the prior-bar ATR15. The 5m retest and reclaim loop uses only closed
bars and invalidates on a close through the stop. Both modes are clean. Deviations: the card-1
"BB outer band" target and the card-2 "skip if range > 2×ATR14(1h)×5" filter are missing. Entries
start at fixed 12:30 UTC, and the card itself says to check DST on the NY open. `win_idx` maps to
non-monotone values ([3,2,4] and [12,6,24]), which breaks X3, and `mode` is a strategy switch.
- **Break mode frequency is 5× below the card:** 30 IS signals = 0.6/wk against ~3/wk. The likely
  causes are the range ≤ 2.5×ATR14(30m) cap (London 07:00 to 12:00 ranges are wide relative to the
  30m ATR) and the BB filter (a close beyond the London range is often also beyond 2σ, so it is
  rejected).
Instructions:
0. Report the IS signal count after each filter (none, range cap only, BB only, both) and explain
   the gap. If the cap is the cause, test 3.0 and 4.0×ATR30 as IS variants. With BB, the card text
   says to skip the *zone*. Check whether that means "skip the day" or "take the next bar", and
   document the choice.
1. Split it into two ids (`london_range_ny_break` and `london_range_retest`), or follow X3 strictly.
   Make the window grids monotone (for example `ny_bars: [2,3,4]` and `retest_win: [6,12,24]` as
   real params).
2. Add the card-2 range filter to retest mode. Add a DST-aware NY start variant (08:30 NY) for
   break mode.

## pdh_pdl_breakout — ACCEPT
Findings: PDH/PDL come from the prior 23:00 to 21:00 day. Placement is at 00:05 with an
inside-levels check. `close_beyond` uses the first closed 15m bar. ATR(1h) comes from the last
closed hour before the signal. Flat 20:00. No look-ahead. `unit = ATR(1h)` matches the card's
1.0×ATR stop, so the templates are consistent. The card's "daily midpoint" stop variant is not
present (minor).
Instructions: X1 to X3.

## ib_extension_ny — ACCEPT
Findings: the IB window is complete before the first 5m bar is scanned. The median IB width uses the
prior 20 IBs (`shift(1)`). The VWAP is anchored at the IB start and includes only closed bars. The
fade uses the previous bar's ATR. One trade per day, flat 20:00. No look-ahead. The card grid's
13:20 UTC start is replaced by `ny0930` (DST-aware). Both are sensible. A DST-aware COMEX 08:20 NY
start would be more faithful to the card's intent than a fixed 13:20 UTC. `mode` is a categorical
switch (X3).
Instructions: X1 to X3. Optional: add `ib_start="ny0820"`.

---

## Batch B: reversal, structure, mean reversion

Present: asian_range_fakeout, level_sweep_reclaim, raschke_8020, wyckoff_spring, mp_80pct,
bb_pinbar_fade, rsi_extreme_fade, vwap_sd_fade, overreaction_fade, round_level, plus `_bxutil.py`.
ICT/SMC compliance: the Judas, PDH/PDL-sweep and previous-candle-sweep variants were correctly
dropped. Silver Bullet and Taylor sweep have no module. Good.

Helper `_bxutil.py`: clean. `align` uses `close_sec <= t`. `first_hit` scans [from, to] on the 1s
grid. `cap_per_day` counts signals rather than executed trades: a signal the engine skips because a
position is open still uses up a daily slot. This is minor, but it can drop the second real trade of
the day (level_sweep, wyckoff, overreaction, holy_grail and supertrend use the same pattern).

## asian_range_fakeout — REDO
Findings:
- Look-ahead: none. The range is complete at `asian_end`, signals use closed bars, and ATR includes
  the closed signal bar.
- **Re-arm bug.** When an excursion lasts longer than `max_bars_outside` and is still outside,
  `state` resets to 0. On the next outside close it re-arms with `first_i` and `ext` reset. The
  "within N bars of the first outside close" rule is then bypassed, and the stop is placed beyond
  the extreme of the re-armed part only, not the true excursion extreme. That understates R and
  inflates win-rate statistics.
- The 15m variant (practitioners card) is not faithful. It needs stop buffer 0.1×ATR (code
  `stop_buf` [0.2, 0.5]), time exit 16:00 (code 20:00 fixed), `max_bars_outside` 4/8/16 (code max 8)
  and the range filter "skip if range > 1.5×ATR14(1h)×6" (missing). The card-1 `target_mode`
  (midpoint / opposite / 2R) is lost in template mode (X1).
- Frequency: H1 defaults 2.46/wk (card 2 to 3/wk) and 15m 3.6/wk (card 1.5 to 2.5/wk). OK.
Instructions (IS only):
1. Fix the re-arm. Once an excursion has expired while still outside, require a close back inside
   the range before a new break can arm, and keep `ext` as the full excursion extreme.
2. Make the variant-specific parameters explicit: `exit_h: [20, 16]`, `stop_buf: [0.0, 0.1, 0.2, 0.5]`,
   `max_bars_outside` in bars of the chosen tf (1/2/3/5 for H1 and 4/8/16 for 15m). Add the range
   filter. Consider two ids (H1 and 15m) so that the neighbourhoods are meaningful.
3. Re-screen with defaults and rerun with X1 to X3. The existing opt CSV was made with buggy code.

## level_sweep_reclaim (Turtle Soup 15m) — REDO
Findings:
- Look-ahead: none. The prior N-bar extreme excludes bar i, the age logic is correct, and the
  trigger is the first 1s touch after the bar close.
- **Stop is anchored to the wrong price.** `sl = side*(level − ext) + 0.1·ATR` is a distance from
  the *level*. The engine applies it from the *fill*. **56% of IS signals fire within 5 s of the 15m
  close**, because the signal bar has already closed back beyond the level, so the stop entry is
  effectively a market entry that can be far beyond the level. In those trades the stop sits well
  inside the sweep low and is not 0.1 ATR beyond it as the card says. The median sl is only $3.45,
  so R is small and noisy relative to costs.
- Missing card filters: "skip 30 min either side of high-impact US data" and the 1×ATR trail after
  1R. Template trail only approximates the trail.
- Frequency 6.8/wk (card ~5/wk). OK.
Instructions (IS only):
1. Compute the stop from a price known at the decision second: `sl = side*(mid_at(k) − ext) + 0.1·ATR`.
   Alternatively, for immediate triggers (bar already closed beyond the level), treat the entry as a
   market entry at the bar close with the stop at the extreme. Report how many trades are immediate
   triggers.
2. Add a DST-aware news blackout parameter: 08:00 to 09:00 and 09:45 to 10:30 NY every weekday, as
   in `overreaction_fade`, with `news_skip: [True, False]`.
3. Report the median cost as a fraction of R. If it is > 15%, try the 40/80 channels on IS before
   concluding.
4. Rerun with X1 to X3.

## raschke_8020 — ACCEPT (code); see X7
Findings: faithful. The open/close position in the prior day's range, the range ≥ 0.8×ATR(D) filter,
the overshoot then the stop-entry back through yesterday's extreme (sequenced `first_hit`), the stop
at today's extreme − 0.05 ATR, the target at yesterday's midpoint, arming until 16:00, the flat at
20:55 and 1 trade per day. No look-ahead. The trail-the-remainder part of the card is missing
(minor). Frequency: **28 IS trades at defaults** (card 2 to 4 per month), so it is ineligible by
trade count unless `cond="oops"` raises n.
Instructions: X7. Report the oops variant as the frequency-raising variant. No large grid.

## wyckoff_spring — ACCEPT (code)
Findings: faithful. The range uses the previous N bars only. The touch counts are ≥ 2 per side. The
spring depth is 0.05 to 0.5 ATR with a close back inside, in the upper half. The volume rule
compares with the mean of the prior 20 bars. Entry is a stop at the spring high, valid for 3 bars,
or at the bar close. Stop and target are per the card. The session is 08:00 to 20:00. No look-ahead.
The screen shows only **16 IS trades** at defaults (card ~0.5/day ≈ 2.5/wk), more than 3× below the
card. The likely cause is that the low-volume and touch-count conditions together are very
restrictive.
Instructions: X1 to X3. Explain the frequency gap: report the IS counts for `vol_rule="none"`,
`max_width_atr` 3.5/5.0 and `range_bars` 24. If no setting reaches ~60 IS trades, report it as
ineligible (X7) and do not search exits on 16 trades.

## mp_80pct — ACCEPT
Findings: the prior day's profile (tick-volume or TPO, $0.50 bins, value area grown from the POC)
is used only on the next trading day. The reference-open check is ≤ 1 VA width outside value. The
consecutive 30m closes inside the VA are closed bars. The stop is today's extreme − 0.1 ATR, capped
at 1 VA. The target is the opposite VA edge. Entries stop at 16:00. No look-ahead. The partial at
the POC is missing (the templates' scalp_be roughly covers it).
Instructions: X1 to X3.

## bb_pinbar_fade — ACCEPT
Findings: faithful. The prior bar closed outside BB(20, dev). The pin geometry is per the card. The
EMA200(H1) filter uses the last closed H1 bar. Entry is at the pin close, stop is the extreme ±
$0.30, target is the SMA20, hold is 60 min, and the flat is 20:45. No look-ahead. The spread filter
(> $0.40) is missing (minor).
Instructions: X1 to X3. Also report the card's `target_mode` variants (1.0R, 1.5R), which are
template-covered.

## rsi_extreme_fade — REDO (small)
Findings:
- No look-ahead. RSI, EMA200 and ATR come from closed bars.
- **News blackout is not DST-aware.** It skips 12:25 to 12:35 and 13:55 to 14:05 UTC all year, but
  US releases are at 08:30 and 10:00 NY, which is 12:30/14:00 UTC in EDT and **13:30/15:00 UTC in
  EST**. The card's literal UTC times share the same mistake, but its intent is "US releases".
- **Frequency:** 5m defaults give 104 IS signals = 2.0/wk, against the card's 3 to 8 per *day*
  (7× or more below). 1m gives 13/wk. In a bull year, RSI < 30 with close > EMA200 is rare on 5m.
  Report the counts with `ema_filter=False`. If the card's frequency only holds at 1m without the
  filter, say so.
- Signals fire on every bar while the RSI is extreme. With one position at a time that means
  repeated re-entry into the same extreme after each exit. This is plausible per the card ("one
  position at a time"), but report the count of distinct episodes against trades.
Instructions (IS only):
1. Make the blackout NY-local: 08:25 to 08:35 and 09:55 to 10:05 America/New_York.
2. Add `one_per_episode: [False, True]` (re-arm only after the RSI returns to 50) as an IS variant.
3. Rerun with X1 to X3.

## vwap_sd_fade — ACCEPT
Findings: the VWAP and the tick-weighted sd use cumulative sums including the closed bar.
Signals start ≥ 1 h after the anchor, between 07:00 and 20:00. The previous close is outside the
band and the current close is back inside. The stop walks back over consecutive outside closes,
then − 0.25 ATR. The target is the VWAP. Hold is 3 h. No look-ahead. The slope filter matches the
card. The "VWAP slope direction preference" variant is not implemented (minor).
Instructions: X1 to X3.

## overreaction_fade — ACCEPT
Findings: well built. The time-of-day sigma is the per-slot stdev over the prior 60 days
(`shift(1)` on the day pivot). The regime veto uses the prior day's realised vol against the
90th-percentile quantile. The news skip is DST-aware NY (08:30 and 10:00 plus 60 min). It is a
blanket daily proxy, which is acceptable and documented. Entry is the first later closed bar in the
reversal direction, within 6 bars. Stop and target are per the card. No look-ahead. FOMC 14:00 NY is
not in the blackout.
Instructions: X1 to X3. Optional: add the FOMC dates from `fomc_drift.FOMC_DATES` to the blackout
(14:00 to 15:00 NY).

## round_level — ACCEPT (code)
Findings: the momentum and ATR come from the last 15m bar closed before the minute. "Untouched for
4 h" uses the previous W minutes only (`shift(1)`). The trigger second is the first 1s touch inside
the minute, so the minute's low is used only to locate a touch that really happened at that second.
This is clean. The placebo offset of 10.37 is included, which is good. The documented deviation:
market-on-touch instead of the card's limit at L±0.5. The card asks for this to be tested and T5
supports it. Missing: the news blackout (card 1: 30 min around US data; card 2: 10 min). `direction`
is a categorical switch (X3).
Instructions: X1 to X3. Add the DST-aware NY blackout parameter as in level_sweep_reclaim item 2.
Report the placebo-offset rows next to the real ones in the batch report. This is the key control.

---

## Batch C: momentum, time-of-day, trend

Present: last30_momentum, first_last_hh, asian_drift, pmfix, fomc_drift, tsmom_day, holy_grail,
ema_pullback_adx, supertrend_rsi, vwap_cross_mtf, avwap_london.
Not yet present: macro_shock. If it is skipped, the reason must be documented.

## last30_momentum — REDO
Findings:
- Look-ahead: none. The signal price is the 12:59 NY 1m bar close (decision at 12:59:59 NY). The
  open is the first 1m open at or after 18:00 NY on the **previous** NY date (`merge_asof`, strict).
  Sigma is the stdev of the past 60 r_rod values, `shift(1)`.
- DST verified on data: decisions are at 16:59:59 UTC (107, EDT) and 17:59:59 UTC (19, EST). Exits
  are at 17:30 and 18:30 UTC, which is 13:30 NY in both regimes. Correct.
- **`vol_filter` is not the card's filter.** The card wants realised vol from 18:00 to 13:00 NY
  above its 60-day median. The code uses `|r_rod| > median(|r_rod|)`. That is a second threshold on
  the signal itself, collinear with `k`, so it adds no new information.
- The card's "skip US half-days and holidays" filter is not implemented (MLK, Presidents', Good
  Friday, Memorial, Juneteenth, Jul 3/4, Labor, Thanksgiving and the day after, Dec 24/25, Jan 1).
  On those days the 13:30 settlement flow does not exist or comes early.
- `exit_ny="close"` relies on the engine's 20:59:59 flat. The card says 20:55 UTC (X5).
- Frequency 2.9/wk at k = 0.5 and 5.0/wk at k = 0 (card 0.5 to 1 per day). OK. The first trade is on
  2025-02-27 (40-row warm-up).
Instructions (IS only):
1. Re-implement `vol_filter`. Use the realised vol (sum of squared 1m or 5m log returns) from
   18:00 NY of the previous day to signal_end, compared with the median of the previous 60 values
   (`shift(1)`).
2. Add a hard-coded US holiday and early-close list for 2025 to 2026 and skip those days (the
   default skip_holidays=True).
3. Exit "close" at 20:55 UTC explicitly.
4. Rerun with X1 to X3. The native time exit must be in the grid.

## first_last_hh — ACCEPT
Findings: r1 windows: 08:20 to 08:50 NY (DST-aware), 07:00 to 07:30 UTC (mapped correctly to the NY
date) and the Globex reopen 18:00 to 18:30 NY of the previous evening (strict `merge_asof`). The
signal is at 12:59:59 NY. The percentile threshold uses the past 60 values (`shift(1)`). The
mid-confirm uses only prices known by 13:00. Exit is 13:30 NY. No look-ahead. DST is correct, with
the same hour pattern as last30. Frequency is 2.6/wk (card ~0.5/day). Note: the card's
"00:00 to 00:30 UTC" label does not match its own "18:00 to 18:30 NY". The code uses 18:00 NY, which
is acceptable.
Instructions: X1 to X3 and X5 ("close" at 20:55). Optional: the macro-day variant, and the same
holiday skip as last30. last30 and first_last_hh trade the same 13:00 to 13:30 NY window. Report
their trade overlap and correlation if both get through.

## asian_drift — ACCEPT
Findings: the entry is clock-based (decision at 23:59:59 UTC, fill at 00:00:00). The adaptive sign
uses the trailing mean and t-stat of *previous* rows' window returns (`shift(1)`). ATR(D) comes from
prior UTC days. No look-ahead. Unconditional: 5.0/wk, all long. Adaptive-60: 2.9/wk with
101 long / 13 short. Notes: with `lookback=0` the `t_min` setting is ignored, which gives duplicate
combos (dedupe them before counting). `lookback=250` has no signal until about July 2025, so only
half the IS. The practitioner variants "skip Mondays", "long only if the prior 08:00 to 20:00 return
< 0" and the 23:00 entry are not implemented. The adaptive card's 00:05 entry and spread check are
also missing (minor).
Instructions: X1 to X3. Remove the `lookback=0`×`t_min` duplicates from the count. Optional IS
variants: skip_monday and the prior-day-leg filter.

## pmfix — ACCEPT
Findings: the entry is at 07:00 **London** (DST-aware). Decisions are at 05:59:59 UTC in BST (91)
and 06:59:59 UTC in GMT (47), as verified. r_asia runs from 00:00 UTC to the entry. Sigma is the
past 60 values (`shift(1)`). ATR(D) comes from prior days. The stop is beyond the Asian extreme
+ 0.25 ATR. Exits at 10:30 and 15:00 London are DST-aware. No look-ahead. Frequency is 3.2/wk
(card 0.3 to 1/day). `direction_mode` fade/follow is a categorical switch (X3).
Instructions: X1 to X3 and X5 ("close" at 20:55). Optional: a UK bank-holiday skip (no LBMA auction)
and the card's "skip 13:30 UTC tier-1 release" variant, which should be NY-local 08:30.

## fomc_drift — ACCEPT (code); ineligible by trade count (X7)
Findings: the statement time is 14:00 NY localised correctly. p0 is the last 1m close by
statement − 61 s. The decision is at statement + wait − 1 s. ATR5 is the last bar closed before
13:55. No look-ahead. The 2025 and 2026 dates match the Fed calendar (Jan 29, Mar 19, May 7, Jun 18,
Jul 30, Sep 17, Oct 29, Dec 10; Jan 28, Mar 18, Apr 29, Jun 17, Jul 29, Sep 16, Oct 28, Dec 9). At
the defaults there are **6 IS signals**, at most 3 VAL and at most 3 OOS (Oct 28 2026 is after the
data ends). It is structurally unable to meet ≥ 100/≥ 25. `results/fomc_drift_opt.csv` exists, a
300-combination search on 6 to 8 trades, and it is meaningless.
Instructions: do not use `fomc_drift_opt.csv` for anything. Report the screen result only and label
it "ineligible: trade-count gate; possible add-on module". Do not freeze or run OOS.

## tsmom_day — ACCEPT
Findings: the daily close is the last 1h close ≤ 20:59 UTC. EMA_fast − EMA_slow uses closes up to
the previous day. RS_share uses 5m semivariances over the previous 5 days. The decision is at the
close of the 06:00 bar (or 23:00 of the prior day for session_start=0, which is held to the next
21:00 flat as designed). Weekdays only. No look-ahead. The deviation is documented: vol-target sizing
is replaced by fixed-fractional (consistent with the gates). Minor: Sunday's 2-hour stub counts as
one of the "5 days" in RS. Exclude days with < 12 h of bars.
Instructions: X1 to X3 and X5 (exit at 20:55 explicitly rather than with `hold=22h`).

## holy_grail — REDO
Findings:
- No look-ahead on 15m and 5m. ADX/DI use closed bars, "first touch since the ADX cross" is tracked
  by regime id, and the trigger is the first 1s touch of the setup high + 0.05 ATR within 3 bars.
- **Overnight hold bug at `tf=3600`.** Setups are allowed until 18:59 bar start, and the trigger is
  valid for 3 bars, so up to about 21:59 UTC. A trigger at or after 20:59:59 is mapped by the engine
  to the **next** day's 21:00 flat, which is an overnight position. No IS case occurred (only 6
  IS signals at tf=3600), but nothing prevents one in VAL or OOS. This must be fixed before any freeze.
- The stop is the setup-bar low. The card says "lowest low since the touch bar", so lower lows
  during the 3-bar trigger window are ignored. `unit = ATR`, so the templates discard the structural
  stop and target (X4).
Instructions (IS only):
1. Cap the trigger window at 20:55 UTC minus a minimum hold. Simplest: `k1 = min(k0 + 3*tf, k_of(day 20:00))`.
   Also cap `hold` at 20:55.
2. Stop = the lowest low (or highest high) from the setup bar to the trigger second, ± 0.05 ATR as
   needed. Set `unit` to that stop distance.
3. Rerun with X1 to X3.

## ema_pullback_adx — REDO (small)
Findings: no look-ahead. EMAs and ADX use closed bars, the H1 filter uses `merge_asof` on
close_sec, and the dead-market median is `shift(1)`. The logic is faithful to the card. **In
template mode two of the four PARAMS are no-ops** (X4). `exit_mode` and `stop_atr` change only
sl/tp/tp1/be/trail, which `apply_exit` overwrites. So only 6 of the 36 param combos per template are distinct (adx_min × dead_filter), and 30
are duplicates, and the structural swing stop is discarded (unit = ATR). The card's time exit is
20:45, but the engine flat is 20:59:59.
Instructions:
1. Set `unit` = the native stop distance (max of swing − 0.5 ATR and stop_atr × ATR). Remove
   `exit_mode` from PARAMS: the native trail/BE is tested in X1 stage 1 and the templates in
   stage 2.
2. Cap `hold` at 20:45 UTC.
3. Rerun with X1 to X3.

## supertrend_rsi — ACCEPT
Findings: the Supertrend (Wilder ATR) and the RSI cross use closed 5m bars. The session is 08:00 to
17:00 NY, DST-aware, and capped before 20:59 UTC, so in EST the effective window ends at 16:00 NY.
This is correct and documented. Stop = distance to the ST line (min 0.2 ATR), target 2R, max 3 per
NY session. No look-ahead.
Instructions: X1 to X3 (`target_r` from the card is template-covered).

## vwap_cross_mtf — REDO (small)
Findings: no look-ahead. The VWAP includes the closed bar, and the H1/H4 filters use `merge_asof` on
close_sec, so only closed bars are used. `stop_atr` is a no-op under the templates (X4: 3×
duplicates). With `vwap_anchor=13.5`, signals from 07:00 to 13:29 cross a VWAP anchored at **13:30
of the previous day**. That is not a "session VWAP". The spacing is from the last *signal*, but the
card says from the last *exit* (minor).
Instructions:
1. Remove `stop_atr` from PARAMS (the templates cover sl 0.5 to 2 × ATR).
2. Allow signals only ≥ 1 bar after the anchor on the same day (as vwap_sd_fade does).
3. Rerun with X1 to X3.

## avwap_london — ACCEPT
Findings: the AVWAP and sigma bands are cumulative from the anchor and include only closed bars. The
trend share and the 12-bar slope are causal. The pullback state machine uses closed bars. No
look-ahead. Minor issues: in `fade_2sd` the bar open is compared with the band at the bar's close.
Use the band at i−1 for "opens beyond the band". The card's 30-min post-release blackout and the
trail to AVWAP after 1R are missing. The 07:00 anchor is fixed UTC per the card, so a DST-aware
08:00 London variant would be a reasonable IS addition. `mode` is a categorical switch (X3).
Instructions: X1 to X3. Fix the fade's band reference (i−1). Optional: add the DST-aware anchor and
the NY-local news blackout.

---

## Signal-frequency check (IS, card defaults, this audit)

Decision seconds are IS-only (2025) and counted before the engine's one-position filter.
"ok" means within 3× of the card's expected frequency.

| Strategy (variant) | IS signals | /wk | L / S | Card expectation | Note |
|---|---|---|---|---|---|
| asian_range_breakout (defaults, usd filter) | 95 | 1.9 | 54/41 | ~4/wk | stale filter (REDO) |
| asian_range_breakout (pct / none) | 193 / 216 | 3.7 / 4.2 | | | ok |
| asian_range_breakout (vol_state=top) | 9 | 0.2 | 4/5 | ~1.5/wk | REDO |
| crabel_orb_stretch (NR4 / none) | 61 / 230 | 1.2 / 4.4 | 34/27 | 1.5–2.5 / ~5 | ok |
| idnr4_breakout (inside / NR-only) | 23 / 64 | 0.4 / 1.2 | 13/10 | 0.5–1 | X7 |
| williams_vol_breakout | 194 | 3.7 | 108/86 | 3–4.5 | ok (23:xx decisions belong to the next trading day, correct) |
| ny_orb | 251 | 4.8 | 136/115 | ~5 | ok |
| london_range_ny_break (break) | 30 | 0.6 | 15/15 | ~3 | **5× low** |
| london_range_ny_break (retest) | 127 | 2.4 | 79/48 | ~1.5 | ok |
| pdh_pdl_breakout | 177 | 3.4 | 105/72 | ~3 | ok |
| ib_extension_ny (13:30 / ny0930) | 108 / 91 | 2.1 / 1.8 | 50/58 | ~2.5 | ok |
| asian_range_fakeout (H1 / 15m) | 125 / 186 | 2.5 / 3.6 | 54/71 | 2–3 / 1.5–2.5 | ok |
| level_sweep_reclaim | 354 | 6.8 | 174/180 | ~5 | ok; 56% immediate triggers |
| raschke_8020 (8020 / oops) | 28 / 76 | 0.5 / 1.5 | 7/21 | 0.5–1 | X7 |
| wyckoff_spring | 16 | 0.3 | 3/13 | ~2.5 | **8× low** |
| mp_80pct | 57 | 1.1 | 30/27 | 1–1.5 | ok |
| bb_pinbar_fade | 225 | 4.3 | 174/51 | ~5 | ok (EMA200 filter skews long in 2025) |
| rsi_extreme_fade (5m / 1m) | 104 / 691 | 2.0 / 13.3 | 55/49 | 15–40 | **5m is 7× below the card** |
| vwap_sd_fade | 178 | 3.4 | 96/82 | 2.5–5 | ok |
| overreaction_fade | 158 | 3.0 | 91/67 | 2–4 | ok |
| round_level | 214 | 4.1 | 133/81 | ~5 | ok |
| last30_momentum (k=0.5 / k=0) | 126 / 218 | 2.9 / 5.0 | 77/49 | 2.5–5 | ok; DST verified |
| first_last_hh (ny0820 / ny1800 / utc0700) | 115 / 112 / 112 | 2.6 | 64/51 | ~2.5 | ok |
| asian_drift (uncond / adaptive-60) | 246 / 114 | 5.0 / 2.9 | 246/0, 101/13 | 5 / 3 | ok |
| pmfix | 138 | 3.2 | 59/79 | 1.5–5 | ok; DST verified |
| fomc_drift | 6 | 0.15 | 2/4 | 8/yr | X7 |
| tsmom_day (07:00 / 00:00) | 154 / 154 | 3.0 | **154/0** | ~4 | ok, but IS is 100% long (see note) |
| holy_grail (15m / 1h) | 50 / 6 | 1.0 / 0.1 | 26/24 | ~2.5 | borderline (2.6×) |
| ema_pullback_adx | 188 | 3.6 | 99/89 | ~5 | ok |
| supertrend_rsi | 768 | 14.8 | 373/395 | 5–15 | ok (upper end) |
| vwap_cross_mtf | 384 | 7.4 | 286/98 | 5–15 | ok |
| avwap_london (pullback / fade) | 369 / 452 | 7.1 / 8.7 | 222/147 | ~5 | ok |

Notes: tsmom_day is long-only for all of IS because the EMA trend never flipped in 2025, so IS
says nothing about the short leg. It is effectively "long gold during the day" in a bull year. Given
the registry's warning about regime decay from June 2026, the Batch C report must show the IS result
next to a buy-and-hold-daytime benchmark and the VAL long/short split.

---

## Summary table

| Batch | Strategy | Verdict | One-line reason |
|---|---|---|---|
| A | asian_range_breakout | REDO | stale $3–20 range filter gives 1.9/wk vs ~4/wk and selects the quietest days; vol_state "top" leaves 9 trades |
| A | crabel_orb_stretch | ACCEPT | faithful, causal |
| A | idnr4_breakout | ACCEPT (X7) | faithful; 2–4 setups a month, cannot meet the trade-count gate |
| A | williams_vol_breakout | ACCEPT | faithful, causal |
| A | ny_orb | ACCEPT | DST-aware, causal |
| A | london_range_ny_break | REDO | break mode 5× below card frequency (0.6/wk); non-monotone `win_idx`; mode switch |
| A | pdh_pdl_breakout | ACCEPT | faithful, causal |
| A | ib_extension_ny | ACCEPT | causal; mode is categorical |
| B | asian_range_fakeout | REDO | re-arm bug understates the stop; 15m variant not faithful |
| B | level_sweep_reclaim | REDO | stop measured from the level but applied from the fill (56% immediate triggers); no news blackout |
| B | raschke_8020 | ACCEPT (X7) | faithful; 28 IS trades |
| B | wyckoff_spring | ACCEPT | faithful; 16 IS trades, frequency gap must be explained |
| B | mp_80pct | ACCEPT | faithful, causal |
| B | bb_pinbar_fade | ACCEPT | faithful, causal |
| B | rsi_extreme_fade | REDO (small) | news blackout fixed in UTC, misses US releases in EST; 5m frequency 7× below card |
| B | vwap_sd_fade | ACCEPT | faithful, causal |
| B | overreaction_fade | ACCEPT | well built; DST-aware news proxy |
| B | round_level | ACCEPT | causal; placebo included; add news blackout |
| C | last30_momentum | REDO | vol_filter is a duplicate of k, not realised vol; no holiday skip |
| C | first_last_hh | ACCEPT | causal, DST-correct |
| C | asian_drift | ACCEPT | causal; dedupe the t_min×lookback=0 combos |
| C | pmfix | ACCEPT | DST-correct London entry, causal |
| C | fomc_drift | ACCEPT (X7) | dates correct; 6 IS trades; opt CSV meaningless |
| C | tsmom_day | ACCEPT | causal; IS 100% long, so it needs a benchmark comparison |
| C | holy_grail | REDO | tf=3600 trigger window can run past 21:00 and become an overnight hold (latent); stop not the swing low |
| C | ema_pullback_adx | REDO (small) | exit_mode/stop_atr are no-ops under templates; unit should be the structural stop |
| C | supertrend_rsi | ACCEPT | DST-aware, causal |
| C | vwap_cross_mtf | REDO (small) | stop_atr no-op; 13:30 anchor gives a previous-day VWAP in the morning |
| C | avwap_london | ACCEPT | causal; minor fade band reference |

## REDO items to send back

**All batches:** X1 to X7 above. Most important: X1 (native exit in the grid), X2 (staged search,
no random 8% sampling), X3 (monotone PARAMS so that robustness is a real ±1-step neighbourhood) and
X5 (no decision at or after 20:59:59 UTC unless overnight-by-design, and explicit 20:55 exits). None
of the existing `results/*_opt.csv` files should be used to select a finalist. They were made with
random 300-of-N sampling and without the native exit.

**Batch A agent:** asian_range_breakout items 1 to 5. london_range_ny_break items 0 to 2 (explain
the 5× low break-mode frequency filter by filter, split the modes, make the window grids monotone,
add the card-2 range filter and a DST-aware NY start). idnr4:
X7 handling.

**Batch B agent:** asian_range_fakeout items 1 to 3 (re-arm fix, 15m-variant parameters, range
filter). level_sweep_reclaim items 1 to 4 (stop anchored to the decision price, NY news blackout,
cost/R report). rsi_extreme_fade items 1 to 3 (NY-local blackout, one-per-episode variant, frequency explanation).
wyckoff_spring: explain or fix the 16-trade frequency. round_level: news blackout and the placebo
report. raschke_8020: X7 handling.

**Batch C agent:** last30_momentum items 1 to 4 (true realised-vol filter, holiday skip, 20:55
close). holy_grail items 1 to 3 (no triggers after 20:55, swing stop, unit = R). ema_pullback_adx
items 1 to 3. vwap_cross_mtf items 1 to 3. fomc_drift: screen only, ineligible. asian_drift: dedupe
the grid. tsmom_day: IS is 100% long, so report it against a long-daytime benchmark and give the VAL
side split. macro_shock: implement it or document the skip.
