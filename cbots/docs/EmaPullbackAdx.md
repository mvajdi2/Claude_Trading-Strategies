# EmaPullbackAdx (cTrader cBot)

- **Source:** `cbots/src/EmaPullbackAdx.cs`
- **Package:** `cbots/algo/EmaPullbackAdx.algo`
- **Preset (frozen values):** `cbots/presets/EmaPullbackAdx_XAUUSD.cbotset`
- **Mirrors:** `strategies/ema_pullback_adx.py`, with indicators from `bt1s.py` (`ema`, `atr`), the exit template from `evaluate.py::apply_exit`, and the frozen card `strategy_cards/ema_pullback_adx.frozen.json` (code_sha `5be4739bce5e9c13`).

> Status: the card's verdict is **FAIL**. IS PF 1.57, VAL PF 3.35, then OOS PF 0.99 on 40 trades. `research/near_candidates.md` lists it as "excluded because it collapsed out of sample". This cBot exists so the result can be checked in cTrader. It is not a recommendation to trade it.

## Rules (all times UTC)

**Decision timeframe:** closed 15-minute bars. The bot decides at the bar close and enters at market on the first tick of the next bar. Python fills 1 second after the bar's last second.

**Long setup.** Every condition must hold on the bar that just closed:
1. The bar opened between 07:00 and 18:45 (`SignalStartHour` ≤ open hour < `SignalEndHour`).
2. EMA20(m15) > EMA50(m15).
3. ADX14(m15) > `AdxMin` (frozen value 30).
4. The last **fully closed** H1 bar at the m15 close time closed above EMA50(H1). This matches `merge_asof` on close seconds.
5. Bar low ≤ EMA20 and bar close > EMA20 (a pullback that closes back above).
6. Dead-market filter (frozen: on): ATR14(m15) ≥ the median of the previous 1,840 ATR values. The median needs at least 500 valid values and excludes the current bar.

**Short setup:** the mirror image (EMA20 < EMA50, H1 close < EMA50(H1), high ≥ EMA20, close < EMA20).

**Unit (R):**
- Long: `unit = max(close − (lowest low of the last 5 bars − 0.5·ATR), 1.5·ATR)`.
- Short: `unit = max((highest high of the last 5 bars + 0.5·ATR) − close, 1.5·ATR)`.
- The 5-bar window includes the signal bar.

**Exit (frozen card `exit`):**
- Stop = 2.0 × unit, with a floor of $0.15 (`apply_exit`).
- At +0.25 × unit, close 50% and move the stop to break-even (entry + $0).
- Final target = 3.0 × unit.
- No trailing stop: `apply_exit` sets `trail = 0` when a template is applied.
- Time exit at 20:45 UTC. The engine's own 21:00 flat time never binds because of this.

**Frequency and position limits:**
- At most 2 **signals** per UTC day. Python's `groupby(day).head(2)` counts signals, including signals skipped because a position was already open.
- One position at a time (`bt1s.run` skips any signal that arrives while the previous trade is still open).

**Indicators:** all are hand-rolled to match the pandas code exactly.
- EMA: `ewm(span=n, adjust=False)`, seeded with the first close.
- ATR: **simple** rolling mean of true range (`bt1s.atr`). The first TR is NaN, so the first ATR value appears at bar 14.
- ADX: Wilder smoothing as `ewm(alpha=1/n, adjust=False)` applied to TR, +DM, −DM and DX. Each series is seeded at its first valid value, and DX uses the `max(pdi+mdi, 1e-9)` guard.
- cTrader's `DirectionalMovementSystem` and `AverageTrueRange` are **not** used, because their smoothing and seeding differ.
- The hand-rolled EMA, ATR, ADX and median were checked against the pandas functions on 3,000 synthetic bars. Maximum absolute difference: 2e-12.

## Parameters
Defaults equal the frozen values. Every numeric parameter has Min/Max/Step for the cTrader optimiser.

