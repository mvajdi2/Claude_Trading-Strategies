"""Bollinger-inside-Keltner squeeze release breakout (Batch A #9).

Cards marketplaces-bbkc-squeeze-breakout-15m (defaults) and practitioners-bbkc-squeeze-release.
On tf bars: BB = SMA20 +- 2 sd, KC = SMA20 +- kc_mult*ATR20. Squeeze on = BB inside KC.
Signal on the first bar with squeeze off after >= min_sq consecutive squeeze bars, close beyond the
BB band (long: close > upper BB) and, if slope_req, SMA20 rising (falling for shorts).
Entries 06:00-18:00 UTC, max 2 per day. Default exit: stop at the opposite side of the squeeze-bar
range, target 2R (card's "2R" exit variant; the indicator trail is not representable), flat 20:45.
unit = default stop distance.
"""
import numpy as np, pandas as pd
import bt1s
from strategies import batcha_util as U

PARAMS = {
    "tf": [900, 300, 3600],
    "min_sq": [6, 4, 10],
    "kc_mult": [1.5, 1.0, 1.25, 2.0],
    "slope_req": [True, False],
    "target_r": [2.0],
}
EXIT_UNIT = True


def signals(ctx, tf=900, min_sq=6, kc_mult=1.5, slope_req=True, target_r=2.0):
    b = ctx.bars(tf)
    c = b.c.values; h = b.h.values; l = b.l.values
    m = bt1s.sma(c, 20); sd = pd.Series(c).rolling(20).std().values
    a = bt1s.atr(b, 20)
    ub, lb = m + 2 * sd, m - 2 * sd
    uk, lk = m + kc_mult * a, m - kc_mult * a
    sq = (ub < uk) & (lb > lk)
    run = np.zeros(len(c), np.int64)
    for i in range(1, len(c)):
        run[i] = run[i - 1] + 1 if sq[i] else 0
    prev_run = np.r_[0, run[:-1]]
    rel = (~sq) & (prev_run >= min_sq)
    slope = np.r_[0, np.diff(m)]
    lg = rel & (c > ub) & ((slope > 0) | (not slope_req))
    sh = rel & (c < lb) & ((slope < 0) | (not slope_req))
    cs = b.close_sec.values
    sod = (cs + 1) % 86400
    win = (sod > 6 * 3600) & (sod <= 18 * 3600)
    idx = np.where((lg | sh) & win)[0]
    rows = []
    for i in idx:
        k = prev_run[i]
        lo_, hi_ = l[i - k:i].min(), h[i - k:i].max()
        sd_ = 1 if lg[i] else -1
        sl = (c[i] - lo_) if sd_ > 0 else (hi_ - c[i])
        if sl <= 0:
            continue
        rows.append((cs[i], sd_, sl, target_r * sl, sl))
    s = pd.DataFrame(rows, columns=["sec", "side", "sl", "tp", "unit"])
    td = U.tday_of(s.sec.values)
    s = s[pd.Series(td).groupby(td).cumcount().values < 2]
    s["hold"] = np.maximum(U.at(U.tday_of(s.sec.values), 20.75) - s.sec.values, 60)
    return s.reset_index(drop=True)
