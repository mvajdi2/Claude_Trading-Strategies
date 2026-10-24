# Batch D1 results: cross-asset, statistical, microstructure (round-2 cards)

Protocol: `evaluate.py` (staged harness). Screen at card defaults on IS, then the staged IS search:
stage 1 = full sorted PARAMS grid with the card's own exit (≤ 141 combos), stage 2 = all 53 exit
templates on the top-3 plateau settings. Then a single VAL look at one finalist, freeze, commit,
and a single OOS run. Costs: cTrader model (spread max($0.10, 0.3×Dukascopy), $0.03 slippage,
$0.07/oz commission), 1 s fill latency. DD = max equity drawdown at 0.5 % risk per trade, compounding.

## Selection rule (committed on its own before any D1 grid was run)

Applied identically to all 7 strategies by `research/d1_select.py` (IS columns only):

1. **Finalist setting** = the stage-1 (card-exit) setting with the highest plateau score, i.e. the
   harness's median IS PF(R) over the setting and its sorted ±1 neighbours that have n_IS ≥ 60,
   among settings with n_IS ≥ 60. Ties: the higher own IS PF(R).
2. **Exit**: among the 53 stage-2 templates of that setting, a template is eligible if the median
   IS PF(R) of its template neighbours is ≥ 1.30 (neighbours: same family; ±1 step in sl with the
   rest fixed; ±1 step in the final tp with tp1/f1/be fixed; trail family ±1 step in sl and in
   trail; the template itself excluded). The best eligible template replaces the card exit only if
   its IS PF(R) is higher than the card exit's (by > 0.005). Ties: the lower sl, then the card exit.
3. **VAL**: the single finalist's VAL row is the strategy's only VAL look.
4. **Freeze + single OOS** only if the finalist has IS PF(R) ≥ 1.30 **and** VAL PF ≥ 1.30.
   Never re-tune after OOS.
5. Strategies whose natural frequency cannot reach n_IS ≥ 60 at any setting get no stage 2 and no
   finalist: reported as "ineligible by trade count" (X7).
6. Structural branch switches kept as PARAMS (e.g. regime branch) are listed last and disclosed;
   the neighbourhood median is also reported without them. Control/benchmark variants (e.g. the
   follow-the-gap control) are not in the search and are reported separately.

Conventions used by every D1 module (`strategies/_d1util.py`): cross-asset 1m BID bars are joined
on the minute-start index, so the cross-asset close used at a decision second is that of a bar that
closed at the same second as the XAU bar (t+59) or earlier; explicit 20:55 UTC flat (or 20:45 where
the card says so); `unit` = the native stop distance; no PARAMS key that only changes sl/tp.

## Results (finalist per the rule above; VAL = the single final look)

Combos = stage 1 + stage 2, all counted. PF(R) = R-normalised PF. DD at 0.5 % risk. tw = trades/week.

