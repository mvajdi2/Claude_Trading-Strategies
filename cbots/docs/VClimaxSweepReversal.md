# VClimaxSweepReversal (cTrader cBot)

- **Source:** `cbots/src/VClimaxSweepReversal.cs`
- **Package:** `cbots/algo/VClimaxSweepReversal.algo`
- **Presets:** `cbots/presets/VClimaxSweepReversal_XAUUSD.cbotset` (standard, bug-fixed sizing) and `cbots/presets/VClimaxSweepReversal_XAUUSD_reference.cbotset` (reproduces the original PF 3.23 run)
- **Upgrade of:** `cbots/reference/MV_Gold_Sub5s_VClimaxReversal_cBot.cs` and its preset `MV_Gold_Sub5s_VClimaxReversal_XAUUSD.cbotset`. Both are Antigravity originals and are left untouched.
- **Signal reference:** `cbots/reference/gold_sub5s_reversal_engine.py` (`detect_v_climax_signals`, `simulate_1s_trades` arch1/arch2).
- **Original cTrader result:** `cbots/reference/ctrader_cli_12m_ticks_summary.json`.
  - Tick data from server, 17 Oct 2025 → 16 Sep 2026, EUR account.
  - 63 closed legs, WR 92.1%, PF 3.23, equity DD 3.9%.

> **Caveat (from `research/near_candidates.md`):** the parameters were fitted on the same 12 months that produced PF 3.23, so the result has **never been tested out of sample**. Treat it as in-sample. The only clean test left is forward demo trading from Nov 2026, or a cTrader run on Jan–Sep 2025, which the original never saw.

The signal logic, the exit logic and every original default are **unchanged**. The bugs fixed and the standard features added are listed under "Diff vs original" below.

## Rules (all times UTC)

**1-second bars**
- Every tick updates a 1-second **mid** bar: O/H/L/C of (bid+ask)/2, plus the closing bid and ask.
- A second is finalised when the first tick of a later second arrives. The signal is evaluated then, and the order is sent on that same tick ("decide at the close, enter on the next tick").
- Only seconds that have ticks are stored. Windows count stored bars, as the Python does.
- A ring buffer holds the last 14,416 bars. No signal is possible until 14,406 bars are stored, which is about 4 hours of ticking seconds after the bot starts.

**Pre-checks on the closed second `t`**
- Fewer than `MaxOpenPositions` (1) positions are open with this label.
- At least `CooldownSeconds` (180) have passed since the last entry's signal second.
- The hour is not 21. With `LiquidHoursOnly`, the hour must be in [`SessionStartHourUtc`, `SessionEndHourUtc`] = [6, 20].
- The bar's closing spread is ≤ `MaxSpreadUsd` (0.35).
- The last 6 bars span 1–6 real seconds (`t − t₋₅`), which rules out gaps.

**Impulse and rejection**
- Window values:
  - h5 / l5 = highest high / lowest low of bars t−4..t.
  - h6 / l6 = the same over bars t−5..t.
- Impulse: impUp = h5 − l6, impDn = h6 − l5.
- Short candidate: impUp ≥ `MinImpulse5sUsd` (3.20), h5 − close ≥ `MinRejectionRatio` (0.60) × impUp, close < open, and high < previous high.
- Long candidate: the mirror image.

**Volatility gates**
- Stats are the mean and **population** std of 1-second closes over the last 900, 3600 and 14400 bars, including bar t.
- s3600 ≥ 7.50 and s900 ≥ 5.00.
- s900 ≤ 1.00 × s3600 (anti-news gate).
- s3600 ≥ 0.35 × s14400 (anti-box gate).

**Structure and exhaustion**
- hPre / lPre = high / low of the `StructuralWindowSec` (14400) bars ending at t−6.
- z = (close − m14400) / max(s14400, 0.10).

**Entry triggers**
- **Short** if all of these hold:
  - impUp ≥ 0.35 × s3600;
  - h5 > hPre + 0.10;
  - close < hPre − 0.15;
  - m3600 > m14400;
  - z ≥ 1.50.
- **Long** is the mirror image.

