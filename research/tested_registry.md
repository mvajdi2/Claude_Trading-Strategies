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

## Batch B (reversal, structure, mean reversion), 1s engine, staged `evaluate.py`; details in `research/results_batchB.md`

| ID | Idea | Combos | Best IS-selected IS / VAL / OOS (PF, WR) | Verdict | Where |
|---|---|---|---|---|---|
| B1a | asian_range_fakeout: Asian range (00–06) H1 close-outside / close-back-inside fade | 255 | IS PF 0.93, 40.6 (n69) / VAL 0.23, 17.4 | REJECT at screen | `strategies/asian_range_fakeout.py` |
| B1b | asian_range_fakeout_15m: same, 15m closes + range filter | 267 | IS 1.19, 92.7 (n151) / VAL 1.20, 89.4 (PF(R) 0.68) | REJECT at screen | `strategies/asian_range_fakeout_15m.py` |
| B2 | level_sweep_reclaim: Turtle Soup on N-bar 15m channel (stop entry back through old extreme) | 213 | IS 1.05, 51.0 (n145) / VAL 0.46, 45.8 | REJECT at screen | `strategies/level_sweep_reclaim.py` |
| B3 | raschke_8020: fade the day after open/close at opposite extremes (+ Oops variant) | 2 | IS PF(R) 0.51 (n28) / oops 0.76 (n76) | REJECT (ineligible by trade count; oops fails screen) | `strategies/raschke_8020.py` |
| B4 | wyckoff_spring: 5m spring/upthrust out of a 2-touch range | 231 | IS 1.35, 36.7 (n60) / VAL 0.40, 31.8 | REJECT at screen | `strategies/wyckoff_spring.py` |
| B5 | mp_80pct: Market Profile 80 % rule (re-entry into prior value area) | 195 | IS 1.17, 42.9 (n70) / VAL 1.72, 58.3 | REJECT at screen (IS PF(R) 1.20 < 1.3) | `strategies/mp_80pct.py` |
| B6 | bb_pinbar_fade: BB(20) close-outside + pin bar, H1 EMA200 aligned (5m) | 248 | IS 1.50, 49.4 (n81) / VAL 2.13, 58.1 (n31) / OOS 0.52, 39.4 (n33) | OOS FAIL | `strategies/bb_pinbar_fade.py`, `strategy_cards/bb_pinbar_fade.frozen.json` |
| B7 | rsi_extreme_fade: RSI14 extreme with EMA200 filter | 125 | IS 1.24, 40.5 (n116) / VAL 1.80, 43.2 | REJECT at screen (IS PF(R) 1.17) | `strategies/rsi_extreme_fade.py` |
| B8 | vwap_sd_fade: session VWAP sigma-band re-entry fade to VWAP | 177 | IS 0.91, 37.1 (n350) / VAL 0.43, 31.6 | REJECT at screen | `strategies/vwap_sd_fade.py` |
| B9 | overreaction_fade: time-of-day vol-normalised 30m overreaction fade | 207 | IS 1.30, 71.4 (n140) / VAL 1.12, 67.9 | REJECT at VAL | `strategies/overreaction_fade.py` |
| B10 | round_level: $10/20/50 round-number first touch, bounce vs break, placebo offset 10.37 | 255 | IS 1.45, 81.9 (n72, step 50 break) / VAL 0.36, 54.8; real vs placebo median IS PF(R) 0.804 vs 0.800 | REJECT at VAL (no level effect) | `strategies/round_level.py` |
| B11 | silver_bullet (ICT) | 0 | – | SKIPPED – ICT/SMC excluded by user | – |
| B12 | taylor_sweep (sweep + VWAP/EMA reclaim) | 0 | – | SKIPPED – ICT/SMC excluded by user | – |

Batch B observation: no reversal or mean-reversion idea reached PF ≥ 1.5 on IS with n ≥ 60. The round-number "effect" equals its placebo.

### Batch A rerun after review (research/reviews/batchA.md; staged harness 2ca67cf; final VAL look each)

| ID | Idea | Combos (earlier + rerun) | Finalist IS / VAL / OOS (PF, WR, n) | Verdict |
|---|---|---|---|---|
| A6 | london_range_ny_break (break mode, DST-aware ny0830 start) | 300 + 267 | IS 1.86, 59.7, 67 / VAL 1.68, 70.0, 20 / OOS 0.47, 39.3, 28 | OOS FAIL |
| A6b | london_range_retest (split from A6; template-neighbour median definition documented in results_batchA.md) | shared + 195 | IS 1.46, 81.0, 147 / VAL 0.57 | CLOSED at VAL |
| A2 | crabel_orb_stretch (card exit in stage 1) | 300 + 267 | IS 1.13 (PF(R) 1.34), 37.3, 67 / VAL 0.26 | CLOSED at VAL |
| A8 | ib_extension_ny (break only, native-stop unit, DST starts) | 120 + 213 | IS PF(R) 0.96 | CLOSED (IS) |
| A8b | ib_fade_ny (split from A8) | shared + 177 | IS 1.58, 51.6, 91 / VAL 2.13, 52.9, 34 / OOS 1.88, 53.1, 32 | OOS FAIL |
| A9 | bbkc_squeeze (card trail exit + card-2 stop) | 120 + 267 | IS 1.44, 41.7, 163 / VAL 0.92 | CLOSED at VAL |
| A10 | noise_area_momentum (exit-latency fix, gap_adj) | 120 + 231 | IS PF(R) 1.00 | CLOSED (IS) |
| A11a | shanghai_orb (split from shanghai_open; SHFE holidays) | shared + 267 | IS 1.47, 49.8, 237 / VAL 0.91 | CLOSED at VAL |
| A11b | shfe_open_mom (split; night variant; SHFE holidays) | shared + 177 (171 distinct: exit_utc is a no-op for the night anchor) | IS PF(R) 1.26 | CLOSED (IS) |

