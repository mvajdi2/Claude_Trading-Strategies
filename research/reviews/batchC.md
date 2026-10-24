# Batch C review (boss), 2026-10-24

Inputs reviewed:
- `research/results_batchC.md` and registry rows C1–C12
- `results/<id>_opt_stage1.csv`, `_opt_exits.csv` and `_trades.csv`
- the code of all Batch C modules
- `strategy_cards/ema_pullback_adx.frozen.json` and `avwap_london.frozen.json`, with git history

I re-derived every finalist from the CSVs using IS columns only. For each strategy I also computed
the finalist the protocol's top-plateau rule would have produced, for comparison.

## Early-audit REDOs: all implemented, and implemented correctly

| Item | Check |
|---|---|
| last30 vol filter | Now the true realised vol: the sum of squared 1m log returns from the 18:00 NY session open to the signal bar, with the cross-session return removed, compared with the median of the prior 60 sessions (`shift(1)`). Correct and causal. |
| last30 holidays | `US_SKIP` lists every 2025–26 NYSE/CME holiday and early close. Spot-checked: 2025-01-09, 2025-04-18, 2026-04-03 (Good Friday), 2026-06-19, 2026-07-03. Correct. |
| last30 20:55 | "close" = 20:55 UTC explicitly. Correct. |
| holy_grail overnight cap | Trigger window capped at 20:00 UTC on the setup day. `hold` runs to 20:55. No same-session decision after 20:59. Correct. |
| holy_grail structural stop | Stop = min(setup low, lowest 1s low from the bar close to the trigger second) − (lvl − swing), floored at 0.2 ATR. `unit` = that stop. Causal: the low of the trigger second is known at the end of that second. Correct. |
| ema_pullback_adx | `exit_mode` removed. `unit` = the structural stop. The native exit is the card's trail + BE. `hold` runs to 20:45. Correct. |
| vwap_cross_mtf | `stop_atr` removed from PARAMS. Signals start ≥ 1 bar after the same-day anchor. `hold` runs to 20:45. Correct. |
| fomc_drift | Screen only. The 120-combination pre-audit optimise was discarded. Dates were re-verified against federalreserve.gov. Correct. |
| asian_drift duplicates | lookback = 0 × t_min ≠ default returns no signals (counted, empty). Acceptable; the stage-1 count of distinct settings is disclosed (191). |
| tsmom benchmark + VAL split | Done. The benchmark (long every weekday, same stop and exit) has IS PF(R) 1.55, against 1.56 for the strategy, so the filter adds nothing. VAL split: long 87 trades, PF 0.73; short 8 trades, PF 0.97. Correct and honest. |
| macro_shock | Documented skip (see point f). |
| X5 / other | Explicit 20:55/20:45 exits; avwap fade uses the i−1 band; tsmom RS uses full days only (≥ 144 5m bars). |

## Points the coordinator asked about

**(a) The finalist rule was "top IS PF(R), n_IS ≥ 60", not the top plateau. Does it matter?**
It is a protocol deviation, but **no verdict changes**. I compared the two rules:
- **Same setting under both rules:** last30, first_last_hh, pmfix, holy_grail, supertrend_rsi and
  vwap_cross_mtf. Only the exit tie-break differs. The verdicts are unchanged (rejected on IS, or
  at VAL).
- **tsmom_day:** the report actually used the plateau setting (20_100, card exit, IS PF(R) 1.56),
  not its own rule's top row (10_50, 1.58). That is inconsistent with its stated rule, but it
  matches the protocol. VAL rejection.
- **asian_drift:** the plateau finalist would have been lookback 120 (best IS PF(R) 1.50) rather
  than lookback 250. Its VAL was already contaminated before the audit, so no new look is possible,
  and both settings are the same long-only day-leg beta in IS. Closed.
- **ema_pullback_adx:** the plateau finalist would have been adx 25 / stop_atr 1.0 (best IS PF(R)
  1.60). The strategy has been OOS-run, so it is final under the hard rule, and its OOS (PF 0.99)
  is far from the gates anyway.
