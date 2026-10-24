"""COMEX gold options expiry / first-notice run-up pressure, with placebo (Batch D2-7).

Card r2-comex-expiry-pressure. Screen + sign check + placebo only (pre-declared; ~24 events/yr).
Event days (CME business days = weekdays that are not CME full holidays, list below):
  expiry: monthly OG gold options last trading day = 4th last business day of the month before the
          contract month; moved to the prior business day if that day is a Friday or the business day
          before a holiday (CME rule; checks: Jan 28 2025, Mar 26 2025 as published).
  fnd:    the 2 business days before First Notice Day of the active GC months (Feb, Apr, Jun, Aug,
          Oct, Dec); FND = last business day of the month before the contract month.
  placebo (control): business days 7-9 before month end (3 days per month).
Rule (mode short): on an event day, r5 = mid(08:20 NY) - close 5 trading days earlier (21:00 UTC);
if r5 >= r5_min*ATR14(D) -> SELL at 08:20 NY (COMEX open), stop 1.0*ATR14(1h) above, no target,
exit 13:35 NY. mode reverse: on the same qualifying days BUY at 13:35 NY, stop 1.0*ATR14(1h), exit
20:55 UTC. skip_t1: skip days with a tier-1/2 calendar release (card "param").
unit = native stop distance.
"""
import numpy as np, pandas as pd
import bt1s
from strategies import _d2util as D

PARAMS = {
    "r5_min": [0.0, 0.5, 1.0, 1.5],
    "event_set": ["expiry", "fnd", "expiry+fnd"],
}
DEFAULTS = dict(r5_min=0.5, event_set="expiry+fnd")
EXIT_UNIT = True
CME_HOLIDAYS = set(pd.to_datetime([
    "2025-01-01", "2025-01-20", "2025-02-17", "2025-04-18", "2025-05-26", "2025-06-19", "2025-07-04",
    "2025-09-01", "2025-11-27", "2025-12-25", "2026-01-01", "2026-01-19", "2026-02-16", "2026-04-03",
    "2026-05-25", "2026-06-19", "2026-07-03", "2026-09-07", "2026-11-26", "2026-12-25",
]).date)


def bdays(start="2024-12-01", end="2026-12-31"):
    d = pd.bdate_range(start, end)
    return [x.date() for x in d if x.date() not in CME_HOLIDAYS]


def event_days(kind):
    bd = bdays()
    bds = pd.Series(bd)
    ym = pd.Series([(x.year, x.month) for x in bd])
    out = set()
    for (y, m), idx in bds.groupby(ym).groups.items():
        days = list(bds[idx])
        if kind == "expiry":
            e = days[-4]
            i = bd.index(e)
            nxt = bd[i + 1] if i + 1 < len(bd) else None
            before_hol = nxt is not None and (pd.Timestamp(nxt) - pd.Timestamp(e)).days > (3 if pd.Timestamp(e).dayofweek == 4 else 1)
            if pd.Timestamp(e).dayofweek == 4 or before_hol:
                e = bd[i - 1]
            out.add(e)
        elif kind == "fnd":
            if (m % 12) + 1 in (2, 4, 6, 8, 10, 12):
                out.update(days[-3:-1])
        elif kind == "placebo":
            out.update(days[-10:-7])
    return out


def signals(ctx, r5_min=0.5, event_set="expiry+fnd", mode="short", skip_t1=False, placebo=False):
    if placebo:
        days = event_days("placebo")
    else:
        days = set().union(*[event_days(k) for k in event_set.split("+")])
    if skip_t1:
        rel = set(pd.to_datetime(D.events(ctx, D.TIER1 + D.TIER2).date).dt.date)
        days -= rel
    days = sorted(days)
    t_in = D.ny_sec([str(d) for d in days], [8 * 60 + 20] * len(days))
    t_out = D.ny_sec([str(d) for d in days], [13 * 60 + 35] * len(days))
    b1h = ctx.bars(3600)
    td = (b1h.index.values + 3 * 3600) // 86400                    # trading day (21:00 UTC roll)
    dly = b1h.groupby(td).agg(h=("h", "max"), l=("l", "min"), c=("c", "last"))
    dly["atr"] = bt1s.atr(dly, 14)
    a1h = bt1s.atr(b1h, 14)
    c1h = b1h.close_sec.values
    rows = []
    for d, ti, to in zip(days, t_in, t_out):
        tdi = (ti + 3 * 3600) // 86400
        prev = dly.loc[dly.index < tdi]
        if len(prev) < 20:
            continue
        atrD = prev.atr.iloc[-1]
        r5 = D.mid_at(ctx, np.array([ti]))[0] - prev.c.iloc[-5]
        if not np.isfinite(atrD) or r5 < r5_min * atrD:
            continue
        j = np.searchsorted(c1h, ti - 1, "right") - 1
        a = a1h[j]
        if mode == "short":
            rows.append((ti, -1, a, to - ti))
        else:
            rows.append((to, 1, a, int(D.hold_to(np.array([to]), np.array([to + 86400]))[0])))
    s = pd.DataFrame(rows, columns=["sec", "side", "sl", "hold"])
    s["tp"] = 0.0
    s["unit"] = s.sl
    return s[np.isfinite(s.sl) & (s.sl > 0)].sort_values("sec").reset_index(drop=True)
