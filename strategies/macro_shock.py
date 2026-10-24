"""Tier-1 US data shock (NFP/CPI) 15-minute direction, held for hold_h hours (Batch D2-5).

Card academic-macro-shock-15m-drift (previously skipped for lack of a verified calendar).
Events: NFP and/or CPI rows of the verified calendar (08:30 New York, DST aware via the calendar's
UTC column; merged timestamps such as NFP+claims count as NFP).
p0 = mid at T-60s (08:29 NY), p15 = mid at T+899s (last second before 08:45 NY), decision at T+899.
r15 = p15/p0 - 1. Shock size proxy (no consensus data): med = median |r15| of the previous 24 releases
of the same type; pooled over NFP+CPI when the type has < 24 history (needs >= 6 prior events).
LONG if r15 > s*med, SHORT if r15 < -s*med. Whipsaw filter: skip if sign(mid(08:35) - p0) != sign(r15).
Card exit: stop at p0 (the 08:29 pre-release price), no target, time exit hold_h hours (1 h) after
entry, hard flat 20:55 UTC. unit = native stop distance.
Frequency: <= ~22 IS events even for NFP+CPI -> ineligible by trade count (X7); screen + small grid.
placebo=True: same rules on matched no-release weekdays at 08:30 NY.
"""
import numpy as np, pandas as pd
from strategies import _d2util as D

PARAMS = {
    "s": [0.5, 1.0, 1.5, 2.0],
    "events": ["CPI", "NFP", "NFP+CPI"],
}
DEFAULTS = dict(s=1.0, events="NFP+CPI")
EXIT_UNIT = True


def signals(ctx, s=1.0, events="NFP+CPI", hold_h=1.0, placebo=False):
    inc = tuple(events.split("+"))
    ev = D.events(ctx, ("NFP", "CPI"), placebo=placebo)
    T = ev.sec.values.astype(np.int64)
    p0 = D.mid_at(ctx, T - 60)
    p15 = D.mid_at(ctx, T + 899)
    p6 = D.mid_at(ctx, T + 299)
    r15 = p15 / p0 - 1
    med = D.prior_stat(np.abs(r15), ev.type.values, 24, "median", pooled_min=6)
    side = np.where(r15 > s * med, 1, np.where(r15 < -s * med, -1, 0))
    whip = np.sign(p6 - p0) != np.sign(r15)
    dec = T + 899
    sl = side * (p15 - p0)
    hold = D.hold_to(dec, dec + int(hold_h * 3600))
    out = pd.DataFrame(dict(sec=dec, side=side, sl=sl, tp=0.0, hold=hold, unit=sl))
    ok = (side != 0) & ~whip & np.isfinite(med) & (sl > 0.05) & ev.type.isin(inc).values
    return out[ok].sort_values("sec").reset_index(drop=True)
