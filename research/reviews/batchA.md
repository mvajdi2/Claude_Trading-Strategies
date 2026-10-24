# Batch A review (boss), 2026-10-24

Inputs reviewed: `research/results_batchA.md`, the Batch A section of `research/tested_registry.md`,
`results/<id>_opt.csv` for all 11 modules, `strategy_cards/asian_range_breakout.frozen.json` (with
git history), the code of all 11 modules plus `batcha_util.py`, and my earlier
`research/reviews/early_audit.md`. I re-read the 3 modules that were not there at the early audit
(bbkc_squeeze, noise_area_momentum, shanghai_open). I re-derived every number in the report's
"best IS-selected" table from the opt CSVs.

## Overall judgement

- **Reporting honesty: good.** Every IS and VAL figure in the results table matches the top
  `pfR_IS` row (n_IS ≥ 60) of the corresponding CSV. The registry matches the report. The 420-combo
  overrun on asian_range_breakout is disclosed. The scalp+BE win-rate artefact is identified
  correctly. No verdict is softened.
- **Protocol: followed as the harness allowed at the time, with two harness defects now fixed.**
  - The freeze of asian_range_breakout was committed (8e55849, `oos_run: false`) before the OOS
    record (205ccd0), and the code hash still matches (2699d1a2c347355a).
  - One finalist per strategy was compared on VAL.
  - Finalists were chosen on IS columns only.
  - The defects: random 120/300-of-N sampling with no card exits (early-audit X1/X2), and list-order
    robustness neighbours (X3). The frozen asian_range_breakout `robust_median_pf_IS` = 1.92 was
    computed with the old wrong neighbours. It does not matter, because the OOS verdict is FAIL on
    WR, PF and n anyway.
- **Selection rule was "top single row", not a plateau.** That was the old harness. The new staged
  harness fixes it for any rerun.
- **The pdh_pdl near-miss decision was correct.** The `close_beyond=True` / 07:00–18:00 /
  scalp_be sl 3 row was 4th on IS PF(R) (2.98). It stood out only because of its VAL PF of 2.49
  (n 30). Promoting it would have been selection on VAL. Not freezing it was the right call. This
  row is now VAL-tainted. It must not come back later, whether under this id, under a "v2" id, or
  as a "new" variant that happens to equal it.
- **VAL-leak policy for this review.** The agent has already seen VAL for every strategy. I decide
  reruns only from code, card and harness defects plus IS evidence, never from VAL results. A rerun
  is requested only where (a) the code was not faithful to the card or had a bug, or (b) the card's
  own exit could not be represented by any exit template, so harness defect X1 was material for
  that strategy. Random sampling (X2) on its own is **not** grounds for a rerun: the IS-chosen
  finalist's VAL rejection stands. For every rerun, the VAL check of the new IS-selected finalist
  is **that strategy's final VAL look**. If it fails, the strategy is closed for good.

---

## asian_range_breakout — ACCEPT (OOS FAIL, final)
Findings: frozen on the top IS PF(R) row (ATR range filter 0.2–1.0×ATR(D), prior-day RV top
tercile, buffer $2, orders until 12:00, flat 16:00; exit sl 2×range, tp 1×range). IS 72 trades,
WR 62.5, PF 2.13. VAL 38 trades, PF 2.40. OOS 16 trades, WR 68.8, PF 2.11. Stress PF 2.10, DD 0.51.
It fails the WR > 75, PF > 3 and n ≥ 25 OOS gates. It also never met WR/PF on IS or VAL. The freeze
was committed before OOS and the hash is unchanged. The verdict is final.
- Budget: 420 combinations (> 300). This is disclosed, and it is moot after OOS.
- My early-audit finding (the stale $3–20 USD filter) did not affect the frozen candidate, which uses
  the scale-free ATR filter.
- **No v2.** A `pct`-filter or other re-filtered version would not be *materially different* from
  the tested ATR-filter version. Its motivation would come from the OOS outcome, so it is not
  justified.
