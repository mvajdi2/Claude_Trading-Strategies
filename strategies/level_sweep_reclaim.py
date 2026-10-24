"""Turtle Soup (Raschke/Connors) on an N-bar 15m channel, Batch B #2.

Card: books-turtle-soup-15m. PDH/PDL-sweep and previous-candle-sweep variants dropped (user
excluded ICT/SMC). Long: closed 15m bar makes a new N-bar low, undercutting the prior N-bar low by
>= overshoot*ATR14, and that prior low was set >= min_age bars earlier. A buy stop at the prior low
is valid for the next 2 bars: emulated by the first 1s high >= level (market fill 1 s later).
Stop = lowest low since the breakout bar - 0.1*ATR, measured from the mid at the decision second
(the price the engine fills from, audit fix: many triggers are immediate because the signal bar
already closed back beyond the level); column `immediate` = trigger within 5 s of the bar close.
news_skip: no triggers 08:00-09:00 / 09:45-10:30 New York (DST-aware). Card trail after 1R is
approximated by the exit templates. Target 1.5R; time exit 16 bars (4h) or 20:55;
session 07:00-20:00 UTC; max 2 trades/day. unit = stop distance (R). Mirror for shorts.
"""
import numpy as np, pandas as pd, bt1s
from strategies._bxutil import DAY, frame, first_hit, ext, cap_per_day, mid_at, ny_blackout

PARAMS = {
    "channel_bars": [20, 40, 80],
    "min_age_bars": [3, 4, 6],
    "overshoot_atr": [0.1, 0.2, 0.4],
    "news_skip": [False, True],
}
DEFAULTS = dict(channel_bars=20, min_age_bars=4, overshoot_atr=0.2, news_skip=True)
EXIT_UNIT = True


def signals(ctx, channel_bars=20, min_age_bars=4, overshoot_atr=0.2, news_skip=True, target_r=1.5, tf=900,
            valid_bars=2, hold_bars=16):
    b = ctx.bars(tf)
    a = bt1s.atr(b, 14)
    H, L = b.h.values, b.l.values
    idx = b.index.values; cs = b.close_sec.values
    n = len(b); N = channel_bars
    from numpy.lib.stride_tricks import sliding_window_view as swv
    # prior window = bars i-N .. i-1
    wl = swv(L, N)[:-1]; wh = swv(H, N)[:-1]       # row r covers bars r..r+N-1 -> for bar i=r+N
    lo_prev = np.full(n, np.nan); hi_prev = np.full(n, np.nan)
    lo_age = np.zeros(n, int); hi_age = np.zeros(n, int)
    lo_prev[N:] = wl.min(1); hi_prev[N:] = wh.max(1)
    lo_age[N:] = N - wl.argmin(1)                    # bars between the prior low and bar i
    hi_age[N:] = N - wh.argmax(1)
    span_ok = np.zeros(n, bool)
    span_ok[N:] = (idx[N:] - idx[:-N]) <= N * tf * 1.6   # no weekend gap inside the channel
    hr = (idx % DAY) / 3600.0
    sess = (hr >= 7) & (hr + tf / 3600.0 <= 20)
    rows = []
    for side, cond, lvl, age in (
            (1, L < lo_prev - overshoot_atr * a, lo_prev, lo_age),
            (-1, H > hi_prev + overshoot_atr * a, hi_prev, hi_age)):
        ok = cond & (age >= min_age_bars) & span_ok & sess & np.isfinite(a)
        for i in np.flatnonzero(ok):
            level = lvl[i]
            s_end = min(cs[i] + valid_bars * tf, idx[i] - idx[i] % DAY + 20 * 3600)
            k = first_hit(ctx, cs[i] + 1, s_end, level, up=(side == 1))
            if k < 0:
                continue
            ex = ext(ctx, idx[i], k, up=(side == -1))
            sl = side * (mid_at(ctx, k) - ex) + 0.1 * a[i]
            if sl <= 0:
                continue
            flat = idx[i] - idx[i] % DAY + 20 * 3600 + 55 * 60
            rows.append(dict(sec=k, side=side, sl=sl, tp=target_r * sl, unit=sl,
                             hold=min(hold_bars * tf, flat - k), immediate=int(k - cs[i] <= 5)))
    df = frame(rows)
    if news_skip and len(df):
        df = df[~ny_blackout(df.sec.values)].reset_index(drop=True)
    return cap_per_day(df, 2)
