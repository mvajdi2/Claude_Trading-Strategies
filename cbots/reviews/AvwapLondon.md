# AvwapLondon — PASS (re-review 2026-10-25; initial verdict PASS)

Compile: 0 errors / 0 warnings
`cd cbots/build && flock /tmp/cbot_build.lock dotnet build -nologo -v q -p:Bot=AvwapLondon -warnaserror` (2026-10-25T11:17:56Z, cTrader.Automate 1.0.21).
One `Robot` subclass, the class name matches the file, and `[Robot(AccessRights = AccessRights.None, TimeZone = TimeZones.UTC)]` is present.

Reviewed: `cbots/src/AvwapLondon.cs`, the preset and the docs (commit 68bfdff).
Compared against:
- `strategies/avwap_london.py` (`signals`, `_pullback`);
- `bt1s.atr` and `bt1s._run` (trailing semantics);
- `evaluate.py::apply_exit`;
- the frozen card: anchor 23.0, trend_frac 0.7, touch_band 0.0, mode pullback, exit sl 2.0 / trail 1.0 / tp 0.

## Checks run
- **Preset keys and defaults.** All 46 property names equal the 46 preset keys, and every default equals its preset value. The frozen values are correct: Anchor Utc2300, TrendFrac 0.7, TouchBand 0.0, Mode Pullback, SlMult 2, TrailingStopMult 1, TpMult 0, Tp1Mult 0, MaxSignalsPerDay 2, ForceFlat 20:55.
- **Optimiser ranges.** Every numeric parameter has Min/Max/Step, and the ranges cover the grid (trend_frac 0.6/0.7/0.8, touch_band −1/0; anchor and mode are enums).
- **Trailing semantics.** In Python, `trail = 1.0·u` with `tp1 = 0`, so `trail_on` is active from entry with `best = entry`. After the first second the stop becomes entry − 1·u, tighter than the 2·u initial stop, and it then ratchets on the best exit-side price. The cBot matches:
  - `TrailOn` is set at registration, with `Best = EntryPrice`;
  - on the first tick `ns = entry − 1·d` is ≥ $0.05 better than the broker SL at 2·d, so `ModifyPosition` moves it;
  - it then ratchets on bid (long) or ask (short), only tightens, and closes at market if crossed.
- **AVWAP.** Typical price × `Bars.TickVolumes`, divided by `max(cv, 1)`. σ = √max(E[tp²] − vw², 0). The group is `floor((bar start − 23:00) / 1 day)`, which equals the Python `grp`. frac_up includes the current bar. The slope is `vw[i] − vw[i−12]` with `nbar > 12`. All match Python.
- **Determinism.** No `DateTime.Now`, no `Random` and no `TimeZoneInfo`.

## Findings
No BLOCKER and no MAJOR findings.

| # | Severity | Where | What / why |
|---|---|---|---|
| 1 | MINOR | AvwapLondon.cs:332–339 | **DrawLevels draws 3 trend lines for every 5-minute bar**, about 830 objects a day, and never removes them. Live, or in a long visual backtest, the chart builds up hundreds of thousands of objects and slows down. It is already a no-op in optimisation and silent backtests. |
| 2 | MINOR | AvwapLondon.cs:320 | A session's first bars with zero volume use vw = tp, while Python uses vw = 0 (which counts as "close above"). cTrader bars always have TickVolume ≥ 1, so this has no practical effect. |
| 3 | MINOR | docs | **Volume weighting is the largest source of divergence.** `Bars.TickVolumes` (broker ticks) replaces the Dukascopy tick count, and the docs say so clearly. In a cTrader backtest on m1/bar data instead of tick data, TickVolumes can be synthetic. Add "use Tick data from server" as a requirement, not only as a recommendation. |

Checklist results (all OK):
- **Market order.** Relative stop pips from the fill, and no TP (TpMult 0, so `tpPips` is null).
- **Sizing.** cash / (2·d × LotSize × TickValue/TickSize). It is normalised down, capped, and skipped below the minimum. This sizes for 0.5% at 2·d, which is also the R basis in Python.
- **Max signals per day.** At most 2 signals per UTC day (signal day = close_sec day, counted before the trade guards and for history signals too, as `groupby(day).head(2)` does). One position at a time.
- **Times.** Signals come from bars opening 08:00–19:55, and the bot is flat at 20:55.
- **No look-ahead.** Closed 5m bars only (`Count−2`, from `BarOpened`). The fade mode uses the previous bar's band (`_prevVw`/`_prevSd`, reset per session).
- **Events.** Every handler is unsubscribed. `LoadMoreHistory` (4 days) degrades gracefully.

