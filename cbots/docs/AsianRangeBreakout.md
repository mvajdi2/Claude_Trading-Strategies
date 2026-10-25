# AsianRangeBreakout (cTrader cBot)

Port of the frozen Python strategy `strategies/asian_range_breakout.py` (helpers in
`strategies/batcha_util.py`) with the settings in `strategy_cards/asian_range_breakout.frozen.json`.

- Source: `cbots/src/AsianRangeBreakout.cs`
- Package: `cbots/algo/AsianRangeBreakout.algo`
- Preset: `cbots/presets/AsianRangeBreakout_XAUUSD.cbotset` (frozen values)

Research status: candidate #1 in `research/near_candidates.md`. OOS PF 2.11, WR 69%, DD 0.5%, n = 16.
It **does not** meet the WR > 75% / PF > 3 targets. Use it for backtesting and demo only.

## Rules (frozen settings, all times UTC)
1. **Range:** the high and low of the 1-minute bars that open from 00:00 up to (not including) 06:00.
   W = high − low. The range needs at least 60% of the expected 1-minute bars (216 of 360).
2. **Range filter (`RangeFilter = Atr`):** 0.2 × ATR14 ≤ W ≤ 1.0 × ATR14.
   - ATR14 is a simple mean of the true range over 14 daily bars.
   - Daily bars run 23:00–21:00 UTC and need at least 300 one-minute bars.
   - The bot uses the last daily bar completed before today.
3. **Vol-state filter (`VolState = Top`):**
   - Realised variance (RV) for a day = the sum of squared 5-minute log returns over the bars that
     open 00:00–20:55 UTC.
   - Yesterday's RV must rank in the top third (percentile ≥ 2/3) of the last 250 days that have an
     RV value. At least 60 days of history are required.
4. **Orders at 06:00:**
   - The bot checks the mid price. If it is not strictly inside (low − 2.00, high + 2.00), it skips
     the day.
   - Otherwise it places a buy stop at high + 2.00 and a sell stop at low − 2.00, both expiring at
     12:00 UTC.
   - The orders are OCO: the first fill cancels the other.
   - The bot also cancels any leftover order at 12:00, in case the broker's expiry is late.
   - A side is skipped if its level is within the broker's minimum stop distance of the market.
5. **Exit (frozen `{"sl": 2.0, "tp": 1.0}`, unit = W):**
   - Stop = 2.0 × W and target = 1.0 × W, both measured from the actual entry fill. When a fill
     slips, the bot moves the SL and TP back to these distances from the fill price.
   - The stop is at least $0.15 (Python `apply_exit`) and at least the broker's minimum distance.
   - All positions close at 16:00 UTC (`StrategyFlatHourUtc`).
6. **Limits:** one trade per day. Size = 0.5% of equity at risk over the stop distance.
7. **Standard guards:** force-flat at 20:55 UTC, spread cap at order placement, daily-loss limit,
   max trades and positions, cooldown, weekday toggles.
8. **Optional exits (off by default):** partial TP1, break-even, trailing stop and max hold.

