"""RSI(14) extreme fade with EMA200 trend filter, Batch B #7. Card: practitioners-rsi-extreme-ema200-fade.

Long: closed bar with close > EMA200 and RSI14 < rsi_lo -> buy at close; short: close < EMA200 and
RSI14 > 100 - rsi_lo. Stop 1.0*ATR14, target 2.0*ATR14 (card's ATR replacement of the 5/10-pip
script exits), time exit hold_min or 20:00 UTC; session 07:00-20:00 UTC; skip 08:25-08:35 and
09:55-10:05 New York time (US releases, DST-aware; audit fix of the fixed-UTC window).
one_per_episode: only the first bar of each RSI extreme episode signals; re-arm after RSI crosses
back through 50. Otherwise every extreme bar signals (engine holds one position at a time).
unit = ATR14(tf) (the card's stop). Card defaults: tf 300, rsi_lo 30, ema_filter True, hold 60.
"""
import numpy as np, pandas as pd, bt1s
from strategies._bxutil import DAY, frame, ny_blackout

PARAMS = {
    "tf": [60, 300],
    "rsi_lo": [20, 25, 30],
    "ema_filter": [False, True],
    "hold_min": [30, 60, 120],
    "one_per_episode": [False, True],
}
DEFAULTS = dict(tf=300, rsi_lo=30, ema_filter=True, hold_min=60, one_per_episode=False)
EXIT_UNIT = True


def _episode_first(cond, rsi, side):
    """first bar of each episode; re-arm only after RSI returns through 50"""
    out = np.zeros(len(cond), bool); armed = True
    for i in range(len(cond)):
        if not armed and ((rsi[i] >= 50) if side == 1 else (rsi[i] <= 50)):
            armed = True
        if armed and cond[i]:
            out[i] = True; armed = False
    return out


def signals(ctx, tf=300, rsi_lo=30, ema_filter=True, hold_min=60, one_per_episode=False,
            stop_atr=1.0, target_atr=2.0):
    b = ctx.bars(tf)
    C = b.c.values; idx = b.index.values; cs = b.close_sec.values
    a = bt1s.atr(b, 14); r = bt1s.rsi(C, 14); e = bt1s.ema(C, 200)
    hr = (cs % DAY) / 3600.0
    sess = (hr >= 7) & (hr < 20) & np.isfinite(a) & (a > 0)
    news = ny_blackout(cs, ((8 * 60 + 25, 8 * 60 + 35), (9 * 60 + 55, 10 * 60 + 5)))
    ext_lo = r < rsi_lo; ext_hi = r > 100 - rsi_lo
    if ema_filter:
        ext_lo &= C > e; ext_hi &= C < e
    ext_lo &= sess & ~news; ext_hi &= sess & ~news
    if one_per_episode:
        ext_lo = _episode_first(ext_lo, r, 1); ext_hi = _episode_first(ext_hi, r, -1)
    lg = sess & ~news & ext_lo; sh = sess & ~news & ext_hi
    side = np.where(lg, 1, np.where(sh, -1, 0))
    m = side != 0
    flat = idx - idx % DAY + 20 * 3600
    df = pd.DataFrame(dict(sec=cs[m], side=side[m], sl=stop_atr * a[m], tp=target_atr * a[m],
                           hold=np.minimum(hold_min * 60, flat[m] - cs[m]), unit=a[m]))
    return frame(df.to_dict("records"))