| Strategy | Combos | IS-selected setting (exit) | IS n / WR / PF / PF(R) / DD% / tw | VAL n / WR / PF / PF(R) / DD% / tw | OOS n / WR / PF / PF(R) / DD% / tw | Verdict |
|---|---|---|---|---|---|---|
| reopen_gap_fade | 279 (120+159) | g_min 0.1, delay 60, exit 03:00, include_daily (card exit) | 62 / 56.5 / 1.27 / 0.90 / 3.0 / 1.28 | 39 / 48.7 / 0.72 / 0.71 / 3.5 / 1.92 | – | REJECT (IS); follow control also loses |
| gold_silver_residual | 267 pre-fix + 267 rerun = 534 | N 24, S_in 3.0, w 1.0, S_out 0.0 (card exit) | 81 / 46.9 / 1.28 / 1.12 / 3.9 / 1.59 | 37 / 32.4 / 0.80 / 0.64 / 7.9 / 2.12 | – | REJECT (IS, after bug-fix rerun) |
| vr_kalman_regime | 240 (81+159) | q 12, vr_band 0.25, z_in 2.5, both (fixed sl 1.5 / tp 3.0) | 87 / 59.8 / 1.73 / 1.66 / 3.0 / 1.70 | 40 / 55.0 / 0.79 / 0.88 / 2.3 / 2.19 | – | REJECT at VAL |
| tick_intensity_follow | 267 (108+159) | zN 4, imb 0.1, s_cap 1.5, hold 10, follow (card exit) | 291 / 43.0 / 0.90 / 0.77 / 21.0 / 6.06 | 95 / 35.8 / 0.72 / 0.58 / 14.9 / 4.75 | – | REJECT (IS) |
| usd_impulse_catchup | 294 (135+159) | W 30, k 4.0, hold 30, leader XAGUSD (fixed sl 2.0 / tp 2.0) | 94 / 59.6 / 1.99 / 1.76 / 1.06 / 1.89 | 22 / 45.5 / 2.13 / 1.67 / 0.48 / 1.22 | 12 / 33.3 / 0.25 / 0.35 / 0.79 / 0.71 (stress PF 0.25) | **OOS FAIL** (final) |
| common_factor_residual | 267 (108+159) | EntryZ 1.5, Zwin 16, ExitZ 0.3, members XAU,XAG,EURUSD (card exit) | 371 / 48.2 / 1.09 / 1.01 / 12.8 / 7.44 | 112 / 51.8 / 0.94 / 1.06 / 4.4 / 5.33 | – | REJECT (IS) |
| riskoff_rebound | 267 (108+159) | W 30, kN 2.0, kG 2.0, hold 120, mirror on (card exit) | 83 / 68.7 / 1.30 / 1.23 / 3.1 / 1.75 | 50 / 66.0 / 0.86 / 1.00 / 2.7 / 2.40 | – | REJECT (IS) |

**No D1 strategy passes the gates.** No setting met WR > 75 % / PF > 3 / DD < 5 % on IS (the harness
reported 0 IS gate passers for every strategy). Only usd_impulse_catchup qualified for freeze + OOS,
and it failed OOS.

### Per-strategy details

**reopen_gap_fade** (card r2-reopen-gap-fade)
- Screen (card defaults g_min 0.5, delay 30, 07:00, weekend/holiday only): IS n 7, PF 0.42, PF(R) 0.66. VAL n 10.
- Count: at the card's g_min 0.3–1.0 there are only 7–30 IS+VAL trades. Daily-break gaps are almost
  always < 0.3 × ATR14(1h). So g_min 0.1 and 0.2 were added as count variants, and delay 120 was dropped to keep within budget.
  Only g_min 0.1 with include_daily reaches n_IS ≥ 60 (12 eligible stage-1 rows).
- No template reached a neighbour median ≥ 1.3, so the card exit was kept. Best IS PF(R) of any row with n ≥ 60: 1.33.
- Long/short (IS, finalist): long 12 PF(R) 0.82, short 50 PF(R) 0.92.
- **Follow-the-gap control** (same entries, opposite side, same distances), IS:
  - finalist: n 62, WR 50.0, PF 0.67, PF(R) 0.76;
  - card defaults: n 7, PF(R) 1.28.
  - Neither fade nor follow works on IS, so the idea is dropped, as the card says.

**gold_silver_residual** (card r2-gold-silver-residual-revert)
- **Bug and rerun.** The first run coded the target |S| ≤ S_out literally, so S_out = 0 never fired
  and the S_out = 0 rows had no score target. Pre-fix finalist (same setting; scalp_be sl 1 / tp1 0.5 /
  f1 0.5 / tp 1.5 / BE): IS PF(R) 1.67, VAL n 36, PF 1.29, so it would have closed at VAL.
  The fix (S back to −S_out or beyond = crossing) is a code defect, not a VAL-driven change. Pre-fix grids are kept as
  `results/gold_silver_residual_opt*_prefix.csv`. The rerun, under the same rule, picks the same setting with the card exit
  (only one template was eligible: trail sl 2 / trail 1.5, PF(R) 1.065 < card 1.12). IS PF(R) 1.12, so rejected on IS.
  Its VAL row (PF 0.80) is shown for completeness only.
- Screen (rerun): IS n 388, WR 43.6, PF 0.86, PF(R) 0.88, 7.6/wk (card: 1–3 per day before filters). VAL PF 1.04.
- Long/short (IS, rerun finalist): long 43 PF(R) 1.90, short 38 PF(R) 0.67.
- Silver-leg diagnostic (card note): mean per-trade log return, IS
  - gold leg: +4.3 bp;
  - silver leg traded opposite: −15.4 bp.
  - The spread did not converge through silver; the gold-leg gains are directional (long side, 2025 trend).
