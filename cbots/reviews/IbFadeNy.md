# IbFadeNy — PASS (re-review 2026-10-25; initial verdict PASS)

Compile: 0 errors / 0 warnings
`cd cbots/build && flock /tmp/cbot_build.lock dotnet build -nologo -v q -p:Bot=IbFadeNy -warnaserror` (2026-10-25T11:17:53Z, cTrader.Automate 1.0.21).
One `Robot` subclass, the class name matches the file, and `[Robot(AccessRights = AccessRights.None, TimeZone = TimeZones.UTC)]` is present.

Reviewed: `cbots/src/IbFadeNy.cs`, the preset and the docs (commit 68bfdff).
Compared against:
- `strategies/ib_fade_ny.py`, plus `batcha_util.window_hl` and `local_sec`;
- `bt1s.atr`;
- the frozen card: ib_start ny0820, ib_minutes 30, wide_mult 1.2, exit sl 2.0 / tp 3.0 × d.

## Checks run
- **Preset keys and defaults.** All 44 property names equal the 44 preset keys, and every default equals its preset value. The frozen values are correct: IbStart Ny0820, IbMinutes 30, WideMult 1.2, ExitStyle UnitMultiples, SlMult 2, TpMult 3, StrategyFlatHourUtc 20, SignalEndHourUtc 18.
- **Optimiser ranges.** Every numeric parameter has Min/Max/Step, and the ranges cover the grid (ib_minutes 30/60, wide_mult 1.2/1.3/1.5; ib_start is an enum).
- **US DST helper.** `NthSunday` and `IsUsDst` were ported exactly to Python and compared with `zoneinfo America/New_York` for every day from 2024 to 2027: 0 mismatches. They were also compared with `batcha_util.local_sec` on the switch dates, giving the IB start in UTC for 08:20 New York:

  | Date | cBot | Python |
  |---|---|---|
  | 2025-03-07 Fri | 13:20 | 13:20 |
  | 2025-03-09 Sun | 12:20 | 12:20 |
  | 2025-03-10 Mon | 12:20 | 12:20 |
  | 2025-10-31 Fri | 12:20 | 12:20 |
  | 2025-11-02 Sun | 13:20 | 13:20 |
  | 2025-11-03 Mon | 13:20 | 13:20 |
  | 2026-03-06 Fri | 13:20 | 13:20 |
  | 2026-03-08 Sun | 12:20 | 12:20 |
  | 2026-03-09 Mon | 12:20 | 12:20 |
  | 2026-10-30 Fri | 12:20 | 12:20 |
  | 2026-11-01 Sun | 13:20 | 13:20 |
  | 2026-11-02 Mon | 13:20 | 13:20 |

  09:30 New York is +70 minutes in both. All match.
- **Determinism.** No `DateTime.Now`, no `Random` and no `TimeZoneInfo`.

## Findings
No BLOCKER and no MAJOR findings.

| # | Severity | Where | What / why |
|---|---|---|---|
| 1 | MINOR | IbFadeNy.cs:234 | The start-up message showing how many prior IBs were loaded goes through `Log()`, so it only prints with VerboseLog on. Without it you cannot see whether the 45-day history load worked, or whether the wide filter is waiting for 10 IBs. |
| 2 | MINOR | IbFadeNy.cs:452–455 | After 20:00, `ClosePos` runs on every tick while a position exists, with no "closing" guard, so a rejected close prints on every tick. |
| 3 | MINOR | IbFadeNy.cs:197, 476 | `_nextUnit` and `Register` are called from both `OpenMarket` and `Positions.Opened`. `ContainsKey` makes this harmless, but it is redundant. |

Checklist results (all OK):
- **Market order.** It uses relative stop and target pips from the fill (`dist / PipSize`), which equals Python's distances from the entry fill.
- **Sizing.** cash / (stop × LotSize × TickValue/TickSize). It is normalised down, capped, and skipped below the minimum, and LotSize is read from `Symbol`.
- **Partial close and moves.** TP1 is skipped unless both parts are ≥ the minimum volume. BE and trailing use `ModifyPosition` with absolute prices, only tighten, respect the broker minimum, and close at market if the level is already crossed.
- **No look-ahead.**
  - The IB is finalised only after a closed bar at or after t1.
  - The 5m logic runs on closed bars (`Count−2`) from `BarOpened`.
  - The ATR is the previous bar's (`A[j−1]`): it is read before the current bar's TR is added.
  - History signals are not traded (the `live` check).
