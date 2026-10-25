# VClimaxSweepReversal — PASS

Compile: 0 errors / 0 warnings
`cd cbots/build && flock /tmp/cbot_build.lock dotnet build -nologo -v q -p:Bot=VClimaxSweepReversal -warnaserror` (2026-10-25T11:17:49Z, cTrader.Automate 1.0.21).
One `Robot` subclass, the class name matches the file, and `[Robot(AccessRights = AccessRights.None, TimeZone = TimeZones.UTC)]` is present.

Reviewed: `cbots/src/VClimaxSweepReversal.cs`, `cbots/presets/VClimaxSweepReversal_XAUUSD.cbotset`, `cbots/docs/VClimaxSweepReversal.md` (commit 20a5b54).
Compared against:
- `cbots/reference/MV_Gold_Sub5s_VClimaxReversal_cBot.cs`, line by line;
- its `.cbotset`;
- `cbots/reference/gold_sub5s_reversal_engine.py` (`detect_v_climax_signals`, `simulate_1s_trades`).

## Presets and parameters
- All 53 property names equal the 53 preset keys, and all defaults equal the preset values.
- Every one of the 25 original preset values carries over unchanged. `OrderLabel` was renamed to `Label`, with the same value.
- Every numeric parameter has Min/Max/Step. The original Min/Max are kept.
- No `DateTime.Now`, no `Random` and no `TimeZoneInfo`. Time comes from `Server.TimeInUtc`, as in the original.

## Verification of the documented fixes
| # | Verdict | Notes |
|---|---|---|
| B1 sizing basis | **correct** | `LegacyScale` reproduces the original exactly: `ComputeVolume(max(scale,5))` = equity·r / (dist·PipValue/PipSize), which is the original `riskUsd/(refPips·PipValue)`. `StopDistance` risks r% at the 5.5·scale stop. The documented claim "PF and WR are unchanged" is only approximate (finding 2). |
| B2 skip below min | correct | `ComputeVolume` returns 0, and the entry is skipped. |
| B3 ring buffer | correct | `Bar(i) = _ring[(head − count + i + cap) % cap]` addresses the oldest bar first. Capacity is 14,416, as in the original, and it is never negative. Its contents are equal to the original `List` with `RemoveAt(0)`. |
| B4 unsubscribe | correct | `OnStop` removes the `Positions.Closed` handler. |
| B5 signed cushion | correct | `entry + sd·CushionSlMult·scale` equals the original for the allowed range −1.5…0. |
| B6 checked modify/close | correct | Results are checked. `TightenStop` only tightens, and closes at market if the level is already crossed. With the default multiples the cushion has room ≥ 1.7·scale and the ratchet ≥ 0.6·scale, so the "room < broker min → silently skip (not retried)" branch cannot fire for them. |
| B7 per-position state + adoption | correct | Dictionary keyed by `Position.Id`, removed on Closed. Adoption recovers the scale from the TP, and the stage from the SL location (`> −0.9·SlMult·scale` → TP1 done; `> 0` → ratchet done). Minor: `EntrySec` is taken from `EntryTime` instead of the signal second, about 1 s apart. |
| B8 entry spread | correct | Both the signal-bar spread (line 347) and the live spread (line 444) are checked. |
| B9 log skipped partial | correct | Behaviour is unchanged and now logged. |

**Behaviour otherwise unchanged.** These were compared line by line:
- the aggregator;
- the `minReq` warm-up;
- the position, cooldown, hour-21, session (6–20 inclusive), spread and `dt5 ∈ (0,6]` checks;
- the h5/l5/h6/l6, imp/rej and turn-bar conditions;
- the population std over 900/3600/14400;
- the gates, the structural window `[n−6−W, n−6)`, the z-score and the short-before-long order;
- `scale = max(s900, 4.5)`, SL 5.5, TP2 2.2 (Arch 1 TP 0.7), TP1 0.65 at 0.7;
- cushion −1.0, ratchet 1.1 → 0.5, ratchet allowed on the same tick as TP1;
- the cooldown measured from the signal second, and max hold from the signal second.

All of these are identical to the original.

## Findings
No BLOCKER and no MAJOR findings.

| # | Severity | Where | What / why |
|---|---|---|---|
| 1 | MINOR | VClimaxSweepReversal.cs:518, 597 | **TP1 profit is missing from the daily-loss sum.** `_realisedToday` is only fed by `Positions.Closed`, so the profit of the 65% TP1 partial is never counted. Only the runner's result is: for example, the cushion stop at −1·scale on 35% counts as a loss even though the trade made money. The guard is conservative. |
| 2 | MINOR | docs B1 row | **"PF and WR are unchanged" is only approximately true.** `StopDistance` weights trades ∝ 1/scale for every scale. `LegacyScale` weights ∝ 1/max(scale, 5), so trades with s900 ∈ [4.5, 5) get up to about 10% different relative size, and the money PF changes slightly. WR is unchanged. |
| 3 | MINOR | docs "Diff vs original" | **Some small behaviour changes are not listed.** (a) The stop and TP are raised to the broker minimum distance (lines 448–450). (b) A failed max-hold close is retried on every tick, where the original tried once and forgot the position. (c) `MaxLots` = 20 caps `LegacyScale` volume, where the original was capped only by VolumeInUnitsMax. (d) The 3% daily-loss guard is on by default. With `SizingBasis = LegacyScale`, one stop-out is about 2.75% of equity, so the guard can block entries after one or two losses. It should be set to 0 to reproduce the reference run. |
| 4 | MINOR | VClimaxSweepReversal.cs:540–546 | `MoveToBreakEven` and `TrailingStopMult` only work in Arch 2 (`UseCushionRatchetRunner = true`). In Arch 1 the standard BE/trailing options do nothing, and the parameter table does not say so. |
| 5 | MINOR | naming | **Standard parameter names are not used.** `Tp1CloseFraction` (fraction) and `MaxHoldSeconds` are kept under their original names instead of the standard `Tp1ClosePercent` and `MaxHoldMinutes`. This is acceptable because it keeps the original presets loadable, and it is documented. |

