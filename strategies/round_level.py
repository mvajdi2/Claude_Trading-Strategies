"""Round-number level first-touch reaction (bounce vs break, with placebo offset), Batch B #10.
Cards: marketplaces-round20-level-fade (defaults) + practitioners-round20-level-reaction.

Levels L = k*step + offset (offset 10.37 = placebo). Long-bounce setup: price approaches L from
above, the level zone [L-1, L+1] has not traded in the previous untouched_h hours (1m lows all
> L+1), and price trades down to L+0.50 (the card's limit price). MARKET-ENTRY VARIANT: the
decision is the first second whose 1s low <= L+0.50 and the engine fills at market 1 s later
(the cards use a limit at L+0.50). Momentum filter: close-to-close drop over the last 4 closed 15m
bars >= momentum_atr*ATR14(15m) (0 = off). Stop 2.5 USD beyond the level (3.0 from entry), target
1.5R, time exit hold_min or 20:45; news_skip: no entries 08:00-09:00 / 09:45-10:30 New York; session 06:00-20:00 UTC; one trade per level per day.
direction="break" trades the other way (sell the touch from above), same distances.
Mirror for approaches from below. unit = 3.0 USD (stop distance).
"""
import numpy as np, pandas as pd, bt1s
from strategies._bxutil import DAY, frame, first_hit, align, ny_blackout

PARAMS = {
    "step": [10, 20, 50],
    "offset": [0.0, 10.37],          # 10.37 = placebo levels
    "momentum_atr": [0.0, 1.0],
    "hold_min": [60, 240],
    "news_skip": [False, True],
    "direction": ["bounce", "break"],  # categorical switch, listed last
}
DEFAULTS = dict(step=20, offset=0.0, momentum_atr=1.0, hold_min=240, news_skip=True, direction="bounce")
EXIT_UNIT = True


def signals(ctx, step=20, offset=0.0, momentum_atr=1.0, hold_min=240, news_skip=True, direction="bounce",
            stop_beyond=2.5, target_r=1.5, untouched_h=4, zone=1.0, entry_off=0.5):
    m = ctx.bars(60); b15 = ctx.bars(900)
    H, L, C = m.h.values, m.l.values, m.c.values
    idx = m.index.values; cs = m.close_sec.values
    n = len(m)
    a15 = align(b15, bt1s.atr(b15, 14), idx - 1)           # last 15m bar closed before this minute
    c15 = b15.c.values
    mom = c15 - np.r_[np.full(4, np.nan), c15[:-4]]
    mom = align(b15, mom, idx - 1)
    W = untouched_h * 60
    pmin = pd.Series(L).rolling(W, min_periods=W // 2).min().shift(1).values   # previous W minutes
    pmax = pd.Series(H).rolling(W, min_periods=W // 2).max().shift(1).values
    pc = np.r_[np.nan, C[:-1]]
    sod = idx % DAY
    sess = (sod >= 6 * 3600) & (sod < 20 * 3600)
    # nearest level below / above the previous close
    lb = np.floor((pc - offset) / step) * step + offset
    la = lb + step
    # from above: touch of lb + entry_off in this minute, zone untouched before
    fa = sess & (L <= lb + entry_off) & (pmin > lb + zone)
    fb = sess & (H >= la - entry_off) & (pmax < la - zone)
    if momentum_atr > 0:
        fa &= mom <= -momentum_atr * a15
        fb &= mom >= momentum_atr * a15
    sl = stop_beyond + entry_off
    sgn = 1 if direction == "bounce" else -1
    rows = []; seen = set()
    for appr, mask, lev in ((-1, fa, lb), (1, fb, la)):
        for i in np.flatnonzero(mask):
            key = (idx[i] // DAY, round(lev[i], 2))
            if key in seen:
                continue
            seen.add(key)
            px = lev[i] + entry_off if appr == -1 else lev[i] - entry_off
            k = first_hit(ctx, idx[i], cs[i], px, up=(appr == 1))
            if k < 0:
                continue
            side = sgn * (1 if appr == -1 else -1)
            flat = idx[i] - sod[i] + 20 * 3600 + 45 * 60
            rows.append(dict(sec=k, side=side, sl=sl, tp=target_r * sl, unit=sl,
                             hold=min(hold_min * 60, flat - k)))
    df = frame(rows)
    if news_skip and len(df):   # card: skip 30 min around scheduled US data (08:30 / 10:00 NY)
        df = df[~ny_blackout(df.sec.values)].reset_index(drop=True)
    return df
