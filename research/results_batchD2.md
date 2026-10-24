# Batch D2 results: macro-calendar strategies (round-2 cards + academic macro shock)

Protocol: `evaluate.py` (staged harness). Screen at card defaults on IS, then the staged IS search:
stage 1 = full sorted PARAMS grid with the card's own exit (≤ 141 combos), stage 2 = all 53 exit
templates on the top-3 plateau settings (n_IS ≥ 60). Then a single VAL look at one finalist, freeze,
commit, and a single OOS run. Costs: cTrader model (spread max($0.10, 0.3×Dukascopy) at each second,
$0.03 slippage, $0.07/oz commission), 1 s fill latency. DD = max equity drawdown at 0.5 % risk per
trade, compounding.

## Selection rule (committed on its own before any D2 grid was run)

Applied identically to every D2 strategy that gets a grid, by `research/d2_select.py` (a copy of the
D1 selector; IS columns only):

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
6. Controls are **not** in the search grid and never choose anything: the placebo run (same rules at
   matched non-release times), the card's `mode=break` / `large_mode=follow` controls, and the cost
   sensitivity runs. They are run once on the IS-selected finalist (or at defaults when there is no
   finalist) and reported next to it.
7. Pre-declared scope by card (from the batch plan, before any result was seen):
   - `month_end_fix`, `comex_expiry`: screen + sign check + placebo only (≈ 12–24 events/yr), no grid,
     no freeze.
   - `macro_shock`: NFP+CPI only (card restriction) gives ≤ ~22 IS events → X7; screen, at most a small
     card-exit grid (≤ 12 rows, counted), placebo, no stage 2, no freeze.
   - `release_bracket`: the finalist is also reported under `bt1s.STRESS` and under raw Dukascopy
     spreads (`bt1s.Cost(sp_k=1.0, sp_min=0.0)`), IS and (at the single VAL look) VAL; these runs
     never select anything.
   - Long/short splits are reported for every finalist.

## Calendar conventions (`strategies/_d2util.py`)

The real calendar (`ctx.calendar()`, `data/calendar/us_macro_2025_2026.csv`) has columns
`event, date_local, time_local, datetime_utc, source_url, verified, note` and no tier column. Rows whose
note starts with `SCHEDULED` are dropped. Tiers are defined in the module (researcher choice):

| Tier | Events |
|---|---|
| 1 | NFP, CPI, FOMC_statement |
| 2 | PCE, GDP_advance, GDP_second, GDP_third, retail_sales, PPI, ISM_manufacturing, ISM_services, JOLTS |
| claims | jobless_claims (kept separate; joins an event set only where a card names 08:30 releases) |
| excluded | FOMC_minutes (no data surprise; only used to exclude placebo days) |

Releases sharing one timestamp are merged into one event whose type is the highest-tier member
(order NFP > CPI > FOMC_statement > PCE > GDP_advance > retail_sales > PPI > ISM_manufacturing >
ISM_services > JOLTS > GDP_second > GDP_third > jobless_claims). Shutdown cancellations simply have no
row; merged/shifted releases are used at their actual recorded time. Release times are New-York local
and the calendar's UTC column is DST-aware. The FOMC press conference (14:30 ET on statement days) is
not in the file; where a card needs it, it is derived as statement time + 30 min.

There is no consensus/actual data. Where a card needs "surprise size", the proxy is gold's own realised
initial reaction (the first seconds/minutes move, scaled by the history of the same quantity on prior
events, or by pre-release volatility), stated per strategy.

Placebo (control): every event is moved to the same New-York clock time on a matched weekday with no
calendar release of any kind on that day (offsets tried in order −7, +7, −1, +1, −2, +2 calendar days;
US holidays excluded). The event type label is kept, so history-based scalings behave the same way.

Other conventions: `unit` = the native stop distance; explicit 20:55 UTC flat (20:45 where the card
says so); no PARAMS key that only changes sl/tp; numeric PARAMS sorted ascending, categorical keys
last.

## Results

(filled in after the runs)