Checklist results (all OK):
- Market order stop and target are in pips (`dist / PipSize`). `ModifyPosition` gets absolute prices rounded to `Digits`. `IsSuccessful` is checked everywhere.
- Partial close is skipped unless both parts are ≥ the minimum volume.
- Sizing uses `Symbol.LotSize`, `PipValue` and `PipSize` (nothing hard-coded), normalised down, capped, and skipped below the minimum volume.
- **Look-ahead:** decisions are made only on a completed 1-second bar, and the order goes out on the first tick of a later second. This is causal and the same as the original.
- Events are unsubscribed. The OnTick hot path is O(1) per tick; the window stats run only on candidate bars, and the O(14,400) cost there is the same as the original.

## Fix instructions
None required for PASS. Optional:
1. Count TP1 partial profits in the daily-loss guard. Use `History.FindAll(Label, SymbolName)` with `ClosingTime >= _day`, or add the realised P&L of `closeUnits` when the partial close succeeds.
2. Docs:
   - Reword B1 to "WR unchanged; PF changes slightly because relative trade size now follows 1/scale instead of 1/max(scale, 5)".
   - Add 3(a)–(d) to "Diff vs original".
   - In "Recommended backtest settings", add "set MaxDailyLossPercent = 0 when using LegacyScale to reproduce the reference".
   - Note that BE and trailing apply only in Arch 2.

## Fidelity table (vs original cBot, the stated source)
| Rule | Original | New cBot | Match? |
|---|---|---|---|
| 1 s bars | mid O/H/L/C + bid/ask close; finalised on the first tick of a later second | identical | yes |
| Buffer | `List`, cap 14,416, `RemoveAt(0)` | ring array, cap 14,416 | yes (B3) |
| Warm-up | n ≥ max(14406, W+6) | identical | yes |
| Position check | none open with label | `< MaxOpenPositions` (1) | yes |
| Cooldown | cur.sec − last entry signal sec < 180 → skip | identical | yes |
| Hours | hour 21 blocked; Liquid: 6 ≤ h ≤ 20 | identical (session hours as parameters, default 6/20) | yes |
| Spread | signal-bar spread ≤ 0.35 | same + live spread at entry | B8 |
| Gap check | dt5 ∈ (0, 6] | identical | yes |
| Impulse / rejection / turn bar | h5−l6, h6−l5; rej ≥ 0.6·imp; close<open & high<prevHigh (mirror) | identical | yes |
| Stats | mean + population std of closes over 900/3600/14400 incl. t | identical | yes |
| Vol gates | s3600 ≥ 7.5, s900 ≥ 5, s900 ≤ 1.0·s3600, s3600 ≥ 0.35·s14400 | identical | yes |
| Structure | hPre/lPre over [n−6−W, n−6) | identical | yes |
| Short trigger | imp ≥ 0.35·s3600, h5 > hPre+0.10, C < hPre−0.15, m3600 > m14400, z ≥ 1.5 | identical | yes |
| Long trigger | mirror | identical | yes |
| Scale | max(s900, 4.50) | max(s900, MinScaleUsd = 4.50) | yes |
| SL / TP | 5.5·scale / 2.2·scale (Arch 1: 0.7·scale), pips from fill | identical (+ broker min clamp) | yes |
| TP1 + cushion | fav ≥ 0.7·scale → close 65%, SL → entry − 1.0·scale | identical (signed formula) | yes (B5, B9) |
| Ratchet | after TP1, fav ≥ 1.1·scale → SL → entry + 0.5·scale | identical | yes |
| Max hold | now − signal sec ≥ 3600 → close | identical (retried if the close fails) | yes |
| Sizing | equity·0.5% / (max(scale,5)·$/unit) | default: / (5.5·scale·$/unit); `LegacyScale` = original | B1 |
| Min volume | raised to min | skipped | B2 |

**Against the Python engine (for information; not a defect, since the stated source is the original cBot):**
- Python uses sample std (ddof 1), the cBot population std.
- Python dedups all signals within 180 s and simulates overlapping trades; the cBot holds one position at a time.
- Python checks the ratchet from the second after TP1.

All three are documented under "Things deliberately not changed".
