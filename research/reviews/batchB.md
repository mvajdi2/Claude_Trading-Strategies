# Batch B review (boss), 2026-10-24

Inputs reviewed:
- `research/results_batchB.md` and the Batch B section of `research/tested_registry.md`
- `results/<id>_opt_stage1.csv`, `_opt_exits.csv` and `_opt_exits_extra.csv` for all Batch B modules
- `results/batchB_redo_diag.txt` and `results/batchB_opt2.txt`
- `strategy_cards/bb_pinbar_fade.frozen.json`, with its git history
- the code of the Batch B modules and `strategies/_bxutil.py`

I re-derived every reported finalist from the CSVs.

## Overall judgement

- **Early-audit REDOs: all implemented, and implemented correctly.**
  - **Re-arm fix (`_bxutil.fakeout_core`).** I traced the logic.
    - Once an excursion reaches `max_bars_outside` while still outside, it is marked `expired`, and
      the next close back inside cannot trade.
    - A new break can only arm after that close back inside. The stop uses the full excursion
      extreme.
    - A close through the whole range skips the day.
    - The edge case `max_bars_outside = 1` behaves correctly.
    - The module was split into an H1 id and a 15m id. The 15m id has its card's defaults (16:00
      exit, stop_buf 0.1, max bars 4/8/16) and the range filter, which uses the last closed H1 ATR.
  - **Turtle Soup stop anchoring.** `sl = side*(mid_at(k) − ext) + 0.1·ATR` is now measured from
    the price at the decision second. Immediate triggers (52%) are reported, with an `immediate`
    column.
  - **NY blackout.** `_bxutil.ny_blackout` uses America/New_York and is DST-aware. It is used by
    level_sweep_reclaim and round_level (08:00–09:00 and 09:45–10:30 NY) and by rsi_extreme_fade
    (08:25–08:35 and 09:55–10:05 NY).
  - **round_level placebo.** A matched real-vs-placebo comparison is reported: median IS PF(R) 0.804
    vs 0.800. There is no round-number effect. This is good control work.
  - **wyckoff frequency.** It is explained filter by filter: the low-volume rule, the 2.5×ATR15
    width cap and the two-touch rule together give 16 trades, and relaxing all three gives 262.
    The relaxed settings were in the stage-1 grid.
  - **raschke_8020.** Screen only (X7): 28 IS trades for the card version. The oops variant has IS
    PF(R) 0.76, so no grid was run. Correct.
  - **rsi_extreme_fade frequency.** Explained: the card's 3–8 per day holds only without the EMA200
    filter.
- **ICT/SMC exclusion: complied with.**
  - There are no silver_bullet or taylor_sweep modules.
  - The Judas/FVG, PDH/PDL-sweep and previous-candle-sweep variants were dropped and the drops are
    documented.
  - `level_sweep_reclaim` contains only the Turtle Soup N-bar channel. "FVG", "order block" and
    "killzone" appear in no Batch B module. "Judas" appears only in a docstring that says it was
    dropped.
- **Cross-cutting items: complied with.**
  - Numeric PARAMS are sorted, with categorical switches last.
  - There are no exit-only PARAMS keys, and `unit` is the structural stop (X4).
  - Time exits are explicit, and no same-session decision falls after 20:59 UTC (X5).
  - The `_bxutil.py` sha256 (4d6700a43bb1ecec) is in the bb_pinbar freeze note and matches the
    current file. The file is unchanged since 4cd56de (X6).
- **Reporting honesty: good.** Every "best IS-selected" row matches the CSVs, and the verdicts are
  not softened. There are two small inconsistencies (see the report fixes at the end).
- **Harness issue (stage-2 plateau ranking ignored `n_IS`).**
  - It hit bb_pinbar_fade (all 3 plateau settings had n_IS 10–21) and rsi_extreme_fade (all 3 had
    n_IS 0).
  - It partly hit mp_80pct (2 of 3 settings had n ≈ 30) and wyckoff_spring (1 of 3 had n = 31).
  - It is fixed in affb4d3. Its effect on each strategy is judged below.

---

## asian_range_fakeout (H1) — ACCEPT (reject)
Findings: the code is fixed and faithful (see above). The defaults were re-screened: IS PF(R) 0.63.
In stage 1 (96 combos), the best plateau with n ≥ 60 is 0.84, and no stage-1 row reaches PF(R) 1.0.
The best stage-2 row is IS PF(R) 1.07, which is < 1.3, so it is rejected on IS. The VAL figure
shown is the final look. 255 combos were counted.