- **avwap_london:** the plateau finalist (trend_frac 0.6) has a best IS PF(R) of only 1.16. Under
  the protocol, avwap_london would have been **rejected on IS and never frozen**. Its freeze used a
  peak (neighbourhood median IS PF 0.97, which the agent disclosed). The OOS run therefore tested a
  peak-picked setting. Nothing was tuned on OOS and the verdict is FAIL, so the outcome is unharmed.
  It is recorded here as a deviation.
- **Conclusion:** rerunning with the correct rule would need new VAL looks (and for two strategies,
  new OOS runs) on strategies already looked at. That is not allowed, and it could not reach the
  WR > 75 / PF > 3 gates on this evidence anyway.

**(b) asian_drift's VAL was seen before the audit.** Acceptable as handled. The rerun selected by an
IS rule and arrived at the same setting, and the report states the contamination openly. The
strategy is closed, with no further VAL use. The IS edge is long-daytime beta: the adaptive sign was
long on all 112 IS days.

**(c) Stage-2 slots used on n_IS < 60 settings before affb4d3.** Acceptable. In every affected case
(last30, first_last_hh, tsmom_day, holy_grail, avwap_london), the setting the agent chose as
finalist had its full 53 templates. Only the alternative slots were lost. Refilling them now would
be a rerun after VAL has been seen. The holy_grail rows with IS PF(R) ≈ 22 come from the n = 14
1h setting and were correctly excluded.

**(d) pmfix rerun after the `exit` column collision.** Legitimate. It was a genuine harness defect:
the strategy's `exit` parameter was overwritten by the template-name column, so the first run lost
the parameter (24 rows, no stage 2). The parameter was renamed `exit_at` and the strategy rerun.
Only the rerun was used, and the 24 broken rows are counted. The single finalist VAL look (follow,
a 1.0, 20:55, fixed sl 2 / tp 2: IS PF(R) 1.82, VAL PF 1.09) is final. The exit is the centre of the
tp 1.5 / 2.0 / 3.0 tie (1.81 / 1.82 / 1.90), an IS-only choice.

**(e) ema_pullback_adx: frozen because of IS, or because of its strong VAL?** From the CSV:
- **Best IS row:** scalp_be with sl 1.0 (IS PF(R) 1.812, VAL PF 2.69).
- **Frozen row:** sl 2.0 (IS PF(R) 1.797, VAL PF 3.35). The sl 3.0 row has IS PF(R) 1.585.
- **Why sl 2.0 can be justified on IS:** it is the centre of the sl 1/2/3 row, with neighbours
  1.81 and 1.58, and the frozen note says "sl 1.0/2.0 neighbours equal".
- **Can't be proven:** the tie was broken toward the row with the better VAL. I cannot prove
  whether VAL influenced that choice.
- **Why the verdict is unaffected:** the freeze decision itself does not depend on the tie-break.
  Both rows have IS PF(R) ≥ 1.3 and VAL PF ≥ 1.3, so protocol required a freeze either way.
- **Freeze while IS PF 1.57 < 3:** correct. The freeze/OOS qualifier is IS PF(R) ≥ 1.3 and
  VAL PF ≥ 1.3, not the pass gates.
- **Order:** the freeze was committed (a421a6a, 00:19:53, `oos_run: false`, v3 hash 5be4739bce5e9c13,
  which still matches) before OOS (00:20:20).
- **Recommendation:** for any future tie, fix the tie-break rule in advance (for example, the
  centre of the tied family, or the lower sl).

**(f) macro_shock skipped because bls.gov blocked the schedule.** Acceptable. batches.md says to
implement it "only if NFP/CPI release dates can be listed reliably; otherwise skip and say so". The
agent documented the 403 bot block and the 2025 shutdown-disrupted calendar, which makes dates from
memory unreliable. Nothing was invented. If the user wants it later, they can supply a verified
release calendar file and it goes through the full pipeline as a new idea.

