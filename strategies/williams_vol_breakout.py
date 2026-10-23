"""Larry Williams volatility breakout from the day open (Batch A #4).

Card books-williams-vol-breakout. O = open at ref_open UTC (23:00 = trading-day open, or 07:00).
R = previous day's (23:00-21:00) range, or mean of the last range_lb ranges. Stop orders at O + k*R
and O - k*R, live from ref_open to end_h UTC; first touch wins, 1 trade/day.
Default exit: stop k_stop*R from entry, no target, flat 20:55 UTC. unit = R.
"""
import numpy as np, pandas as pd
from strategies import batcha_util as U

PARAMS = {
    "k": [0.5, 0.3, 0.7, 1.0],
    "ref_open": [23, 7],
    "range_lb": [1, 3],
    "end_h": [20, 16],
    "k_stop": [0.5],
}
EXIT_UNIT = True


def signals(ctx, k=0.5, ref_open=23, range_lb=1, end_h=20, k_stop=0.5):
    b = ctx.bars(60)
    tds = U.trading_days(ctx)
    d = U.daily(ctx)
    R = U.prev_rows(d.rng.rolling(range_lb).mean().to_frame("r"), tds)["r"].values
    t0 = U.at(tds, ref_open)
    i = np.searchsorted(b.index.values, t0, "left")
    i = np.minimum(i, len(b) - 1)
    o = b.o.values[i]
    first_bar = b.index.values[i]
    ok = np.isfinite(R) & (first_bar - t0 < 1800) & (R > 0)    # open bar must exist near ref time
    tds, R, o, t0 = tds[ok], R[ok], o[ok], first_bar[ok]
    up, dn = o + k * R, o - k * R
    sec, side = U.first_touch(ctx, t0, U.at(tds, end_h), up, dn)
    f = sec > 0
    flat = U.at(tds, 20 + 55 / 60)
    return pd.DataFrame(dict(sec=sec[f], side=side[f], sl=k_stop * R[f], tp=0.0,
                             hold=np.maximum(flat - sec, 60)[f], unit=R[f]))
