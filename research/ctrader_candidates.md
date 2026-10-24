# cTrader candidates

**Status: no candidates** (47 ideas tested across Batches A, B, C, D1, D2; 7 reached OOS, all failed). No strategy met all gates in `docs/TASK_PROMPT.md` on unseen data
(WR > 75%, PF > 3, max DD < 5% at 0.5% risk, met separately on IS 2025, VAL Jan–May 2026 and
OOS Jun–Oct 2026, with the trade-count, stress and robustness minimums).

## OOS frontier (frozen before OOS; for information only, NOT recommended for live trading)

| Strategy | IS PF / WR | VAL PF / WR | OOS PF / WR / n | Why it fails |
|---|---|---|---|---|
| asian_range_breakout | 2.13 / 62% | 2.40 / 63% | 2.11 / 69% / 16 | WR, PF, OOS n < 25 |
| ib_fade_ny | 1.58 / 52% | 2.13 / 53% | 1.88 / 53% / 32 | WR, PF |
| avwap_london | 1.20 / 45% | 1.35 / 48% | 1.56 / 46% / 61 | WR, PF; IS peak not plateau |
| ema_pullback_adx | 1.57 / 88% | 3.35 / 91% | 0.99 / 80% / 40 | PF collapsed OOS |
| london_range_ny_break | 1.86 / 60% | 1.68 / 70% | 0.47 / 39% / 28 | PF collapsed OOS |
| bb_pinbar_fade | 1.50 / 49% | 2.13 / 58% | 0.52 / 39% / 33 | PF collapsed OOS |
| usd_impulse_catchup (round 2) | 1.99 / 60% | 2.13 / 46% | 0.25 / 33% / 12 | PF collapsed OOS |

Their OOS data has been used, so none of these can be re-tuned and re-tested on the same period.
Relaxing the gates needs the user's explicit decision, and the result would need fresh data
(e.g. forward or demo trading after Oct 2026, or cTrader data the Dukascopy set doesn't cover).

Frozen parameters: `strategy_cards/<id>.frozen.json`. Per-trade OOS records: `results/<id>_trades.csv`.
Reviews: `research/reviews/`.
