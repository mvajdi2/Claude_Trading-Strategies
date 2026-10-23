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
