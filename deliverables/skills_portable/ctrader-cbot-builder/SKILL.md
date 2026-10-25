---
name: ctrader-cbot-builder
description: Write production-grade cTrader Automate (cAlgo, C# .NET 6) cBots from a strategy specification or source (Python, Pine, MQL, plain-language rules), with a full standard feature set (risk modes, sessions, spread/daily-loss guards, partial TP, break-even, trailing, optimiser-ready parameters with Min/Max/Step), a .cbotset preset and documentation, compiled against the official cTrader.Automate API. Use when asked to write, port, convert or build a cTrader cBot.
---

# cTrader cBot builder

Turn a trading strategy into a cBot that trades exactly as specified in cTrader, is safe on a
live account, and can be optimised in cTrader's optimiser.

## Inputs
Whatever the user provides: plain-language rules, a Python, Pine or MQL source, a backtest
module, or a parameter card. If entry, exit, session or sizing rules are ambiguous, ask once,
then write down every assumption in the bot's doc under "Assumptions".

## Files you produce (per bot), in a working folder chosen with the user
- `src/<BotName>.cs`: one file, one public class `<BotName> : Robot`, namespace `cAlgo.Robots`.
- `presets/<BotName>_<SYMBOL>.cbotset`: JSON preset with the chosen default values.
  Format: `{"Chart": {"Symbol": "XAUUSD", "Period": "m1"}, "Parameters": {"<PropertyName>": value, ...}}`.
  Each key must be the C# **property name**.
- `docs/<BotName>.md`: the rules in plain language, a parameter table (name, default,
  optimisation range, meaning), the source it mirrors, assumptions, known differences from the
  source backtest, and recommended cTrader backtest settings.
- `algo/<BotName>.algo`: the importable cTrader package, produced by the compile step.

## Compile check (mandatory: 0 errors, 0 warnings)
Copy `templates/CBotCheck.csproj` from this skill into `<workdir>/build/`, with the bots in
`<workdir>/src/`. Then run:
```bash
cd <workdir>/build
dotnet build -nologo -v q -p:Bot=<BotName> -warnaserror
```
- The project compiles `src/<BotName>.cs` against the official **`cTrader.Automate`** NuGet
  package. That's the same cAlgo.API that cTrader uses, so API mistakes show up as compile errors.
- A successful build writes `algo/<BotName>.algo`, ready to import into cTrader.
- It sets `UseSharedCompilation=false`, so the compiler server can't hold file locks between
  builds.
- If `dotnet` is missing, install the .NET 8 SDK. On Windows or macOS use the installer from
  https://dotnet.microsoft.com/download. On Linux or a sandbox run
  `curl -sSL https://dot.net/v1/dotnet-install.sh | bash -s -- --channel 8.0` and add
  `~/.dotnet` to PATH. The project targets net6.0, which the 8.0 SDK can build.
- If you can't install .NET (no shell or no network), say so plainly. Mark the bot "not
  compile-verified" and ask the user to build it in cTrader (Automate → Build) and send back any
  errors.
- Optionally pin a newer `cTrader.Automate` version in the csproj if the user's cTrader is newer.

## Standard features: every bot must include all of these
Group the parameters with `Group = "..."`, in this order:

1. **Identity:** `Label` and `TradeComment`. Filter positions and orders by label **and** symbol,
   so several bots can share one account.
2. **Risk & sizing:**
   - `RiskMode` enum {`PercentOfEquity`, `FixedLots`, `FixedCash`}, with `RiskPercent`
     (default 0.5), `FixedLots`, `FixedCashRisk` and a `MaxLots` cap.
   - Lots = risk cash / (stop distance in price × `Symbol.LotSize`). Convert to units, then
     `Symbol.NormalizeVolumeInUnits(v, RoundingMode.Down)`, clamped to the min/max volume and
     MaxLots.
   - **Skip** the trade if the volume is below the minimum. Never round up into extra risk.
   - Read the lot size from `Symbol.LotSize`. Never hard-code it.
3. **Account protection:**
   - `MaxSpreadUsd` (or pips): checked at the moment of entry.
   - `MaxDailyLossPercent`: realised P&L today from `History` for this label and symbol (this
     counts **partial closes**, which don't raise `Positions.Closed`) plus open P&L, against
     the UTC day's start equity. Block new entries for the rest of the day; optionally close all.
     Refresh on close and partial-close events and at most once a minute in `OnTick`.
   - `MaxTradesPerDay`, `MaxOpenPositions` (this label only), `CooldownMinutes`.
4. **Session & calendar:**
   - The strategy's trading window.
   - `ForceFlatHourUtc` / `ForceFlatMinute` (default 20:55 UTC): close positions and cancel
     pending orders.
   - `TradeMonday` … `TradeFriday` toggles.
   - Local exchange times (New York, London) must be **DST-aware**, with the rules written in code:
     - US: 2nd Sunday of March to 1st Sunday of November, 02:00 local.
     - EU: last Sunday of March to last Sunday of October, 01:00 UTC.
   - Never use `TimeZoneInfo` IDs, which differ between Windows and Linux.
5. **Strategy signal parameters:** every tunable value of the strategy, with the chosen default.
   Express mode switches as enums.
6. **Exit management:**
   - Stop and target as multiples of the strategy's own risk unit (ATR, range width, structural
     stop distance), if that's how the strategy defines them.
   - Optional partial TP (`Tp1Mult`, `Tp1ClosePercent`) via `ClosePosition(pos, units)`. Skip it
     if either part would fall below the minimum volume.
   - `MoveToBreakEven` + `BreakEvenOffsetUsd`.
   - `TrailingStopMult` (0 = off), done by hand with `ModifyPosition`, tighten-only.
   - `MaxHoldMinutes`.
7. **Diagnostics:**
   - `VerboseLog` (Print on signals, orders and errors).
   - `DrawLevels`: no-op in optimisation. Remove the previous session's chart objects so they
     don't pile up.
   - An unconditional startup `Print` with the earliest loaded bar time for each series used, so
     the user can check warm-up.

**Optimiser-ready:** every numeric `[Parameter]` has `DefaultValue`, `MinValue`, `MaxValue` and
`Step`, with ranges around sensible or source-grid values. Enums and bools are optimisable as they
are.

## Correctness rules (the ctrader-cbot-review skill checks every one)
- `[Robot(AccessRights = AccessRights.None, TimeZone = TimeZones.UTC)]`. Use `Server.Time`, never
  `DateTime.Now`. No randomness.
- **No look-ahead:**
  - Read higher timeframes with `MarketData.GetBars(TimeFrame.X)`. On a new bar, decide from
    index `Count - 2` (the bar that just closed), never the forming bar.
  - Session ranges and daily levels must be complete before use.
  - Decide at bar close and enter on the next tick.
- **Units:**
  - `ExecuteMarketOrder` / `PlaceStopOrder` / `PlaceLimitOrder` take stop-loss and take-profit
    in **pips**: `pips = priceDistance / Symbol.PipSize`.
  - `ModifyPosition` takes **absolute prices**, rounded to `Symbol.Digits`.
  - Respect the broker's minimum stop distance.
- **Orders:**
  - Check `TradeResult.IsSuccessful` and log the error.
  - Never assume a position exists after an order.
  - Stop orders get an expiry or are cancelled explicitly.
- **OCO breakouts:**
  - Cancel the sibling on fill.
  - If both fill in one burst, close the second position immediately and don't register it.
  - Recommend a hedging account in the doc.
- **Robustness:**
  - Guard nulls, NaN, empty collections, indicator warm-up and division by zero (ATR, sigma,
    range, PipSize).
  - Close guard: at most one close attempt per position per minute, so a rejected close doesn't
    repeat every tick.
- **State:**
  - Reset day counters on the UTC date change.
  - Keep per-position state in a `Dictionary<int,...>` keyed by `Position.Id`, removed on close.
  - Write the risk unit into the order comment (e.g. `TradeComment|u=3.420`, at most 100
    characters, read back culture-invariant, finite > 0 only) so a restarted bot can recover its
    exits exactly.
- **Events:** subscribe in `OnStart`, unsubscribe in `OnStop`. No heavy work per tick.
- **Indicators:**
  - Match the source's formulas exactly. A simple-mean ATR differs from Wilder's.
  - Pandas `ewm(span, adjust=False)` is a standard EMA, and Wilder smoothing is `alpha = 1/n`.
  - Hand-write an indicator when the built-in one differs.
  - VWAP is hand-built from `Bars.TickVolumes`, and the doc must say tick data from the server is
    required.
- Obsolete API calls are warnings and must be replaced, so the bot compiles cleanly with
  `-warnaserror`.

## Fidelity
Port the rules exactly: session times, filters, level definitions, stop and target units, partial,
break-even and trailing as specified, trades per day, cutoff and flat times. List every
unavoidable difference in the doc under "Known differences": broker bid bars versus mid bars, real
fills versus a modelled spread, tick volume versus tick count, history warm-up.