- **`LoadMoreHistory`.** It degrades gracefully: the loop breaks on ≤ 0 and catches exceptions.
- **Events.** Every handler is unsubscribed.

## Fix instructions
None required for PASS. Optional:
1. Change line 234 from `Log` to `Print`, and include `_b1.OpenTimes[0]`.
2. Add a `_closing` guard to `ClosePos`.

## Fidelity table
| Rule | Python | cBot | Match? |
|---|---|---|---|
| IB start | `local_sec(td, 08:20, America/New_York)` | `IbStartUtc`: coded US rule, 08:20 + 4 h (EDT) or 5 h (EST) | yes (DST verified) |
| IB window | 1m bars starting in [t0, t0+30m), ≥ 60% (18 bars) | `need = int(0.6·30)` = 18 | yes |
| Median | `W.rolling(20, min_periods=10).median().shift(1)` over valid IBs | median of the previous ≤ 20 valid widths, ≥ 10 | yes |
| Wide filter | W > 1.2·med | `w > WideMult·med` | yes |
| Scan bars | 5m bars starting ≥ t1 and ≤ 17:55 (close ≤ 18:00) | `t ≥ _ibT1`, `t ≤ 18:00 − 5 min` | yes |
| Probe | H > rh → probe_hi, ext_hi = max H (same bar can probe and signal) | identical | yes |
| Short | probe_hi and mid < C < rh (checked first) | identical order | yes |
| Long | probe_lo and rl < C < mid | identical | yes |
| d | ext_hi + 0.1·A[j−1] − C (mirror) | `_extHi + ProbeAtrMult·atrPrev − c` | yes |
| ATR | SMA14 TR on 5m, previous bar | queue of 14 TRs before adding the current bar | yes |
| One per day | `break` after the first signal (even if invalid) | `_active = false` before the validity checks | yes |
| Stop / target | `apply_exit` sl = 2.0·d, tp = 3.0·d (native mid target overridden) | UnitMultiples SlMult 2, TpMult 3 | yes |
| Native | sl = d, tp = C − mid | `ExitStyle.Native` | yes |
| Flat | hold → 20:00 UTC | StrategyFlatHourUtc 20 (+ force flat 20:55) | yes |
| Entry | close_sec + 1 s market | first tick after the 5m close, market | yes |

---
## Re-review (commits bcad00f, 19dea4c)
Re-compiled at HEAD b2590b1 (includes csproj `UseSharedCompilation=false`, 8444ef4): `cd cbots/build && flock /tmp/cbot_build.lock dotnet build -nologo -v q -p:Bot=<Bot> -warnaserror` → **0 errors / 0 warnings** (2026-10-25 11:36Z). Preset keys == property names, defaults == preset == frozen values, every numeric parameter has Min/Max/Step (re-checked by script); 1 Robot class, UTC/AccessRights.None; no DateTime.Now/Random/TimeZoneInfo. The committed `.algo` was built from the current source (no source change since the `.algo` commit); note that `.algo` packaging is not byte-reproducible (two consecutive builds of identical source differ), so rebuild diffs are noise and were reverted.

| Item | Status | Notes |
|---|---|---|
| 1 start-up line | done | `Print` with earliest m1/m5 bar and prior IBs (median needs 10); docs explain the no-history case (start ≥ 1 month earlier). |
| 2 close guard | done, correct | the same once-a-minute `_closing` dictionary as AsianRangeBreakout, cleared on Closed. |
| 3 redundant Register | unchanged | harmless (`ContainsKey`); it was optional. |
| Extra: History daily loss | correct | same `RecomputeRealized` as AsianRangeBreakout (Label+Symbol, UTC day, at most once a minute plus on close/partial). |
| DST / signal / exit | unchanged | diff touches only logging, close guard and daily loss; the DST helper is untouched and its earlier verification still applies. |

**Final verdict: PASS** (0 blockers, 0 majors).
