---
name: strategy-evaluate
description: Evaluate, optimise and validate intraday XAUUSD strategies end to end (IS screen, IS optimisation with exit templates, VAL confirmation, freeze, single blind OOS run, stress and robustness checks) against pass gates WR > 75%, PF > 3, DD < 5%, and produce the cTrader candidate list. Use after strategies are coded with onesec-backtest, or when asked to optimise or validate a strategy.
---

# Strategy evaluation and optimisation

Harness: `evaluate.py` (it enforces the protocol). Gates and splits are defined in
`docs/TASK_PROMPT.md`. Never change them without the user's approval.

## Splits
IS = 2025, VAL = Jan–May 2026, OOS = Jun 2026 → end. `screen` and `optimise` never simulate
signals dated in OOS.

## Pipeline per strategy
1. **Screen:** `python3 evaluate.py screen <id>` runs the published defaults on IS and VAL.
   Continue if IS PF(R) ≥ 1.2 with ≥ 60 trades, or if the mechanism plainly works before costs.
   Otherwise record it as rejected in `research/tested_registry.md` with its numbers.
2. **Optimise on IS:** `python3 evaluate.py optimise <id> --max 300`. This samples parameters ×
   exit templates (fixed, scalp + break-even, trailing) and writes `results/<id>_opt.csv`.
   Choose using **IS columns only**. Prefer a broad plateau over the single best row, and check
   that neighbouring settings are also good.
3. **Confirm on VAL:** the chosen setting must also pass the gates on VAL. You may compare at most
   3 finalists on VAL. Using VAL to choose more than that turns it into in-sample data.
4. **Freeze:**
   `python3 evaluate.py freeze <id> '{"params": {...}, "exit": {...}, "note": "why"}'`.
   This records the code hash and the neighbourhood robustness (median IS PF of ±1-step neighbours).
   Commit the frozen card with git before step 5.
5. **Single OOS run:** `python3 evaluate.py oos <id>` runs base and stress costs and returns the
   verdict PASS/FAIL. It refuses to run a second time or after code changes.
6. **Tick-level check (PASS only):** re-run the frozen trades with `simulate.sim_many` at 120 ms
   latency. PF must stay > 3 and WR > 75%.

## Gates (all required; see docs/TASK_PROMPT.md)
WR > 75%, $ PF > 3, max DD < 5% at 0.5% risk per trade, met separately on IS, VAL and OOS.
Also required: ≥ 100 trades in IS+VAL, ≥ 25 in OOS, stress PF > 2 with DD < 7%, and
neighbourhood median IS PF > 2.

## Making a strategy better (IS only)
- Regime filters: ATR or volatility floors and caps, trend filter (higher-timeframe EMA slope),
  day-of-week, session windows, distance to daily open or VWAP, prior-day range.
- Exit structure: a high WR with PF > 3 needs a small, frequently hit first target **and** small
  losses. Look for setups whose MAE (maximum adverse excursion) is naturally small, rather than
  widening the stop. Check `mae`/`mfe` in the trades table.
- Combining strategies is allowed only if each part is frozen separately.
- Every combination you try counts. Report the total per idea.

## Report
- Append each idea to `research/tested_registry.md`: id, combinations tested, best IS / VAL /
  OOS numbers, verdict.
- Candidates that PASS go in `research/ctrader_candidates.md` with: exact rules, parameters,
  exit, sizing (0.5% risk), sessions in UTC, and the cTrader backtest settings (XAUUSD, m1 or
  tick data, dates Jan 2025 → now, commission $7 per lot round trip, spread from broker).
- If nothing passes, write the frontier: for each idea, the best IS-selected setting and its
  IS / VAL / OOS WR, PF, DD and trades per week. Do not soften the verdict.
