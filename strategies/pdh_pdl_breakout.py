"""Previous-day high/low OCO breakout, one trade per day (Batch A #7).

Card marketplaces-pdh-pdl-oco-breakout. PDH/PDL from the previous 23:00-21:00 UTC day. From start_h
(default 00:05) to end_h UTC: buy stop at PDH + buffer, sell stop at PDL - buffer (first touch wins);
skip the day if price is already outside at placement. close_beyond=True: instead enter on the first
15m close beyond the level. Default exit: stop stop_atr*ATR14(1h) from entry, target 2R, flat 20:00.
unit = ATR14(1h) of the last closed hour before the signal.
"""
import numpy as np, pandas as pd
import bt1s
from strategies import batcha_util as U

PARAMS = {
    "buffer_usd": [0.3, 0.0, 1.0],
    "close_beyond": [False, True],
    "start_h": [5 / 60, 7],
    "end_h": [18, 12],
    "stop_atr": [1.0],
    "target_r": [2.0],
}
EXIT_UNIT = True


def signals(ctx, buffer_usd=0.3, close_beyond=False, start_h=5 / 60, end_h=18, stop_atr=1.0, target_r=2.0):
    tds = U.trading_days(ctx)
    p = U.prev_rows(U.daily(ctx)[["h", "l"]], tds)
    up = p.h.values + buffer_usd; dn = p.l.values - buffer_usd
    t0, t1 = U.at(tds, start_h), U.at(tds, end_h)
    m0 = U.mid_at(ctx, t0 - 1)
    ok = np.isfinite(up) & (m0 < up) & (m0 > dn)
    tds, up, dn, t0, t1 = tds[ok], up[ok], dn[ok], t0[ok], t1[ok]
    if close_beyond:
        x = U.first_close_cross(ctx.bars(900), tds, t0, t1, up, dn)
        sec, side = x.sec.values, x.side.values
        td_s = x.index.values
    else:
        sec, side = U.first_touch(ctx, t0, t1, up, dn)
        f = sec > 0
        sec, side, td_s = sec[f], side[f], tds[f]
    h1 = ctx.bars(3600); a1 = bt1s.atr(h1, 14)
    i = np.searchsorted(h1.close_sec.values, sec, "left") - 1
    atr = a1[np.maximum(i, 0)]
    g = np.isfinite(atr) & (atr > 0)
    sl = stop_atr * atr
    flat = U.at(td_s, 20)
    return pd.DataFrame(dict(sec=sec, side=side, sl=sl, tp=target_r * sl,
                             hold=np.maximum(flat - sec, 60), unit=atr))[g].reset_index(drop=True)
