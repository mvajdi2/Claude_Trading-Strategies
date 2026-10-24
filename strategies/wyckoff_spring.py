"""Wyckoff spring / upthrust out of an intraday range (5m), Batch B #4.
Card: books-wyckoff-spring-upthrust-5m.

Range = high/low of the previous range_bars 5m bars, width <= max_width_atr*ATR14(15m, last closed),
each side touched >= 2 times (bar extreme within 0.2*ATR14(5m) of the edge). Spring bar: low below
range low by 0.05-0.5*ATR14(5m), close back inside the range and in the upper half of the bar,
tick volume vs 20-bar mean per vol_rule (low: <= 1.0x, high: >= 1.5x, none). Entry: buy stop at the
spring-bar high valid 3 bars (first 1s high >= level, market fill 1 s later); entry="close" enters
at the spring-bar close instead. Stop = spring low - 0.1*ATR(5m); target = range high; time exit
24 bars or 20:55; session 08:00-20:00 UTC; max 2/day. Mirror for upthrusts. unit = stop distance.
"""
import numpy as np, pandas as pd, bt1s
from numpy.lib.stride_tricks import sliding_window_view as swv
from strategies._bxutil import DAY, frame, first_hit, align, cap_per_day

PARAMS = {
    "range_bars": [24, 36, 72],
    "max_width_atr": [2.0, 2.5, 3.5, 5.0],
    "vol_rule": ["low", "high", "none"],
    "entry": ["stop", "close"],
}
DEFAULTS = dict(range_bars=36, max_width_atr=2.5, vol_rule="low", entry="stop")
EXIT_UNIT = True


def signals(ctx, range_bars=36, max_width_atr=2.5, vol_rule="low", entry="stop", tf=300):
    b = ctx.bars(tf); b15 = ctx.bars(900)
    a5 = bt1s.atr(b, 14)
    a15 = align(b15, bt1s.atr(b15, 14), b.close_sec.values)
    O, H, L, C, V = b.o.values, b.h.values, b.l.values, b.c.values, b.n.values.astype(float)
    idx = b.index.values; cs = b.close_sec.values
    n = len(b); N = range_bars
    wh = swv(H, N)[:-1]; wl = swv(L, N)[:-1]
    rh = np.full(n, np.nan); rl = np.full(n, np.nan)
    rh[N:] = wh.max(1); rl[N:] = wl.min(1)
    tol = 0.2 * a5
    th = np.zeros(n); tl = np.zeros(n)
    th[N:] = (wh >= (rh[N:] - tol[N:])[:, None]).sum(1)
    tl[N:] = (wl <= (rl[N:] + tol[N:])[:, None]).sum(1)
    span_ok = np.zeros(n, bool); span_ok[N:] = (idx[N:] - idx[:-N]) <= N * tf * 1.6
    vm = pd.Series(V).shift(1).rolling(20).mean().values
    if vol_rule == "low":
        vok = V <= 1.0 * vm
    elif vol_rule == "high":
        vok = V >= 1.5 * vm
    else:
        vok = np.ones(n, bool)
    hr = (idx % DAY) / 3600.0
    base = span_ok & (rh - rl <= max_width_atr * a15) & (th >= 2) & (tl >= 2) & vok \
        & (hr >= 8) & (hr + tf / 3600.0 <= 20) & np.isfinite(a5)
    mid = 0.5 * (H + L)
    spring = base & (L < rl - 0.05 * a5) & (L >= rl - 0.5 * a5) & (C > rl) & (C < rh) & (C >= mid)
    upthr = base & (H > rh + 0.05 * a5) & (H <= rh + 0.5 * a5) & (C < rh) & (C > rl) & (C <= mid)
    rows = []
    for side, m in ((1, spring), (-1, upthr)):
        for i in np.flatnonzero(m):
            flat = idx[i] - idx[i] % DAY + 20 * 3600 + 55 * 60
            if entry == "stop":
                lvl = H[i] if side == 1 else L[i]
                k = first_hit(ctx, cs[i] + 1, min(cs[i] + 3 * tf, flat - 3600), lvl, up=(side == 1))
                if k < 0:
                    continue
            else:
                lvl = C[i]; k = cs[i]
            stop = L[i] - 0.1 * a5[i] if side == 1 else H[i] + 0.1 * a5[i]
            tgt = rh[i] if side == 1 else rl[i]
            sl = side * (lvl - stop); tp = side * (tgt - lvl)
            if tp <= 0:
                continue
            rows.append(dict(sec=k, side=side, sl=sl, tp=tp, unit=sl, hold=min(24 * tf, flat - k)))
    return cap_per_day(frame(rows), 2)
