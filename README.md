# XAUUSD tick-level strategy research

Research pipeline on Dukascopy XAUUSD ticks (Jan 2025 – Oct 2026, ~145M ticks).

## Rebuild the data
```bash
pip install numpy pandas numba lightgbm scikit-learn requests
WORKERS=16 python3 download_ticks.py   # ~15-60 min, throttled by Dukascopy
python3 build_ticks.py                 # -> data/ticks/ticks_YYYYMM.npz
```

## Study 1: sub-5-second spike reversal (result: rejected)
`stage_a_events.py` … `stage_j_oos.py`. Splits: IS = 2025, VAL = Jan–May 2026, OOS = Jun–Oct 2026.
Frozen candidate in `strategy.py`: IS PF(R) 2.18 / WR 90.9%, VAL 1.58 / 90.3%,
**OOS 0.46 / 79.2% — failed**. See `data/frozen_results.json`, `data/frontier_frozen_signal.csv`.

Cost model (`simulate.py`): quotes rebuilt around Dukascopy mid with cTrader-like spread
(0.30 × Dukascopy spread, min $0.10), $0.03 slippage per market fill, $0.07/oz commission,
120 ms entry latency.