- The finalist sits at a grid corner (N 24, S_in 3.0, w 1.0).

**vr_kalman_regime** (card r2-vr-regime-kalman-revert)
- Screen: IS n 213, WR 54.5, PF 0.92, PF(R) 0.88, 4.2/wk (card 1–2 per day while a regime is active). VAL PF 0.95.
- Card vr_lo/vr_hi are parametrised as a symmetric vr_band (0.10/0.15/0.25 covers both card grids).
  snr 0.01, L_vr 576 and z_stop 3.5 are fixed at card defaults (budget).
- The finalist is a grid corner. Card exit IS PF(R) 1.54; template fixed sl 1.5 / tp 3.0, with neighbour median 1.455.
- Splits:

  | Split | IS | VAL |
  |---|---|---|
  | long | n 48, PF(R) 1.87 | n 26, PF 0.80 |
  | short | n 39, PF(R) 1.45 | n 14, PF 0.74 |
  | REVERT branch | n 59, PF(R) 1.27 | n 37, PF 0.74 |
  | TREND branch | n 28, PF(R) 2.26 | n 3 |
- Benchmark: regime gate off (unconditional Kalman-z fade, same exit), IS n 513, PF 0.92, PF(R) 0.87. The VR gate helps in IS
  but does not hold in VAL.
- Neighbourhood note: regime_branch is a structural key and is part of the harness plateau.