## asian_range_fakeout_15m — ACCEPT (reject)
Findings: faithful to the practitioners card. The best plateau is 0.83. The best stage-2 row is
scalp+BE with 92.7% WR but IS PF(R) 1.12, the familiar exit artefact. Rejected on IS. 267 combos.

## level_sweep_reclaim (Turtle Soup) — ACCEPT (reject)
Findings: stop anchoring and the news blackout are fixed. Stage-1 plateaus are all ≤ 0.73, and the
best stage-2 row has IS PF(R) 0.96. A clean rejection.
Report fix (no rerun): the diagnostic file prints "median cost $0.070, cost/R 2.6%", while the
report says about $0.24 and about 5.7% of R. The report's figure matches the cost model
(0.10 + 2×0.03 + 0.07). The diagnostic's figure looks like commission only. Correct the diagnostic
line, or annotate it in the report. The conclusion (cost is not the reason it fails) holds either
way.

## raschke_8020 — ACCEPT (reject; ineligible by trade count)
Findings: handled per X7. 2 screen runs and no grid.

## wyckoff_spring — ACCEPT (reject)
Findings: the frequency gap is explained. Of the stage-2 settings, 2 of 3 had n ≥ 60
(72 / 5.0 / none / stop and 72 / 5.0 / none / close). The third (n = 31) produced IS PF(R) up to 5.17,
which was correctly ignored as an n < 60 artefact. The reported finalist (24 / 5.0 / high / close,
card exit, IS PF(R) 1.25) is the best stage-1 row by PF(R), **not** the top plateau setting, so it
breaks the stated rule. It is harmless: every candidate is below IS PF(R) 1.3, so no VAL decision
depended on it. Fix the wording in the report (see below).

## mp_80pct — ACCEPT (reject)
Findings: faithful and causal. Only 1 of the 3 stage-2 settings had n ≥ 60 (harness issue). That one
setting is the top n ≥ 60 plateau (0.68 / 2 / 23:00 / tick-volume), which is what the fixed harness
would also rank first, so the selection-relevant setting was covered. Its best stage-2 row is IS
PF(R) 1.20, which is < 1.3.
I do **not** ask for stage 2 to be rerun on settings #2 and #3:
- IS evidence is weak everywhere (stage-1 PF(R) ≤ 1.16, plateau ≤ 1.08).
- The finalist's VAL has already been seen (PF 1.72). A rerun now would be motivated by that VAL
  number.
- The rerun would also take the count over budget (195 + 106).

## bb_pinbar_fade — ACCEPT (OOS FAIL, final)
Findings:
- Code: faithful and causal (early audit).
- Harness defect and the manual extra stage 2:
  - The harness ran stage 2 on three settings with n_IS 10–21, which is useless.
  - The agent then ran an extra stage 2 (53 templates) on the best plateau setting with n ≥ 60:
    bb_dev 2.5, wick_body 1.5, EMA filter on, 5m, plateau 1.13. That is exactly the setting the
    fixed harness now ranks first. So the extra run corrected a harness defect and was decided from
    IS ranking, not from VAL.
  - The exit was chosen as the centre of the IS plateau of fixed sl 1.0R: tp 1.5, 2.0 and 3.0 give
    IS PF(R) 1.41, 1.40 and 1.45, and tp 2.0 was chosen. That is an IS-only, plateau-centred choice.
  - Counting: 195 + 53 = 248 was counted correctly.
- Qualification: IS PF(R) 1.40 ≥ 1.3 and VAL PF 2.13 ≥ 1.3. Freezing it and running one OOS was
  required by protocol, and that is what was done.
- The freeze commit (4cd56de, 00:10:20, `oos_run: false`) precedes the OOS run (00:10:42), under
  the v2 hash scheme in force at the time. The strategy file and `_bxutil.py` are unchanged since.
- OOS: 33 trades, WR 39.4, PF 0.52, PF(R) 0.71. Stress PF 0.35, DD 7.0. **FAIL, final.**
- The freeze-time robustness median (0.99) includes the `ema_filter` and `tf` switches. The stage-1
  plateau score (1.13) is the better indicator, and it is also weak. Both are reported honestly.
Instructions: none.