Instructions: none.

## crabel_orb_stretch — REDO (harness X1 material; final VAL look)
Findings: the code is faithful and causal (early audit). The card's exit is the stop at the opposite
side of the OR (capped at 1.5×ATR15), **no target**, and a time exit at 12:00. No template has
tp = 0 without a trail, so the card exit was tested only in the single screen run (IS PF(R) 1.30 at
defaults). The IS top row is a scalp_be artefact (WR 83.6, PF(R) 2.39).
Instructions: see the REDO list (item A-2).

## idnr4_breakout — ACCEPT (reject; ineligible by trade count)
Findings: faithful and causal. The card version has 23 IS trades. The NR-only variant has 64 IS
trades with a best IS PF(R) of 1.29 (< 1.3). No row reaches IS PF(R) 1.3. Even the NR-only variant
cannot reach ≥ 100 IS+VAL trades. Rejecting it is correct.
Instructions: none.

## williams_vol_breakout — ACCEPT (reject)
Findings: faithful and causal. Card exit: stop 0.5R, no target, flat 20:55, with R = the prior
day's range (about $40–60). The template {sl 0.5, tp 3.0} (×R) puts the target 3R away, which is
practically unreachable intraday, so it reproduces the card exit. X1 is therefore not material. The
IS-selected finalist (IS PF(R) 1.64) was rejected at VAL by the rule. That stands.
Instructions: none.

## ny_orb — ACCEPT (reject)
Findings: DST-aware and causal. The card exit (sl 0.5W, tp 2W) is exactly the template
{sl 0.5, tp 2.0} and was also run in screen (IS PF(R) 0.96). Best IS PF(R) is 1.11 (< 1.3).
Rejection on IS is correct.
Instructions: none.

## london_range_ny_break — REDO (card fidelity + structural switch; final VAL look)
Findings:
- The agent addressed the 5× frequency gap by adding `rng_atr_max` [2.5, 5, 99]. The IS top row
  uses 5.0 and has 85 IS trades. Good.
- Open fidelity and harness issues:
  - break and retest are two different strategies mixed in one random sample (`mode`), and retest
    "never ranked near the top" in that mixed sample.
  - `win_idx` maps to non-monotone values ([3,2,4] / [12,6,24]), so robustness and plateau
    neighbours are wrong even under the new harness, which sorts the *index*, not the window.
  - Retest mode lacks the card-2 filter "skip if London range > 2×ATR14(1h)×5".
  - Break mode starts at a fixed 12:30 UTC, although the card says to check the DST shift of the NY
    open.
  - The card-1 "BB zone" rule is interpreted as "take the next bar" without documentation.
Instructions: see the REDO list (item A-1).

## pdh_pdl_breakout — ACCEPT (reject; near-miss handling correct)
Findings: faithful and causal. The card exit (1×ATR1h stop, 2R) is exactly the template
{sl 1.0, tp 2.0} and was run in screen (IS PF(R) 1.35). X1 is not material. The IS-selected
finalist (scalp_be tp1 0.25, IS WR 94.0 / PF 3.87, passing the IS gates) was rejected at VAL
(PF 0.60) by the rule. The decision not to promote the 4th-ranked row is correct (see above). The
card's "daily midpoint stop" variant was never implemented, but that is minor and does not justify
a rerun after VAL.
Instructions: none. The `close_beyond` near-miss stays closed.

## ib_extension_ny — REDO (harness X1 material; final VAL look)
Findings: causal. The card exits are structural: break mode has its stop at the IB mid and its
target at ext×W beyond the broken edge; fade mode has its stop at the probe extreme + 0.1 ATR and
its target at the IB mid. With `unit = W`, none of these can be represented by a template, so the
card's design (especially the fade with a mid target) was searched only in the screen. `mode` is a
strategy switch, and fade with tp1/BE templates is not the card.
Instructions: see the REDO list (item A-3).

