# Batch A results: breakouts and session ranges

Protocol: `evaluate.py` (screen at card defaults on IS → optimise on IS with exit templates → VAL → freeze → single OOS).
Costs: cTrader model (spread max($0.10, 0.3×Dukascopy), $0.03 slip, $0.07/oz commission), 1 s fill latency. DD = max equity DD at 0.5 % risk/trade.
Selection rule, applied the same way to every strategy: the finalist is the top IS PF(R) row with n_IS ≥ 60. It goes to freeze + OOS only if IS PF(R) ≥ 1.3 **and** VAL PF ≥ 1.3. Optimise budget: 300 for screen passers and promising ideas, 120 (fairness run) for clear screen failures.
Code: `strategies/<name>.py` plus the shared helper `strategies/batcha_util.py`. Optimise tables: `results/<name>_opt.csv`.

## Screen (card defaults, IS)

| Strategy | IS n | WR % | PF | PF(R) | DD % | Screen |
|---|---|---|---|---|---|---|
| asian_range_breakout | 95 | 44.2 | 0.86 | 0.87 | 6.8 | fail (the card's $3–20 range filter keeps few days at 2025–26 prices; 0 VAL trades) |
| crabel_orb_stretch | 61 | 41.0 | 1.10 | 1.30 | 3.7 | pass (VAL PF 0.27) |
| idnr4_breakout | 23 | 52.2 | 1.19 | 1.39 | 1.6 | fail (too few trades: ~0.5/wk) |
| williams_vol_breakout | 194 | 44.3 | 1.03 | 1.09 | 7.0 | fail |
| ny_orb | 251 | 26.7 | 0.94 | 0.96 | 8.5 | fail |
| london_range_ny_break | 30 | 70.0 | 1.84 | 2.40 | 1.4 | fail on count (the card's 2.5×ATR30 range filter → 0.6/wk); optimised at 300 because PF(R) was high |
| pdh_pdl_breakout | 177 | 42.4 | 1.42 | 1.35 | 6.4 | pass |
| ib_extension_ny | 108 | 38.0 | 0.82 | 0.86 | 8.3 | fail |
| bbkc_squeeze | 111 | 44.1 | 0.94 | 1.11 | 4.7 | fail |
| noise_area_momentum | 517 | 28.1 | 0.91 | 0.79 | 14.0 | fail |
| shanghai_open | 258 | 35.3 | 0.97 | 0.97 | 11.9 | fail |

## Best IS-selected setting per strategy

| Strategy | Combos | Best IS-selected setting (params; exit in units of `unit`) | IS n / WR / PF / PF(R) / DD% / tr/wk | VAL n / WR / PF / PF(R) / DD% / tr/wk | OOS n / WR / PF / PF(R) / DD% / tr/wk | Verdict |
|---|---|---|---|---|---|---|
| asian_range_breakout | 420 (120 + 300) | range 00–06 UTC, buffer $2.0, orders until 12:00, range 0.2–1.0×ATR14(D), prior-day RV top tercile, flat 16:00; exit sl 2.0×range, tp 1.0×range | 72 / 62.5 / 2.13 / 2.33 / 1.00 / 1.87 | 38 / 63.2 / 2.40 / 2.33 / 0.36 / 1.82 | 16 / 68.8 / 2.11 / 1.77 / 0.51 / 0.97 (stress PF 2.10, DD 0.51) | **OOS FAIL** (WR, PF and n<25 gates; neighbourhood median IS PF 1.92) |
| crabel_orb_stretch | 300 | OR 15 m, stretch 1.0×, lookback 20, NR4; scalp_be sl 2, tp1 0.5 (50 %), tp 3, BE | 61 / 83.6 / 3.04 / 2.39 / 0.84 / 1.31 | 29 / 58.6 / 0.31 / 0.34 / 3.39 / 1.46 | – | REJECT at VAL |
| idnr4_breakout | 120 | buffer 0.05 ATR, NR4 without the inside-day condition, SAR on; trail sl 0.5, trail 1.5 | 64 / 40.6 / 1.04 / 1.29 / 4.10 / 1.39 | 17 / 29.4 / 0.63 / 0.56 / 3.51 / 0.86 | – | REJECT at screen (card version: 23 IS trades) |
| williams_vol_breakout | 120 | k 1.0, open 23:00, R = prior day range, entries until 16:00; sl 2.0R, tp 1.0R | 68 / 60.3 / 1.58 / 1.64 / 0.62 / 1.35 | 29 / 41.4 / 0.64 / 1.08 / 0.71 / 1.43 | – | REJECT at VAL |
| ny_orb | 120 | OR 15 m, 5 m close, cutoff 11:00 NY; trail sl 0.5, trail 1.5 | 241 / 27.4 / 1.07 / 1.11 / 8.95 / 4.66 | 101 / 22.8 / 0.67 / 0.55 / 17.35 / 4.84 | – | REJECT at screen |
| london_range_ny_break | 300 | break mode, London 07–12, first 3 NY 30 m bars, BB filter on, range ≤ 5×ATR30; sl 1.0, tp 1.5 | 85 / 62.4 / 2.13 / 2.21 / 1.69 / 1.64 | 30 / 30.0 / 0.52 / 0.79 / 2.43 / 1.52 | – | REJECT at VAL (retest mode never ranked near the top) |
| pdh_pdl_breakout | 300 | buffer $1.0, stop orders 07:00–18:00; scalp_be sl 2×ATR1h, tp1 0.25 (50 %), tp 3, BE | 116 / 94.0 / 3.87 / 3.42 / 0.96 / 2.27 | 38 / 84.2 / 0.60 / 0.62 / 1.74 / 1.91 | – | REJECT at VAL (passed IS gates; 3 IS gate passers, 0 also on VAL) |
| ib_extension_ny | 120 | IB 12:00 UTC + 30 m, breakout mode only (narrow < 0.85×median); sl 2.0W, tp 1.0W | 85 / 72.9 / 1.35 / 1.32 / 2.27 / 1.77 | 32 / 62.5 / 1.07 / 0.86 / 2.31 / 1.58 | – | REJECT at VAL |
| bbkc_squeeze | 120 | 15 m, squeeze ≥ 4 bars, KC 1.5, no slope filter; scalp_be sl 2, tp1 0.25 (70 %), tp 3, BE | 140 / 85.7 / 1.44 / 1.63 / 0.99 / 2.72 | 67 / 77.6 / 0.74 / 0.70 / 1.70 / 3.19 | – | REJECT at VAL |
| noise_area_momentum | 120 | anchor 13:30 UTC, lookback 14, band 1.5×, 60 m checks; sl 2, tp 1.5 band widths | 150 / 47.3 / 1.46 / 1.35 / 2.52 / 3.08 | 71 / 36.6 / 0.93 / 0.77 / 2.96 / 3.40 | – | REJECT at VAL |
| shanghai_open | 120 | momentum mode, window 02:30–02:45 UTC, q 0.5σ, flat 06:00; sl 2σ, tp 2σ | 121 / 56.2 / 1.28 / 1.28 / 2.53 / 2.80 | 51 / 43.1 / 0.82 / 0.81 / 3.39 / 2.45 | – | REJECT at screen |

## Notes
- **No OOS PASS in Batch A.** Only asian_range_breakout reached OOS. It stayed profitable out of sample (PF 2.1 at base and stress cost), but it trades about once a week, so OOS has only 16 trades, and its WR of about 65 % is far below the 75 % gate.
- The pattern seen across ideas: a small first target plus break-even (scalp_be, tp1 = 0.25 unit) pushes IS WR to 85–95 % (pdh_pdl, bbkc, crabel), but the PF collapses on VAL (< 1). The high WR comes from the exit shape, not from an entry edge.
- pdh_pdl_breakout with `close_beyond=True` (15 m close), 07:00–18:00, scalp_be sl 3, tp1 0.25 was 4th by IS PF(R) (2.98) and had VAL PF 2.49 (n 30). It was not the IS-selected finalist, so it was **not** frozen or OOS-tested. Promoting it would mean choosing on VAL.
- Card adaptations: Shanghai anchors are fixed UTC (no DST in China); NY ORB and the `ny0930` IB variant use America/New_York with DST. noise_area_momentum's VWAP/band trailing exit is precomputed from closed 30/15/60 m bars and passed as `hold`; vol-target sizing is not modelled. bbkc_squeeze's default exit uses the card's 2R variant, because the indicator trail cannot be expressed in the engine.
- Combination counts exclude the single screen run per strategy. asian_range_breakout is over the 300 budget (420) because of an early 120-combo sample taken before the 300 run.

---

# Rerun after review (research/reviews/batchA.md, harness 2ca67cf)

Scope: A-1 london_range_ny_break + london_range_retest, A-2 crabel_orb_stretch, A-3 ib_extension_ny + ib_fade_ny,
A-4 bbkc_squeeze, A-5 noise_area_momentum, A-6 shanghai_orb + shfe_open_mom. All other Batch A verdicts stand.

## Selection rule (written before any rerun was executed)
1. Screen at card defaults (only the IS row is read).
2. `evaluate.optimise(id, 300)`: stage 1 = full sorted PARAMS grid with the card exit (≤ 141 combos), stage 2 = all 53
   exit templates on the harness's top-3 plateau settings. The optimise printout is suppressed; a selector script reads
   only IS columns until the finalist is fixed.
3. Finalist setting = stage-1 row with n_IS ≥ 60 and the highest plateau score (median IS PF(R) over the setting and its
   sorted ±1 neighbours); ties broken by the row's own IS PF(R).
4. Exit = card exit, unless a stage-2 template on that same setting (n_IS ≥ 60) has a higher IS PF(R) **and** the median IS
   PF(R) of its adjacent templates (same template family, ±1 step in sl or in tp — trail distance for the trail family)
   is ≥ 1.3; then the best such template.
5. Only then is the finalist's VAL row printed. This is the strategy's final VAL look. If IS PF(R) ≥ 1.3 and VAL PF ≥ 1.3
   → freeze, commit, run OOS once. Otherwise the strategy is closed.

## Rerun results (final VAL look per strategy)

Combos = earlier run + rerun (stage 1 + stage 2). For split modules, the earlier run was shared with the parent id.

| Strategy | Combos | Finalist (IS-selected by the rule above) | Exit | IS n / WR / PF / PF(R) / DD% / tr/wk | VAL n / WR / PF / PF(R) / DD% / tr/wk | OOS n / WR / PF / PF(R) / DD% / tr/wk | Verdict |
|---|---|---|---|---|---|---|---|
| london_range_ny_break | 300 (mixed, earlier) + 267 = 567 | London 08–12, ny_start ny0830, 3 bars, range ≤ 2.5×ATR30, target_r 1.5 (plateau 1.36) | template sl 2.0, tp 1.5 (adjacent median 1.52; card exit IS PF(R) 1.43) | 67 / 59.7 / 1.86 / 1.74 / 1.89 / 1.30 | 20 / 70.0 / 1.68 / 2.52 / 0.50 / 1.07 | 28 / 39.3 / 0.47 / 0.58 / 2.59 / 1.40 (stress PF 0.45) | **OOS FAIL** (neighbourhood median IS PF 1.81) |
| london_range_retest | (shared 300) + 195 | retest_win 24, stop_atr 1.0, target_r 3.0 (plateau 1.31) | scalp_be sl 2, tp1 0.5 (50 %), tp 3, BE (adjacent median 1.36) | 147 / 81.0 / 1.46 / 1.39 / 2.38 / 2.84 | 60 / 73.3 / 0.57 / 0.59 / 3.16 / 2.96 | – | CLOSED at VAL |
| crabel_orb_stretch | 300 + 267 = 567 | OR 5 m, stretch 0.5×, lookback 10, NR4 (plateau 1.34) | card (opposite-OR stop, no target, flat 12:00) | 67 / 37.3 / 1.13 / 1.34 / 4.81 / 1.44 | 33 / 24.2 / 0.26 / 0.28 / 8.36 / 1.67 | – | CLOSED at VAL |
| ib_extension_ny | 120 (mixed, earlier) + 213 = 333 | ny0930, IB 30 m, narrow 0.85, ext 1.5 (plateau 0.96) | card | 75 / 36.0 / 1.04 / 0.96 / 4.16 / 1.59 | 36 / 36.1 / 1.01 / 0.92 / 4.44 / 1.80 | – | CLOSED (IS PF(R) < 1.3) |
| ib_fade_ny | (shared 120) + 177 | ny0820, IB 30 m, wide 1.2 (plateau 0.80; card exit IS PF(R) 1.25) | template sl 2.0, tp 3.0 (adjacent median 1.37) | 91 / 51.6 / 1.58 / 1.45 / 4.58 / 1.94 | 34 / 52.9 / 2.13 / 1.30 / 2.30 / 1.65 | 32 / 53.1 / 1.88 / 1.50 / 1.51 / 1.68 (stress PF 1.86, DD 1.51) | **OOS FAIL** (WR, PF; neighbourhood median IS PF 1.42) |
| bbkc_squeeze | 120 + 267 = 387 | 15 m, min_sq 6, KC 2.0, trail exit, squeeze-range stop (plateau 1.38) | card (SMA20 close-through trail) | 163 / 41.7 / 1.44 / 1.38 / 2.67 / 3.14 | 63 / 34.9 / 0.92 / 0.96 / 2.42 / 3.00 | – | CLOSED at VAL |
| noise_area_momentum | 120 + 231 = 351 | anchor 07:00, lookback 20, band 1.5, checks 15 m, no gap adj (plateau 0.99) | card (VWAP/band trail, 3-unit catastrophe stop) | 438 / 27.6 / 1.00 / 1.00 / 8.74 / 9.15 | 186 / 23.7 / 0.82 / 0.82 / 4.40 / 8.86 | – | CLOSED (IS PF(R) < 1.3) |
| shanghai_orb | (shared 120) + 267 | range 02:30 + 30 m, stop = opposite range side, target 2R (plateau 1.29) | card | 237 / 49.8 / 1.47 / 1.38 / 3.83 / 4.58 | 93 / 44.1 / 0.91 / 0.75 / 5.07 / 4.52 | – | CLOSED at VAL |
| shfe_open_mom | (shared 120) + 177 | night open 13:00–13:30, q 0.5, held to 15:00 (plateau 1.08) | card (stop at start price) | 121 / 35.5 / 1.25 / 1.26 / 14.82 / 2.87 | 48 / 20.8 / 0.57 / 0.54 / 8.56 / 2.37 | – | CLOSED (IS PF(R) < 1.3) |

Rerun notes
- **No OOS PASS.** london_range_ny_break broke down out of sample (PF 0.47). ib_fade_ny stayed profitable out of sample (PF 1.88, WR 53 %, n 32), but it is nowhere near WR > 75 / PF > 3.
- noise_area_momentum flip check: at defaults there are 5 same-check flip signals, and all 5 were executed both before and after the fix. The old code did not drop flips: its exit filled at the decision second s, so the flip filled at s+1. What the old code did have is the 0 s exit look-ahead. That is now fixed: the exit fills at s+1 and the flip at s+2.
- Harness quirk: stage 2 runs templates on the top-3 plateau rows *without* requiring each row's own n_IS ≥ 60. For ib_extension_ny, bbkc_squeeze and crabel_orb_stretch, the rule's finalist (n_IS ≥ 60) was not among those three, so it had no templates and kept the card exit, as the written rule says.
- Card changes in this rerun:
  - london_range_ny_break: BB target capped at the entry-bar band; the BB-zone rule is documented.
  - london_range_retest: card filter range > 2×ATR14(1h)×5 added.
  - SHFE holidays 2025–26 skipped in shanghai_orb and shfe_open_mom; the night session is also skipped on the eve of a holiday. The list was checked against the SHFE 2026 notice.
  - shfe night variant: the card's "exclude US data days" rule is not implemented, because the repo has no release calendar.
  - noise_area_momentum: anchor trimmed to 07:00 to fit the 141-combo budget.
  - crabel_orb_stretch: the card's target variant did not fit the 141-combo budget.
- The old `shanghai_open.py` is kept for the record. It is superseded by shanghai_orb and shfe_open_mom.
