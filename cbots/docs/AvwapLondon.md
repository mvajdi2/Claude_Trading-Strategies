# AvwapLondon (cTrader cBot)

Port of the frozen Python strategy `strategies/avwap_london.py` with the settings in
`strategy_cards/avwap_london.frozen.json`.

- Source: `cbots/src/AvwapLondon.cs`
- Package: `cbots/algo/AvwapLondon.algo`
- Preset: `cbots/presets/AvwapLondon_XAUUSD.cbotset` (frozen values)

Research status: candidate #3 in `research/near_candidates.md`. OOS PF 1.56, WR 46%, DD 0.8%, n = 61.
It **does not** meet the targets. The IS setting was a peak, not a plateau. Use it for backtesting and
demo only.

## Rules (frozen settings, 5-minute bars, all times UTC)
1. **Anchored VWAP:** resets at **23:00 UTC**, the session start (`Anchor = Utc2300`).
   - Typical price (H+L+C)/3 is weighted by **`Bars.TickVolumes`**.
   - The bot also computes the volume-weighted standard deviation σ, giving σ bands.
2. **Trend:**
   - `frac_up` is the share of 5-minute closes since the anchor that are above the VWAP, including
     the current bar.
   - Uptrend: `frac_up ≥ 0.7` and VWAP > VWAP 12 bars earlier. Downtrend is the mirror.
3. **Signal window:** bars that open 08:00–20:00, with at least 12 bars since the anchor, ATR14 ready
   and σ > 0.
4. **Pullback entry (`Mode = Pullback`):**
   - In an uptrend, a bar whose low ≤ VWAP + 0 × σ arms a long.
   - The first bar, the same one or a later one, that closes above the VWAP **and** above its open
     triggers the long.
   - Losing the trend disarms the setup. Shorts mirror this.
   - The entry is a market order on the first tick after the signal bar closes.
5. **Limits:** at most **2 signals per UTC day** (Python `groupby(day).head(2)`). A signal that
   arrives while a position is open is skipped **and still counts**, as in Python.
6. **Unit d:** for a long, max(close − (VWAP − 1.5σ), 0.5 × ATR14 on 5m). Shorts mirror this. The
   ATR is a simple mean of the true range including the signal bar.
7. **Exit (frozen `{"sl": 2.0, "trail": 1.0, "tp": 0}`, unit = d):**
   - Initial stop = 2.0 × d from the fill.
   - A **trailing stop of 1.0 × d is active from the entry**: stop = best price since entry
     − 1.0 × d, and it only ratchets.
   - Because the best price starts at the entry price, the effective initial stop is 1.0 × d right
     after the fill, exactly as in the Python engine.
   - No fixed target. Close everything at **20:55 UTC** (`ForceFlatHourUtc:ForceFlatMinute`).
8. **Standard guards:** spread cap, daily-loss limit, max trades and positions, cooldown, weekday
   toggles.
9. **Optional exits (off by default):** partial TP1, break-even and max hold. The trailing stop is
   on, because it is part of the frozen exit.