## Parameters
| Group | Parameter | Default (frozen) | Optimisation range | Meaning |
|---|---|---|---|---|
| Identity | `Label` | ARB_XAUUSD | – | Label |
| Identity | `TradeComment` | AsianRangeBreakout | – | Trade Comment |
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
| Session & Calendar | `RangeStartHourUtc` | 0 | 0 – 3 step 1 | Range Start Hour UTC |
| Session & Calendar | `RangeEndHourUtc` | 6 | 4 – 8 step 1 | Range End Hour UTC (orders placed) |
| Session & Calendar | `CutoffHourUtc` | 12 | 8 – 15 step 1 | Order Cutoff Hour UTC (expiry) |
| Session & Calendar | `StrategyFlatHourUtc` | 16 | 12 – 20 step 1 | Strategy Flat Hour UTC |
| Session & Calendar | `ForceFlatHourUtc` | 20 | 0 – 23 step 1 | Force Flat Hour UTC |
| Session & Calendar | `ForceFlatMinute` | 55 | 0 – 59 step 5 | Force Flat Minute |
| Session & Calendar | `TradeMonday` | true | true / false | Trade Monday |
| Session & Calendar | `TradeTuesday` | true | true / false | Trade Tuesday |
| Session & Calendar | `TradeWednesday` | true | true / false | Trade Wednesday |
| Session & Calendar | `TradeThursday` | true | true / false | Trade Thursday |
| Session & Calendar | `TradeFriday` | true | true / false | Trade Friday |
| Strategy Signal | `BufferUsd` | 2.0 | 0.25 – 3.0 step 0.25 | Breakout Buffer (USD) |
| Strategy Signal | `RangeFilter` | Atr | Usd / Atr / Pct / None | Range Filter |
| Strategy Signal | `RngUsdMin` | 3.0 | 1.0 – 10.0 step 0.5 | Usd Filter: Min W (USD) |
| Strategy Signal | `RngUsdMax` | 20.0 | 10.0 – 40.0 step 1.0 | Usd Filter: Max W (USD) |
| Strategy Signal | `RngAtrMin` | 0.2 | 0.0 – 0.5 step 0.05 | Atr Filter: Min W / ATR |
| Strategy Signal | `RngAtrMax` | 1.0 | 0.5 – 2.0 step 0.1 | Atr Filter: Max W / ATR |
| Strategy Signal | `RngPctMin` | 0.3 | 0.1 – 1.0 step 0.1 | Pct Filter: Min W % |
| Strategy Signal | `RngPctMax` | 1.6 | 0.8 – 3.0 step 0.1 | Pct Filter: Max W % |
| Strategy Signal | `AtrPeriodDays` | 14 | 5 – 30 step 1 | Daily ATR Period (days) |
| Strategy Signal | `MinDailyBars` | 300 | 100 – 1000 step 50 | Min 1m Bars Per Daily Bar |
| Strategy Signal | `MinRangeBarFrac` | 0.6 | 0.3 – 1.0 step 0.1 | Min Range Bar Fraction |
| Strategy Signal | `VolState` | Top | All / MidTop / Top | Vol State Filter |
| Strategy Signal | `VolLookbackDays` | 250 | 100 – 300 step 50 | Vol Lookback (days) |
| Strategy Signal | `VolMinHistoryDays` | 60 | 20 – 120 step 10 | Vol Min History (days) |
| Strategy Signal | `HistoryDays` | 400 | 30 – 800 step 10 | History To Load (calendar days) |
| Exit Management | `ExitStyle` | UnitMultiples | UnitMultiples / Native | Exit Style |
| Exit Management | `SlMult` | 2.0 | 0.5 – 3.0 step 0.25 | Stop Mult (x W) |
| Exit Management | `TpMult` | 1.0 | 0.0 – 3.0 step 0.25 | Target Mult (x W, 0 = none) |
| Exit Management | `TgtX` | 1.5 | 0.5 – 3.0 step 0.25 | Native Target (x W) |
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
| `range_end` | 5, 6, 7 | `RangeEndHourUtc` |
| `buffer_usd` | 0.5, 2.0 | `BufferUsd` |
| `cutoff` | 9, 12 | `CutoffHourUtc` |
| `vol_state` | all, midtop, top | `VolState` |
| `rng_filter` | usd, atr | `RangeFilter` (also pct and none) |
| `range_start` | 0 | `RangeStartHourUtc` |
| `flat_h` | 16 | `StrategyFlatHourUtc` |
| `tgt_x` | 1.5 | `TgtX` |

The exit templates (`sl` 0.5–2.0, `tp` 0.5–3.0) map to `SlMult` and `TpMult`.
`ExitStyle = Native` reproduces the card's own exit: stop = buy level − sell level, target = `TgtX` × W.

## Python source mapping
| Python | cBot |
|---|---|
| `U.trading_days`, `U.window_hl(b, at(td,0), at(td,6), min_frac=0.6)` | `ProcessM1` range accumulation; `TryDecide` checks the bar count against `MinRangeBarFrac` |
| `U.daily(ctx)` (1m bars with hour < 21 or ≥ 23, trading day = (t + 1 h) date, nb ≥ 300), `atr14 = TR.rolling(14).mean()` | `ProcessM1` daily aggregation, `FlushDaily`, `DailyAtrBefore` |
| `U.prev_rows(...)` (last row strictly before today) | `DailyAtrBefore(today)` and `VolPctBefore(today)` use only completed days before today |
| `U.realized_var` (sum of squared 5m log returns, bars opening before 21:00, by UTC date) | `ProcessM5`, `FlushRv` |
| `U.vol_state_pct` (`rolling(250, min_periods=60).rank(pct=True)`) | `VolPctBefore` (average rank for ties, like pandas) |
| `rng_filter` usd / atr / pct / else | `RangeFilter` Usd / Atr / Pct / None |
| `mid_at(start − 1)` strictly inside the levels | mid price at the first tick of the 06:00 bar, strictly inside |
| `U.first_touch(...)` OCO between range end and cutoff | `PlaceStopOrder` × 2 with expiry at the cutoff; `OnPendingFilled` and `OnPositionOpened` cancel the sibling |
| exit template `sl = 2.0 × unit`, `tp = 1.0 × unit`, `unit = rng`; `sl ≥ 0.15` | `SlMult`, `TpMult`, `MinStopUsd`; SL and TP re-based on the fill price |
| `hold = flat_h − sec` | close at `StrategyFlatHourUtc` |
| engine: one position at a time, flat 21:00 | `MaxOpenPositions = 1`, `MaxTradesPerDay = 1`, force-flat 20:55 |

