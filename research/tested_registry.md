# Ideas already tested (do not resubmit unless materially different)

| ID | Idea | Result | Where |
|---|---|---|---|
| T1 | Sub-5s V-Climax sweep reversal, low frequency (Antigravity cBot) | cTrader tick backtest PF 3.23 at deal level, ~35 trades/yr; Q4 weakest | original Antigravity folder |
| T2 | HF1: high-frequency sub-5s spark reversal with scale-in | OOS PF 0.43 — rejected | Antigravity session |
| T3 | Sub-5s spark reversal + order-flow features (tick rate, imbalance, spread) | no edge after costs — rejected | Antigravity session |
| T4 | Sub-5s sweep of 15/30-min level + spread widening + rejection flow, scalp + runner | IS PF(R) 2.18, VAL 1.58, OOS 0.46 — rejected | `strategy.py`, `stage_*.py` |
| T5 | Retest limit entry after spike rejection | worse than market entry (adverse selection) — rejected | `stage_g_limit.py` |
| T6 | LightGBM on spike features | overfit (IS top decile strong, VAL flat) — rejected | `stage_d_model.py` |
| T7 | Scheduled anchors (Tokyo/London open, LBMA AM/PM fix, COMEX open/close, US data 08:30/10:00 ET, NYSE open, 16:00 fix) × momentum/fade/run-up continuation/reversal | 6/4,160 passed IS+VAL (below chance); all ≤ PF 1.07 OOS — rejected | `s2_*.py` |
| T8 | NYSE-open first-minute momentum | IS PF(R) 1.62, VAL 1.76, OOS 0.75 — rejected | `s3_nyse*.py` |

Observation: every candidate so far degraded from June 2026; treat regime robustness as a primary concern.

## Batch A (breakouts and session ranges), 1s engine, `evaluate.py`; details in `research/results_batchA.md`

| ID | Idea | Combos | Best IS-selected IS / VAL / OOS (PF, WR) | Verdict | Where |
|---|---|---|---|---|---|
| A1 | asian_range_breakout: Asian range 00–06 OCO stop breakout + ATR range filter + prior-day vol-state filter | 420 | IS PF 2.13 WR 62.5 (n72) / VAL 2.40, 63.2 (n38) / OOS 2.11, 68.8 (n16) | OOS FAIL (WR, PF, n<25) | `strategies/asian_range_breakout.py`, `strategy_cards/asian_range_breakout.frozen.json` |
| A2 | crabel_orb_stretch: London 07:00 OR + stretch, NR4/NR7 | 300 | IS 3.04, 83.6 (n61) / VAL 0.31, 58.6 | REJECT at VAL | `strategies/crabel_orb_stretch.py` |
| A3 | idnr4_breakout: ID/NR4 next-day breakout with SAR | 120 | IS PF(R) 1.29 (n64, NR-only variant) / VAL 0.63; card version only 23 IS trades | REJECT at screen | `strategies/idnr4_breakout.py` |
| A4 | williams_vol_breakout: open ± k·prior range | 120 | IS 1.58, 60.3 (n68) / VAL 0.64, 41.4 | REJECT at VAL | `strategies/williams_vol_breakout.py` |
| A5 | ny_orb: NY 09:30 OR 15 m, 5 m close entry | 120 | IS 1.07, 27.4 / VAL 0.67 | REJECT at screen | `strategies/ny_orb.py` |
| A6 | london_range_ny_break: London range broken in early NY (plain + retest) | 300 | IS 2.13, 62.4 (n85) / VAL 0.52, 30.0 | REJECT at VAL | `strategies/london_range_ny_break.py` |
| A7 | pdh_pdl_breakout: PDH/PDL OCO stop breakout | 300 | IS 3.87, 94.0 (n116, passes IS gates) / VAL 0.60, 84.2 | REJECT at VAL | `strategies/pdh_pdl_breakout.py` |
| A8 | ib_extension_ny: NY initial balance narrow→break / wide→fade | 120 | IS 1.35, 72.9 / VAL 1.07, 62.5 | REJECT at VAL | `strategies/ib_extension_ny.py` |
| A9 | bbkc_squeeze: BB-inside-KC squeeze release | 120 | IS 1.44, 85.7 / VAL 0.74, 77.6 | REJECT at VAL | `strategies/bbkc_squeeze.py` |
| A10 | noise_area_momentum: time-of-day noise band breakout + VWAP trail | 120 | IS 1.46, 47.3 / VAL 0.93, 36.6 | REJECT at VAL | `strategies/noise_area_momentum.py` |
| A11 | shanghai_open: Shanghai 01:30 5 m ORB / SHFE open half-hour momentum | 120 | IS 1.28, 56.2 / VAL 0.82, 43.1 | REJECT at screen | `strategies/shanghai_open.py` |

Batch A observation: scalp + break-even exits produce 85–95 % IS WR on breakout entries, but none holds on VAL. No Batch A idea passes.
