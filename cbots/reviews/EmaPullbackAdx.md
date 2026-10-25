# EmaPullbackAdx — PASS

Compile: 0 errors / 0 warnings
`cd cbots/build && flock /tmp/cbot_build.lock dotnet build -nologo -v q -p:Bot=EmaPullbackAdx -warnaserror` (2026-10-25T11:17:47Z, cTrader.Automate 1.0.21).
One `Robot` subclass, the class name matches the file, and `[Robot(AccessRights = AccessRights.None, TimeZone = TimeZones.UTC)]` is present.

Reviewed: `cbots/src/EmaPullbackAdx.cs`, `cbots/presets/EmaPullbackAdx_XAUUSD.cbotset`, `cbots/docs/EmaPullbackAdx.md` (commit 20a5b54).
Compared against: `strategies/ema_pullback_adx.py`, `bt1s.py` (`ema`, `atr`, `_run`), `evaluate.py::apply_exit` and `strategy_cards/ema_pullback_adx.frozen.json`.

## Numerical checks (scratchpad scripts, not committed)
- **Indicators.** The cBot's EMA20, SMA-ATR14, ADX14 (`ewm alpha=1/14`, NaN seeding) and the `rolling(1840, min_periods=500).median().shift(1)` dead filter were ported line by line to Python. On 3,000 synthetic bars they were compared with `bt1s.ema`, `bt1s.atr`, `ema_pullback_adx.adx` and the pandas median:
  - maximum absolute difference: EMA 1.8e-12, ATR 0, ADX 5e-14, median 0;
  - the NaN masks are identical.
- **Presets.**
  - All 48 `[Parameter]` property names equal the 48 `.cbotset` keys.
  - Every default equals its preset value, and the frozen values are correct (AdxMin 30, StopAtrMult 1.5, UseDeadFilter true, SlMult 2, Tp1Mult 0.25, Tp1ClosePercent 50, TpMult 3, MoveToBreakEven true, TrailingStopMult 0).
  - Every numeric parameter has Min/Max/Step, and its default lies inside the range.
- **Determinism.** No `DateTime.Now`, no `UtcNow`, no `Random` and no `TimeZoneInfo` in the source.

## Findings
No BLOCKER and no MAJOR findings.

| # | Severity | Where | What / why |
|---|---|---|---|
| 1 | MINOR | EmaPullbackAdx.cs:498, 566 | **TP1 partial profit is missing from the daily-loss sum.** `_realisedToday` is only updated in `Positions.Closed`, which does not fire for a partial close. After a 50% TP1 followed by a break-even stop, the day's realised P&L reads 0 instead of the TP1 gain. The guard is conservative (it can only trigger earlier), and at 0.5% risk with ≤ 2 trades a day it never binds. |
| 2 | MINOR | EmaPullbackAdx.cs:257 | The force-flat reason string hard-codes "time exit 20:45" even when `TimeExitHour/Minute` are changed. Cosmetic. |
| 3 | MINOR | EmaPullbackAdx.cs:228 | **Restart adoption can understate the unit.** It recovers `unit = |entry − SL| / SlMult`. When the stop was floored by `MinStopUsd` or the broker minimum, the unit comes out too large, so TP1 is placed slightly further away. This only affects restarts. |
| 4 | MINOR | docs §Known differences | **Stop/target clamping is undocumented.** The bot clamps the stop and target to the broker minimum distance (`MinStopDistance` and `MinTpDistance`, lines 438–441). The docs do not mention this. It is harmless on XAUUSD. |