**tick_intensity_follow** (card r2-tick-intensity-imbalance-follow)
- Card default imb_min 0.3: IS n 8 (0.26/wk, against the card's 1–4 per day). On Dukascopy quotes the 1m IMB has
  sd 0.097, and |IMB| ≥ 0.3 occurs in 0.2 % of zN ≥ 3 bars. imb_min was recalibrated to 0.1/0.15/0.2 (disclosed in
  the module). s_cap 1.2 was dropped for budget.
- Finalist IS PF(R) 0.77. Best of any row: follow 0.91, fade_wide 0.49.
- Long/short IS: long 164 PF(R) 0.62, short 127 PF(R) 1.02.
- Zero-cost run of the finalist: IS PF(R) 1.16. That is a small pre-cost edge, well below cTrader costs, consistent with T3. fade_wide at zero cost: PF(R) 0.73.

**usd_impulse_catchup** (card r2-usd-impulse-catchup) — frozen, OOS FAIL (final)
- Screen at card defaults (USD2, W 10, k 3, hold 30): IS n 233, WR 53.7, PF 0.67, PF(R) 0.68, 4.7/wk (card 2–6). VAL PF 0.81.
- Fixed: rho_max 0.5, corr_max −0.2 (sign-adjusted to ≥ +0.2 for XAGUSD/USATECH, because their correlation with gold is positive), news_skip on.
  stop_mult and tgt_frac are exit-only and were left to the templates.
- Finalist: leader XAGUSD, W 30, k 4.0, hold 30 min.
  - Card exit: IS PF(R) 1.265.
  - Template fixed sl 2.0 / tp 2.0: IS PF(R) 1.758. 52 of 53 templates had neighbour median ≥ 1.3.
- IS PF(R) 1.76 ≥ 1.3 and VAL PF 2.13 ≥ 1.3, so it was frozen (commit 01c6bcd, before OOS).
  - Code hash v3 1e501d2caf57ac97 (covers `_d1util.py`, sha256[:16] 289fc7dab1b30ac0, which is unchanged since then).
  - Neighbourhood median IS PF: 1.11 (harness, including the categorical leader neighbour USDJPY), 1.38 numeric keys only.
    Both are below the 2.0 robustness gate.
- **OOS (single run): n 12, WR 33.3, PF 0.25, PF(R) 0.35, DD 0.8 %; stress PF 0.25. FAIL.**
  - OOS long 5 (WR 60, PF 0.23), short 7 (WR 14, PF 0.29).
- Long/short: IS long 44 PF(R) 1.30, short 50 PF(R) 2.25. VAL long 11 PF 8.78, short 11 PF 0.53.
- Benchmarks (IS, same entries and exit):
  - side flipped: PF(R) 0.42;
  - always long: PF(R) 0.62;
  - random side: median PF(R) 0.95 over 20 draws (95th percentile 1.24).
  - The IS signal was real relative to chance in IS, but it did not hold in OOS.
- Frozen params: `{"W_min": 30, "k": 4.0, "hold_min": 30, "leader": "XAGUSD"}`, exit `{"sl": 2.0, "tp": 2.0}` (× unit = native stop).

**common_factor_residual** (card r2-common-factor-residual-m15)
- Fix before optimise: the first screen blanked the cumulative residual for Zwin bars after every break, because
  returns across a gap were NaN (Z finite on only 60 % of bars, IS n 69, PF(R) 0.76). Returns across the break are now kept,
  and a missing residual adds 0. Only the fixed version was optimised.
- Screen (post-fix): IS n 111, WR 42.3, PF 0.65, PF(R) 0.69, 2.25/wk. VAL PF 2.28.
- Frequency against the card's 3–6/wk: 4.2 crosses/wk pass the filters, but positions last about 3 h, one at a time.
- Entry needs a fresh cross of ±EntryZ (documented).
- Finalist PF(R) 1.01. Best IS PF(R) of any row: 1.11.
- Long/short IS: long 207 PF(R) 0.98, short 164 PF(R) 1.04.
- Brent was used only in the 5-member variant (data arrived before the optimise).

**riskoff_rebound** (card r2-riskoff-coliquidation-rebound)
- Screen (card defaults, long only): IS n 43, WR 76.7, PF 1.69, PF(R) 1.69, 0.9/wk (card 2–5 per month). VAL n 25, PF 0.82.
- Long-only settings reach n_IS ≥ 60 only at the loosest thresholds. Most eligible rows use mirror on (adds the risk-on short).
- Finalist (mirror on) IS PF(R) 1.23, so rejected on IS. Best of any row: 1.57.
- Long/short: IS long 53 PF(R) 2.02, short 30 PF(R) 0.63. VAL long 28 PF 0.93, short 22 PF 0.76.
- Benchmark (IS, long only, W 30, kG 2):
  - with the Nasdaq condition (kN 2): n 59, PF(R) 1.93;
  - gold-only sell-off rebound (no Nasdaq condition): n 174, PF(R) 1.33.
  - So the co-liquidation condition adds something in IS, but only on fewer than 60 trades.
- Not done: USA500 as the risk proxy (card param). It was not in the grid, and its data arrived after the run.

### Protocol notes
- The selection rule and selector were committed (c414e82) before any D1 grid.
- The harness `optimise` log prints a top-15 table that includes VAL columns. Only the summary line was read.
  Finalists were picked with `research/d1_select.py` on IS columns, and VAL was printed only for each finalist.
- Exploratory IS-only runs before the grids (reopen count checks at g_min 0.1–0.2, the tick IMB distribution, and the
  common_factor frequency diagnosis) used no VAL data.
- News filters use the verified calendar (`data/calendar/us_macro_2025_2026.csv`, which has no tier column). The D1
  tier-1 set is NFP, CPI, PPI, FOMC statement, retail sales, GDP advance, PCE, ISM manufacturing/services and JOLTS.
  "Any release" filters (usd_impulse_catchup, tick_intensity_follow) use every row.
- Each screen ran once. gold_silver_residual's first screen used a DST proxy before the calendar landed, and it was re-screened on the calendar.

### Post-review notes (boss review research/reviews/batchD1.md: ACCEPT, documentation only)
- **riskoff_rebound variants are closed.** The long-only variant (e.g. W 30, kN 2, kG 2: IS PF(R) 1.93 on n 59)
  and a USA500-proxy variant (card param, never run) are closed and are not to be revived under any id.
  riskoff_rebound's verdict (REJECT on IS) is final.
- **gold_silver_residual post-fix VAL row.** The post-fix finalist was already rejected on IS
  (IS PF(R) 1.12 < 1.30) before its VAL row (PF 0.80) was printed. That row informed no decision; it is
  shown for completeness only.