---

## Per-strategy verdicts

### last30_momentum — ACCEPT (reject at VAL)
The fixes are correct. Card defaults have IS PF(R) 0.68. The finalist (k 0.25, vol filter on, 20:55,
scalp_be) has IS PF(R) 1.41 and VAL PF 0.73, so it is rejected. The high IS WR (89.8) is the scalp+BE
artefact.

### first_last_hh — ACCEPT (reject on IS)
Best IS PF(R) 1.24 (18:00 NY window, vol pct 75), below 1.3.

### asian_drift — ACCEPT (reject at VAL; VAL contaminated before the audit, disclosed)
In IS it is long-daytime beta (100 % long). VAL PF 0.75. See points (a) and (b).

### pmfix — ACCEPT (reject at VAL)
The card's fade loses in IS. Follow: IS PF(R) 1.82, VAL PF 1.09. See point (d).

### fomc_drift — ACCEPT (ineligible by trade count)
6 IS trades. Screen only. Not frozen. Correct.

### tsmom_day — ACCEPT (reject at VAL)
IS is 100 % long and equals the benchmark. VAL PF 0.74. This is honest reporting of a beta effect.

### holy_grail — ACCEPT (reject at VAL)
The overnight cap and swing stop are correct. Finalist: IS PF(R) 1.36, VAL PF 0.87. Frequency is
about 1 trade per week against the card's ~2.5, which is explained by the first-touch-per-episode
rule.

### ema_pullback_adx — ACCEPT (OOS FAIL, final)
OOS: 40 trades, WR 80.0, PF 0.99. Stress PF 1.00. See points (a) and (e).

### supertrend_rsi — ACCEPT (reject on IS)
Best IS PF(R) 1.09 with 385 trades.

### vwap_cross_mtf — ACCEPT (reject on IS)
Best IS PF(R) 1.08.

### avwap_london — ACCEPT (OOS FAIL, final; frozen under the deviating rule, see point a)
- IS PF 1.20, VAL PF 1.35, OOS PF 1.56 (61 trades, WR 45.9). Stress PF 1.52.
- It is positive in all three periods but has a flat neighbourhood (0.97) and is far below the
  gates.
- The freeze commit (a421a6a) precedes OOS (00:20:31), and the hash still matches.

### macro_shock — ACCEPT (skipped, documented)

## Summary table

| Strategy | Verdict | One-line reason |
|---|---|---|
| last30_momentum | ACCEPT (reject at VAL) | fixes correct; VAL PF 0.73 |
| first_last_hh | ACCEPT (reject on IS) | IS PF(R) 1.24 |
| asian_drift | ACCEPT (reject at VAL) | long beta in IS; VAL 0.75; VAL pre-seen and disclosed |
| pmfix | ACCEPT (reject at VAL) | rerun after the column bug was legitimate; VAL 1.09 |
| fomc_drift | ACCEPT (ineligible) | 6 IS trades |
| tsmom_day | ACCEPT (reject at VAL) | equals the long-daytime benchmark; VAL 0.74 |
| holy_grail | ACCEPT (reject at VAL) | VAL 0.87 |
| ema_pullback_adx | ACCEPT (OOS FAIL, final) | OOS PF 0.99 |
| supertrend_rsi | ACCEPT (reject on IS) | IS PF(R) 1.09 |
| vwap_cross_mtf | ACCEPT (reject on IS) | IS PF(R) 1.08 |
| avwap_london | ACCEPT (OOS FAIL, final) | OOS PF 1.56, WR 46; peak-picked (protocol deviation) |
| macro_shock | ACCEPT (skipped) | release dates not verifiable |

## Instructions for the Batch C agent

**ACCEPT – no further work.** No reruns, no freezes, no VAL or OOS looks.