## bbkc_squeeze — REDO (card fidelity: default exit not implemented; final VAL look)
Findings: causal. Indicators come from closed bars and the stop is from the squeeze-bar range. Both
cards' **default** exit is a trail: an exit on a close back through the KC midline / SMA20. The
agent replaced it with the 2R variant and said the trail "cannot be expressed in the engine". It
can: noise_area_momentum in this same batch precomputes a closed-bar trailing exit and passes it as
`hold`, and the same works here. The variant the cards treat as primary was never tested. The
card-2 stop "opposite KC band or 1.5×ATR14(15m), whichever is closer" is also missing.
Instructions: see the REDO list (item A-4).

## noise_area_momentum — REDO (bug + harness X1 material; final VAL look)
Findings:
- Causal on entries. The sigma per check time comes from prior days, and the VWAP comes from closed
  bars.
- **Exit latency bug.** `hold = s - e_sec - 1` makes the engine exit at second `s = T-1`, which is
  the second whose price triggered the exit decision. The entry has a ≥ 1 s delay, but the exit
  has 0 s. That is a small favourable look-ahead.
- The card's defining exit is the VWAP/band trail (no target). Every template adds a target, a
  price trail or BE on top of it. Only the single screen run tested the card exit.
- Vol-target sizing not being modelled is acceptable and documented. The card's gap-adjusted anchor
  variant is missing.
Instructions: see the REDO list (item A-5).

## shanghai_open — REDO (card fidelity + harness X1 material; final VAL look)
Findings:
- Causal. The anchors are fixed UTC, which is correct because Shanghai has no DST.
- The card exits are not representable by templates. The ORB uses a fixed $5 stop and $10 target
  while `unit` is the range width. The momentum variant has its stop at the start price and no
  target while `unit` is sigma.
- Missing card filter: "skip Chinese public holidays (SHFE closed)". On those days the mechanism is
  absent and the signal is noise (Golden Week, the Spring Festival week, Qingming, Labour Day,
  Dragon Boat and Mid-Autumn).
- The SHFE night-open variant (13:00 UTC, held to 15:00) is missing.
- `mode` orb/mom mixes two cards.
Instructions: see the REDO list (item A-6).

---

## Summary table

| Strategy | Verdict | One-line reason |
|---|---|---|
| asian_range_breakout | ACCEPT (OOS FAIL, final) | protocol clean; fails WR/PF/n on OOS; no v2 (not materially different) |
| crabel_orb_stretch | REDO | card time exit (no target) not representable by templates; rerun staged, final VAL look |
| idnr4_breakout | ACCEPT (reject) | ineligible by trade count; IS PF(R) < 1.3 |
| williams_vol_breakout | ACCEPT (reject) | card exit equivalent to template sl 0.5/tp 3R; IS finalist failed VAL |
| ny_orb | ACCEPT (reject) | card exit equals a template; IS PF(R) 1.11 |
| london_range_ny_break | REDO | mixed modes, non-monotone window grid, missing card-2 filter, fixed-UTC NY start |
| pdh_pdl_breakout | ACCEPT (reject) | card exit equals a template; finalist failed VAL; not promoting the near-miss was correct |
| ib_extension_ny | REDO | structural card exits (IB mid) never searched |
| bbkc_squeeze | REDO | cards' default trail exit not implemented (it can be precomputed into `hold`) |
| noise_area_momentum | REDO | 0-second exit latency bug; card's VWAP-trail exit never searched without added targets |
| shanghai_open | REDO | card exits not representable; Chinese-holiday filter missing; modes mixed |

## REDO instructions to send to the Batch A agent

General rules for every rerun below:
- Use the new staged `evaluate.py optimise`. Stage 1 is the card exit over the full sorted grid,
  and stage 2 is the templates on the top 3 plateau settings.
- With 53 templates, **stage 1 must have ≤ 141 combinations**. Shrink PARAMS to the card's grid
  (plus at most one researcher variant per key) and put numeric lists in ascending order.
