# AsianRangeBreakout — FIX

Compile: 0 errors / 0 warnings
`cd cbots/build && flock /tmp/cbot_build.lock dotnet build -nologo -v q -p:Bot=AsianRangeBreakout -warnaserror` (2026-10-25T11:17:51Z, cTrader.Automate 1.0.21).
One `Robot` subclass, the class name matches the file, and `[Robot(AccessRights = AccessRights.None, TimeZone = TimeZones.UTC)]` is present.

Reviewed: `cbots/src/AsianRangeBreakout.cs`, the preset and the docs (commit 68bfdff).
Compared against:
- `strategies/asian_range_breakout.py` and `strategies/batcha_util.py` (`window_hl`, `daily`, `prev_rows`, `realized_var`, `vol_state_pct`, `first_touch`, `mid_at`);
- `evaluate.py::apply_exit`;
- the frozen card: range_end 6, buffer 2.0, cutoff 12, vol_state top, rng_filter atr, flat 16, exit sl 2.0 / tp 1.0 × W.

## Checks run
- **Preset keys and defaults.** All 54 property names equal the 54 preset keys, and every default equals its preset value. The frozen values are correct: RangeEndHourUtc 6, BufferUsd 2.0, CutoffHourUtc 12, VolState Top, RangeFilter Atr, StrategyFlatHourUtc 16, ExitStyle UnitMultiples, SlMult 2, TpMult 1, TgtX 1.5.
- **Optimiser ranges.** Every numeric parameter has Min/Max/Step, and the ranges cover the Python grid (range_end 5/6/7, buffer 0.5/2.0, cutoff 9/12; the filters are enums).
- **Vol-state percentile.** The cBot's `(less + (eq+1)/2) / cnt` over the last ≤ 250 rows (minimum 60) was compared with pandas `rolling(250, min_periods=60).rank(pct=True)` on 400 integer series with heavy ties. Maximum difference: 0, with identical NaN masks.
- **RV definition.** The 5-minute log returns are taken over **all** bars (the return of the 00:00 bar is against the 23:55 bar), summed for bars opening before 21:00 on the UTC date. The cBot does the same (`_prev5Close` is updated on every bar, and only bars before 21:00 are accumulated).
- **Previous completed day only.**
  - `VolPctBefore(today)` ranks the last flushed day, i.e. D−1 (Friday on a Monday).
  - `DailyAtrBefore(today)` uses the 23:00–21:00 rows with td < today, each with ≥ 300 bars, and the ATR needs 15 rows (first TR NaN).
  - Both equal `prev_rows`.
- **Determinism.** No `DateTime.Now`, no `Random` and no `TimeZoneInfo`.

## Findings
| # | Severity | Where | What / why |
|---|---|---|---|
| 1 | **MAJOR** | AsianRangeBreakout.cs:549–580 | **A double fill is not neutralised.** The sibling is cancelled in `PendingOrders.Filled` and `Positions.Opened`. That is enough in a backtest, where the handlers run synchronously, but live the cancel is a server round-trip. In a fast spike the second stop can fill first, which the docs admit. `OnPositionOpened` then registers the second position too (`_tradesToday` becomes 2, and `MaxOpenPositions`/`MaxTradesPerDay` are never checked on fills). On a hedging account the bot ends up holding opposite legs, each with a 2·W stop and its own costs, which can lose up to 2× the intended risk in a whipsaw. On a netting account the second fill silently closes the first. Python never has two positions: one trade per day, and a day where both sides touch in one second is skipped. |
| 2 | MINOR | docs §Vol-state history | **The vol-state window length differs from Python in 2025, and `LoadMoreHistory` is unverified in backtests.** Python's data starts on 2025-01-01, so its window grows from 60 days to 250 days over 2025. A cBot that loaded 400 days uses a full 250-day window from day one, so the "top tercile" days differ throughout 2025, not only before April. Separately, `LoadMoreHistory()` exists in API 1.0.21, but it is not certain that the backtester serves history before the start date. If it returns 0, the window instead builds up inside the test. The docs should state both cases and how to tell which one happened (see the next finding). |
| 3 | MINOR | AsianRangeBreakout.cs:270 | The start-up message showing how many daily rows and RV days were loaded goes through `Log()`, so it only prints with VerboseLog on. Without it you cannot see whether the history load worked. |
| 4 | MINOR | AsianRangeBreakout.cs:496–507 | **A side can be skipped where Python would place it.** A side is skipped when its level is within `MinStopLossDistance` of the market. Python places both orders whenever the mid is strictly inside (up, dn). The level is ≥ $2 away (the buffer), so in practice this rarely matters. Document it. |
| 5 | MINOR | AsianRangeBreakout.cs:527–531 | After `StrategyFlatHourUtc`, `ClosePos` is called on every tick while a position exists. There is no "closing" guard, so a rejected close prints on every tick. |
| 6 | MINOR | AsianRangeBreakout.cs:229, 561, 565 | `_nextUnit` is never set (dead code). |
| 7 | MINOR | docs | Documented differences, acceptable: the spread is checked when the orders are placed, not at the fill; the bid/ask trigger vs Python's mid touch; the stop-level fill vs Python's next-second market fill; the both-sides-in-one-second skip cannot be replicated. |

