# Batch C results: momentum, time-of-day, trend

Protocol: `evaluate.py`. Screen at card defaults on IS, then the staged IS search (harness 2ca67cf):
stage 1 is the full sorted PARAMS grid with the card's own exit, stage 2 is all 53 exit templates on
the top-3 plateau settings. Then VAL, freeze, and a single OOS run.
Costs: cTrader model (spread max($0.10, 0.3×Dukascopy), $0.03 slippage, $0.07/oz commission), 1 s
fill latency. DD = max equity drawdown at 0.5 % risk per trade, compounding.

**Selection rule (the same for every strategy).** The finalist is the top IS PF(R) row with
n_IS ≥ 60 from the staged search, read from IS columns only. Where several exits tie, the middle of
the tie is taken. The finalist goes to freeze + OOS only if IS PF(R) ≥ 1.3 **and** VAL PF ≥ 1.3.
One finalist per strategy was looked at on VAL.

**Audit fixes applied before the staged rerun** (research/reviews/early_audit.md, Batch C and
X1–X7):
- last30_momentum: real realised-vol filter (sum of squared 1m log returns from 18:00 NY to the
  signal, compared with the median of the previous 60 sessions), US holiday and early-close skip
  for 2025–26, "close" exit at exactly 20:55 UTC.
- holy_grail: no triggers after 20:00 UTC; stop = lowest low (highest high) from the setup bar to
  the trigger second; unit = that stop; flat at 20:55.
- ema_pullback_adx: unit = structural stop; `exit_mode` removed from PARAMS (the card's trail+BE is
  the native stage-1 exit); time exit 20:45.
- vwap_cross_mtf: `stop_atr` removed from PARAMS; signals only from 1 bar after the same-day anchor;
  time exit 20:45.
- asian_drift: the lookback=0 × t_min≠1.0 duplicates return no signals, so they are counted but are
  empty.
- Explicit 20:55 UTC exits (X5): first_last_hh, pmfix, tsmom_day, supertrend_rsi, avwap_london.
  avwap fade now uses the band at i−1. first_last_hh also gets the US holiday skip. tsmom RS uses
  full days only (≥ 12 h of bars).
- pmfix: the parameter `exit` was renamed `exit_at`, because it collided with the harness's `exit`
  column. The first staged run lost that parameter (24 rows, no stage 2). It was rerun, and only
  the rerun is used.

**Protocol notes.**
- Every strategy had already been run once through the old random-sample optimiser (pre-audit; 300
  combos for asian_drift, tsmom_day and ema_pullback_adx, 120 for the rest). Those combos are
  counted below. Their CSVs were overwritten and not used for selection.
- Only asian_drift's old output was read, and it showed VAL columns. Its VAL for the finalist
  (PF 0.75) was therefore known before the rerun. The rerun picked the same setting by IS rules.
- For every other strategy, the post-fix VAL check of the single finalist is its final VAL look.
- Stage 2 ran at 00:07 UTC. The harness fix "plateau ranking requires n_IS ≥ 60" (affb4d3) landed
  at 00:12. So in last30, first_last_hh, pmfix, tsmom_day, holy_grail and avwap_london, one or two
  of the three stage-2 slots went to settings with n_IS < 60. Those rows are excluded from
  selection.
- Stage 2 was **not** rerun after VAL had been seen, so that VAL stays clean.
- PARAMS lists keep the card default first. The harness sorts every grid internally for the
  plateau and the neighbourhood (`_sorted_grid`).

## Screen (card defaults, after the audit fixes)

| Strategy | IS n | WR % | PF | PF(R) | DD % | tr/wk | VAL PF | Screen |
|---|---|---|---|---|---|---|---|---|
| last30_momentum | 120 | 43.3 | 0.88 | 0.68 | 10.2 | 2.8 | 0.92 | fail |
| first_last_hh | 114 | 30.7 | 0.54 | 0.49 | 18.2 | 2.6 | 1.06 | fail |
| asian_drift (always long 00–07) | 246 | 50.8 | 1.16 | 1.25 | 2.7 | 5.0 | 1.04 | pass |
| pmfix (fade, a=0.5, 15:00 London) | 138 | 41.3 | 0.75 | 0.79 | 10.3 | 3.2 | 0.58 | fail (follow variant is the positive side) |
| fomc_drift | 6 | 66.7 | 8.09 | 7.64 | 0.5 | 0.15 | 0.00 (n=1) | **ineligible: trade-count gate** (8 FOMC/yr); possible add-on module |
| tsmom_day | 156 | 57.7 | 1.20 | 1.38 | 1.9 | 5.0 | 0.73 | pass |
| holy_grail | 50 | 54.0 | 1.34 | 1.21 | 3.3 | 1.0 | 0.83 | fail (n < 60; 1.0/wk vs card ~2.5/wk) |
| ema_pullback_adx | 127 | 47.2 | 1.18 | 1.37 | 4.5 | 2.5 | 0.61 | pass |
| supertrend_rsi | 453 | 36.2 | 0.94 | 0.88 | 20.7 | 8.7 | 0.96 | fail |
| vwap_cross_mtf | 345 | 48.7 | 0.86 | 0.86 | 18.2 | 6.7 | 0.73 | fail |
| avwap_london | 240 | 48.3 | 0.87 | 0.90 | 9.0 | 4.6 | 1.13 | fail |
| macro_shock | – | – | – | – | – | – | – | **SKIPPED**: NFP/CPI dates could not be checked on bls.gov (see below) |

