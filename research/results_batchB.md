# Batch B results: reversal, structure, mean reversion (1s engine, `evaluate.py`)

Splits: IS 2025, VAL Jan–May 2026, OOS Jun 2026 onwards. All costs are cTrader-equivalent. Each cell
reads **n / WR % / PF($) / PF(R) / maxDD % / trades per week**.

Protocol:
- `screen` at the card defaults, then the **staged** `optimise --max 300`, which is the harness after
  the boss audit. Stage 1 is the full sorted grid with the card's own exit. Stage 2 runs 53 exit
  templates on the top-3 plateau settings.
- The setting was chosen on IS columns only. VAL was looked at only for that one row, and only
  rows with IS PF(R) ≥ 1.3 were considered as finalists.
- The first round of optimisation used random 120/300-of-N sampling and code from before the audit.
  Those results were discarded and not used for selection. For the strategies rerun because of
  audit defects (asian_range_fakeout, level_sweep_reclaim, rsi_extreme_fade, round_level), the VAL
  figures below are their final VAL look.
- `unit` is the card's structural stop distance (R) everywhere. The exceptions are
  rsi_extreme_fade (ATR14, which is the card's stop) and round_level (a fixed $3.00 stop, as the
  card specifies).
- "Combos" counts stage 1 plus stage 2, plus any extra stage-2 runs.

| Strategy (cards) | Combos | Best IS-selected setting | IS | VAL | OOS | Verdict |
|---|---|---|---|---|---|---|
| asian_range_fakeout (H1; marketplaces-asian-range-fakeout-h1) | 255 | asian_end 7, max_bars_outside 1, stop_buf 0.5, exit 20:00; trail sl 1.0R / trail 1.5R | 69 / 40.6 / 0.93 / 1.07 / 4.4 / 1.35 | 23 / 17.4 / 0.23 / 0.27 / 4.6 / 1.22 | – | REJECT at screen (defaults IS PF(R) 0.63) |
| asian_range_fakeout_15m (practitioners-asian-range-false-break-fade) | 267 | asian_end 6, mbo 4, stop_buf 0.0, exit 20:00, no range filter; scalp_be sl 3 / tp1 0.25 f 0.7 / tp 1.5 / BE | 151 / 92.7 / 1.19 / 1.12 / 1.7 / 2.92 | 66 / 89.4 / 1.20 / 0.68 / 1.4 / 3.21 | – | REJECT at screen (defaults 0.77) |
| level_sweep_reclaim (Turtle Soup 15m only; books-turtle-soup-15m) | 213 | channel 80, min_age 6, overshoot 0.2 ATR, no news skip; fixed sl 2R / tp 2R | 145 / 51.0 / 1.05 / 0.96 / 9.0 / 2.82 | 59 / 45.8 / 0.46 / 0.74 / 7.3 / 2.89 | – | REJECT at screen (defaults 0.70) |
| raschke_8020 (books-raschke-8020-daily) | 2 (screen only, X7) | card defaults; `cond=oops` variant | 8020: 28 / 32.1 / 0.99 / 0.51 / 5.7 / 0.61; oops: 76 / 35.5 / 0.98 / 0.76 / 6.3 / 1.56 | 8020: 7 / 42.9 / 1.73 / 1.39; oops: 34 / 35.3 / 0.72 / 1.05 | – | REJECT: ineligible by trade count (card version); oops variant fails screen |
| wyckoff_spring (books-wyckoff-spring-upthrust-5m) | 231 | plateau finalist: range 72, width ≤ 5.0 ATR15, vol_rule none, stop entry (plateau 1.02); card exit 112 / 31.3 / 0.93 / 1.04 / 11.2 / 2.16; best stage-2 exit fixed sl 1R / tp 3R | 112 / 33.9 / 0.95 / 1.12 / 8.5 / 2.16 | not looked at (no finalist ≥ 1.3) | – | REJECT at screen (defaults n=16 IS). Highest single IS row, off-plateau: range 24 / width 5.0 / vol high / close, n60, PF(R) 1.25 |
| mp_80pct (books-mp-80pct-rule) | 195 | VA 68 %, 2 confirm bars, ref 23:00, tick-volume profile; trail sl 2R / trail 1.5R | 70 / 42.9 / 1.17 / 1.20 / 1.9 / 1.36 | 24 / 58.3 / 1.72 / 1.47 / 0.9 / 1.22 | – | REJECT at screen (defaults 0.64; best IS < 1.3) |
| bb_pinbar_fade (marketplaces-bb-pinbar-fade-m5) | 248 | bb_dev 2.5, wick_body 1.5, EMA200(H1) filter on, 5m; fixed sl 1.0R / tp 2.0R | 81 / 49.4 / 1.50 / 1.40 / 5.6 / 1.57 | 31 / 58.1 / 2.13 / 2.30 / 2.1 / 1.56 | **33 / 39.4 / 0.52 / 0.71 / 5.4 / 1.70**; stress PF 0.35, DD 7.0 | **OOS FAIL** (frozen for the honest frontier; gates not met on IS or VAL either) |
| rsi_extreme_fade (practitioners-rsi-extreme-ema200-fade) | 125 | plateau finalist: 5m, RSI < 20 / > 80, no EMA filter, hold 60 min, one per episode (plateau 0.95); card exit 116 / 38.8 / 1.13 / 1.05 / 5.7 / 2.26; best stage-2 exit trail sl 0.5 / trail 1.5 | 116 / 27.6 / 0.92 / 1.16 / 11.8 / 2.26 | not looked at (no finalist ≥ 1.3) | – | REJECT at screen (defaults 0.76). Highest single IS row: hold 120 min, card exit, PF(R) 1.17 |
| vwap_sd_fade (practitioners-vwap-3sd-fade) | 177 | band 2.0 sd, anchor 00:00, slope filter on; trail sl 1R / trail 1.5R | 350 / 37.1 / 0.91 / 0.97 / 14.3 / 6.77 | 152 / 31.6 / 0.43 / 0.59 / 22.0 / 7.39 | – | REJECT at screen (defaults 0.86) |
| overreaction_fade (academic-overreaction-fade-volnorm) | 207 | z 3.0, 30 min window, hold 90 min, no news skip; scalp_be sl 3 / tp1 0.5 f 0.5 / tp 1.5 / BE | 140 / 71.4 / 1.30 / 1.32 / 1.4 / 2.94 | 28 / 67.9 / 1.12 / 1.06 / 1.3 / 1.38 | – | REJECT at VAL |
| round_level (marketplaces-round20-level-fade + practitioners-round20-level-reaction) | 255 | step 50, offset 0, momentum 1.0 ATR, hold 240 min, news skip, **break**; scalp_be sl 3 / tp1 0.5 f 0.5 / tp 3 / BE | 72 / 81.9 / 1.45 / 1.45 / 2.2 / 1.50 | 73 / 54.8 / 0.36 / 0.36 / 10.0 / 3.93 | – | REJECT at VAL; placebo shows no level effect |
| silver_bullet (ICT) | 0 | – | – | – | – | SKIPPED – ICT/SMC excluded by user |
| taylor_sweep (liquidity sweep + reclaim) | 0 | – | – | – | – | SKIPPED – ICT/SMC excluded by user |

