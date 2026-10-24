"""Session-VWAP sigma-band fade back to VWAP (5m), Batch B #8. Card: practitioners-vwap-3sd-fade.

VWAP anchored daily at `anchor` UTC (tick-count weighted typical price), sd = volume-weighted stdev
of typical price around VWAP. Long: previous bar closed below VWAP - band_sd*sd and the current bar
closes back above the lower band -> buy at close. Stop = excursion low (consecutive outside bars +
signal bar) - 0.25*ATR14(5m); target = VWAP; time exit 3h or 20:00 UTC; session 07:00-20:00 UTC
(and >= 1h after the anchor). slope_filter: skip if |EMA50 - EMA50[10 bars ago]| > 1.0*ATR14
(strong trend veto). Mirror for shorts. unit = stop distance (R).
"""
import numpy as np, pandas as pd, bt1s
from strategies._bxutil import DAY, frame

PARAMS = {
    "band_sd": [2.0, 2.5, 3.0],
    "anchor": [0, 7, 13.5],
    "slope_filter": [False, True],
}
DEFAULTS = dict(band_sd=3.0, anchor=0, slope_filter=False)
EXIT_UNIT = True


def signals(ctx, band_sd=3.0, anchor=0, slope_filter=False, tf=300, hold_h=3):
    b = ctx.bars(tf)
    H, L, C = b.h.values, b.l.values, b.c.values
    idx = b.index.values; cs = b.close_sec.values
    a = bt1s.atr(b, 14)
    sod = idx % DAY
    in_s = (sod >= anchor * 3600) & (sod < 21 * 3600)
    grp = np.where(in_s, idx // DAY, -1)
    tp_ = (H + L + C) / 3; w = b.n.values.astype(float)
    g = pd.Series(grp)
    cw = pd.Series(w).groupby(grp).cumsum().values
    cpw = pd.Series(tp_ * w).groupby(grp).cumsum().values
    cp2 = pd.Series(tp_ * tp_ * w).groupby(grp).cumsum().values
    vw = cpw / np.maximum(cw, 1)
    sd = np.sqrt(np.maximum(cp2 / np.maximum(cw, 1) - vw ** 2, 0))
    lo_b, up_b = vw - band_sd * sd, vw + band_sd * sd
    hr = (cs % DAY) / 3600.0
    ok = in_s & (hr >= 7) & (hr < 20) & (sod >= anchor * 3600 + 3600) & np.isfinite(a)
    if slope_filter:
        e = bt1s.ema(C, 50)
        sl10 = np.abs(e - np.r_[np.full(10, np.nan), e[:-10]])
        ok &= ~(sl10 > 1.0 * a)
    same = np.r_[False, grp[1:] == grp[:-1]] & (grp >= 0)
    prev_out_lo = np.r_[False, C[:-1] < lo_b[:-1]] & same
    prev_out_hi = np.r_[False, C[:-1] > up_b[:-1]] & same
    lg = ok & prev_out_lo & (C > lo_b)
    sh = ok & prev_out_hi & (C < up_b)
    rows = []
    for side, m in ((1, lg), (-1, sh)):
        for i in np.flatnonzero(m):
            j = i - 1   # walk back over consecutive outside closes
            while j - 1 >= 0 and same[j] and ((C[j - 1] < lo_b[j - 1]) if side == 1 else (C[j - 1] > up_b[j - 1])):
                j -= 1
            if side == 1:
                stop = L[j:i + 1].min() - 0.25 * a[i]
            else:
                stop = H[j:i + 1].max() + 0.25 * a[i]
            sl = side * (C[i] - stop); tp = side * (vw[i] - C[i])
            if tp <= 0:
                continue
            flat = idx[i] - idx[i] % DAY + 20 * 3600
            rows.append(dict(sec=cs[i], side=side, sl=sl, tp=tp, unit=sl,
                             hold=min(hold_h * 3600, flat - cs[i])))
    return frame(rows)
