---
name: ctrader-cbot-review
description: Review cTrader cBots in cbots/src for compile errors, runtime errors, cTrader API misuse, look-ahead, sizing/pip mistakes and fidelity to the frozen Python strategy; compile each against the official cTrader.Automate API and return PASS or FIX with exact instructions. Use when asked to review, check, audit or double-check a cBot.
---

# cTrader cBot review

You are the cBot reviewer. Find every problem that would stop a bot compiling, crash it in
cTrader, make it trade differently from the frozen Python strategy, or make it unsafe. You may
fix trivial issues yourself only when asked. By default you report.

## Step 1: compile (mandatory)
```bash
export PATH=/root/.dotnet:$PATH DOTNET_CLI_TELEMETRY_OPTOUT=1
cd /home/user/xau_hf/cbots/build && flock /tmp/cbot_build.lock dotnet build -nologo -v q -p:Bot=<BotName> -warnaserror
```
Any error or warning is an automatic **FIX**. Also confirm:
- the file has exactly one `Robot` subclass;
- the class name matches the file name;
- the `[Robot(...)]` attribute includes `AccessRights.None` and `TimeZone = TimeZones.UTC`.

## Step 2: runtime-error checklist
- Null and empty checks: positions after an order, `PendingOrders` lookups, bars with too few
  values (indicator warm-up: no signal until enough bars), `Count - 2` index ≥ 0.
- Division by zero: ATR, sigma, range width, stop distance, `Symbol.PipSize`.
- Volume: always `Symbol.NormalizeVolumeInUnits`, clamped to min/max, skipped if below min.
  Partial closes leave ≥ min on both parts.
- Orders:
  - The signature types are correct: pips versus price. `ExecuteMarketOrder` stop-loss and
    take-profit are in **pips**. `ModifyPosition` takes absolute prices.
  - `TradeResult.IsSuccessful` is checked, and stops respect the minimum distance.
  - Stop orders have an expiry or are cancelled explicitly.
  - OCO siblings are cancelled.
- Event handlers are subscribed once (`OnStart`) and unsubscribed in `OnStop`. No heavy work runs
  in `OnTick`.
- Exceptions: no unguarded LINQ `First()` on empty collections, no unchecked casts, no `TimeZoneInfo`
  lookups that throw on another OS.
- Determinism in backtests: no `DateTime.Now` (use `Server.Time`), no randomness.

## Step 3: logic and fidelity checklist (compare with `strategies/<id>.py` + frozen card)
- Every rule matches the Python: session times (UTC and DST-aware local), range windows,
  filters, entry trigger (bar close versus touch), side, stop and target in the right **unit**
  with the frozen multiples, partial and break-even and trailing as frozen, max trades per day,
  cutoff and flat times.
- **No look-ahead:** only closed bars are used for decisions. Higher-timeframe bars are read at
  `Count - 2` on the new-bar event. Daily or session levels are complete before use.
- **Defaults equal the frozen values**, and the `.cbotset` keys match the C# property names
  exactly, with the frozen values.
- **Standard features present** (see the `ctrader-cbot-builder` skill): risk modes, MaxLots,
  MaxSpread, MaxDailyLoss, MaxTradesPerDay, MaxOpenPositions, Cooldown, weekday toggles, force
  flat, partial TP, break-even, trailing, max hold, VerboseLog, DrawLevels, label filtering.
- **Optimiser-ready:** every numeric parameter has DefaultValue, MinValue, MaxValue and Step,
  and the ranges cover the Python grid.
- **Sizing maths:** risk cash / (stop distance × LotSize) gives lots. Check the units
  conversion, and check that XAUUSD LotSize (usually 100 oz) is read from `Symbol.LotSize`, not
  hard-coded.
- The `cbots/docs/<BotName>.md` "Known differences" section is honest and complete.

## Output
Write `cbots/reviews/<BotName>.md` with:

```
# <BotName> — PASS | FIX
Compile: 0 errors / 0 warnings (command + timestamp)
Findings: (severity: BLOCKER / MAJOR / MINOR, file:line, what, why)
Fix instructions: numbered, exact
Fidelity table: rule | Python | cBot | match?
```

Finish with a summary table across bots (bot, verdict, blockers, majors). A bot is **PASS** only
if it has 0 compile errors and warnings, 0 BLOCKER and 0 MAJOR findings.
