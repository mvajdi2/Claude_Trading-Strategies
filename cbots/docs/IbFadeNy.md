# IbFadeNy (cTrader cBot)

Port of the frozen Python strategy `strategies/ib_fade_ny.py` (helpers in
`strategies/batcha_util.py`) with the settings in `strategy_cards/ib_fade_ny.frozen.json`.

- Source: `cbots/src/IbFadeNy.cs`
- Package: `cbots/algo/IbFadeNy.algo`
- Preset: `cbots/presets/IbFadeNy_XAUUSD.cbotset` (frozen values)

Research status: candidate #2 in `research/near_candidates.md`. OOS PF 1.88, WR 53%, DD 1.5%, n = 32.
It **does not** meet the targets. Use it for backtesting and demo only.

## Rules (frozen settings)
1. **Initial balance (IB):** the high and low of the 1-minute bars that open from **08:20 to 08:50
   New York time** (`IbStart = Ny0820`, `IbMinutes = 30`). W = IB width.
   - New York time is DST-aware and coded in the bot with the US rule: 2nd Sunday of March to 1st
     Sunday of November. 08:20 New York is 12:20 UTC in summer and 13:20 UTC in winter.
   - The IB needs at least 60% of the expected 1-minute bars (18 of 30).
2. **Wide filter:** W > 1.2 × the median W of the previous 20 valid IBs. At least 10 earlier IBs
   are required.
3. **Probe:** after the IB, on each closed 5-minute bar that closes by 18:00 UTC:
   - A bar high above the IB high marks an upper probe. A bar low below the IB low marks a lower
     probe.
   - The bot keeps track of the probe's extreme.
4. **Entry:** the first 5-minute close back inside the IB that does not go past the midpoint.
   - Upper probe: a close between the IB mid and the IB high opens a short.
   - Lower probe: a close between the IB low and the IB mid opens a long.
   - The short check runs first, as in Python. The probe and the close back can happen in the same
     bar. One signal per day.
   - The entry is a market order on the first tick after the signal bar closes.
5. **Unit d:** the distance from the signal close to (probe extreme ± 0.1 × ATR14 on 5m). The ATR is
   a simple mean of the true range, read on the bar **before** the signal bar (Python `A[j-1]`). No
   trade if d ≤ 0.
6. **Exit (frozen `{"sl": 2.0, "tp": 3.0}`, unit = d):**
   - Stop = 2.0 × d and target = 3.0 × d from the fill. The stop is at least $0.15.
   - Close at **20:00 UTC** (`StrategyFlatHourUtc`).
7. **Standard guards:** force-flat at 20:55, spread cap, daily-loss limit, max trades and positions,
   cooldown, weekday toggles.
8. **Optional exits (off by default):** partial TP1, break-even, trailing stop and max hold.

