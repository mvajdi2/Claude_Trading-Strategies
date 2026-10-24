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
