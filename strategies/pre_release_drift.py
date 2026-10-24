"""Pre-announcement drift continuation into US releases, cross-asset confirmed (Batch D2-2).

Card r2-pre-release-drift-10et (Kurov-Sancetta-Strasser-Wolfe pre-release informed trading).
Event sets (the card's E10 members Conference Board confidence, existing/pending home sales and
industrial production are NOT in the verified calendar, so E10 reduces to the two ISM releases):
  "ISM_only"  = ISM_manufacturing, ISM_services (10:00 ET)                       [card E10 / ISM_only]
  "ISM_JOLTS" = + JOLTS (10:00 ET)                                               [card E10_plus_UMich_JOLTS, UMich missing]
  "all10"     = every 10:00 ET tier-1/2 release (adds PCE when released at 10:00)
  "all_t12"   = all10 + the 08:30 ET tier-1/2 releases (researcher widening for the trade-count gate;
                KSSW find no pre-drift for 08:30 releases, so this is a hypothesis)
Merged same-timestamp releases are one event (_d2util). For T = release time, decision at T - d_entry min:
DG = XAU log return over [T-30m, T-d], DS = USA500 1m log return, DU = USD2 = 0.5*(-r EURUSD)+0.5*r USDJPY
over the same window (cross-asset closes of bars that closed by T-30m-1s and T-d-1s).
Each is z-scored ((x - mean)/sd) against the same NY clock window on the previous 40 weekdays with no
calendar release at that clock time. Votes V = [zG >= z_min] + [zS <= -z_min] + [zU <= -z_min];
LONG at T-d if zG >= z_min and V >= v_min (mirror for SHORT).
Card exit: stop = max(1.0*|DG| in price, 0.5*ATR14(5m)) (stop_mult 1.0), no target, time exit T+5 min.
Filters: skip_830 (default on): a 10:00 ET event is skipped if an 08:30 ET NFP/CPI/PCE/GDP/retail-sales
release is on the same day; skip if the XAU spread at the decision second > 2x its median at the same
clock second over the previous 20 weekdays.
unit = native stop distance; stop_mult/target are exit-only -> templates. exit_min, skip_830 fixed at
the card defaults (5, True) to keep stage 1 <= 141.
placebo=True: matched no-release weekdays at the same NY clock time.
"""
import numpy as np, pandas as pd
import bt1s
from strategies import _d2util as D

PARAMS = {
    "d_entry": [1, 2, 5],
    "z_min": [0.5, 1.0, 1.5],
    "v_min": [1, 2, 3],
    "event_set": ["ISM_only", "ISM_JOLTS", "all10", "all_t12"],
}
DEFAULTS = dict(d_entry=2, z_min=1.0, v_min=2, event_set="ISM_only")
EXIT_UNIT = True
T830_SKIP = ("NFP", "CPI", "PCE", "GDP_advance", "GDP_second", "GDP_third", "retail_sales")


def event_table(ctx, event_set, placebo=False):
    if event_set == "ISM_only":
        ev = D.events(ctx, ("ISM_manufacturing", "ISM_services"), placebo)
    elif event_set == "ISM_JOLTS":
        ev = D.events(ctx, ("ISM_manufacturing", "ISM_services", "JOLTS"), placebo)
    else:
        ev = D.events(ctx, D.TIER1 + D.TIER2, placebo)
        ev = ev[(ev.minute == 600) | ((ev.minute == 510) & (event_set == "all_t12"))]
    return ev.reset_index(drop=True)


def _window_returns(ctx, T, d_entry):
    a = T - 1800; b = T - d_entry * 60
    dg = np.log(D.mid_at(ctx, b) / D.mid_at(ctx, a))
    def xr(sym):
        c = ctx.m1(sym).c
        return np.log(c.reindex(b - 60).values / c.reindex(a - 60).values)
    ds = xr("USA500IDXUSD")
    du = 0.5 * -xr("EURUSD") + 0.5 * xr("USDJPY")
    return dg, ds, du


def signals(ctx, d_entry=2, z_min=1.0, v_min=2, event_set="ISM_only", exit_min=5, skip_830=True, placebo=False):
    ev = event_table(ctx, event_set, placebo)
    cal = D.calendar_rows(ctx)
    busy = {}
    for mnt in (510, 600):
        busy[mnt] = set(cal[cal.time_local == ("08:30" if mnt == 510 else "10:00")].date_local)
    t830 = set(cal[(cal.time_local == "08:30") & cal.event.isin(T830_SKIP)].date_local)
    wd = [x.date() for x in pd.bdate_range("2024-10-01", "2026-12-31") if x.date() not in set(D.US_HOLIDAYS)]
    base = {}
    b1i = ctx.bars(60).index.values
    for mnt in (510, 600):
        days = [d for d in wd if str(d) not in busy[mnt]]
        Tb = D.ny_sec([str(d) for d in days], [mnt] * len(days))
        g, s_, u = _window_returns(ctx, Tb, d_entry)
        sp = D.spread_at(ctx, Tb - d_entry * 60)
        live = np.isin(Tb - 1860, b1i) & np.isin(Tb - d_entry * 60 - 60, b1i)   # XAU bars exist (no pre-data days)
        base[mnt] = pd.DataFrame(dict(rt=Tb, g=g, s=s_, u=u, sp=sp))[live].dropna(subset=["g"])
    b5 = ctx.bars(300); a5 = bt1s.atr(b5, 14); c5 = b5.close_sec.values
    rows = []
    for _, e in ev.iterrows():
        T = int(e.sec); mnt = int(e.minute)
        if skip_830 and mnt == 600 and e.date in t830:
            continue
        bb = base[mnt]; prev = bb[bb.rt < T - 3600].tail(40)
        if len(prev) < 30:
            continue
        g, s_, u = (x[0] for x in _window_returns(ctx, np.array([T]), d_entry))
        if not np.isfinite(g):
            continue
        z = lambda x, col: (x - prev[col].mean()) / prev[col].std()
        zG, zS, zU = z(g, "g"), z(s_, "s"), z(u, "u")
        dec = T - d_entry * 60
        if D.spread_at(ctx, np.array([dec]))[0] > 2 * prev.sp.tail(20).median():
            continue
        vl = int(zG >= z_min) + int(np.nan_to_num(zS) <= -z_min) + int(np.nan_to_num(zU) <= -z_min)
        vs = int(zG <= -z_min) + int(np.nan_to_num(zS) >= z_min) + int(np.nan_to_num(zU) >= z_min)
        if zG >= z_min and vl >= v_min:
            sd = 1
        elif zG <= -z_min and vs >= v_min:
            sd = -1
        else:
            continue
        px = D.mid_at(ctx, np.array([dec]))[0]
        j = np.searchsorted(c5, dec, "right") - 1
        sl = max(1.0 * abs(px - D.mid_at(ctx, np.array([T - 1800]))[0]), 0.5 * a5[j])
        rows.append((dec, sd, sl, int(D.hold_to(np.array([dec]), np.array([T + exit_min * 60]))[0])))
    s = pd.DataFrame(rows, columns=["sec", "side", "sl", "hold"]).astype({"sec": np.int64, "side": int, "sl": float, "hold": np.int64})
    s["tp"] = 0.0
    s["unit"] = s.sl
    return s[np.isfinite(s.sl) & (s.sl > 0.05)].sort_values("sec").reset_index(drop=True)