Checklist results (all OK):
- **Pending orders.**
  - `PlaceStopOrder` gets relative stop and target pips plus an expiry at the cutoff, and unfilled orders are also cancelled explicitly at the cutoff (line 526).
  - On fill, the stop and target are re-based to the actual entry with `ModifyPosition` (absolute prices rounded to `Digits`), matching Python's distances from the entry fill.
- **Sizing.** cash / (stop × LotSize × TickValue/TickSize) gives lots, then units. It is capped at min(VolumeInUnitsMax, MaxLots), normalised down, and skipped below the minimum. LotSize is not hard-coded.
- **No look-ahead.** All history is processed on closed bars (`Count−2`) through the `BarOpened` events, and the range is complete at 06:00 before the decision.
- **Events.** Every handler is unsubscribed in `OnStop`.

## Fix instructions
1. **(MAJOR)** In `OnPositionOpened` (line 555), before `Register`:
   - Count the other open positions with this label and symbol (excluding `p`).
   - If there is at least one, or `_tradesToday >= MaxTradesPerDay`, call `ClosePosition(p)` straight away. Log "OCO double fill: closed second position" (as a `Print`), call `CancelMyPending`, and `return` without registering.
   - Keep the existing sibling cancel.
   - Add to the docs: "use a hedging account; on a netting account a second fill would offset the first".
   - Update the "Rare double fill" bullet to describe the new behaviour.
2. Change the start-up message at line 270 from `Log` to `Print`, and include `_b5.OpenTimes[0]` and `_b1.OpenTimes[0]` so the earliest loaded bar is visible.
3. Docs, §Vol-state history:
   - Python's percentile window grows from 60 to 250 days through 2025, while the cBot with full history uses 250 from the start, so the filtered days differ during 2025.
   - Whether `LoadMoreHistory` returns data in the cTrader backtester depends on the platform. Check the start-up line. If no history was loaded, start the backtest ≥ 3 months before the comparison period.
4. Optional: document finding 4, add a `_closing` HashSet guard to `ClosePos` (as in EmaPullbackAdx), and remove `_nextUnit`.

## Fidelity table
| Rule | Python | cBot | Match? |
|---|---|---|---|
| Range window | 1m bars starting in [00:00, 06:00) of the calendar day, ≥ 60% of bars (216) | `ProcessM1`, `need = int(0.6·360)` = 216 | yes |
| W | rh − rl | `_rH − _rL` | yes |
| ATR filter | 0.2·atr14 ≤ W ≤ 1.0·atr14; atr14 = SMA14 of TR on 23:00–21:00 daily rows with ≥ 300 m1 bars, previous td | `DailyAtrBefore(today)`, same row rule, `n ≥ p+1` | yes |
| Vol state top | `vol_state_pct ≥ 2/3`: rolling(250, 60) rank pct of the previous day's RV (sum of squared 5m log returns, bars < 21:00) | `VolPctBefore`, exact pandas tie rule | yes (verified numerically) |
| Inside check | mid at 05:59:59 strictly inside (dn, up) | mid at the first tick ≥ 06:00 strictly inside | yes (documented) |
| Levels | rh + 2.0 / rl − 2.0 | `_rH + BufferUsd` / `_rL − BufferUsd` | yes |
| Trigger | first 1 s mid touch in [06:00, 12:00); both sides in one second → skip; market fill next second | buy/sell stop orders at the levels, expiring at 12:00 + explicit cancel; OCO cancel on fill | yes in intent (fill model documented); double fill → **finding 1** |
| Stop | `apply_exit` sl = 2.0·W (floor 0.15) from the entry fill | `SlMult·W`, floor MinStopUsd/broker min, re-based to the fill | yes |
| Target | tp = 1.0·W from the fill | `TpMult·W`, re-based | yes |
| Native exit | sl = up − dn, tp = 1.5·W | `ExitStyle.Native` | yes |
| Flat | hold → 16:00 UTC | `StrategyFlatHourUtc` 16 (+ force flat 20:55) | yes |
| Trades per day | 1 (one touch per day) | MaxTradesPerDay 1, OCO | yes, except finding 1 |