Documentation only:
1. In `results_batchC.md`, state that the finalist rule used (top IS PF(R)) deviated from the
   protocol's top-plateau rule. List the plateau-rule finalists: asian_drift lookback 120;
   ema_pullback_adx adx 25 / stop_atr 1.0; avwap_london trend_frac 0.6, which would have been
   rejected on IS. Note that tsmom_day's reported row is the plateau row. Do **not** report VAL
   figures for those alternative rows.
2. ema_pullback_adx: state how the sl 1.0 vs 2.0 tie was broken (centre of sl 1/2/3), and that the
   freeze decision did not depend on it.

---

# Overall conclusion across Batches A, B and C (for the final report)

1. **No strategy passes the gates.** No idea meets WR > 75 %, PF > 3, DD < 5 % with ≥ 100 IS+VAL
   and ≥ 25 OOS trades on unseen data. Under the honesty clause, the deliverable is the frontier,
   not a candidate list. `research/ctrader_candidates.md` should say "no candidates".
2. **What was tested.**
   - 33 batch ideas (A 11, B 10, C 12), with several split into separate ids during review. ICT/SMC
     ideas were excluded as the user instructed (silver_bullet, taylor_sweep and the sweep
     variants).
   - Rejected on IS (best IS PF(R) < 1.3) or at their single VAL look: the large majority.
   - Ineligible by trade count: 3 (idnr4_breakout, raschke_8020, fomc_drift).
   - Skipped: macro_shock, documented.
   - Reached OOS: 6 frozen ids (asian_range_breakout, london_range_ny_break, ib_fade_ny,
     bb_pinbar_fade, ema_pullback_adx, avwap_london). All 6 **FAIL**.
3. **OOS frontier.** Profitable but nowhere near the gates:

   | Id | OOS PF | OOS WR | OOS trades | Stress PF |
   |---|---|---|---|---|
   | asian_range_breakout | 2.11 | 69 % | 16 | 2.10 |
   | ib_fade_ny | 1.88 | 53 % | 32 | 1.86 |
   | avwap_london | 1.56 | 46 % | 61 | 1.52 |

   High-WR settings exist only through scalp + break-even exits (tp1 = 0.25–0.5R). Examples:
   ema_pullback_adx (OOS WR 80 %, PF 0.99) and pdh_pdl (IS WR 94 %, VAL PF 0.60). In those
   settings, PF depends on rare runners and collapses out of sample.
4. **Structural findings.**
   - The WR > 75 % and PF > 3 gates together require an average win/loss ratio of about 1 or more
     at 75 % WR. None of the intraday XAUUSD ideas tested (breakout, reversal, time-of-day, trend
     pullback) produces this after realistic cTrader costs.
   - The time-of-day "edges" (asian_drift, tsmom_day, pmfix follow) are 2025 bull-trend beta. They
     equal a long-daytime benchmark in IS and reverse in 2026.
   - The round-number effect equals its placebo.
   - This agrees with the registry's earlier observation that candidates degrade from June 2026.
5. **Process integrity.**
   - Every OOS freeze was committed before its OOS run, and no strategy was re-tuned after OOS.
   - Harness defects were found in review and fixed in the harness:
     - card exits not searched;
     - random sampling;
     - list-order neighbours;
     - helper files missing from the freeze hash;
     - plateau ranking with n_IS < 60;
     - the `exit` column collision.
   - Reruns were limited to genuine defects, each with a single final VAL look.
   - Remaining deviations are documented and change no verdict: Batch C's top-PF(R) finalist rule,
     and asian_drift's VAL seen before the audit.
6. **Recommendation.** Report the frontier honestly. Do not loosen the gates or move the splits
   without the user's explicit approval. If the user wants to continue, the only defensible
   directions are:
   - materially new ideas (for example the deferred EURUSD-residual card, or macro_shock with a
     user-supplied verified release calendar) run through the full pipeline;
   - or an explicit user decision to relax the WR/PF gates. ib_fade_ny and avwap_london would then
     be the starting points, and they would need fresh, untouched data, because their current OOS
     has been used.
