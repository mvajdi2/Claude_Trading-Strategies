"""Raschke 80-20 reversal (with Williams 'Oops' variant), Batch B #3. Card: books-raschke-8020-daily.

Yesterday (23:00-21:00 UTC) opened in the top extreme_frac of its range and closed in the bottom
extreme_frac, range >= 0.8*ATR14(daily). Today from 01:00 UTC, after price trades >= overshoot_atr*ATR
below yesterday's low, a buy stop at yesterday's low (emulated: first 1s high >= level, market fill
1 s later), armed until arm_until UTC. Stop = today's low so far - 0.05*ATR; target = midpoint of
yesterday's range; time exit 20:55 UTC; max 1 trade/day. Mirror for shorts.
cond="oops": drop the open/close-at-extreme condition (any day, range filter kept).
unit = stop distance (R).
"""
import numpy as np, pandas as pd
from strategies._bxutil import DAY, frame, first_hit, ext, daily_bars, daily_atr

PARAMS = {
    "extreme_frac": [0.1, 0.2, 0.25],
    "overshoot_atr": [0.05, 0.1, 0.2],
    "arm_until": [12, 16],
    "cond": ["8020", "oops"],
}
DEFAULTS = dict(extreme_frac=0.2, overshoot_atr=0.1, arm_until=16, cond="8020")
EXIT_UNIT = True


def signals(ctx, extreme_frac=0.2, overshoot_atr=0.1, arm_until=16, cond="8020", min_range_atr=0.8):
    d = daily_bars(ctx)
    atr = daily_atr(d, 14)
    days = d.index.values
    rows = []
    for j in range(1, len(d)):
        td, yd = days[j], days[j - 1]
        if td - yd > 3:            # need the actual previous trading day (weekend gap <= 3)
            continue
        y = d.iloc[j - 1]; A = atr.iloc[j - 1]
        if not np.isfinite(A):
            continue
        rg = y.h - y.l
        if rg < min_range_atr * A or rg <= 0:
            continue
        po = (y.o - y.l) / rg; pc = (y.c - y.l) / rg
        day0 = td * DAY - 3600                     # 23:00 UTC start of trading day td
        t_arm0 = td * DAY + 3600                   # 01:00 UTC
        t_arm1 = td * DAY + int(arm_until * 3600)
        flat = td * DAY + 20 * 3600 + 55 * 60
        mid = 0.5 * (y.h + y.l)
        for side in (1, -1):
            if cond == "8020":
                if side == 1 and not (po >= 1 - extreme_frac and pc <= extreme_frac):
                    continue
                if side == -1 and not (po <= extreme_frac and pc >= 1 - extreme_frac):
                    continue
            lvl = y.l if side == 1 else y.h
            ov = lvl - side * overshoot_atr * A
            k1 = first_hit(ctx, t_arm0, t_arm1, ov, up=(side == -1))
            if k1 < 0:
                continue
            k2 = first_hit(ctx, k1 + 1, t_arm1, lvl, up=(side == 1))
            if k2 < 0:
                continue
            ex = ext(ctx, day0, k2, up=(side == -1))
            sl = side * (lvl - ex) + 0.05 * A
            tp = side * (mid - lvl)
            if tp <= 0:
                continue
            rows.append(dict(sec=k2, side=side, sl=sl, tp=tp, unit=sl, hold=flat - k2))
    df = frame(rows)
    if len(df):
        df = df.groupby((df.sec.values + 3600) // DAY).head(1).reset_index(drop=True)
    return df
