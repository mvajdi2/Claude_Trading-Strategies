"""First-seconds impulse capture on US releases, 1s execution (Batch D2-4).

Card r2-release-bracket-impulse.
Events (event_set):
  "card" = the card's list: NFP, CPI, PCE, GDP_advance, retail_sales, PPI, FOMC_statement
  "t12"  = card + ISM_manufacturing, ISM_services, JOLTS, GDP_second, GDP_third (all tier 1+2)
  "all"  = t12 + stand-alone jobless claims (researcher widening for the trade-count gate)
Merged same-timestamp releases are one event typed by the highest-tier member (_d2util).
PR = high/low of the 1s mid grid over [T-15min, T-5s]. At T+s1: I = mid(T+s1) - mid(T-5s).
sd_I = std of I over the previous 24 events of the chosen set (pooled; needs >= 10 prior events).
LONG if I >= k_imp*sd_I and mid(T+s1) > PR_high; SHORT if I <= -k_imp*sd_I and mid(T+s1) < PR_low.
Decision second = T+s1 (its close); the engine fills at the close of T+s1+1 at the modelled spread.
Filter: skip if the raw spread at T+s1 > spread_cap * median raw spread at T+s1 over the previous 20
events of the set. One trade per event.
Card exit: stop 0.75*|I| from entry (stop_frac 0.75), target 1.0*|I| (tgt_mult 1.0), time exit
T + exit_min (5 min). unit = native stop distance, so the templates scale the card stop (stop_frac,
tgt_mult and the trail variant are exit-only and searched by the templates).
placebo=True: same rules at matched no-release weekdays at the same NY clock time.
"""
import numpy as np, pandas as pd
from strategies import _d2util as D

PARAMS = {
    "s1_sec": [3, 10, 30, 60],
    "k_imp": [0.5, 1.0, 1.5],
    "spread_cap": [2.0, 3.0, 5.0],
    "event_set": ["card", "t12", "all"],
}
DEFAULTS = dict(s1_sec=10, k_imp=1.0, spread_cap=3.0, event_set="card")
EXIT_UNIT = True
SETS = {
    "card": ("NFP", "CPI", "PCE", "GDP_advance", "retail_sales", "PPI", "FOMC_statement"),
}
SETS["t12"] = SETS["card"] + ("ISM_manufacturing", "ISM_services", "JOLTS", "GDP_second", "GDP_third")
SETS["all"] = SETS["t12"] + ("jobless_claims",)


def event_table(ctx, event_set="card", placebo=False):
    return D.events(ctx, SETS[event_set], placebo=placebo)


def signals(ctx, s1_sec=10, k_imp=1.0, spread_cap=3.0, event_set="card", exit_min=5, placebo=False):
    ev = event_table(ctx, event_set, placebo)
    T = ev.sec.values.astype(np.int64)
    p_pre = D.mid_at(ctx, T - 5)
    p1 = D.mid_at(ctx, T + s1_sec)
    I = p1 - p_pre
    PRh, PRl = D.hl_between(ctx, T - 900, T - 5)
    sdI = D.prior_stat(I, np.zeros(len(I)), 24, "std", pooled_min=10)
    sdI[np.arange(len(I)) < 10] = np.nan
    sp = D.spread_at(ctx, T + s1_sec)
    spmed = D.prior_stat(sp, np.zeros(len(I)), 20, "median", pooled_min=10)
    spmed[np.arange(len(I)) < 10] = np.nan
    ok_sp = sp <= spread_cap * spmed
    lg = (I >= k_imp * sdI) & (p1 > PRh)
    sh = (I <= -k_imp * sdI) & (p1 < PRl)
    side = np.where(lg, 1, np.where(sh, -1, 0))
    dec = T + s1_sec
    sl = 0.75 * np.abs(I)
    tp = 1.0 * np.abs(I)
    hold = D.hold_to(dec, T + exit_min * 60)
    s = pd.DataFrame(dict(sec=dec, side=side, sl=sl, tp=tp, hold=hold, unit=sl))
    ok = (side != 0) & ok_sp & np.isfinite(sdI) & (sl > 0.05) & (hold > 30)
    return s[ok].sort_values("sec").reset_index(drop=True)