## Known differences
- **Fill model:**
  - Python detects the first 1-second bar that touches a level and fills at the next second's mid
    + half-spread + $0.03.
  - cTrader fills the stop order at the level, or worse when the price gaps through it. The stop
    order triggers on the bid or ask side, while Python's 1-second highs and lows are mid prices.
  - Python skips a day when both levels are touched in the same second. cTrader cannot detect this.
- **Prices:** Python bars are built from the Dukascopy mid. cTrader bars use the broker's bid. Range
  highs and lows, ATR and RV therefore differ slightly, by about half the spread.
- **Decision time:** Python uses the mid at 05:59:59. The cBot uses the mid at the first tick of the
  first 1-minute bar at or after 06:00.
- **Vol-state history (window length):**
  - Python's data starts on 2025-01-01, so the top-tercile filter only became active after 60 days
    of RV, around late March 2025. Its percentile window then grows from 60 to 250 days through
    2025, and is a full 250 days only from about late 2025 onward.
  - The cBot tries to load `HistoryDays` (400) of 5-minute history at start with
    `LoadMoreHistory`. If that works, it uses a full 250-day window from the first day. The
    top-tercile days, and therefore the traded days, then differ from Python **throughout 2025**,
    not only in Q1. From about 2026 on, both use 250-day windows and should agree.
  - The backtester may not serve history before the start date: `LoadMoreHistory` can return
    nothing. In that case the window builds up inside the test, as in Python, and the bot takes no
    vol-filtered trades until 60 RV days exist.
  - **How to tell which case happened:** the bot always prints a start-up line:
    `started: earliest m1 bar …, earliest m5 bar …; daily rows N (ATR needs 15), RV days M (vol
    state needs 60)`.
    - If the earliest m5 bar is about the start date (RV days ≈ 0), nothing was loaded. Start the
      backtest at least **3 months before** the period you want to compare. To mimic Python
      exactly, start on 01/01/2025.
    - If the earliest bar is about a year before the start, the full window was loaded.
- **Daily bars:** the bot builds the 23:00–21:00 UTC daily bars from 1-minute bars, as Python does,
  instead of using the broker's D1 bars. Broker data gaps change the bar count and so the
  ≥ 300-bar rule.
- **Bars with few ticks:** Python drops 5-minute bars with fewer than 5 ticks. cTrader has no such
  filter, which affects RV only marginally.
- **Spread guard:** the spread is checked when the orders are placed at 06:00, not at the fill.
- **Daily-loss guard:** it counts this bot's label only (realised P&L of today from `History`, so
  partial closes are included, refreshed on each close and every minute, plus open P&L): realised P&L from history since 00:00 UTC
  plus open P&L. Python has no daily-loss guard. The 3% default never triggers at 0.5% risk with
  one trade per day.
- **Force-flat:** 20:55 UTC instead of the Python engine's 21:00. Positions are already flat at
  16:00, so nothing changes.
- **OCO double fill:**
  - Live, cancelling the sibling stop order is a server round-trip. In a fast spike the second
    stop can fill before the cancel arrives.
  - The bot neutralises this in `OnPositionOpened`. If another position with this label and
    symbol is already open, or today's trade count has reached `MaxTradesPerDay`, the new position
    is closed at market at once and never registered. The bot prints
    `OCO double fill: closed second position`, and any remaining pending orders are cancelled.
  - The cost of such an event is one extra round trip (spread + commission + slippage on the
    second leg). Python instead skips a day where both levels are touched within one second.
  - **Use a hedging account.** On a netting account, the second fill would offset or reverse the
    first position before the bot can react, and the "close the second leg" logic cannot restore
    the original trade.
- **Minimum stop distance:**
  - At 06:00 the bot places a side only if its level is further from the market than the broker's
    `MinStopLossDistance`. This means more than that distance above the ask for the buy stop, or
    below the bid for the sell stop.
  - Python places both orders whenever the mid is strictly inside the levels.
  - The levels are at least the $2 buffer outside the range, and XAUUSD minimum distances are
    usually 0, so this rarely matters. When it does, the log prints `side skipped`.
  - SL and TP distances are also widened to at least the broker's minimum stop and target
    distances.

## Recommended cTrader backtest settings
- Symbol **XAUUSD**, chart period **m1**. The bot loads its own m1 and m5 series.
- Data: **Tick data from server (accurate)**.
- Dates: **01/01/2025 → today**. Check the `started:` log line for loaded history. See
  "Vol-state history". Also look at **Jun–Oct 2026** on its own (the blind OOS period).
- Commission: **$7 per lot round trip** ($3.50 per side). Spread: the broker's real spread.
- Account type: **hedging** (see "OCO double fill"). Starting balance: for example 10,000 USD. Risk mode PercentOfEquity, 0.5%.
- Load `cbots/presets/AsianRangeBreakout_XAUUSD.cbotset`.
