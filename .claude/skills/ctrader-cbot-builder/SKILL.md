---
name: ctrader-cbot-builder
description: Write production-grade cTrader Automate (cAlgo, C# .NET 6) cBots from this repo's frozen Python strategies, with the standard feature set (risk modes, sessions, spread/daily-loss guards, partial TP, break-even, trailing, optimisable parameters with Min/Max/Step) and a .cbotset preset of the frozen settings. Use when asked to write, port or convert a strategy into a cTrader cBot.
---

# cTrader cBot builder

Turn a frozen strategy (`strategies/<id>.py` + `strategy_cards/<id>.frozen.json`) into a cBot that
behaves the same way in cTrader and can be optimised there.

## Files you produce (per bot)
- `cbots/src/<BotName>.cs`: one file, one public class `<BotName> : Robot`, namespace `cAlgo.Robots`.
- `cbots/presets/<BotName>_XAUUSD.cbotset`: JSON preset with the **frozen** parameter values.
  Format: `{"Chart": {"Symbol": "XAUUSD", "Period": "m1"}, "Parameters": {"<ParamName>": value, ...}}`,
  where each key is the C# **property name**.
- `cbots/docs/<BotName>.md`: the rules in plain language, a parameter table (name, default = frozen
  value, optimisation range, meaning), the Python source it mirrors, and known differences
  between the Python backtest and cTrader.

## Compile check (mandatory, must pass with 0 errors and 0 warnings)
```bash
export PATH=/root/.dotnet:$PATH DOTNET_CLI_TELEMETRY_OPTOUT=1
cd /home/user/xau_hf/cbots/build && flock /tmp/cbot_build.lock dotnet build -nologo -v q -p:Bot=<BotName>
```
`CBotCheck.csproj` compiles `../src/<Bot>.cs` against the official `cTrader.Automate` NuGet API
(the same cAlgo.API that cTrader uses). A successful build also writes the importable cTrader
package `cbots/algo/<BotName>.algo`. Commit the `.algo` alongside the source. If .NET is missing, install it with
`curl -sSL https://dot.net/v1/dotnet-install.sh | bash -s -- --channel 8.0 --install-dir /root/.dotnet`.

## Standard features: every bot must include all of these

Group the parameters with `Group = "..."`, in this order:

1. **Identity:** `Label` (string; positions are filtered by label + symbol so several bots can
   share one account), `TradeComment`.
2. **Risk & sizing:**
   - `RiskMode` enum {`PercentOfEquity`, `FixedLots`, `FixedCash`}, with `RiskPercent`
     (default 0.5), `FixedLots`, `FixedCashRisk`, `MaxLots` cap.
   - Volume = risk cash / (stop distance in price × Symbol.LotSize) → convert to units →
     `Symbol.NormalizeVolumeInUnits(v, RoundingMode.Down)`, clamped to
     [`Symbol.VolumeInUnitsMin`, min(`Symbol.VolumeInUnitsMax`, MaxLots in units)].
   - Skip the trade if the volume would fall below the minimum.
3. **Account protection:**
   - `MaxSpreadUsd`: skip the entry if the spread at the moment of entry exceeds it.
   - `MaxDailyLossPercent`: block new entries for the rest of the UTC day once realised +
     unrealised loss since the day's start equity exceeds it. Optionally close all positions.
   - `MaxTradesPerDay`, `MaxOpenPositions` (counted with this bot's label only).
   - `CooldownMinutes` after a trade closes.
4. **Session & calendar:**
   - Trading window (start/end UTC hour, or the strategy's own window).
   - `ForceFlatHourUtc` / `ForceFlatMinute` (default 20:55): close everything and cancel
     pending orders.
   - `TradeMonday` … `TradeFriday` toggles.
   - New York or London local times must be **DST-aware**. Implement the US rule (2nd Sunday of
     March to 1st Sunday of November, 02:00 local) and the EU rule (last Sunday of March to last
     Sunday of October, 01:00 UTC) in code. Do not rely on `TimeZoneInfo` IDs, which differ between
     Windows and Linux.
5. **Strategy signal parameters:** every tunable value from the Python `PARAMS` and the frozen
   card, with the frozen value as `DefaultValue`.
6. **Exit management:**
   - Stop and target as multiples of the strategy's risk `unit` (as in the frozen `exit`), so the
     cBot matches the Python exactly.
   - Optional partial take-profit: `Tp1Mult` and `Tp1ClosePercent`. Use
     `ClosePosition(pos, units)` with a normalised volume, and skip it if either remainder would
     be below the minimum volume.
   - `MoveToBreakEven` with `BreakEvenOffsetUsd`.
   - `TrailingStopMult` (0 = off): your own trailing using `ModifyPosition`, so the
     distance can follow the unit.
   - `MaxHoldMinutes` time exit.
7. **Diagnostics:** `VerboseLog` (Print on signals, orders, errors) and `DrawLevels` (chart objects
   for ranges, levels and VWAP; must be a no-op in optimisation, so check `IsBacktesting`/`RunningMode`
   only if needed).

**Optimiser-ready parameters:** every numeric `[Parameter]` gets `DefaultValue`, `MinValue`,
`MaxValue` and `Step`, chosen around the Python grid. Enum and bool parameters are optimisable as
they are.

## Correctness rules (the cBot reviewer checks every one)
- `[Robot(AccessRights = AccessRights.None, TimeZone = TimeZones.UTC)]`. All times are UTC.
- **No look-ahead.**
  - Decisions on higher timeframes use `MarketData.GetBars(TimeFrame.MinuteN)` and only closed
    bars: in `OnBar` of the chart, or on a new bar of the series, read index `Count - 2` (the bar
    that just closed), never `Last(0)`.
  - Session ranges are complete before use.
  - Mirror the Python rule "decide at the close of the bar, enter on the next tick".
- Prices and distances are in **price units (USD)**. Convert to pips only where the API
  needs pips: `ExecuteMarketOrder(type, SymbolName, units, Label, slPips, tpPips, comment)` or
  `PlaceStopOrder(..., slPips, tpPips, expiry)`, with `pips = distance / Symbol.PipSize`. Round
  absolute stop and target prices to `Symbol.Digits`.
- Stop orders (OCO breakouts): place both with the same label and cancel the sibling in
  `PendingOrders.Filled` / `Positions.Opened` handlers. Expire them at the cutoff with the expiration
  argument or by cancelling explicitly. Respect the broker's minimum stop distance.
- Check `TradeResult.IsSuccessful` and log the error. Never assume a position exists after an
  order. Guard against `null` and NaN, and against division by zero (ATR = 0, sigma = 0).
- Indicators: use the built-in `Indicators.AverageTrueRange`, `ExponentialMovingAverage`,
  `DirectionalMovementSystem` (ADX) and so on where they match the Python definition. If the Python
  uses a simple average of true range, implement that by hand (cTrader's ATR uses its own MA type
  setting; pass `MovingAverageType.Simple` where needed). VWAP is built by hand, weighted by tick
  volume.
- **State:** day counters reset on the UTC date change. Keep per-position extra state (tp1 done,
  best price) in a `Dictionary<int,...>` keyed by `Position.Id`, and clean it up on
  `Positions.Closed`.
- Use `Positions.FindAll(Label, SymbolName)`. Unsubscribe events in `OnStop`.
- Must compile with **0 errors and 0 warnings** (obsolete API calls are warnings; replace them).

## Fidelity to the Python strategy
Port the rules in `strategies/<id>.py` (and helpers such as `strategies/batcha_util.py`) exactly:
same session times, filters, level definitions, stop and target units, frozen exit multiples,
one trade per day where the Python has it, and flat times. Wherever the cBot must differ (for
example tick-volume VWAP versus Dukascopy tick count, or broker daily-bar boundaries), document it in
`cbots/docs/<BotName>.md` under "Known differences".
