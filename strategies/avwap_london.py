"""London-anchored VWAP trend pullback with band reclaim (and a 2-sigma fade control).

Card: books-avwap-london-pullback.
AVWAP anchored at `anchor` UTC (tick-count weighted) with tick-weighted sigma bands, 5m bars,
signals 08:00-20:00 UTC.
pullback (long): share of 5m closes since the anchor above AVWAP >= trend_frac, AVWAP slope over
  12 bars > 0; a bar's low touches AVWAP + touch_band*sigma; entry at the first later (or same) bar
  that closes above AVWAP with close > open. Stop below AVWAP - 1.5 sigma (min 0.5 ATR14), target
  +2 sigma band (min 1R). Mirror for shorts.
fade_2sd: a 5m bar opens beyond +-2 sigma and closes back inside -> fade to AVWAP; stop 0.25 ATR
  beyond the bar extreme.
Max 2 trades per day, flat 20:55 UTC. unit = stop distance.
"""
import numpy as np, pandas as pd
from numba import njit
import bt1s

PARAMS = {
    "anchor": [7.0, 23.0, 13.5],
    "trend_frac": [0.7, 0.6, 0.8],
    "touch_band": [0.0, -1.0],
    "mode": ["pullback", "fade_2sd"],
}
EXIT_UNIT = True


@njit(cache=True)
def _pullback(grp, L, H, O, C, vw, sd, frac_up, slope, trend_frac, tb, ok):
    n = len(C)
    out = np.zeros(n, np.int64)
    tl = False; ts = False; g0 = -1
    for i in range(n):
        if grp[i] != g0:
            tl = False; ts = False; g0 = grp[i]
        if not ok[i]:
            continue
        upt = frac_up[i] >= trend_frac and slope[i] > 0
        dnt = (1 - frac_up[i]) >= trend_frac and slope[i] < 0
        if upt and L[i] <= vw[i] + tb * sd[i]:
            tl = True
        if dnt and H[i] >= vw[i] - tb * sd[i]:
            ts = True
        if not upt:
            tl = False
        if not dnt:
            ts = False
        if tl and C[i] > vw[i] and C[i] > O[i]:
            out[i] = 1; tl = False
        elif ts and C[i] < vw[i] and C[i] < O[i]:
            out[i] = -1; ts = False
    return out


def signals(ctx, anchor=7.0, trend_frac=0.7, touch_band=0.0, mode="pullback"):
    b = ctx.bars(300)
    grp = (b.index.values - int(anchor * 3600)) // 86400
    tp = ((b.h + b.l + b.c) / 3).values
    v = b.n.astype(float).values
    g = pd.Series(grp)
    cv = pd.Series(v).groupby(grp).cumsum().values
    vw = pd.Series(tp * v).groupby(grp).cumsum().values / np.maximum(cv, 1)
    ex2 = pd.Series(tp * tp * v).groupby(grp).cumsum().values / np.maximum(cv, 1)
    sd = np.sqrt(np.maximum(ex2 - vw ** 2, 0))
    C, O, H, L = b.c.values, b.o.values, b.h.values, b.l.values
    above = (C > vw).astype(float)
    frac_up = pd.Series(above).groupby(grp).cumsum().values / (g.groupby(grp).cumcount().values + 1)
    nbar = g.groupby(grp).cumcount().values + 1
    slope = vw - np.r_[np.full(12, np.nan), vw[:-12]]
    slope = np.where(nbar > 12, slope, np.nan)
    a = bt1s.atr(b, 14)
    hour = (b.index.values % 86400) / 3600
    ok = (hour >= 8) & (hour < 20) & np.isfinite(a) & np.isfinite(slope) & (nbar >= 12) & (sd > 0)
    if mode == "pullback":
        sig = _pullback(grp, L, H, O, C, vw, sd, frac_up, np.nan_to_num(slope), trend_frac, touch_band, ok)
        m = sig != 0
        side = sig[m]
        sl = np.where(side == 1, C[m] - (vw[m] - 1.5 * sd[m]), (vw[m] + 1.5 * sd[m]) - C[m])
        sl = np.maximum(sl, 0.5 * a[m])
        tpd = np.where(side == 1, vw[m] + 2 * sd[m] - C[m], C[m] - (vw[m] - 2 * sd[m]))
        tpd = np.maximum(tpd, sl)
    else:
        hi_b = vw + 2 * sd; lo_b = vw - 2 * sd
        hp = np.r_[np.nan, hi_b[:-1]]; lp = np.r_[np.nan, lo_b[:-1]]   # band at the open = band at i-1
        same = np.r_[False, grp[1:] == grp[:-1]]
        sh = ok & same & (O > hp) & (C < hi_b)
        lg = ok & same & (O < lp) & (C > lo_b)
        m = sh | lg
        side = np.where(lg, 1, -1)[m]
        sl = np.where(side == 1, C[m] - L[m], H[m] - C[m]) + 0.25 * a[m]
        tpd = np.abs(C[m] - vw[m])
    s = pd.DataFrame(dict(sec=b.close_sec.values[m].astype(np.int64), side=side.astype(int), sl=sl,
                          tp=tpd, hold=0, unit=sl))
    s["hold"] = ((s.sec // 86400) * 86400 + 20 * 3600 + 55 * 60 - s.sec).astype(np.int64)   # flat 20:55 UTC
    s["day"] = s.sec // 86400
    return s.groupby("day").head(2).drop(columns="day").reset_index(drop=True)