## Parameters
| Group | Parameter | Default (frozen) | Optimisation range | Meaning |
|---|---|---|---|---|
| Identity | `Label` | IBF_XAUUSD | – | Label |
| Identity | `TradeComment` | IbFadeNy | – | Trade Comment |
| Risk & Sizing | `RiskMode` | PercentOfEquity | PercentOfEquity / FixedLots / FixedCash | Risk Mode |
| Risk & Sizing | `RiskPercent` | 0.5 | 0.1 – 3.0 step 0.1 | Risk % of Equity |
| Risk & Sizing | `FixedLots` | 0.1 | 0.01 – 50.0 step 0.01 | Fixed Lots |
| Risk & Sizing | `FixedCashRisk` | 100.0 | 10.0 – 10000.0 step 10.0 | Fixed Cash Risk |
| Risk & Sizing | `MaxLots` | 10.0 | 0.01 – 100.0 step 0.01 | Max Lots |
| Account Protection | `MaxSpreadUsd` | 1.0 | 0.1 – 5.0 step 0.1 | Max Spread (USD) |
| Account Protection | `MaxDailyLossPercent` | 3.0 | 0.0 – 20.0 step 0.5 | Max Daily Loss % (0 = off) |
| Account Protection | `CloseOnDailyLoss` | false | true / false | Close All On Daily Loss |
| Account Protection | `MaxTradesPerDay` | 1 | 1 – 10 step 1 | Max Trades Per Day |
| Account Protection | `MaxOpenPositions` | 1 | 1 – 10 step 1 | Max Open Positions |
| Account Protection | `CooldownMinutes` | 0 | 0 – 1440 step 15 | Cooldown Minutes |
| Session & Calendar | `IbStart` | Ny0820 | Utc1330 / Ny0820 / Ny0930 | IB Start |
| Session & Calendar | `IbMinutes` | 30 | 15 – 60 step 15 | IB Minutes |
| Session & Calendar | `SignalEndHourUtc` | 18 | 14 – 20 step 1 | Signal End Hour UTC (5m bar close) |
| Session & Calendar | `StrategyFlatHourUtc` | 20 | 16 – 21 step 1 | Strategy Flat Hour UTC |
| Session & Calendar | `ForceFlatHourUtc` | 20 | 0 – 23 step 1 | Force Flat Hour UTC |
| Session & Calendar | `ForceFlatMinute` | 55 | 0 – 59 step 5 | Force Flat Minute |
| Session & Calendar | `TradeMonday` | true | true / false | Trade Monday |
| Session & Calendar | `TradeTuesday` | true | true / false | Trade Tuesday |
| Session & Calendar | `TradeWednesday` | true | true / false | Trade Wednesday |
| Session & Calendar | `TradeThursday` | true | true / false | Trade Thursday |
| Session & Calendar | `TradeFriday` | true | true / false | Trade Friday |
| Strategy Signal | `WideMult` | 1.2 | 1.0 – 1.6 step 0.05 | Wide Mult (W > x median) |
| Strategy Signal | `IbMedianLookback` | 20 | 10 – 40 step 5 | IB Median Lookback (IBs) |
| Strategy Signal | `IbMedianMinPeriods` | 10 | 5 – 20 step 5 | IB Median Min IBs |
| Strategy Signal | `MinIbBarFrac` | 0.6 | 0.3 – 1.0 step 0.1 | Min IB Bar Fraction |
| Strategy Signal | `ProbeAtrMult` | 0.1 | 0.0 – 0.5 step 0.05 | Probe ATR Mult |
| Strategy Signal | `AtrPeriod` | 14 | 7 – 28 step 1 | ATR Period (5m) |
| Exit Management | `ExitStyle` | UnitMultiples | UnitMultiples / Native | Exit Style |
| Exit Management | `SlMult` | 2.0 | 0.5 – 3.0 step 0.25 | Stop Mult (x d) |
| Exit Management | `TpMult` | 3.0 | 0.0 – 4.0 step 0.25 | Target Mult (x d, 0 = none) |
| Exit Management | `MinStopUsd` | 0.15 | 0.0 – 1.0 step 0.05 | Min Stop (USD) |
| Exit Management | `Tp1Mult` | 0.0 | 0.0 – 2.0 step 0.25 | TP1 Mult (x unit, 0 = off) |
| Exit Management | `Tp1ClosePercent` | 50.0 | 10.0 – 90.0 step 10.0 | TP1 Close % |
| Exit Management | `MoveToBreakEven` | false | true / false | Move To Break-Even |
| Exit Management | `BreakEvenTriggerMult` | 1.0 | 0.25 – 3.0 step 0.25 | BE Trigger (x unit, used when TP1 off) |
| Exit Management | `BreakEvenOffsetUsd` | 0.0 | 0.0 – 2.0 step 0.1 | BE Offset (USD) |
| Exit Management | `TrailingStopMult` | 0.0 | 0.0 – 3.0 step 0.25 | Trailing Stop Mult (x unit, 0 = off) |
| Exit Management | `TrailStepUsd` | 0.05 | 0.01 – 1.0 step 0.01 | Trail Min Step (USD) |
| Exit Management | `MaxHoldMinutes` | 0 | 0 – 1440 step 15 | Max Hold Minutes (0 = off) |
| Diagnostics | `VerboseLog` | false | true / false | Verbose Log |
| Diagnostics | `DrawLevels` | true | true / false | Draw Levels |