Finalist rule. For wyckoff_spring and rsi_extreme_fade, the rows above are the protocol's top-plateau
setting with n_IS ≥ 60, plus its best stage-2 exit. An earlier draft listed their best single-row
IS PF(R) instead. Both stay below 1.3 either way, and the verdicts are unchanged.

round_level placebo. The offset 10.37 is a control, not a tradable setting. The harness ranked
placebo-offset settings at the top of the stage-1 plateau. Placebo rows were excluded by hand when
choosing the finalist, which was taken from the real-level (offset 0) rows only.

Variants dropped for the same reason: the Judas/Asia-sweep FVG component (books-ict-judas-asia-sweep),
the PDH/PDL sweep-reclaim (practitioners-pdh-pdl-sweep-reclaim) and the previous-candle sweep
(marketplaces-prev-candle-sweep-m15).

## Screen at card defaults (IS, then VAL)
| Strategy | IS n / WR / PF / PF(R) | VAL n / WR / PF / PF(R) |
|---|---|---|
| asian_range_fakeout (H1, after the re-arm fix) | 117 / 39.3 / 0.69 / 0.63 | 36 / 27.8 / 0.34 / 0.35 |
| asian_range_fakeout_15m | 168 / 32.7 / 0.78 / 0.77 | 70 / 37.1 / 1.07 / 0.82 |
| level_sweep_reclaim (stop from decision mid, news skip) | 275 / 34.6 / 0.64 / 0.70 | 139 / 45.3 / 0.98 / 1.14 |
| raschke_8020 | 28 / 32.1 / 0.99 / 0.51 | 7 / 42.9 / 1.73 / 1.39 |
| wyckoff_spring | 16 / 37.5 / 1.27 / 1.18 | 7 / 28.6 / 2.16 / 1.15 |
| mp_80pct | 57 / 43.9 / 0.98 / 0.64 | 19 / 47.4 / 0.54 / 0.35 |
| bb_pinbar_fade | 215 / 39.1 / 0.86 / 0.94 | 78 / 34.6 / 0.64 / 0.87 |
| rsi_extreme_fade (NY-local blackout) | 76 / 34.2 / 0.73 / 0.76 | 30 / 43.3 / 2.11 / 1.51 |
| vwap_sd_fade | 171 / 31.0 / 0.92 / 0.86 | 68 / 32.4 / 0.90 / 0.79 |
| overreaction_fade | 140 / 61.4 / 1.08 / 1.16 | 28 / 78.6 / 2.38 / 2.01 |
| round_level (news skip) | 158 / 39.9 / 0.83 / 0.83 | 184 / 38.6 / 0.69 / 0.69 |
| round_level placebo (offset 10.37) | 170 / 38.8 / 0.81 / 0.81 | 179 / 41.3 / 0.82 / 0.82 |