## Best IS-selected setting per strategy

Exits are given in units of the module's `unit`, which is the card's stop distance unless stated.
"card" means the module's native exit.

| Strategy | Combos (pre-audit + staged) | Best IS-selected setting | IS n / WR / PF / PF(R) / DD% / tr/wk | VAL n / WR / PF / PF(R) / DD% / tr/wk | OOS n / WR / PF / PF(R) / DD% / tr/wk | Verdict |
|---|---|---|---|---|---|---|
| last30_momentum | 120 + 207 = 327 | k 0.25, signal 13:00 NY, exit 20:55 UTC, vol_filter on; scalp_be sl 3, tp1 0.5 (50 %), tp 3, BE (unit = 2.5×ATR14 1m) | 88 / 89.8 / 1.55 / 1.41 / 1.42 / 2.04 | 48 / 81.3 / 0.73 / 0.51 / 2.48 / 2.37 | – | REJECT at VAL |
| first_last_hh | 120 + 195 = 315 | first window 18:00–18:30 NY (prev. evening), no mid confirm, vol pct 75, exit 20:55; fixed sl 0.5, tp 2 | 64 / 26.6 / 1.13 / 1.24 / 4.35 / 1.50 | 27 / 18.5 / 0.77 / 0.82 / 5.54 / 1.48 | – | REJECT (IS PF(R) < 1.3) |
| asian_drift | 300 + 199 (191 distinct) = 499 | adaptive sign, lookback 250 d, t_min 0, window 08–20 UTC (day leg; adaptive sign = long on all 112 IS days); trail sl 1.0, trail 0.5 (unit = ATR14 D1) | 112 / 50.0 / 1.53 / 1.75 / 1.80 / 4.84 | 102 / 41.2 / 0.75 / 0.74 / 3.51 / 4.86 | – | REJECT at VAL (VAL also seen pre-audit) |
| pmfix | 120 + 24 (broken) + 183 = 327 | **follow** mode, a 1.0σ, exit 20:55 UTC; fixed sl 2.0, tp 2.0 (unit = Asian extreme + 0.25 ATR(D)) | 67 / 61.2 / 1.58 / 1.82 / 0.96 / 1.54 | 27 / 55.6 / 1.09 / 1.22 / 0.50 / 1.33 | – | REJECT at VAL |
| fomc_drift | 120 (discarded per audit) | screen only: wait 30, m 1.0, follow | 6 / 66.7 / 8.09 / 7.64 / 0.53 / 0.15 | 1 / 0 / 0 / 0 / 0.52 / – | – | INELIGIBLE (trade count), not frozen |
| tsmom_day | 300 + 183 = 483 | EMA 20/100 of daily closes, RS ≤ 0.6, entry 00:00 UTC, card exit (stop 1.5×ATR1h×√14, flat 20:55) | 156 / 57.7 / 1.36 / 1.56 / 1.78 / 5.01 | 95 / 50.5 / 0.74 / 0.86 / 4.96 / 4.65 | – | REJECT at VAL; IS = long-daytime beta (benchmark below) |
| holy_grail | 120 + 195 = 315 | ADX > 25, EMA20, 15m; fixed sl 1.5, tp 3 (unit = swing stop) | 80 / 46.3 / 1.66 / 1.36 / 4.70 / 1.59 | 36 / 30.6 / 0.87 / 0.91 / 2.98 / 1.79 | – | REJECT at VAL |
| ema_pullback_adx | 300 + 177 = 477 | ADX > 30, stop_atr 1.5, dead-market filter on; scalp_be sl 2.0, tp1 0.25 (50 %), tp 3.0, BE (unit = structural stop) | 91 / 87.9 / 1.57 / 1.80 / 0.58 / 1.80 | 45 / 91.1 / 3.35 / 1.73 / 0.50 / 2.22 | 40 / 80.0 / 0.99 / 1.09 / 1.31 / 1.97 (stress PF 1.00, DD 1.26) | **OOS FAIL** (IS PF and OOS PF gates; neighbourhood median IS PF 1.40, numeric-only 1.27) |
| supertrend_rsi | 120 + 186 = 306 | ST(7, 4.0), RSI 55/45; fixed sl 1.0, tp 3.0 (unit = ST distance) | 385 / 39.2 / 1.13 / 1.09 / 8.89 / 7.42 | 148 / 39.2 / 1.33 / 1.11 / 4.19 / 7.05 | – | REJECT (IS PF(R) < 1.3) |
| vwap_cross_mtf | 120 + 171 = 291 | EMA200 on H1/H4, VWAP anchor 13:30 UTC; fixed sl 2.0, tp 3.0 (unit = ATR14 5m) | 324 / 46.6 / 1.05 / 1.08 / 10.17 / 6.34 | 126 / 45.2 / 0.98 / 1.01 / 5.84 / 6.04 | – | REJECT (IS PF(R) < 1.3) |
| avwap_london | 120 + 195 (180 distinct; fade ignores trend_frac/touch_band) = 315 | anchor 23:00 UTC, trend share 0.7, touch AVWAP, pullback; trail sl 2.0, trail 1.0 (unit = −1.5σ stop) | 138 / 44.9 / 1.20 / 1.41 / 2.43 / 2.66 | 62 / 48.4 / 1.35 / 1.39 / 1.05 / 3.03 | 61 / 45.9 / 1.56 / 1.56 / 0.83 / 3.03 (stress PF 1.52, DD 0.87) | **OOS FAIL** (WR and PF gates; neighbourhood median IS PF 0.97, numeric-only 0.99) |
| macro_shock | 0 | – | – | – | – | SKIPPED (dates not verifiable on bls.gov) |