- Before running, write the selection rule into the report. **Finalist = the stage-1 setting with
  the best plateau score (median IS PF(R) over its sorted ±1 neighbours, n_IS ≥ 60). Then choose
  either the card exit or the stage-2 template, whichever has the higher IS PF(R), provided its
  adjacent templates (±1 step in sl or tp) have median IS PF(R) ≥ 1.3. Otherwise keep the card
  exit.** IS columns only. Never look at the VAL columns of non-finalist rows to choose anything.
- **The VAL check of that single finalist is the strategy's final VAL look.** If the finalist has
  IS PF(R) ≥ 1.3 and VAL PF ≥ 1.3, freeze it (the hash now covers the helpers and bt1s) and run OOS
  once. Otherwise the strategy is closed with that result.
- Count and report all combinations again (the earlier 120/300 plus the rerun), and update the
  registry rows.

A-1 **london_range_ny_break**
1. Split it into `london_range_ny_break` (break mode) and `london_range_retest` (retest mode),
   each with its own PARAMS. Use real monotone window params (`ny_bars: [2,3,4]`,
   `retest_win: [6,12,24]`) in place of `win_idx`.
2. Break mode:
   - Keep `rng_atr_max: [2.5, 5.0]` (drop 99, which is no filter, unless the card supports it).
   - Add `ny_start: ["12:30", "ny0830"]`, where ny0830 = 08:30 America/New_York, DST-aware.
   - In the module docstring, document the BB-zone interpretation ("skip the bar and take the next
     bar in the window").
3. Retest mode: add the card-2 filter "skip if London range > 2×ATR14(1h)×5" and `stop_atr: [0.3, 0.5, 1.0]`
   as in the card grid.
4. Re-screen both at card defaults, then run the staged optimise. Final VAL look for each.

A-2 **crabel_orb_stretch**: sort PARAMS (`or_minutes [5,15,30]`, `stretch_mult [0.5,1.0,1.5,2.0]`,
`stretch_lookback [5,10,20]`, `nr_filter`). Stage 1 must use the card exit (stop opposite OR,
capped 1.5×ATR15, no target, flat 12:00). Add the card's target variant
`tgt: [none, 1.0×(OR width + stretch)]` as a param if it fits within 141. Run the staged optimise.
Final VAL look.

A-3 **ib_extension_ny**
1. Split the modes into `ib_extension_ny` (break) and `ib_fade_ny` (fade), or freeze `mode` as a
   single value per run.
2. Set `unit` = the native stop distance so that the templates scale the card stop.
3. Replace the fixed-UTC "13:30"/"12:00" starts with DST-aware `ny0820` (COMEX open) and `ny0930`,
   keeping "13:30" as the card default. Sort `narrow_mult [0.5,0.7,0.85]`, `wide_mult [1.2,1.3,1.5]`
   and `ext_target [0.5,1.0,1.5]`.
4. Run the staged optimise. Final VAL look for each.

A-4 **bbkc_squeeze**
1. Implement the cards' default exit as a precomputed `hold`: exit at the close of the first
   closed bar that closes back through the SMA20 (KC midline), capped at 20:45 UTC. Use
   `exit_mode: ["trail", "2R"]`.
2. Add the card-2 stop variant `stop_mode: ["squeeze_range", "kc_or_1.5atr"]`.
3. Sort `min_sq [3,4,6,10,12]` (trim to fit), `kc_mult [1.0,1.25,1.5,2.0]` and `tf [300,900,3600]`.
4. Run the staged optimise. Final VAL look.

A-5 **noise_area_momentum**
1. Fix the exit latency: `hold = s - e_sec`, so that the exit fills ≥ 1 s after the decision
   second, as entries do. Flip case: the engine skips an entry whose fill second is ≤ the previous
   exit second. After the fix, the flipped entry's `sec` must therefore be `s + 1` (fill at s + 2).
   Otherwise every flip is silently dropped. Report the flip count before and after the fix.
2. Add the card's gap-adjusted anchor variant
   `gap_adj: [False, True]`, with upper anchor = max(O, prior 21:00 close) and lower = min(O, prior
   21:00 close).
3. Sort `lookback_days [10,14,20]`, `band_mult [0.75,1.0,1.25,1.5]` and `check_every [900,1800,3600]`.
   Trim `anchor` if needed to fit within 141.
4. Stage 1 is the card exit (VWAP/band trail via `hold`, catastrophe stop only). Run the staged
   optimise. Final VAL look.

A-6 **shanghai_open**
1. Split it into `shanghai_orb` and `shfe_open_mom`.
2. Add a hard-coded SHFE holiday list for 2025–2026 and skip those days (default on).
3. ORB: `stop_usd [2.5, 5.0, 7.5, "range"]` and `target_r [1.0, 1.5, 2.0]` as in the card. Set
   `unit` = the native stop distance.
4. Momentum: add the night-open variant `anchor: ["day_01:00", "night_13:00"]` (13:00 UTC open,
   first 30 min, held to 15:00 UTC). Use `exit_utc [03:30, 05:00, 06:30]` and `q [0.0, 0.5, 1.0]`,
   and set `unit` = the native stop distance (to the start price).
5. Run the staged optimise. Final VAL look for each.

**No further work** on asian_range_breakout (final), idnr4_breakout, williams_vol_breakout,
ny_orb or pdh_pdl_breakout. Their rejections stand. The pdh_pdl `close_beyond` near-miss is
VAL-tainted and must not be revived under any id.

---

# Rerun review (boss), 2026-10-24

Inputs reviewed:
- the "Rerun after review" section of `research/results_batchA.md` and the registry rerun table
- `results/<id>_opt_stage1.csv` and `_opt_exits.csv` for the 9 rerun ids
- the new modules (london_range_retest, ib_fade_ny, shanghai_orb, shfe_open_mom) and the changed
  modules
- `strategy_cards/london_range_ny_break.frozen.json` and `ib_fade_ny.frozen.json`, with their git
  history

I re-applied the agent's written selection rule to the CSVs with my own script, reading IS columns
only.

## Protocol checks

- **Selection rule written before the runs.** The rule is in `results_batchA.md`, and it is part of
  the freeze commit e705d8a (00:12:41), which comes before both OOS runs. Git cannot prove it was
  written before the stage-1 runs: the CSVs date from 00:10:46 to 00:11:36, and there is only one
  commit. I accept the agent's statement. In future, commit the rule on its own before running.
- **IS-only selection.** Re-applying the rule (top stage-1 plateau with n_IS ≥ 60, ties broken by
  PF(R), then a template only if it beats the card exit and its adjacent templates have median
  ≥ 1.3) reproduces the reported finalist setting for all 9 ids. It also reproduces the exit for
  8 of 9. The exception is london_range_retest:
  - My application picks fixed {sl 0.5, tp 3.0}: IS PF(R) 1.41, adjacent median 1.302.
  - The agent picked scalp_be sl 2, tp1 0.5, tp 3: IS PF(R) 1.39, adjacent median 1.36.
  - The difference is a borderline adjacency calculation at the 1.30 threshold. The two IS PF(R)
    values are almost equal, and both choices were made on IS.
  - This does **not** justify a rerun: the strategy's one VAL look has been used. I have also not
    looked at the alternative's VAL, and nobody should.
- **VAL shown only for each finalist.** Consistent with the rule and the report: one VAL row per id.
  The harness CSVs do contain VAL columns for every row, which is unavoidable. The agent says its
  selector script read IS columns only, and nothing in the selections contradicts that.
- **Freeze before OOS.**
  - london_range_ny_break: frozen 00:12:03, committed in e705d8a at 00:12:41 with
    `oos_run: false`, OOS run at 00:12:52.
  - ib_fade_ny: frozen 00:12:30, same commit, OOS run at 00:13:00.
  - Both used hash scheme v2, which was in force at the time. v3 (affb4d3) landed later, and that is
    acceptable.
  - The OOS records were committed in 437a497.
- **Budget.** The per-idea counts exceed 300 when the earlier, discarded random-sample run is
  included (for example 567 for london and crabel). That earlier run was not used for selection,
  and the rerun was requested by me. Each rerun was within its own 300. This is accepted and
  disclosed.

## A-5 flip dispute: the agent is right

Old code: `hold = s − e_sec − 1`, so the exit filled at second s (the 0 s exit look-ahead). A flip
decided at s filled at s+1, which is after `busy_until = s`, so flips were **not** dropped. My A-5
instruction was a precaution for the *fixed* code: once the exit moves to s+1, a flip decided at s
would be dropped. The new code does exactly the right thing:
- `hold = s − e_sec`, so the exit fills at s+1.
- A same-check flip is decided at s+1 and fills at s+2.
- Deciding later uses no extra information.

I withdraw the claim that the old code dropped flips. The real defect was the 0 s exit look-ahead,
and it is fixed.

## Finalists with no stage-2 rows (crabel_orb_stretch, ib_extension_ny, bbkc_squeeze)

The harness ran templates on the top-3 plateau rows without requiring n_IS ≥ 60 (fixed in affb4d3).
For these three, the rule's finalist was not among those rows, so it kept the card exit, exactly as
the pre-written rule says.

**Acceptable; no further action.** Reasons:
1. The card exit is the protocol's primary candidate, and the templates are optional exploration.
   The rule was applied as written.
2. All three VAL looks have already been used: crabel VAL PF 0.26, bbkc 0.92, ib_extension_ny 1.01
   (IS PF(R) 0.96). Running templates now and checking VAL again would be a second VAL look on the
   same setting, which is exactly the leak to avoid.

## Per-id verdicts

| Id | Verdict | Reason |
|---|---|---|
| london_range_ny_break | ACCEPT (OOS FAIL, final) | rule-selected finalist (plateau 1.36, template sl 2/tp 1.5); IS 1.74 / VAL 1.68 (n 20); OOS PF 0.47, stress 0.45 |
| london_range_retest | ACCEPT (closed at VAL) | IS-selected (borderline exit choice noted); VAL PF 0.57 |
| crabel_orb_stretch | ACCEPT (closed at VAL) | card exit, IS PF(R) 1.34; VAL PF 0.26 |
| ib_extension_ny | ACCEPT (closed on IS) | IS PF(R) 0.96 |
| ib_fade_ny | ACCEPT (OOS FAIL, final) | weak plateau (0.80), template sl 2/tp 3 lifts IS PF(R) to 1.45; VAL PF 2.13; OOS PF 1.88, WR 53, n 32, stress 1.86. Profitable out of sample, but far below the WR > 75 / PF > 3 gates. Record it on the frontier. |
| bbkc_squeeze | ACCEPT (closed at VAL) | card trail exit, IS PF(R) 1.38; VAL PF 0.92 |
| noise_area_momentum | ACCEPT (closed on IS) | latency fix verified; IS PF(R) 1.00 |
| shanghai_orb | ACCEPT (closed at VAL) | SHFE holidays added; IS PF(R) 1.38; VAL PF 0.91 |
| shfe_open_mom | ACCEPT (closed on IS) | IS PF(R) 1.26. Minor: for the night anchor, `exit_utc` is a no-op (held to 15:00), so that part of the grid is duplicates. It does not affect the verdict. |

**Batch A final: ACCEPT – no further work.** Every Batch A id is now closed: OOS FAIL (3 ids:
asian_range_breakout, london_range_ny_break, ib_fade_ny), rejected on IS, or rejected at its final
VAL look. Only documentation remains:
1. Annotate the london_range_retest exit-adjacency calculation (which neighbours were used).
2. Note the `exit_utc` no-op for the shfe night anchor.