| Group | Parameter | Default | Optimisation range (min–max / step) | Meaning |
|---|---|---|---|---|
| Identity | `Label` | EmaPullbackAdx | – | Positions are filtered by label + symbol |
| Identity | `TradeComment` | EmaPullbackAdx | – | Order comment |
| Risk | `RiskMode` | PercentOfEquity | enum: PercentOfEquity / FixedLots / FixedCash | Sizing mode |
| Risk | `RiskPercent` | 0.5 | 0.1–3.0 / 0.1 | % of equity lost if the stop is hit |
| Risk | `FixedLots` | 0.10 | 0.01–10 / 0.01 | Lots in FixedLots mode |
| Risk | `FixedCashRisk` | 500 | 10–10000 / 10 | Account-currency risk in FixedCash mode |
| Risk | `MaxLots` | 5.0 | 0.01–50 / 0.01 | Volume cap |
| Protection | `MaxSpreadUsd` | 0.60 | 0.05–3.0 / 0.05 | Skip the entry if spread > this |
| Protection | `MaxDailyLossPercent` | 3.0 | 0–10 / 0.5 | Block entries for the day once the loss exceeds this (0 = off) |
| Protection | `CloseAllOnDailyLoss` | false | bool | Also close open positions when the limit is hit |
| Protection | `MaxTradesPerDay` | 2 | 0–10 / 1 | Executed entries per UTC day (0 = off) |
| Protection | `MaxOpenPositions` | 1 | 1–5 / 1 | 1 = Python's one-position-at-a-time rule |
| Protection | `CooldownMinutes` | 0 | 0–240 / 15 | Wait after a close (Python: none) |
| Session | `SignalStartHour` | 7 | 0–23 / 1 | First m15 bar-open hour that can signal |
| Session | `SignalEndHour` | 19 | 1–24 / 1 | Bar-open hour limit (exclusive) |
| Session | `TimeExitHour` / `TimeExitMinute` | 20 / 45 | 0–23 / 1, 0–59 / 5 | Strategy time exit |
| Session | `ForceFlatHourUtc` / `ForceFlatMinute` | 20 / 55 | 0–23 / 1, 0–59 / 5 | Standard force-flat time; also cancels pending orders |
| Session | `TradeMonday` … `TradeFriday` | true | bool | Weekday toggles |
| Signal | `EmaFastPeriod` | 20 | 10–50 / 5 | m15 EMA (pullback level) |
| Signal | `EmaSlowPeriod` | 50 | 30–100 / 10 | m15 trend EMA |
| Signal | `HtfEmaPeriod` | 50 | 20–100 / 10 | H1 trend EMA |
| Signal | `AdxPeriod` | 14 | 7–28 / 1 | ADX length |
| Signal | `AdxMin` | **30** | 15–40 / 5 (Python grid 20, 25, 30) | `adx_min` |
| Signal | `AtrPeriod` | 14 | 7–28 / 1 | ATR length (SMA of TR) |
| Signal | `StopAtrMult` | **1.5** | 0.5–3.0 / 0.25 (grid 1.0, 1.5, 2.0) | `stop_atr` |
| Signal | `SwingBars` | 5 | 2–15 / 1 | Swing window |
| Signal | `SwingAtrBuffer` | 0.5 | 0–1.5 / 0.25 | ATR buffer beyond the swing |
| Signal | `UseDeadFilter` | **true** | bool (grid true / false) | `dead_filter` |
| Signal | `DeadFilterLookbackBars` | 1840 | 460–3680 / 460 | Median window (20 × 92 bars) |
| Signal | `DeadFilterMinBars` | 500 | 100–1500 / 100 | Minimum valid ATR values for the median |
| Signal | `MaxSignalsPerDay` | 2 | 0–6 / 1 | Python `head(2)` (0 = off) |
| Exit | `SlMult` | **2.0** | 0.5–3.0 / 0.5 (templates 0.5–3.0) | Stop = SlMult × unit |
| Exit | `MinStopUsd` | 0.15 | 0.05–1.0 / 0.05 | Stop floor (`apply_exit`) |
| Exit | `TpMult` | **3.0** | 0–4 / 0.5 (templates 0.5–3.0) | Final target (0 = none) |
| Exit | `Tp1Mult` | **0.25** | 0–1.0 / 0.25 (templates 0.25, 0.5) | Partial target (0 = off) |
| Exit | `Tp1ClosePercent` | **50** | 10–90 / 10 (templates 50, 70) | % closed at TP1 |
| Exit | `MoveToBreakEven` | **true** | bool | Stop to entry + offset after TP1 (`be = 1`) |
| Exit | `BreakEvenOffsetUsd` | 0.0 | 0–1.0 / 0.05 | `be_off` |
| Exit | `TrailingStopMult` | 0.0 | 0–2.0 / 0.5 (templates 0.5, 1.0, 1.5) | Own trailing stop as a multiple of unit. Active from entry, or after TP1 if TP1 is on |
| Exit | `MaxHoldMinutes` | 0 | 0–600 / 30 | Extra time cap (0 = off; Python has none) |
| Diagnostics | `VerboseLog` | false | bool | Log signals, skips and orders |
| Diagnostics | `DrawLevels` | true | bool | Entry, SL, TP1 and TP lines; no-op in optimisation |

**Sizing:**
- Risk cash = equity × RiskPercent (or FixedCashRisk).
- units = cash / (stop distance × value of a $1 move per unit). The value per unit is `Symbol.PipValue / Symbol.PipSize`, which is 1 for a USD account, so lots = cash / (stop × `Symbol.LotSize`).
- The result is capped at min(`VolumeInUnitsMax`, MaxLots × LotSize) and normalised down.
- The trade is **skipped** if the volume falls below `VolumeInUnitsMin`.