## Audit items (early_audit.md, Batch B)
- **asian_range_fakeout.** Fixed the re-arm bug. An excursion that expires while price is still
  outside the range now has to close back inside before a new break can arm, and the stop uses the
  full extreme of the excursion. The code is shared in `_bxutil.fakeout_core`. The module is split
  into an H1 id and a 15m id. The 15m id uses its card's parameters: exit at 16:00 by default,
  stop_buf 0.1, max bars 4/8/16 and the range filter (> 1.5×ATR14(1h)×6). The re-screen is above.
- **level_sweep_reclaim.**
  - The stop is now measured from the mid at the decision second, so the engine's fill price and
    the stop distance refer to the same price.
  - Immediate triggers (≤ 5 s after the 15m close, where the bar had already closed back through
    the level): 144 of 275 IS trades (52 %).
  - Median stop is $4.23. Round-trip cost is about $0.24 (spread floor $0.10 + 2 × $0.03 slippage
    + $0.07 commission), which is about 5.7 % of R. The 40- and 80-bar channels give median stops
    of $4.55 and $4.30 (about 5.5–5.8 %). Cost is therefore not the reason this fails.
  - The NY news blackout (08:00–09:00 and 09:45–10:30 New York time, DST-aware) is `news_skip`.
- **rsi_extreme_fade.** The blackout now uses New York local time (08:25–08:35 and 09:55–10:05).
  `one_per_episode` (re-arm only after RSI crosses 50) has been added. IS frequency:

  | tf | EMA filter | per bar | one per episode |
  |---|---|---|---|
  | 5m | on | 104 signals → 76 trades (1.5 per week) | 49 |
  | 5m | off | 3,435 signals → 1,630 trades (31 per week, about 6 per day) | 555 |
  | 1m | on | 693 → 457 (8.8 per week) | 287 |
  | 1m | off | 16,153 → 8,424 (162 per week) | 2,658 |

  The card's "3–8 per day" holds only at 5m without the EMA200 filter, or at 1m without it. In the
  2025 bull trend, RSI < 30 above EMA200 is rare. The extra stage 2 (53 templates) was run because
  the harness's top-3 plateau settings had 0 IS trades, so stage 2 had produced nothing.
- **wyckoff_spring.** IS trade counts at the defaults and with one filter relaxed at a time:

  | Setting | IS trades |
  |---|---|
  | defaults | 16 |
  | vol_rule = none | 53 |
  | width ≤ 3.5 ATR | 56 |
  | width ≤ 5.0 ATR | 85 |
  | range 24 bars | 71 |
  | vol none + width 5.0 | 217 |
  | vol none + width 5.0 + range 24 bars | 262 |

  The low frequency comes from three filters acting together: the low-volume rule, the
  2.5×ATR15 width cap (the median 36-bar range is 3.4×ATR15) and the two-touch rule. The relaxed
  settings were in the stage-1 grid and none reached IS PF(R) 1.3.
- **round_level.** Added the NY news blackout. Placebo control (stage 1, card exit, 48 matched
  settings): median IS PF(R) is 0.804 at the real levels and 0.800 at the placebo levels. Bounce
  trades at real $20 and $50 levels do worse than at the placebo levels (for example step 20 bounce
  0.68–0.86 against 0.81–1.00). The harness's top plateau settings were placebo-offset rows. The
  only real-level row above 1.3 (step 50, break) collapsed on VAL (PF 0.36). There is no evidence
  of a round-number effect.
- **raschke_8020.** Handled under X7. The card version is ineligible with 28 IS trades. The oops
  variant (76 IS trades) gives IS PF(R) 0.76, so no grid was run.
- **Cross-cutting.**
  - X1/X2: staged harness.
  - X3: numeric PARAMS sorted, `direction` listed last.
  - X4: there are no exit-only PARAMS keys, and `unit` is the structural stop.
  - X5: every time exit is explicit (16:00, 20:00, 20:45 or 20:55 UTC). No same-session decision
    falls after 20:59.
  - X6: the `_bxutil.py` sha256 is recorded in the frozen note. `_bxutil.py` has not been edited
    since the freeze.
- **bb_pinbar_fade robustness.** The freeze reports a neighbourhood median IS PF of 0.99, which
  includes the `ema_filter` and `tf` switches. The stage-1 plateau score of the chosen setting was
  1.13.

## Summary
No Batch B strategy passes. Only bb_pinbar_fade reached IS PF(R) ≥ 1.3 and VAL PF ≥ 1.3. It was
frozen and run once on OOS, where it failed: PF 0.52, WR 39 %, stress PF 0.35. The pattern from
Batch A holds here too. Scalp plus break-even exits produce 70–93 % WR in IS without PF ≥ 1.5, and
nothing survives into June 2026 onwards.
