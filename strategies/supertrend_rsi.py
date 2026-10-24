"""NY-session Supertrend + RSI 55/45 momentum on 5m bars, 1:2 RR.

Card: practitioners-ny-supertrend-rsi.
Session 08:00-17:00 New York (DST-aware; exit at 17:00 NY capped at 20:55 UTC). Long at the close of a 5m
bar when Supertrend(st_atr_len, st_mult) is bullish and RSI14 crosses above rsi_up; short when
bearish and RSI14 crosses below 100 - rsi_up. Stop = distance to the Supertrend line (min 0.2 ATR),
target = 2 * stop. Max 3 trades per NY session. unit = stop distance (so exit templates scale R).
"""
import numpy as np, pandas as pd
from numba import njit
import bt1s

NY = "America/New_York"

PARAMS = {
    "st_atr_len": [10, 7, 14],
    "st_mult": [3.0, 2.0, 4.0],
    "rsi_up": [55, 52, 60],
}
EXIT_UNIT = True


@njit(cache=True)
def _supertrend(h, l, c, atr, mult):
    n = len(c)
    up = np.full(n, np.nan); dn = np.full(n, np.nan); st = np.full(n, np.nan); dirn = np.zeros(n)
    for i in range(n):
        if not np.isfinite(atr[i]):
            continue
        m = 0.5 * (h[i] + l[i])
        bu = m + mult * atr[i]; bl = m - mult * atr[i]
        if i == 0 or not np.isfinite(up[i - 1]):
            up[i] = bu; dn[i] = bl; dirn[i] = 1; st[i] = bl
            continue
        up[i] = bu if (bu < up[i - 1] or c[i - 1] > up[i - 1]) else up[i - 1]
        dn[i] = bl if (bl > dn[i - 1] or c[i - 1] < dn[i - 1]) else dn[i - 1]
        if dirn[i - 1] == 1:
            dirn[i] = -1 if c[i] < dn[i] else 1
        else:
            dirn[i] = 1 if c[i] > up[i] else -1
        st[i] = dn[i] if dirn[i] == 1 else up[i]
    return st, dirn


def signals(ctx, st_atr_len=10, st_mult=3.0, rsi_up=55):
    b = ctx.bars(300)
    pc = b.c.shift(1)
    tr = np.maximum(b.h - b.l, np.maximum((b.h - pc).abs(), (b.l - pc).abs()))
    atr_w = tr.ewm(alpha=1 / st_atr_len, adjust=False).mean().values
    st, dirn = _supertrend(b.h.values, b.l.values, b.c.values, atr_w, st_mult)
    r = bt1s.rsi(b.c.values, 14)
    rp = np.r_[np.nan, r[:-1]]
    lt = b.time.dt.tz_localize("UTC").dt.tz_convert(NY).dt.tz_localize(None)
    mn = (lt.dt.hour * 60 + lt.dt.minute).values + 5        # minutes at bar close
    nyday = lt.dt.normalize().values
    sess = (mn > 8 * 60) & (mn <= 17 * 60) & ((b.close_sec.values % 86400) < 21 * 3600 - 60)
    C = b.c.values
    lg = sess & (dirn == 1) & (r > rsi_up) & (rp <= rsi_up)
    sh = sess & (dirn == -1) & (r < 100 - rsi_up) & (rp >= 100 - rsi_up)
    m = lg | sh
    stop = np.abs(C - st)[m]
    stop = np.maximum(stop, 0.2 * atr_w[m])
    s = pd.DataFrame(dict(sec=b.close_sec.values[m].astype(np.int64), side=np.where(lg, 1, -1)[m],
                          sl=stop, tp=2 * stop, hold=0, unit=stop, day=nyday[m]))
    s["hold"] = ((s.sec // 86400) * 86400 + 20 * 3600 + 55 * 60 - s.sec).astype(np.int64)   # flat 20:55 UTC
    s = s[np.isfinite(s.sl)]
    return s.groupby("day").head(3).drop(columns="day").reset_index(drop=True)
