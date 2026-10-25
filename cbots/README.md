# cTrader cBots: top 5 candidates

All five compile against the official cTrader Automate API (`cTrader.Automate` 1.0.21) with
**0 errors and 0 warnings**, and passed the independent cBot review (`reviews/`).
**None has been run in cTrader yet.** Backtest them in cTrader (tick data from server) before any
demo or live use. None met the research targets on unseen data (see `../research/near_candidates.md`).

| cBot | Import | Preset | Doc | Review | Strategy | Python blind test (Jun–Oct 2026) |
|---|---|---|---|---|---|---|
| AsianRangeBreakout | `algo/AsianRangeBreakout.algo` | `presets/AsianRangeBreakout_XAUUSD.cbotset` | `docs/AsianRangeBreakout.md` | PASS | 00–06 UTC range, OCO stops ±$2, vol-state + ATR filter | PF 2.11, WR 69%, 16 trades |
| IbFadeNy | `algo/IbFadeNy.algo` | `presets/IbFadeNy_XAUUSD.cbotset` | `docs/IbFadeNy.md` | PASS | 08:20 NY initial balance, wide-IB probe fade | PF 1.88, WR 53%, 32 trades |
| AvwapLondon | `algo/AvwapLondon.algo` | `presets/AvwapLondon_XAUUSD.cbotset` | `docs/AvwapLondon.md` | PASS | 23:00-anchored VWAP trend pullback, trailing stop | PF 1.56, WR 46%, 61 trades |
| EmaPullbackAdx | `algo/EmaPullbackAdx.algo` | `presets/EmaPullbackAdx_XAUUSD.cbotset` | `docs/EmaPullbackAdx.md` | PASS | m15 EMA pullback, ADX ≥ 30, scalp + break-even | PF 0.99, WR 80%, 40 trades |
| VClimaxSweepReversal | `algo/VClimaxSweepReversal.algo` | `presets/VClimaxSweepReversal_XAUUSD.cbotset` (0.5% true risk) and `…_reference.cbotset` (reproduces the original PF 3.23 run) | `docs/VClimaxSweepReversal.md` | PASS | Sub-5s V-climax sweep reversal (Antigravity), 9 bugs fixed | in-sample only: cTrader PF 3.23 |

## Standard features in every bot
- **Risk mode:** % of equity, fixed lots or fixed cash, with a max-lots cap.
- **Guards:** max spread, max daily loss (realised from History, including partial closes, plus
  open P&L), max trades per day, max open positions, cooldown.
- **Calendar:** weekday toggles and force flat at 20:55 UTC. New York local times adjust for
  DST in code.
- **Exits:** stop and target as multiples of each strategy's own unit, optional partial TP,
  break-even, trailing stop and max hold.
- **Diagnostics:** VerboseLog, DrawLevels.
- **Account sharing:** label + symbol filtering, so the bots can run side by side on one
  (hedging) account.
- **Optimisation:** every numeric parameter has Default/Min/Max/Step for the cTrader optimiser.

## Rebuild / re-check
```bash
export PATH=/root/.dotnet:$PATH
cd cbots/build && flock /tmp/cbot_build.lock dotnet build -nologo -v q -p:Bot=<BotName> -warnaserror
```
This writes `algo/<BotName>.algo`. The skills are `.claude/skills/ctrader-cbot-builder` and
`.claude/skills/ctrader-cbot-review`.

## Suggested cTrader backtest
XAUUSD, m1 chart, **tick data from server**, 01/01/2025 → today, commission $7 per lot round trip,
hedging account. Check each bot's startup line to confirm enough history loaded for its filters,
then compare the Jun–Oct 2026 period with the Python numbers above.