## Parameters
| Group | Parameter | Default (frozen) | Optimisation range | Meaning |
|---|---|---|---|---|
| Identity | `Label` | AVW_XAUUSD | – | Label |
| Identity | `TradeComment` | AvwapLondon | – | Trade Comment |
| Risk & Sizing | `RiskMode` | PercentOfEquity | PercentOfEquity / FixedLots / FixedCash | Risk Mode |
| Risk & Sizing | `RiskPercent` | 0.5 | 0.1 – 3.0 step 0.1 | Risk % of Equity |
| Risk & Sizing | `FixedLots` | 0.1 | 0.01 – 50.0 step 0.01 | Fixed Lots |
| Risk & Sizing | `FixedCashRisk` | 100.0 | 10.0 – 10000.0 step 10.0 | Fixed Cash Risk |
| Risk & Sizing | `MaxLots` | 10.0 | 0.01 – 100.0 step 0.01 | Max Lots |
| Account Protection | `MaxSpreadUsd` | 1.0 | 0.1 – 5.0 step 0.1 | Max Spread (USD) |
| Account Protection | `MaxDailyLossPercent` | 3.0 | 0.0 – 20.0 step 0.5 | Max Daily Loss % (0 = off) |
| Account Protection | `CloseOnDailyLoss` | false | true / false | Close All On Daily Loss |
| Account Protection | `MaxTradesPerDay` | 2 | 1 – 10 step 1 | Max Trades Per Day |
| Account Protection | `MaxOpenPositions` | 1 | 1 – 10 step 1 | Max Open Positions |
| Account Protection | `CooldownMinutes` | 0 | 0 – 1440 step 15 | Cooldown Minutes |
| Session & Calendar | `Anchor` | Utc2300 | Utc0700 / Utc2300 / Utc1330 | VWAP Anchor (UTC) |
| Session & Calendar | `SignalStartHourUtc` | 8 | 0 – 12 step 1 | Signal Start Hour UTC |
| Session & Calendar | `SignalEndHourUtc` | 20 | 14 – 21 step 1 | Signal End Hour UTC |
| Session & Calendar | `ForceFlatHourUtc` | 20 | 0 – 23 step 1 | Force Flat Hour UTC |
| Session & Calendar | `ForceFlatMinute` | 55 | 0 – 59 step 5 | Force Flat Minute |
| Session & Calendar | `TradeMonday` | true | true / false | Trade Monday |
| Session & Calendar | `TradeTuesday` | true | true / false | Trade Tuesday |
| Session & Calendar | `TradeWednesday` | true | true / false | Trade Wednesday |
| Session & Calendar | `TradeThursday` | true | true / false | Trade Thursday |
| Session & Calendar | `TradeFriday` | true | true / false | Trade Friday |
| Strategy Signal | `Mode` | Pullback | Pullback / Fade2Sd | Mode |
| Strategy Signal | `TrendFrac` | 0.7 | 0.5 – 0.9 step 0.05 | Trend Fraction |
| Strategy Signal | `TouchBand` | 0.0 | -1.5 – 0.5 step 0.25 | Touch Band (x sigma) |
| Strategy Signal | `SlopeBars` | 12 | 6 – 24 step 3 | Slope / Min Bars Since Anchor |
| Strategy Signal | `StopSigmaMult` | 1.5 | 0.5 – 3.0 step 0.25 | Stop Band (x sigma) |
| Strategy Signal | `MinStopAtrMult` | 0.5 | 0.0 – 1.5 step 0.25 | Min Stop (x ATR) |
| Strategy Signal | `FadeStopAtrMult` | 0.25 | 0.0 – 1.0 step 0.05 | Fade Stop Pad (x ATR) |
| Strategy Signal | `AtrPeriod` | 14 | 7 – 28 step 1 | ATR Period (5m) |
| Strategy Signal | `MaxSignalsPerDay` | 2 | 1 – 5 step 1 | Max Signals Per UTC Day |
| Exit Management | `ExitStyle` | UnitMultiples | UnitMultiples / Native | Exit Style |
| Exit Management | `SlMult` | 2.0 | 0.5 – 3.0 step 0.25 | Stop Mult (x d) |
| Exit Management | `TpMult` | 0.0 | 0.0 – 3.0 step 0.25 | Target Mult (x d, 0 = none) |
| Exit Management | `MinStopUsd` | 0.15 | 0.0 – 1.0 step 0.05 | Min Stop (USD) |
| Exit Management | `Tp1Mult` | 0.0 | 0.0 – 2.0 step 0.25 | TP1 Mult (x unit, 0 = off) |
| Exit Management | `Tp1ClosePercent` | 50.0 | 10.0 – 90.0 step 10.0 | TP1 Close % |
| Exit Management | `MoveToBreakEven` | false | true / false | Move To Break-Even |
| Exit Management | `BreakEvenTriggerMult` | 1.0 | 0.25 – 3.0 step 0.25 | BE Trigger (x unit, used when TP1 off) |
| Exit Management | `BreakEvenOffsetUsd` | 0.0 | 0.0 – 2.0 step 0.1 | BE Offset (USD) |
| Exit Management | `TrailingStopMult` | 1.0 | 0.0 – 3.0 step 0.25 | Trailing Stop Mult (x d, 0 = off) |
| Exit Management | `TrailStepUsd` | 0.05 | 0.01 – 1.0 step 0.01 | Trail Min Step (USD) |
| Exit Management | `MaxHoldMinutes` | 0 | 0 – 1440 step 15 | Max Hold Minutes (0 = off) |
| Diagnostics | `VerboseLog` | false | true / false | Verbose Log |
| Diagnostics | `DrawLevels` | true | true / false | Draw Levels |

The optimisation ranges include the Python `PARAMS` grid:

| Python grid | Values | cBot parameter |
|---|---|---|
| `anchor` | 7.0, 23.0, 13.5 | `Anchor` = Utc0700 / Utc2300 / Utc1330 |
| `trend_frac` | 0.6, 0.7, 0.8 | `TrendFrac` (0.5–0.9, step 0.05) |
| `touch_band` | 0.0, −1.0 | `TouchBand` (−1.5–0.5, step 0.25) |
| `mode` | pullback, fade_2sd | `Mode` = Pullback / Fade2Sd |

The trail exit templates (`sl` 0.5/1/2, `trail` 0.5/1/1.5) map to `SlMult` and `TrailingStopMult`.
The fixed templates map to `TpMult`. `ExitStyle = Native` reproduces the card's own exit:
- Pullback: stop = d, target = max(the ±2σ band, 1 × d).
- Fade2Sd: target = the VWAP.

## Python source mapping
| Python | cBot |
|---|---|
| `grp = (t − anchor·3600) // 86400`; cumulative `tp·n`, `tp²·n`, `n` | `ProcessM5`: `_grp`, `_cv`, `_s1`, `_s2` (with `n` → `Bars.TickVolumes`) |
| `vw = Σtp·v / max(Σv,1)`, `sd = sqrt(max(E[tp²] − vw², 0))` | the same, in `ProcessM5` |
| `frac_up`, `slope = vw − vw[−12]` (nbar > 12) | `_nAbove / _nbar`, `_vwHist`, `SlopeBars` |
| `ok = 8 ≤ hour < 20 & ATR finite & slope finite & nbar ≥ 12 & sd > 0` | `ok` (`SignalStartHourUtc`, `SignalEndHourUtc`) |
| `_pullback` state machine (`tl`, `ts`, reset per group, untouched on non-ok bars) | `_tl`, `_ts`, reset on a new group |
| fade_2sd: open beyond the previous bar's ±2σ band, close back inside | `Mode = Fade2Sd` branch (`_prevVw`, `_prevSd`) |
| `sl = max(C − (vw − 1.5sd), 0.5·ATR)`, `unit = sl` | `d` with `StopSigmaMult`, `MinStopAtrMult` |
| `groupby(day).head(2)` | `_sigDay`, `_sigCount`, `MaxSignalsPerDay` |
| exit template `sl 2.0 × unit`, `trail 1.0 × unit`, `tp 0` | `SlMult`, `TrailingStopMult`, `TpMult = 0` |
| engine trail: `best` starts at the entry, `stop = best − trail`, ratchets, applies from the next second | `ManagePositions` (best = entry price, updated with bid for longs and ask for shorts on every tick; `ModifyPosition` with an absolute price) |
| `hold` to 20:55 | force-flat 20:55 |

## Known differences
- **Volume weighting:**
  - Python weights the VWAP and σ by the **Dukascopy tick count per 5-minute bar**.
  - cTrader uses **`Bars.TickVolumes`**, the broker's tick count, which has a different scale and
    differs from bar to bar.
  - The VWAP level, σ and so `frac_up`, slope and touches will differ somewhat. This is the largest
    source of divergence.
- **Prices:** Python uses the mid. cTrader bars use the bid.
- **Trailing granularity:**
  - Python updates the trailing stop every second from the 1-second extremes.
  - The cBot updates it on ticks, only when the new stop improves on the current one by at least
    `TrailStepUsd` ($0.05), to avoid flooding the server with modifications.
  - If the price has already crossed the computed stop, the bot closes at market.
- **Fills:** market fill on the first tick after the bar closes, at the real spread, versus Python's
  modelled spread + $0.03.
- **History at start:** the bot loads about 4 days of m5 history so the first session's VWAP and ATR
  are complete. Signals found during warm-up are counted but not traded.
- **Daily-loss guard:** it counts this bot's label only. Python has no such guard.

## Recommended cTrader backtest settings
- Symbol **XAUUSD**, chart period **m1**. The bot loads its own m5 series.
- Data: **Tick data from server (accurate)**. Tick data matters here because of the trailing stop.
- Dates: **01/01/2025 → today**. Also look at **Jun–Oct 2026** on its own (the blind OOS period).
- Commission: **$7 per lot round trip**. Spread: the broker's real spread.
- Risk mode PercentOfEquity, 0.5%. Load `cbots/presets/AvwapLondon_XAUUSD.cbotset`.