**Exits:** all distances are multiples of `scale = max(s900, MinScaleUsd = 4.50)`.
- **Arch 2** (`UseCushionRatchetRunner = true`, the default):
  - Stop = 5.5 × scale. Broker take-profit = 2.2 × scale (TP2).
  - At +0.7 × scale: close 65% and move the stop to entry + `CushionSlMult` × scale, i.e. 1.0 × scale behind entry.
  - At +1.1 × scale after TP1: move the stop to entry + 0.5 × scale (ratchet).
- **Arch 1** (`false`): stop 5.5 × scale, single target 0.7 × scale.
- **Time exit** `MaxHoldSeconds` = 3600 after the signal second. The position stays open through the 21:00 rollover, as in the original. `ForceFlatEnabled` is false by default.

## Parameters
Defaults equal the original preset. The original optimiser ranges are kept, and Steps are added.

| Group | Parameter | Default | Optimisation range (min–max / step) | Meaning |
|---|---|---|---|---|
| Identity | `Label` | VCSR_XAUUSD-CH | – | was `OrderLabel`; label + symbol filter |
| Identity | `TradeComment` | Sub5s_VClimaxSweep | – | was hard-coded |
| Risk | `RiskMode` | PercentOfEquity | enum: PercentOfEquity / FixedLots / FixedCash | new |
| Risk | `RiskPercent` | 0.5 | 0.1–5.0 / 0.1 | % of equity at risk |
| Risk | `SizingBasis` | StopDistance | enum: StopDistance / LegacyScale | new; see bug B1 |
| Risk | `FixedLots` | 0.10 | 0.01–20 / 0.01 | new |
| Risk | `FixedCashRisk` | 500 | 10–10000 / 10 | new |
| Risk | `MaxLots` | 20 | 0.01–50 / 0.01 | new (Python `MAX_LOTS` = 20) |
| Protection | `MaxSpreadUsd` | 0.35 | 0.10–1.50 / 0.05 | original; now also checked at entry |
| Protection | `MaxDailyLossPercent` | 3.0 | 0–10 / 0.5 | new (0 = off). On by default; set 0 to reproduce the reference run (see below) |
| Protection | `CloseAllOnDailyLoss` | false | bool | new |
| Protection | `MaxTradesPerDay` | 0 | 0–20 / 1 | new (0 = off, as in the original) |
| Protection | `MaxOpenPositions` | 1 | 1–5 / 1 | new; 1 matches the original's hard-coded rule |
| Protection | `CooldownSeconds` | 180 | 30–3600 / 30 | original (measured from the last entry's signal second) |
| Protection | `CooldownMinutes` | 0 | 0–240 / 5 | new: wait after a close |
| Protection | `MaxSignalLatencySec` | 0 | 0–10 / 1 | new: skip a signal evaluated more than N s after its second (0 = off) |
| Session | `LiquidHoursOnly` | true | bool | original |
| Session | `SessionStartHourUtc` / `SessionEndHourUtc` | 6 / 20 | 0–23 / 1 | were hard-coded (inclusive hours) |
| Session | `ForceFlatEnabled` | false | bool | new (off keeps original behaviour) |
| Session | `ForceFlatHourUtc` / `ForceFlatMinute` | 20 / 55 | 0–23 / 1, 0–59 / 5 | new |
| Session | `TradeMonday` … `TradeFriday` | true | bool | new |
| Signal | `StructuralWindowSec` | 14400 | 1800–14400 / 1800 | original |
| Signal | `MinImpulse5sUsd` | 3.20 | 2.0–10.0 / 0.2 | original |
| Signal | `MinImpulseStdMult` | 0.35 | 0.20–1.00 / 0.05 | original |
| Signal | `MinRejectionRatio` | 0.60 | 0.40–0.90 / 0.05 | original |
| Signal | `MinSweepUsd` | 0.10 | 0.05–1.00 / 0.05 | original |
| Signal | `MinReEntryUsd` | 0.15 | 0.05–1.00 / 0.05 | original |
| Gates | `MinStd900` | 5.00 | 2.0–15.0 / 0.5 | original |
| Gates | `MinStd3600` | 7.50 | 3.0–20.0 / 0.5 | original |
| Gates | `MaxRatio900To3600` | 1.00 | 0.70–1.50 / 0.05 | original |
| Gates | `MinRatio3600To14400` | 0.35 | 0.20–0.80 / 0.05 | original |
| Gates | `MinZ14400` | 1.50 | 1.0–3.0 / 0.1 | original |
| Exit | `UseCushionRatchetRunner` | true | bool | original (Arch 2 / Arch 1) |
| Exit | `MinScaleUsd` | 4.50 | 2.0–8.0 / 0.5 | was hard-coded 4.50 |
| Exit | `Tp1Mult` | 0.70 | 0.40–2.00 / 0.05 | original |
| Exit | `Tp2Mult` | 2.20 | 1.0–5.0 / 0.1 | original |
| Exit | `SlMult` | 5.50 | 2.0–8.0 / 0.25 | original |
| Exit | `Tp1CloseFraction` | 0.65 | 0.50–0.90 / 0.05 | original (standard `Tp1ClosePercent` kept under its original name and unit) |
| Exit | `CushionSlMult` | −1.00 | −1.50–0.00 / 0.1 | original |
| Exit | `RatchetTriggerMult` | 1.10 | 0.8–2.5 / 0.1 | original |
| Exit | `RatchetLockMult` | 0.50 | 0.1–1.5 / 0.1 | original |
| Exit | `MoveToBreakEven` | false | bool | new: after TP1, stop to entry + offset if tighter. **Arch 2 only** (does nothing when `UseCushionRatchetRunner = false`) |
| Exit | `BreakEvenOffsetUsd` | 0.0 | 0–2.0 / 0.1 | new |
| Exit | `TrailingStopMult` | 0.0 | 0–3.0 / 0.25 | new: own trailing stop of N × scale after TP1 (0 = off). **Arch 2 only** |
| Exit | `MaxHoldSeconds` | 3600 | 300–14400 / 300 | original (standard MaxHold, kept in seconds) |
| Diagnostics | `VerboseLog` | false | bool | new; the original printed every entry unconditionally |
| Diagnostics | `DrawLevels` | true | bool | new: swept level, entry, SL, TP1 and TP2 lines; no-op in optimisation |

## Diff vs original (behavioural changes)

### Bugs fixed

| # | Bug in the original | Fix | Effect with default settings |
|---|---|---|---|
| B1 | **Sizing used the wrong distance.** Risk cash was divided by `max(scale, 5) / PipSize × PipValue`, i.e. by about **1 × s900**, while the stop sits at **5.5 × s900**. A stop-out therefore lost about 5.5 × `RiskPercent` (≈ 2.75% at 0.5%). The label "Risk Per Trade (%)" was wrong. | Default `SizingBasis = StopDistance`: risk cash / (stop distance × value of a $1 move per unit). `LegacyScale` reproduces the original formula. | Position size is about 1/5.5 of the original at the same RiskPercent. WR is unchanged. PF changes slightly, because relative trade size now follows 1/scale instead of 1/max(scale, 5): trades with s900 between 4.5 and 5 get up to about 10% different relative weight. Absolute P&L and DD shrink about 5.5×. To compare with the reference equity curve, use `SizingBasis = LegacyScale` (or RiskPercent ≈ 2.75). |
| B2 | Volume below the broker minimum was **raised** to `VolumeInUnitsMin`, which over-risks. | Skip the trade (both sizing bases). | None at normal equity. |
| B3 | Ring buffer was a `List` using `RemoveAt(0)`: an O(14,416) memory shift every second, about 16M times in a 12-month tick backtest. | True circular array with O(1) push. | Same values, much faster backtests and optimisation. |
| B4 | `Positions.Closed` was never unsubscribed. | Unsubscribed in `OnStop`. | None. |
| B5 | Cushion stop used `Math.Abs(CushionSlMult)`. A positive value (a cushion in profit) would have been placed on the loss side. | Signed formula `entry + side × CushionSlMult × scale`. | Identical for the allowed range −1.5…0. |
| B6 | `ModifyPosition` and `ClosePosition` results were not checked. A stop modify that fails, for example because price has already crossed the new level, silently left the wide 5.5 × s900 stop in place. | Results are checked and logged. The stop only moves in the favourable direction. If the new level has already been crossed, the remainder is closed at market, as the Python simulator does when the stop is hit. | Only matters in fast markets. |
| B7 | Exit state was a single set of fields: one position only, and the state was lost on restart. A restarted bot never enforced `MaxHoldSeconds` or the TP1/ratchet logic on a position already open. | State is kept per `Position.Id` in a dictionary and removed on `Positions.Closed`. On start, open positions with this label are adopted: scale is recovered from the take-profit (never modified), and the TP1/ratchet stage from the stop location. | None in backtests. |
| B8 | The spread filter used the closing spread of the **signal** second, not the spread at the moment of entry. | Both are checked against `MaxSpreadUsd`. | Can skip a few entries whose spread widened in the next tick. |
| B9 | When TP1's 65% partial could not be split (volume too small), the stop still moved to the cushion with no message. | Behaviour kept (the cushion stop still applies) but logged, so it is visible. | None. |

### Standard features added
- `RiskMode` (PercentOfEquity / FixedLots / FixedCash) and `MaxLots`.
- Daily loss guard: this label's realised P&L since the UTC day start (read from `History`, so TP1 partial closes count) + unrealised P&L, measured against the day's start equity.
- `MaxTradesPerDay`, `MaxOpenPositions`, cooldown after close, weekday toggles.
- Optional force flat (off by default).
- Optional break-even and trailing stop after TP1 (off by default).
- `VerboseLog`, `DrawLevels`.
- Optimiser Step on every numeric parameter.
- Label + symbol filtering throughout, including the Closed handler, and event unsubscription.

### Other small behaviour changes
- **Broker minimum distance.** The stop and TP are raised to the broker's minimum stop/TP distance when smaller. XAUUSD's minimum is normally 0, so this has no effect.
- **Max-hold close is retried.** If the max-hold close fails, it is retried on every tick. The original tried once and then forgot the position.
- **`MaxLots` caps every sizing basis.** The default of 20 also caps `LegacyScale` volume. The original was capped only by `VolumeInUnitsMax`.
- **The daily-loss guard (3%) is on by default.** With `SizingBasis = LegacyScale`, one stop-out is about 2.75% of equity, so the guard can block further entries that day after one or two losses. The original had no guard.
- **Break-even and trailing are Arch 2 only.** The optional `MoveToBreakEven` and `TrailingStopMult` act only in Arch 2.

### Reproducing the reference run (PF 3.23)
Load `cbots/presets/VClimaxSweepReversal_XAUUSD_reference.cbotset`. It differs from the standard preset in these settings:

| Setting | Value |
|---|---|
| `SizingBasis` | LegacyScale |
| `MaxDailyLossPercent` | 0 |
| `MaxLots` | 50 (high enough not to bind; the reference run never exceeded 0.75 lots) |
| `MaxTradesPerDay` | 0 |
| `CooldownMinutes` | 0 |
| `MaxSignalLatencySec` | 0 |
| `ForceFlatEnabled` | false |
| Break-even and trailing | off |

The remaining differences from the original are the bug fixes B2, B6 and B8, plus the broker-minimum and max-hold-retry changes above. All of them are inactive in normal conditions.

### Things deliberately **not** changed (behaviour as the PF 3.23 run)
- **Population std.** Python's pandas `rolling().std()` uses ddof = 1. The difference is about 0.06% at n = 900.
- **Cooldown measured from the last entry.** Python deduplicates **all** signals within 180 s, traded or not, and simulates overlapping trades. The cBot drops signals while a position is open, and cooldown restarts only on an actual entry.
- **The ratchet can fire on the same tick as TP1.** Python starts the ratchet check one second after TP1.
- **Hour 21 is always blocked**, and positions can be held through the rollover.
- **The `UseCushionRatchetRunner = false` (Arch 1) defaults are inherited from Arch 2** (target 0.7, stop 5.5). The Python Arch 1 study used 0.8 / 5.0.

## Source mapping

| Python (`gold_sub5s_reversal_engine.py`) | cBot |
|---|---|
| `mid_o/h/l/c` 1-second bars | `SecBar` ring buffer built in `OnTick` |
| `h_5,l_5,h_6,l_6`, `imp_up/dn`, `rej_up/dn` | `EvaluateCompletedSecondBar` |
| `dt_5 ∈ (0,6]`, `session_ok` | `dt5` check, `LiquidHoursOnly` + session hours, hour ≠ 21 |
| `no_new_s / no_new_l` turn bar | `cur.MidHigh < prev.MidHigh && close < open` (mirror) |
| `h_pre/l_pre` = `h_w[t−6]` | loop over `[n−6−W, n−6)` |
| `s_900, s_3600, s_14400, m_3600, m_14400`, `z14400` | `ComputeWindowStats` (population std) |
| `vol_ok` gates | `MinStd*`, `MaxRatio900To3600`, `MinRatio3600To14400` |
| cooldown dedup 180 s | `CooldownSeconds` |
| arch2: `tp1, tp2, sl, w1, sl2, ratchet` | `Tp1Mult, Tp2Mult, SlMult, Tp1CloseFraction, CushionSlMult, RatchetTriggerMult, RatchetLockMult` |
| arch1 | `UseCushionRatchetRunner = false` |
| `hold = 3600` | `MaxHoldSeconds` |
| `scale = max(s_900, 4.5)` | `MinScaleUsd` |

## Known differences between the Python backtest and cTrader
1. **Data.**
   - Python uses Dukascopy 1-second bid/ask with an **hourly-average** cTrader spread model, $0.06/oz slippage and $0.06/oz commission.
   - cTrader uses the broker's real ticks and spreads. The broker's mid can differ from Dukascopy's in the sub-second wicks that drive this signal, so signal counts differ (cTrader: 63 legs ≈ 35 trades in 11 months).
2. **Fills.**
   - Python enters at the signal-second close plus half the spread plus slippage. cTrader enters at the next tick's ask or bid.
   - Python fills TP1 at the exact level. cTrader closes the 65% at market when bid or ask reaches it.
   - The runner's stop, TP2 and the time exit are broker or market fills.
3. **Overlapping trades.** Python simulates every deduplicated signal, even while another trade is still open. The cBot holds one position at a time (`MaxOpenPositions = 1`). This was already the case in the original.
4. **Warm-up.** No signal for about 4 hours of ticking seconds after the bot starts, or after a cTrader backtest begins.
5. **Sizing.**
   - Python reports $/oz with a fixed 0.5 lot.
   - The original cBot sized at about 0.5% of equity per 1 × s900 (bug B1).
   - This bot defaults to a true 0.5% risk at the stop. Compare **PF and WR**, not absolute P&L or DD, unless `SizingBasis = LegacyScale`.
6. **Sunday open.** Gold reopens Sunday 22:00–23:00 UTC. Weekend days are not tradable (only Mon–Fri toggles exist). With `LiquidHoursOnly = true` (06–20 UTC) this changes nothing.
7. **DST.** All rules are in UTC, so no local-time conversion is needed.

## Recommended cTrader backtest settings
- Symbol **XAUUSD**, chart period **m1**. The bot works on ticks, so the chart period only affects drawing.
- Data: **Tick data from server**. Do not use m1 bar data: the signal needs sub-second wicks.
- Dates:
  - **01/01/2025 → today**.
  - Also **01/01/2025 → 16/10/2025** on its own: the original never saw that period, so it is the only quasi-out-of-sample check.
  - Also Oct 2025 → Sep 2026, to compare with PF 3.23 / WR 92%.
- Commission **$7 per lot round trip**. Spread from the broker.
- Starting balance 100,000. Load `VClimaxSweepReversal_XAUUSD.cbotset`.
- To reproduce the original run (sizing, equity curve and DD, apart from fill differences), load `VClimaxSweepReversal_XAUUSD_reference.cbotset` (LegacyScale, daily-loss guard off).