### Batch C: momentum, time-of-day, trend (research/results_batchC.md; staged harness 2ca67cf after early audit; final VAL look each)

| ID | Idea | Combos (pre-audit + staged) | Finalist IS / VAL / OOS (PF, WR, n) | Verdict | Where |
|---|---|---|---|---|---|
| C1 | last30_momentum: rest-of-day return → last 30 min before COMEX settle (+ realised-vol filter, US holiday skip) | 120 + 207 | IS 1.55 (PF(R) 1.41), 89.8, 88 / VAL 0.73, 81.3, 48 | REJECT at VAL | `strategies/last30_momentum.py` |
| C2 | first_last_hh: first half-hour (08:20 NY / 07:00 UTC / 18:00 NY) predicts 13:00–13:30 NY | 120 + 195 | IS PF(R) 1.24 (n64) / VAL 0.77 | REJECT (IS) | `strategies/first_last_hh.py` |
| C3 | asian_drift: Asian-hours long drift, unconditional + adaptive sign (incl. 08–20 day leg) | 300 + 199 | IS 1.53 (PF(R) 1.75), 50.0, 112 / VAL 0.75, 41.2, 102 | REJECT at VAL (IS = long beta) | `strategies/asian_drift.py` |
| C4 | pmfix: London open → PM fix after strong Asia, fade/follow | 120 + 24 + 183 | follow: IS 1.58 (PF(R) 1.82), 61.2, 67 / VAL 1.09, 55.6, 27; fade loses on IS | REJECT at VAL | `strategies/pmfix.py` |
| C5 | fomc_drift: post-FOMC statement 30-min drift into the close (Fed-calendar dates) | 120 (discarded) | screen IS n 6 | INELIGIBLE (trade count, X7) | `strategies/fomc_drift.py` |
| C6 | tsmom_day: daily EMA trend sign held intraday, semivariance filter | 300 + 183 | IS 1.36 (PF(R) 1.56), 57.7, 156 (100 % long; equals long-daytime benchmark PF(R) 1.55) / VAL 0.74, 50.5, 95 | REJECT at VAL | `strategies/tsmom_day.py` |
| C7 | holy_grail: ADX first pullback to EMA, stop entry, swing stop | 120 + 195 | IS 1.66 (PF(R) 1.36), 46.3, 80 / VAL 0.87, 30.6, 36 | REJECT at VAL | `strategies/holy_grail.py` |
| C8 | ema_pullback_adx: EMA20/50 + ADX + H1 filter, pullback to EMA20 (M15) | 300 + 177 | IS 1.57 (PF(R) 1.80), 87.9, 91 / VAL 3.35, 91.1, 45 / OOS 0.99, 80.0, 40 | OOS FAIL | `strategies/ema_pullback_adx.py`, `strategy_cards/ema_pullback_adx.frozen.json` |
| C9 | supertrend_rsi: NY Supertrend + RSI 55/45 (5m) | 120 + 186 | IS PF(R) 1.09 (n385) / VAL 1.33 | REJECT (IS) | `strategies/supertrend_rsi.py` |
| C10 | vwap_cross_mtf: session-VWAP cross + H1/H4 EMA filter (5m) | 120 + 171 | IS PF(R) 1.08 (n324) / VAL 0.98 | REJECT (IS) | `strategies/vwap_cross_mtf.py` |
| C11 | avwap_london: anchored-VWAP trend pullback / 2σ fade | 120 + 195 | IS 1.20 (PF(R) 1.41), 44.9, 138 / VAL 1.35, 48.4, 62 / OOS 1.56, 45.9, 61 | OOS FAIL | `strategies/avwap_london.py`, `strategy_cards/avwap_london.frozen.json` |
| C12 | macro_shock: NFP/CPI 15-min shock drift | 0 | – | SKIPPED: release dates not verifiable on bls.gov (403 bot block) | – |

Batch C observation: the time-of-day ideas earn their IS edge from 2025's bull-trend beta (long-daytime benchmark matches) and reverse in VAL 2026. ema_pullback_adx is the only setting that met WR/PF/DD on VAL, and it fell to PF 0.99 in OOS.
