"""Raschke/Connors ID/NR4 next-day breakout with one stop-and-reverse (Batch A #3).

Card books-idnr4-daily-breakout. Setup: yesterday (23:00-21:00 bar) is an inside day and its range is
the narrowest of the last nr_n days. Today, from 01:00 to 18:00 UTC: buy stop at yH + buf*ATR14(D),
sell stop at yL - buf*ATR14(D). Stop = opposite level. If sar_enabled, a touch of the opposite level
after the first entry opens the reverse trade (stop at the original entry level), max once per day.
hv_filter: 6-day HV below 50% of its 100-day range. Flat 20:55 UTC. unit = yesterday's range.
require_inside=False drops the inside-day condition (NR-only variant, more trades).
"""
import numpy as np, pandas as pd
from strategies import batcha_util as U

PARAMS = {
    "buffer_atr": [0.05, 0.0, 0.1],
    "nr_n": [4, 7],
    "sar_enabled": [True, False],
    "hv_filter": [False, True],
    "require_inside": [True, False],
    "start_h": [1],
    "end_h": [18],
}
EXIT_UNIT = True


def signals(ctx, buffer_atr=0.05, nr_n=4, sar_enabled=True, hv_filter=False, require_inside=True,
            start_h=1, end_h=18):
    d = U.daily(ctx).copy()
    d["inside"] = (d.h <= d.h.shift(1)) & (d.l >= d.l.shift(1))
    d["nr"] = d.rng <= d.rng.rolling(nr_n).min()
    lr = np.log(d.c).diff()
    hv = lr.rolling(6).std()
    hmin, hmax = hv.rolling(100, min_periods=60).min(), hv.rolling(100, min_periods=60).max()
    d["hvok"] = hv < hmin + 0.5 * (hmax - hmin)
    tds = U.trading_days(ctx)
    p = U.prev_rows(d[["h", "l", "rng", "atr14", "inside", "nr", "hvok"]].astype(float), tds)
    ok = (p.nr.values == 1) & np.isfinite(p.atr14.values)
    if require_inside:
        ok &= p.inside.values == 1
    if hv_filter:
        ok &= p.hvok.values == 1
    tds, p = tds[ok], p[ok]
    up = p.h.values + buffer_atr * p.atr14.values
    dn = p.l.values - buffer_atr * p.atr14.values
    rng = p.rng.values
    t0, t1 = U.at(tds, start_h), U.at(tds, end_h)
    m0 = U.mid_at(ctx, t0 - 1)
    inside = (m0 < up) & (m0 > dn)
    tds, up, dn, rng, t0, t1 = tds[inside], up[inside], dn[inside], rng[inside], t0[inside], t1[inside]
    sec, side = U.first_touch(ctx, t0, t1, up, dn)
    f = sec > 0
    flat = U.at(tds, 20 + 55 / 60)
    rows = [pd.DataFrame(dict(sec=sec[f], side=side[f], sl=(up - dn)[f], tp=0.0,
                              hold=np.maximum(flat - sec, 60)[f], unit=rng[f]))]
    if sar_enabled:
        g = np.where(f)[0]
        up2 = np.where(side[g] < 0, up[g], np.inf)     # after a short, the reverse is a buy at up
        dn2 = np.where(side[g] > 0, dn[g], -np.inf)
        sec2, side2 = U.first_touch(ctx, sec[g] + 1, t1[g], up2, dn2)
        h = sec2 > 0
        rows.append(pd.DataFrame(dict(sec=sec2[h], side=side2[h], sl=(up - dn)[g][h], tp=0.0,
                                      hold=np.maximum(flat[g] - sec2, 60)[h], unit=rng[g][h])))
    return pd.concat(rows).sort_values("sec").reset_index(drop=True)