## Fix instructions
None required for PASS. Optional:
1. Draw the VWAP and bands as one line per session (update the end point), or keep only today's objects (remove the previous session's on a group change).
2. Docs: say that tick data is required for TickVolumes.

## Fidelity table
| Rule | Python | cBot | Match? |
|---|---|---|---|
| Anchor / group | `(sec − 23·3600) // 86400` | `floor((sec − AnchorSeconds) / 86400)` | yes |
| VWAP | Σtp·n / max(Σn, 1), n = tick count | Σtp·TickVolume / max(Σv, 1) | yes (volume source documented) |
| σ | √max(Σtp²n/Σn − vw², 0) | identical | yes |
| frac_up | cumulative share of C > vw incl. the current bar | `_nAbove / _nbar` | yes |
| Slope | vw − vw[−12], requires nbar > 12 | `_vwHist[nbar−1−12]` | yes |
| ok mask | hour ∈ [8, 20), ATR finite, slope finite, nbar ≥ 12, sd > 0 | identical | yes |
| ATR | SMA14 TR incl. the signal bar | queue including the current bar | yes |
| Pullback state | arm on touch L ≤ vw + 0·sd in an uptrend; disarm when the trend is lost; trigger C > vw & C > O; reset per group; state kept across !ok bars | identical order and resets | yes |
| d | max(C − (vw − 1.5σ), 0.5·ATR) (mirror) | `max(d, MinStopAtrMult·atr)` with StopSigmaMult 1.5 | yes |
| Stop | `apply_exit` sl = 2.0·d (floor 0.15) | SlMult 2, MinStopUsd 0.15 | yes |
| Trail | trail = 1.0·d from entry (best = entry), ratchet only | TrailingStopMult 1, TrailOn at entry, Best = EntryPrice, $0.05 step | yes (granularity documented) |
| Target | tp = 0 (none) | TpMult 0 → no TP | yes |
| Max per day | `groupby(close_sec day).head(2)` | MaxSignalsPerDay 2 on the close day | yes |
| Flat | hold → 20:55 | ForceFlat 20:55 | yes |
| Fade2Sd mode | O beyond the previous bar's 2σ, C back inside, same group; d = bar extreme + 0.25·ATR; tp = |C − vw| | identical | yes |

---
## Re-review (commits bcad00f, a49f5b2, 19dea4c)
Re-compiled at HEAD b2590b1 (includes csproj `UseSharedCompilation=false`, 8444ef4): `cd cbots/build && flock /tmp/cbot_build.lock dotnet build -nologo -v q -p:Bot=<Bot> -warnaserror` → **0 errors / 0 warnings** (2026-10-25 11:36Z). Preset keys == property names, defaults == preset == frozen values, every numeric parameter has Min/Max/Step (re-checked by script); 1 Robot class, UTC/AccessRights.None; no DateTime.Now/Random/TimeZoneInfo. The committed `.algo` was built from the current source (no source change since the `.algo` commit); note that `.algo` packaging is not byte-reproducible (two consecutive builds of identical source differ), so rebuild diffs are noise and were reverted.

| Item | Status | Notes |
|---|---|---|
| 1 DrawLevels accumulation | fixed | `DrawSession`: objects are tracked in `_drawn` and removed when the VWAP group changes, so at most about 3×288 objects exist; still only when `_canDraw && _warm` (no-op in optimisation and silent backtests). |
| 2 docs tick data | done | "Tick data from server … is REQUIRED". |
| Extra: close guard + History daily loss | correct | same as AsianRangeBreakout (Label+Symbol, UTC day, at most once a minute plus on close/partial; once-a-minute close attempts). |
| VWAP / pullback / trailing | unchanged | the only code moved is the drawing block; signal state and `_prevVw` handling are untouched. |

**Final verdict: PASS** (0 blockers, 0 majors).