Checklist results (all OK):
- **Order and stop units.** `ExecuteMarketOrder` gets the stop and target in pips (`dist / PipSize`). `ModifyPosition` gets absolute prices rounded to `Digits`, and every call checks `IsSuccessful`.
- **Sizing.** Volume = cash / (stop distance × PipValue/PipSize), which means lots = cash / (stop × `Symbol.LotSize`) on a USD account. It is capped at min(VolumeInUnitsMax, MaxLots × LotSize), normalised down, and the trade is skipped below the minimum volume. Nothing is hard-coded.
- **Partial close.** It is skipped unless both parts are ≥ the minimum volume.
- **Guards.** Division by zero is guarded (ATR ≤ 0, unit ≤ 0, PipSize ≤ 0). The warm-up guard is `i < max(SwingBars, EmaSlow)`, and NaN ATR or ADX blocks a signal.
- **Events.** `Positions.Closed` is subscribed once and unsubscribed in `OnStop`. `OnTick` does O(1) work except on a new m15 bar.
- **No look-ahead.**
  - The m15 decision uses the closed bar `Count−2`.
  - The H1 filter uses the last H1 bar whose `open + 1h ≤ m15 close`. This equals `merge_asof` on close-seconds (the H1 10:00 bar is used for the m15 10:45 bar, not for 10:30), and that H1 bar is complete.
  - The median excludes the current bar (`shift(1)`).
- **`LoadMoreHistory()`.** It exists in 1.0.21. The loop stops on a return ≤ 0, so a backtest that cannot load more history only delays the dead filter, as documented in Known differences §3.

## Fix instructions
None required for PASS. Optional:
1. Make the daily-loss guard count TP1 profit. Either add the realised part of the TP1 partial to `_realisedToday` (P&L of `closeUnits` at the TP1 price), or compute today's realised P&L from `History.FindAll(Label, SymbolName)` with `ClosingTime >= _day`.
2. Build the force-flat reason string from `TimeExitHour:TimeExitMinute`.
3. Add one line to the docs' Known differences: "stop/target are raised to the broker minimum stop/TP distance when smaller".

## Fidelity table
| Rule | Python | cBot | Match? |
|---|---|---|---|
| Decision bars | `ctx.bars(900)` mid, closed bar, fill at close_sec+1 | m15 bid bars, closed bar `Count−2`, market order on the first tick of the next bar | yes (bid vs mid documented) |
| EMA20/50 | `ewm(span, adjust=False)` | hand-rolled, first-close seed | yes (1.8e-12) |
| ATR14 | `bt1s.atr` = SMA of TR, first TR NaN | SMA of TR, NaN until 14 TRs | yes (exact) |
| ADX14 | Wilder `ewm(alpha=1/n)` on TR, +DM, −DM, DX; DX guard 1e-9 | same recursion and seeding | yes (5e-14) |
| H1 trend | `sign(c − ema50(H1))` via `merge_asof(close_sec)` | last H1 with open+1h ≤ m15 close, own EMA50 | yes |
| Session | bar-start hour ∈ [7, 19) | `OpenTimes[i].Hour` ∈ [7, 19) | yes |
| ADX filter | `ax > adx_min` (30) | `adx > AdxMin` (30) | yes |
| Dead filter | `a >= rolling(1840, min 500).median().shift(1)` | `AtrMedianBefore(i)` over [i−1840, i), ≥ 500 finite | yes (exact) |
| Long trigger | e20>e50, hup>0, L≤e20, C>e20 | identical | yes |
| Short trigger | e20<e50, hup<0, H≥e20, C<e20 | identical | yes |
| Unit | max(C − (swl5 − 0.5a), 1.5a), swing including the signal bar | identical (`SwingBars` 5, `SwingAtrBuffer` 0.5, `StopAtrMult` 1.5) | yes |
| Stop | `apply_exit` sl = 2.0·unit, floor 0.15 | `max(SlMult·unit, MinStopUsd)` (+ broker min) | yes |
| TP1 / BE | tp1 0.25·unit, f1 0.5, be=1 → stop = entry + 0 | Tp1Mult 0.25, 50% close, BE at entry + 0 (retried until applied, market close if crossed) | yes |
| Final target | tp 3.0·unit | TpMult 3.0 broker TP | yes |
| Trail | `apply_exit` sets trail=0 | TrailingStopMult 0 | yes |
| Time exit | hold → 20:45 UTC | TimeExit 20:45 (+ force flat 20:55) | yes |
| Max per day | `groupby(day).head(2)` counts signals | `_signalsToday` counted before the trade guards | yes |
| One position | `bt1s.run` busy_until | MaxOpenPositions 1 | yes |