The optimisation ranges include the Python `PARAMS` grid:

| Python grid | Values | cBot parameter |
|---|---|---|
| `ib_start` | "13:30", "ny0820", "ny0930" | `IbStart` = Utc1330 / Ny0820 / Ny0930 |
| `ib_minutes` | 60, 30 | `IbMinutes` (15–60, step 15) |
| `wide_mult` | 1.3, 1.2, 1.5 | `WideMult` (1.0–1.6, step 0.05) |

The exit templates (`sl` 0.5–2.0, `tp` 0.5–3.0) map to `SlMult` and `TpMult`.
`ExitStyle = Native` reproduces the card's own exit: stop = d, target = the IB midpoint.

## Python source mapping
| Python | cBot |
|---|---|
| `_ib_start` / `U.local_sec(td, 8*60+20, "America/New_York")` | `IbStartUtc`, `IsUsDst`, `NthSunday` (coded US rule, no `TimeZoneInfo`) |
| `U.window_hl(b1, t0, t1, min_frac=0.6)` | `ProcessM1` accumulation; `FinalizeIb` checks the bar count |
| `W.rolling(20, min_periods=10).median().shift(1)`; `W > wide_mult*med` | `FinalizeIb` (median of the previous `IbMedianLookback` widths, then append W) |
| loop over 5m bars `j0 … jend` (start ≥ t1, close ≤ 18:00) | `ProcessM5`, on closed bars only (`Count − 2`) |
| `probe_hi/lo`, `ext_hi/lo`, `a = A[j-1]` | `_probeHi/_probeLo`, `_extHi/_extLo`, `atrPrev` |
| `sl = ext_hi + 0.1a − C` (short), `C − (ext_lo − 0.1a)` (long); `unit = sl` | `d`, `ProbeAtrMult` |
| `hold = 20:00 − sec` | close at `StrategyFlatHourUtc` |
| exit template `sl 2.0 × unit`, `tp 3.0 × unit`, `sl ≥ 0.15` | `SlMult`, `TpMult`, `MinStopUsd`; market order with SL and TP in pips relative to the fill |
| engine: one position at a time, flat 21:00 | `MaxOpenPositions = 1`, `MaxTradesPerDay = 1`, force-flat 20:55 |

## Known differences
- **Prices:** Python uses Dukascopy mid prices. cTrader bars use the broker's bid. IB edges, probes,
  closes and ATR can differ by about half the spread, so a few marginal days can flip.
- **Fills:**
  - Python fills one second after the bar close at the modelled spread + $0.03.
  - cTrader fills the market order at the first tick after the bar closes, at the real ask or bid.
  - Stops and targets are server-side SL and TP orders. Python assumes the stop comes first when
    both are touched within one second.
- **DST:** the bot codes the US rule (valid since 2007) for the IB date. Python uses pandas
  `America/New_York`. They agree for 2025–2026.
- **Median warm-up:** the bot loads about 45 days of m1 history at start to have 20 earlier IBs. If
  the broker returns less, the wide filter waits until 10 IBs exist, the same as Python's
  `min_periods`.
- **Daily-loss guard:** it counts this bot's label only. Python has no such guard. The 3% default
  never triggers at 0.5% risk with one trade per day.
- **Force-flat:** 20:55 UTC. It never binds, because the strategy is flat at 20:00.

## Recommended cTrader backtest settings
- Symbol **XAUUSD**, chart period **m1**. The bot loads its own m1 and m5 series.
- Data: **Tick data from server (accurate)**.
- Dates: **01/01/2025 → today**. Also look at **Jun–Oct 2026** on its own (the blind OOS period).
- Commission: **$7 per lot round trip**. Spread: the broker's real spread.
- Risk mode PercentOfEquity, 0.5%. Load `cbots/presets/IbFadeNy_XAUUSD.cbotset`.
