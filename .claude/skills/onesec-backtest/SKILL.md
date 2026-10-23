---
name: onesec-backtest
description: Implement and backtest an intraday XAUUSD strategy on 1-second bars with the cTrader cost model (bt1s engine), including resampled higher-timeframe bars and indicators. Use when a strategy card or idea needs to be coded and screened, or when asked to backtest on one-second data.
---

# 1-second bar backtesting (bt1s)

Engine: `bt1s.py`. Data: Dukascopy XAUUSD 1s grid built from ticks (`data/grid1s.npz`).
Validated against the tick simulator: on 464 test trades the win rate matched exactly, and the
per-trade P&L correlation was 1.00.

## Before you start
- The data must exist: `data/ticks/*.npz` and `data/grid1s.npz`. If they're missing, run
  `WORKERS=16 python3 download_ticks.py && python3 build_ticks.py`, then
  `python3 -c "import hfdata; hfdata.load_all(rebuild=True)"`. This takes 20–60 minutes because
  Dukascopy throttles downloads.
- Each process needs ~3 GB of RAM for the context. With a 15 GB container, run **no more than 3
  backtest processes at once**.
- Load the context once per process: `ctx = bt1s.Context.load()` (about 25 s).

## Implement a strategy
Create `strategies/<id>.py`, where `<id>` is the card id with `-` replaced by `_`:

```python
import numpy as np, pandas as pd, bt1s

PARAMS = {                      # first value of each list = the published default
    "range_min": [15, 5, 30, 60],
    "atr_n": [14, 10, 20],
}
EXIT_UNIT = True                # True: provide `unit` and let the evaluator search exit templates

def signals(ctx, range_min=15, atr_n=14):
    b = ctx.bars(60)            # 1m OHLC of mid, index = bar start epoch second
    a = bt1s.atr(b, atr_n)
    ...                         # rules on CLOSED bars only
    return pd.DataFrame(dict(
        sec=b.close_sec.values[mask],   # decision second = last second of the closed bar
        side=side[mask],                # +1 long / -1 short
        sl=..., tp=..., hold=...,       # USD distances; hold in seconds
        unit=a[mask],                   # risk unit for exit templates (ATR, range, ...)
    ))
```

Rules:
- **No look-ahead.** Decide on bar close (`close_sec`) and only use bars that have closed by then.
  Never use `h`/`l`/`c` of the bar you're entering on. Session ranges must be complete before the
  first signal that uses them.
- Times are UTC. Positions are forced flat at 20:59:59 UTC by the engine. Sessions: Asia 23–07,
  London 07–12, NY 12–21.
- Higher timeframes: `ctx.bars(tf)` for any `tf` that divides 86400 (60, 300, 900, 3600 …).
  Indicators: `bt1s.ema`, `sma`, `atr`, `rsi`, `session_vwap` (tick-count weighted).
- The engine opens one position at a time and skips signals while a position is open. Do your
  own per-day limits inside `signals()` if the card asks for them.
- Entries fill at the next second's close plus modeled half-spread and slippage. That's about
  1 s of latency, which is more conservative than the 120 ms used in the tick study.

## Run
```python
import bt1s
from strategies import my_id
ctx = bt1s.Context.load()
tr = bt1s.run(ctx, my_id.signals(ctx))          # cost=bt1s.STRESS for the stress run
print(bt1s.report(tr, ("IS", "VAL")))            # never print OOS during research
```
`report` shows n, trades/week, win rate, $ PF, R-normalised PF, expectancy (R), compounded
return, and max drawdown at 0.5% risk per trade.

For screening and optimisation use `python3 evaluate.py screen|optimise <id>` (see the
`strategy-evaluate` skill). It hides OOS automatically.

## Tick-level confirmation (finalists only)
`simulate.sim_many` re-runs the same trades on raw ticks at 120 ms latency. Use it after
freezing, before the candidate list.
