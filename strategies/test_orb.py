"""Smoke-test strategy: London 07:00-07:15 UTC opening range breakout on 1m closes."""
import numpy as np, pandas as pd


def signals(ctx, range_min=15, tgt_r=1.0, hold_h=4):
    b = ctx.bars(60)
    t = b.time
    day = t.dt.floor("D")
    in_rng = (t.dt.hour == 7) & (t.dt.minute < range_min)
    rng = b[in_rng].groupby(day[in_rng]).agg(rh=("h", "max"), rl=("l", "min"))
    after = b[(t.dt.hour >= 7) & (t.dt.hour < 11) & ~in_rng].copy()
    after["day"] = day[after.index]
    after = after.join(rng, on="day")
    rows = []
    for d, g in after.groupby("day"):
        rh, rl = g.rh.iloc[0], g.rl.iloc[0]
        if not np.isfinite(rh):
            continue
        size = rh - rl
        up = g[g.c > rh]; dn = g[g.c < rl]
        first = None
        if len(up) and (not len(dn) or up.index[0] < dn.index[0]):
            first = (up.close_sec.iloc[0], 1, up.c.iloc[0] - rl)
        elif len(dn):
            first = (dn.close_sec.iloc[0], -1, rh - dn.c.iloc[0])
        if first:
            rows.append(dict(sec=first[0], side=first[1], sl=max(first[2], 0.5), tp=tgt_r * size, hold=hold_h * 3600))
    return pd.DataFrame(rows)

PARAMS = {"range_min": [15, 5, 30], "tgt_r": [1.0, 0.5, 2.0], "hold_h": [4, 2]}
