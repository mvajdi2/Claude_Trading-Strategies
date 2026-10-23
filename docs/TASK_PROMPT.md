# Engineered task prompt: XAUUSD day-trading strategy discovery

## Goal
Find **intraday** XAUUSD strategies (flat by the daily close at 21:00 UTC, no overnight hold) that
meet **all** of the gates below on **unseen** data, then hand over a short list of
candidates for confirmation in the cTrader backtester.

## Data
- Dukascopy XAUUSD ticks, Jan 2025 to Oct 2026 (~145M ticks), rebuilt with `download_ticks.py`
  and `build_ticks.py`.
- Research runs on **1-second bars** (`hfdata.load_all()` grid; higher timeframes are resampled from
  it). Finalists are re-checked at **tick level** (`simulate.py`).
- Splits are fixed and never changed:
  **IS = 2025-01-01 to 2025-12-31** (discovery and optimisation),
  **VAL = 2026-01-01 to 2026-05-31** (confirmation; choose between finalists),
  **OOS = 2026-06-01 to the end of the data** (one blind run per frozen candidate).

## Cost and execution model (always on)
cTrader-equivalent spread = max($0.10, 0.30 × Dukascopy spread), $0.03 slippage on every market
fill, $0.07/oz round-trip commission, 120 ms latency. Stress run: spread × 1.5, slippage $0.10,
latency 500 ms. When a stop and a target both fall inside the same 1s bar, the **stop fills
first**.

## Pass gates (all required, on OOS, and also met separately on IS and on VAL)
| Metric | Gate |
|---|---|
| Win rate (net, per trade) | > 75% |
| Profit factor (net $, fixed-fractional sizing) | > 3.0 |
| Max equity drawdown at 0.5% risk per trade, compounding | < 5% |
| Trades | ≥ 100 in IS+VAL, ≥ 25 in OOS |
| Stress run (costs ×1.5, latency 500 ms) | PF > 2.0, DD < 7% |
| Parameter robustness | median PF of the ±1-step neighbourhood > 2.0 on IS |

A candidate that misses a gate is reported with its numbers, never rounded up to "pass".

## Workflow
1. **Research** (skill `strategy-research`, parallel subagents by source type): collect ideas as
   machine-readable strategy cards. Skip anything in `research/tested_registry.md`.
2. **Screen** (skill `onesec-backtest`): implement each card with its published default parameters
   and run it on IS only. Keep it if IS PF(R) ≥ 1.2 with ≥ 60 trades, or if it shows a clear
   structural edge before costs.
3. **Optimise and validate** (skill `strategy-evaluate`): parameter grid on IS (≤ 300 combinations
   per idea, each counted), exit-structure search (fixed, partial + break-even, trailing, time), and
   regime filters. Then VAL confirmation, **freeze** (commit `strategy_cards/<id>.frozen.json`),
   a single OOS run, the stress run, and the robustness check.
4. **Report**: frontier table (WR vs PF vs DD vs trades/week) for every idea tested; candidate
   list `research/ctrader_candidates.md` with exact rules, parameters, sizing, and cTrader settings
   (symbol, period, dates, commission) for the user's native backtest.

## Anti-overfitting rules
- Never use OOS to choose or tune anything. Once OOS has been run, the strategy is either a
  candidate or rejected.
- Report the number of combinations tried per idea; prefer broad plateaus over single peaks.
- Judge by PF on R-normalised (fixed-fractional) trades as well as by $ PF; a strategy whose $ PF
  depends on a few large trades is flagged.
- Rules must be implementable in a cTrader `OnTick`/`OnBar` cBot with no look-ahead.

## Honesty clause
If no idea passes every gate, stop and report the best frontier honestly. Do not loosen the gates
or the splits without the user's explicit approval.