## rsi_extreme_fade — ACCEPT (reject)
Findings:
- The NY blackout fix and the `one_per_episode` variant are correct. The frequency is explained.
- Harness defect: all three stage-2 settings had 0 IS trades, so the normal stage 2 was empty.
- The extra stage 2 (53 rows) was run on the best plateau setting with n ≥ 60 (5m, RSI 20, no EMA
  filter, hold 60, one per episode). IS-only and correctly counted: 72 + 53 = 125.
- Inconsistency: the reported finalist is a *different* row (hold 120, card exit, IS PF(R) 1.17),
  which is the best stage-1 row by PF(R). The best extra stage-2 row is 1.16.
- It is harmless: everything is below 1.3, so it is rejected on IS whichever rule is applied.
- Fix the wording in the report (see below).

## vwap_sd_fade — ACCEPT (reject)
Findings: stage-1 plateaus are ≤ 0.88 and the best stage-2 row has IS PF(R) 0.97. A clean rejection.

## overreaction_fade — ACCEPT (reject at VAL)
Findings: the best stage-2 row is scalp+BE sl 3, tp1 0.5, f 0.5, tp 1.5, with IS PF(R) 1.32 and
n 140, so it qualified for its one VAL check. VAL PF was 1.12, below 1.3, so it was rejected. Its
adjacent templates (f 0.7: 1.30; tp 3.0: 1.26; tp1 0.25: 1.25) sit right at the threshold, so this
is a marginal IS edge at best. The rejection is correct and final.

## round_level — ACCEPT (reject at VAL)
Findings:
- Placebo design: the harness's top-2 plateau settings were placebo rows (offset 10.37). The agent
  correctly refused to trade a placebo. It took the best real-level setting (step 50, break,
  momentum 1.0, hold 240, news skip), whose IS PF(R) of 1.45 comes from a scalp+BE exit. That
  setting's single VAL check gave PF 0.36, so it was rejected.
- Design note for future batches: a placebo offset should be a separate control run, not a key in
  the searchable grid. Here it wasted 106 stage-2 rows and polluted the plateau neighbourhoods.
- The matched comparison (real 0.804 vs placebo 0.800) is the decisive result: there is no level
  effect.

---

## Summary table

| Strategy | Verdict | One-line reason |
|---|---|---|
| asian_range_fakeout | ACCEPT (reject) | re-arm fix correct; best IS PF(R) 1.07 |
| asian_range_fakeout_15m | ACCEPT (reject) | faithful 15m card; best IS PF(R) 1.12 (scalp artefact) |
| level_sweep_reclaim | ACCEPT (reject) | stop anchoring and blackout fixed; best IS PF(R) 0.96 |
| raschke_8020 | ACCEPT (reject) | ineligible by trade count (X7) |
| wyckoff_spring | ACCEPT (reject) | frequency explained; best IS PF(R) 1.25 |
| mp_80pct | ACCEPT (reject) | top plateau setting covered; IS PF(R) 1.20 |
| bb_pinbar_fade | ACCEPT (OOS FAIL, final) | extra stage 2 was IS-only and counted; freeze before OOS; OOS PF 0.52 |
| rsi_extreme_fade | ACCEPT (reject) | fixes correct; IS PF(R) ≤ 1.17 |
| vwap_sd_fade | ACCEPT (reject) | IS PF(R) ≤ 0.97 |
| overreaction_fade | ACCEPT (reject at VAL) | IS PF(R) 1.32 (marginal plateau), VAL PF 1.12 |
| round_level | ACCEPT (reject at VAL) | real levels equal the placebo; finalist VAL PF 0.36 |

## Instructions for the Batch B agent

**ACCEPT – no further strategy work.** No reruns, no new freezes and no further VAL looks for any
Batch B id.

Report-only corrections (documentation, no computation that touches VAL):
1. level_sweep_reclaim: reconcile the cost/R figure. The diagnostic file's "$0.070 / 2.6%" conflicts
   with the report's "~$0.24 / ~5.7%". State the correct number and which one the diagnostic line
   measured.
2. wyckoff_spring and rsi_extreme_fade: the reported "best IS-selected" rows are the best stage-1
   rows by PF(R), not the top plateau settings named in the protocol. Either restate them as "best
   IS row (all < 1.3)", or report the plateau-rule finalist. Both are below IS PF(R) 1.3, so the
   verdicts do not change.
3. round_level: add one line saying that the placebo offset is a control, and that placebo rows were
   excluded from finalist selection by hand.
