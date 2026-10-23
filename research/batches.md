# Evaluation batches (cards in research/cards/*.yaml)

Merged duplicates: implement one strategy module per line; card variants become parameters.

## Batch A: breakouts and session ranges
1. asian_range_breakout: marketplaces-asian-range-oco-breakout + practitioners-asian-range-london-breakout + academic-asian-range-orb-volstate (vol-state filter as a parameter)
2. crabel_orb_stretch: books-crabel-orb-stretch-london
3. idnr4_breakout: books-idnr4-daily-breakout
4. williams_vol_breakout: books-williams-vol-breakout
5. ny_orb: marketplaces-ny-orb-15m-5m
6. london_range_ny_break: marketplaces-london-range-ny-breakout-30m + practitioners-london-range-break-retest (retest as a parameter)
7. pdh_pdl_breakout: marketplaces-pdh-pdl-oco-breakout
8. ib_extension_ny: books-ib-extension-ny
9. bbkc_squeeze: marketplaces-bbkc-squeeze-breakout-15m + practitioners-bbkc-squeeze-release
10. noise_area_momentum: academic-noise-area-momentum
11. shanghai_open: practitioners-shanghai-open-orb + academic-shfe-open-momentum

## Batch B: reversal, structure, mean reversion
1. asian_range_fakeout: marketplaces-asian-range-fakeout-h1 + practitioners-asian-range-false-break-fade + books-ict-judas-asia-sweep
2. level_sweep_reclaim: books-turtle-soup-15m + marketplaces-prev-candle-sweep-m15 + practitioners-pdh-pdl-sweep-reclaim (level type as a parameter)
3. raschke_8020: books-raschke-8020-daily
4. wyckoff_spring: books-wyckoff-spring-upthrust-5m
5. mp_80pct: books-mp-80pct-rule
6. bb_pinbar_fade: marketplaces-bb-pinbar-fade-m5
7. rsi_extreme_fade: practitioners-rsi-extreme-ema200-fade
8. vwap_sd_fade: practitioners-vwap-3sd-fade
9. overreaction_fade: academic-overreaction-fade-volnorm
10. round_level: marketplaces-round20-level-fade + practitioners-round20-level-reaction (bounce vs break + placebo offset)
11. silver_bullet: books-ict-silver-bullet-ny + practitioners-ict-silver-bullet-fvg (market-entry variant included)
12. taylor_sweep: marketplaces-taylor-sweep-1m

## Batch C: momentum, time-of-day, trend
1. last30_momentum: academic-rest-of-day-last30-momentum
2. first_last_hh: academic-first-hh-last-hh-comex
3. asian_drift: practitioners-asia-hours-drift + academic-asian-drift-adaptive
4. pmfix: academic-london-pmfix-short (short and follow variants)
5. fomc_drift: academic-fomc-post-announcement-drift (FOMC statement dates 2025-2026 hard-coded from the Fed calendar)
6. tsmom_day: academic-tsmom-daysession-volscaled
7. holy_grail: books-holy-grail-15m
8. ema_pullback_adx: marketplaces-ema-pullback-adx-m15
9. supertrend_rsi: practitioners-ny-supertrend-rsi
10. vwap_cross_mtf: marketplaces-vwap-cross-mtf-ema-5m
11. avwap_london: books-avwap-london-pullback
12. macro_shock: academic-macro-shock-15m-drift (only if NFP/CPI release dates can be listed reliably; otherwise skip and say so)

Deferred: academic-usd-residual-catchup (needs EURUSD data).
