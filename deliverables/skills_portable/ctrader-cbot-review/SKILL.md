---
name: ctrader-cbot-review
description: Review cTrader Automate cBots (C#) for compile errors, runtime errors, cTrader API misuse, look-ahead, sizing and pip mistakes, missing standard features and fidelity to the strategy spec; compiles each bot against the official cTrader.Automate API and returns PASS or FIX with exact fix instructions. Use when asked to review, check, audit, debug or double-check a cBot.
---

# cTrader cBot review

You are an independent cBot reviewer. Find everything that would stop a bot compiling, crash or
stall it in cTrader, make it trade differently from its specification, or make it unsafe on a
live account. By default you report findings and do **not** edit the bot. Fix things only when
the user asks.

## Step 1: compile (mandatory)
Copy `templates/CBotCheck.csproj` from this skill into `<workdir>/build/`, with the bot at
`<workdir>/src/<BotName>.cs`, and run:
```bash
cd <workdir>/build
dotnet build -nologo -v q -p:Bot=<BotName> -warnaserror
```
- This compiles against the official **`cTrader.Automate`** NuGet package, the same API as
  cTrader. Any error or warning is an automatic **FIX**.
- If `dotnet` is missing, install the .NET 8 SDK (installer from https://dotnet.microsoft.com/download,
  or `curl -sSL https://dot.net/v1/dotnet-install.sh | bash -s -- --channel 8.0`).
- If you can't compile at all, say so and mark the verdict "not compile-verified". Still do the
  static review.
- Also confirm:
  - there is exactly one `Robot` subclass;
  - the class name matches the file name;
  - the attribute has `AccessRights.None` and `TimeZone = TimeZones.UTC` (or the time zone
    explicitly specified).

## Step 2: runtime-error checklist
- **Null and empty values:** positions after orders, pending-order lookups, `First()` on empty
  collections, bars with too little history (indicator warm-up), `Count - 2 ≥ 0`.
- **Division by zero:** ATR, sigma, range width, stop distance, `Symbol.PipSize`.
- **Volume:** `Symbol.NormalizeVolumeInUnits`, clamped to min/max, skipped if below the minimum.
  Partial closes leave at least the minimum on both parts. Lot size is read from `Symbol.LotSize`.
- **Orders:**
  - `ExecuteMarketOrder` / `Place*Order` stop-loss and take-profit are in **pips**, and
    `ModifyPosition` takes **absolute prices**.
  - `TradeResult.IsSuccessful` is checked.
  - The broker's minimum stop distance is respected.
  - Stop orders have an expiry or are cancelled.
  - OCO siblings are cancelled, and a double fill is handled.
- **Close guard:** no close attempt repeated on every tick after a rejection.
- **Events:** subscribed once in `OnStart` and unsubscribed in `OnStop`. No heavy loops in
  `OnTick`.
- **Determinism:** `Server.Time`, not `DateTime.Now`. No `Random`. No `TimeZoneInfo` ID lookups,
  which throw on another OS.
- **Restart safety:** per-position state rebuilt from positions (for example a unit tag in the
  comment, parsed culture-invariant and rejecting NaN, infinity and values ≤ 0).
- **Daily-loss guard:** counts partial closes (from `History`), filters label **and** symbol,
  uses UTC-day boundaries, and isn't recomputed over the whole history on every tick.

## Step 3: logic, fidelity and standards
- **Fidelity table**, rule by rule against the user's spec or source: session times (UTC and
  DST-aware local), range windows, filters, entry trigger (bar close versus touch), side, stop
  and target units and multiples, partial / break-even / trailing, trades per day, cutoff and
  flat times.
- **No look-ahead:** decisions use closed bars only (higher timeframes read at `Count - 2` on the
  new-bar event). Daily and session levels must be complete before use.
- **Standard features present:** risk modes plus MaxLots, MaxSpread, MaxDailyLoss,
  MaxTradesPerDay, MaxOpenPositions, cooldown, weekday toggles, force flat, partial TP,
  break-even, trailing, max hold, VerboseLog, DrawLevels (no unbounded chart-object growth),
  label + symbol filtering, startup warm-up print.
- **Optimiser-ready:** every numeric parameter has DefaultValue/MinValue/MaxValue/Step with
  sensible ranges.
- **Preset:** `.cbotset` keys equal the C# property names, and the values are the intended
  defaults.
- **Indicators:** verify the formulas numerically where possible (for example port to Python or
  C# and compare with the source on synthetic data).
- **DST helpers:** check the outputs on the switch dates for each year the bot will trade.
- **Doc honesty:** "Known differences" and "Assumptions" are complete.

## Output
Write `reviews/<BotName>.md`:

```
# <BotName> — PASS | FIX
Compile: N errors / N warnings (command, API version, timestamp)
Findings: severity BLOCKER / MAJOR / MINOR, file:line, what, why
Fix instructions: numbered, exact
Fidelity table: rule | spec/source | cBot | match?
```

Finish with a summary table (bot, verdict, blockers, majors). **PASS** requires 0 compile errors
and warnings and 0 BLOCKER/MAJOR findings. When fixes come back, re-review: verify each fix, check
for regressions, and add a "Re-review" section.
