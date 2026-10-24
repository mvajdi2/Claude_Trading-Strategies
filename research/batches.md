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
1. asian_range_fakeout: marketplaces-asian-range-fakeout-h1 + practitioners-asian-range-false-break-fade (ICT Judas variant excluded)
2. level_sweep_reclaim: books-turtle-soup-15m only (SMC sweep variants excluded)
3. raschke_8020: books-raschke-8020-daily
4. wyckoff_spring: books-wyckoff-spring-upthrust-5m
5. mp_80pct: books-mp-80pct-rule
6. bb_pinbar_fade: marketplaces-bb-pinbar-fade-m5
7. rsi_extreme_fade: practitioners-rsi-extreme-ema200-fade
8. vwap_sd_fade: practitioners-vwap-3sd-fade
9. overreaction_fade: academic-overreaction-fade-volnorm
10. round_level: marketplaces-round20-level-fade + practitioners-round20-level-reaction (bounce vs break + placebo offset)
11. ~~silver_bullet~~ (ICT, excluded by user)
12. ~~taylor_sweep~~ (SMC liquidity sweep, excluded by user)

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

**User instruction:** no ICT/SMC strategies (FVG, order blocks, liquidity sweeps, Judas, Silver Bullet, killzones).

## Batch D (round 2, research/cards/round2.yaml), no ICT/SMC
### D1: cross-asset, statistical, microstructure (data: XAUUSD 1s + data/m1/*.npz via ctx.m1)
1. common_factor_residual: r2-common-factor-residual-m15
2. usd_impulse_catchup: r2-usd-impulse-catchup (replaces deferred academic-usd-residual-catchup)
3. gold_silver_residual: r2-gold-silver-residual-revert
4. riskoff_rebound: r2-riskoff-coliquidation-rebound (needs USATECHIDXUSD; wait for data/m1/USATECHIDXUSD.npz)
5. reopen_gap_fade: r2-reopen-gap-fade (with follow-the-gap control)
6. tick_intensity_follow: r2-tick-intensity-imbalance-follow
7. vr_kalman_regime: r2-vr-regime-kalman-revert
### D2: macro-calendar (data: ctx.calendar() = data/calendar/us_macro_2025_2026.csv), started once the calendar exists
1. post_release_revert: r2-post-release-small-surprise-revert
2. pre_release_drift: r2-pre-release-drift-10et
3. release_range_crush: r2-post-release-range-crush-fade
4. release_bracket: r2-release-bracket-impulse
5. macro_shock: academic-macro-shock-15m-drift (previously skipped for lack of a calendar)
6. month_end_fix: r2-month-end-fix-hedge-flow (screen/sign check only; too few trades for gates)
7. comex_expiry: r2-comex-expiry-pressure (screen + placebo only; too few trades for gates)
