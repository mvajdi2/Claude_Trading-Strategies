"""Bollinger close-outside + pin-bar fade with H1 EMA200 alignment, Batch B #6.
Card: marketplaces-bb-pinbar-fade-m5.

Long: the previous bar closed below the lower BB(20, bb_dev) and the current (closed) bar is a
bullish pin: lower wick >= wick_body * body, close in the top third of the bar; and the last closed
H1 close > EMA200(H1) (ema_filter). Enter at the pin close (market). Stop = pin low - 0.30 USD;
target = BB middle band (20 SMA) at the signal bar; time exit 60 min; session 07:00-20:00 UTC.
Mirror for shorts. unit = stop distance (R).
"""
import numpy as np, pandas as pd, bt1s
from strategies._bxutil import DAY, frame, align

PARAMS = {
    "bb_dev": [2.0, 2.5, 3.0],
    "wick_body": [1.5, 2.0, 3.0],
    "ema_filter": [False, True],
    "tf": [300, 900],
}
DEFAULTS = dict(bb_dev=2.0, wick_body=2.0, ema_filter=True, tf=300)
EXIT_UNIT = True


def signals(ctx, bb_dev=2.0, wick_body=2.0, ema_filter=True, tf=300, hold_min=60):
    b = ctx.bars(tf); h1 = ctx.bars(3600)
    O, H, L, C = b.o.values, b.h.values, b.l.values, b.c.values
    idx = b.index.values; cs = b.close_sec.values
    sma = bt1s.sma(C, 20); sd = pd.Series(C).rolling(20).std(ddof=0).values
    up, dn = sma + bb_dev * sd, sma - bb_dev * sd
    e200 = align(h1, bt1s.ema(h1.c.values, 200), cs)
    c1 = align(h1, h1.c.values, cs)
    rng = H - L; body = np.abs(C - O)
    lw = np.minimum(O, C) - L; uw = H - np.maximum(O, C)
    prev_below = np.r_[False, C[:-1] < dn[:-1]]
    prev_above = np.r_[False, C[:-1] > up[:-1]]
    hr = (idx % DAY) / 3600.0
    sess = (hr >= 7) & (hr + tf / 3600.0 <= 20) & (rng > 0)
    bull = sess & prev_below & (lw >= wick_body * body) & (C >= L + 2 / 3 * rng)
    bear = sess & prev_above & (uw >= wick_body * body) & (C <= H - 2 / 3 * rng)
    if ema_filter:
        bull &= c1 > e200; bear &= c1 < e200
    rows = []
    for side, m in ((1, bull), (-1, bear)):
        for i in np.flatnonzero(m):
            sl = side * (C[i] - (L[i] if side == 1 else H[i])) + 0.30
            tp = side * (sma[i] - C[i])
            if tp <= 0:
                continue
            flat = idx[i] - idx[i] % DAY + 20 * 3600 + 45 * 60
            rows.append(dict(sec=cs[i], side=side, sl=sl, tp=tp, unit=sl,
                             hold=min(hold_min * 60, flat - cs[i])))
    return frame(rows)