## Source mapping

| Python | cBot |
|---|---|
| `ctx.bars(900)` mid OHLC | `MarketData.GetBars(TimeFrame.Minute15)` (bid OHLC), closed bar `Count-2` |
| `bt1s.ema(c, 20/50)` | `_e20/_e50` (`ProcessM15`) |
| `bt1s.atr(b, 14)` (SMA of TR) | `_atr` (`ProcessM15`) |
| `adx(b)` (`ewm alpha=1/14`) | `_trS/_pdmS/_mdmS/_adx` (`ProcessM15`) |
| `h1` + `merge_asof(close_sec)` + `sign(c − ema50)` | `EvaluateSignal`: last H1 bar with `open + 1h ≤ m15 close`, `H1EmaAt(j)` |
| `rolling(20*92, min_periods=500).median().shift(1)` | `AtrMedianBefore(i)` |
| `hour ∈ [7,19)` on bar start | `SignalStartHour` / `SignalEndHour` on `OpenTimes[i].Hour` |
| `sl = max(structural, stop_atr·a)` → `unit` | `unit` in `EvaluateSignal` |
| `apply_exit(sl=2, tp1=.25, f1=.5, tp=3, be=1)`, `sl ≥ 0.15` | `SlMult`, `Tp1Mult`, `Tp1ClosePercent`, `TpMult`, `MoveToBreakEven`, `MinStopUsd` |
| `hold` → 20:45 | `TimeExitHour/Minute` |
| `groupby(day).head(2)` | `MaxSignalsPerDay` (counts signals, not fills) |
| `bt1s.run` one position at a time | `MaxOpenPositions = 1` |

## Known differences between the Python backtest and cTrader
1. **Price source.** Python builds bars from Dukascopy **mid** prices. cTrader bars are broker **bid** prices.
   - EMA, ADX and ATR differ slightly, and the `low ≤ EMA20` touch can differ by about half a spread.
   - Bars with fewer than 15 ticks are dropped in Python. cTrader keeps every bar.
2. **Fills.**
   - Python fills TP1 at the limit price and the stop at the stop price minus $0.03 slippage, with a modelled spread (0.30× Dukascopy, minimum $0.10).
   - In cTrader, TP1 is a market close when bid (or ask) reaches the level, so it can be slightly better or worse than the limit. Stop and target are broker orders filled at real spread and slippage.
   - When stop and target fall in the same second, Python assumes the stop was hit first. cTrader uses tick order.
3. **Dead-filter history.**
   - Python's median uses a 1,840-bar window over the whole dataset.
   - cTrader needs ≥ 500 m15 bars (about 5.5 trading days) of history before the dead filter can pass. The bot calls `LoadMoreHistory()` on start. If the backtest provides less history, the first days have no trades.
   - EMAs and ADX are seeded from whatever history is loaded. Differences fade after a few hundred bars.
4. **Break-even timing.** Python moves the stop at the second TP1 is touched. The cBot moves it on the same tick through `ModifyPosition`. If the BE level is already crossed, the cBot closes at market.
5. **Broker daily boundary.** All logic uses UTC calendar days, as Python does, so this has no effect.
6. **Standard extras not in the Python** (defaults are neutral or match Python):
   - spread filter ($0.60);
   - daily loss guard (3%);
   - `MaxTradesPerDay` = 2, which is implied by the 2 signals per day;
   - force flat at 20:55, after the 20:45 time exit;
   - weekday toggles, cooldown and max hold (off).
   - Saturday and Sunday are never traded. The signal window is 07–19 UTC, so this changes nothing.
7. **DST.** The strategy uses only UTC times, so no New York or London conversion is needed.
8. **Restart.** If the bot restarts with a position open, it recovers `unit` from the stop distance. A position whose stop is already at break-even keeps its broker SL/TP, and the time exit still applies to it.

## Recommended cTrader backtest settings
- Symbol **XAUUSD**, chart period **m1**. The bot reads m15 and H1 internally.
- Data: **Tick data from server**.
- Dates: **01/01/2025 → today**. Also look at Jun–Oct 2026 on its own: this is the OOS period, where Python gave PF 0.99.
- Commission **$7 per lot round trip** ($3.50 per side). Spread from the broker.
- Starting balance 100,000. Load `EmaPullbackAdx_XAUUSD.cbotset` (RiskPercent 0.5).
- Python reference results at 0.5% risk:

  | Period | PF | WR | DD | Trades |
  |---|---|---|---|---|
  | IS 2025 | 1.57 | 88% | 0.6% | 91 |
  | VAL Jan–May 2026 | 3.35 | 91% | 0.5% | 45 |
  | OOS Jun–Oct 2026 | 0.99 | 80% | 1.3% | 40 |