Frozen cards: `strategy_cards/ema_pullback_adx.frozen.json` and
`strategy_cards/avwap_london.frozen.json`, committed in a421a6a before OOS. Trades are in
`results/<id>_trades.csv`.

## Notes per strategy

- **tsmom_day.** The trend signal was long on every IS day: 156 long, 0 short. Benchmark: long
  every weekday over the same window, same stop and 20:55 exit, starting on the same first date.
  At 00:00 entry it gives IS PF 1.34 / PF(R) 1.55, VAL PF 0.79 (n 105). At 07:00 entry it gives IS
  PF 1.19 / PF(R) 1.38. The strategy's IS PF(R) of 1.56 equals the long-daytime benchmark, so the
  trend and semivariance filter add nothing in IS. VAL split: long n 87, PF 0.73; short n 8,
  PF 0.97.
- **asian_drift.** The unconditional Asian long (card default) has IS PF 1.16 and VAL PF 1.04, a
  weak drift that fits 2025's bull trend. The best IS setting is the adaptive *day leg*
  (08–20 UTC). Its sign was long on all 112 IS days, so in IS it is just long-daytime beta. In VAL
  it went 69 long / 33 short and lost (PF 0.75). lookback = 250 has no
  signals before about July 2025, so it uses only half of IS.
- **pmfix.** The card's fade (short after a strong Asia) loses in IS (PF 0.75). Only the follow
  variant is positive, which matches the Edgeful continuation note on the card. It did not hold on
  VAL (PF 1.09).
- **ema_pullback_adx.** This is the only Batch C setting that met WR/PF/DD on VAL (WR 91.1,
  PF 3.35, DD 0.50, n 45). It missed the IS PF gate (1.57), and in OOS it went to PF 0.99 (WR 80).
  The high WR comes from the 0.25R first target with break-even. PF depends on the rare full-target
  runners.
- **avwap_london.** It was positive on all three periods (PF 1.20 / 1.35 / 1.56) with very low DD.
  But WR is about 46 % and PF is far from 3, and its neighbourhood is flat (median IS PF ~0.97).
  It is a weak, stable trend-pullback, not a candidate.
- **last30_momentum / first_last_hh.** Both trade the same 13:00–13:30 NY window. Neither got
  past IS/VAL, so their overlap was not studied. The rest-of-day and first-half-hour signals show
  no edge after costs on gold in 2025: card-default PF 0.88 and 0.54.
- **holy_grail.** About 1 trade/week against the card's ~0.5/day. The first-touch-per-ADX-episode
  rule is restrictive. On 1h, only 14 IS trades.
- **fomc_drift.** FOMC statement dates were checked on federalreserve.gov (2025: Jan 29, Mar 19,
  May 7, Jun 18, Jul 30, Sep 17, Oct 29, Dec 10; 2026: Jan 28, Mar 18, Apr 29, Jun 17, Jul 29,
  Sep 16, Oct 28, Dec 9; the 2025-08-22 notation vote is excluded). 6 IS trades. Ineligible by
  trade count (X7). The 120-combo pre-audit optimise is discarded.
- **macro_shock: skipped.** bls.gov refuses automated access. curl returns HTTP 403 "Access Denied"
  (Akamai bot policy) for the Employment Situation and CPI release schedules, and the web fetcher
  cannot resolve the host. The 2025 release calendar was also disrupted by the federal shutdown
  (delayed or cancelled releases), so dates from memory are not reliable. Per instructions, the
  strategy was not implemented.

## Summary

No Batch C strategy passes. Two were frozen for the honest frontier, and both failed OOS:
- ema_pullback_adx: OOS WR 80.0, PF 0.99.
- avwap_london: OOS WR 45.9, PF 1.56.

Time-of-day ideas (asian_drift, tsmom_day, pmfix) gain in IS from 2025's bull-trend beta and
reverse in VAL 2026.
