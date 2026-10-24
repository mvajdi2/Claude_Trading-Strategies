"""London-range break and retest continuation in the NY session (rerun A-1, split from london_range_ny_break).

Card practitioners-london-range-break-retest.
London range = 1m high/low 07:00-12:00 UTC. Skip the day if the range > 2*ATR14(1h)*5 (ATR at 12:00).
Breakout: first 15m bar after 12:00 (starting before 17:00) that closes beyond the range with bar
range >= 0.8*ATR14(15m) (ATR of the bars before it). Retest: within `retest_win` 5m bars after the
breakout bar, price comes back to within 0.1*ATR15 of the level, then a 5m bar closes in the breakout
direction beyond the level (long: c > o and c > LH) -> enter at that close. Invalid if a 5m bar closes
through the stop level first.
Card exit: stop = level - stop_atr*ATR15 (long; mirrored short), target target_r*R, flat 19:00 UTC.
1 trade/day. unit = stop distance (USD).
"""
import numpy as np, pandas as pd
import bt1s
from strategies import batcha_util as U

PARAMS = {
    "retest_win": [12, 6, 24],
    "stop_atr": [0.5, 0.3, 1.0],
    "target_r": [2.0, 1.0, 1.5, 3.0],
}
EXIT_UNIT = True


def signals(ctx, retest_win=12, stop_atr=0.5, target_r=2.0):
    b1 = ctx.bars(60)
    tds = U.trading_days(ctx)
    lr = U.window_hl(b1, U.at(tds, 7), U.at(tds, 12), tds, min_frac=0.6)
    tds, LH, LL = lr.index.values, lr.rh.values, lr.rl.values
    h1 = ctx.bars(3600); a1 = bt1s.atr(h1, 14)
    i = np.searchsorted(h1.close_sec.values, U.at(tds, 12), "left") - 1
    atr1h = np.where(i >= 0, a1[np.maximum(i, 0)], np.nan)
    ok = (LH - LL) <= 2 * atr1h * 5
    tds, LH, LL = tds[ok], LH[ok], LL[ok]
    b15 = ctx.bars(900).copy(); b15["atr"] = bt1s.atr(b15, 14)
    b5 = ctx.bars(300)
    b5i = b5.index.values; b5o, b5h, b5l, b5c = b5.o.values, b5.h.values, b5.l.values, b5.c.values
    b15["td"] = U.tday_of(b15.index.values)
    b15["ap"] = b15.atr.shift(1)
    lv = pd.DataFrame(dict(LH=LH, LL=LL, t0=U.at(tds, 12), t1=U.at(tds, 17)), index=tds)
    x = b15.join(lv, on="td", how="inner")
    x = x[(x.index >= x.t0) & (x.index < x.t1)]
    disp = (x.h - x.l) >= 0.8 * x.ap
    x = x[((x.c > x.LH) | (x.c < x.LL)) & disp]
    x = x[~x.td.duplicated()]
    rows = []
    for td, r in zip(x.td.values, x.itertuples()):
        sd = 1 if r.c > r.LH else -1
        lvl = r.LH if sd > 0 else r.LL
        a = r.ap
        stop = lvl - sd * stop_atr * a
        j0 = np.searchsorted(b5i, r.close_sec + 1, "left")
        tend = U.at(td, 19)
        touched = False
        for j in range(j0, min(j0 + retest_win, len(b5i))):
            if b5i[j] + 300 > tend:
                break
            if (b5c[j] - stop) * sd <= 0:
                break
            if not touched and ((sd > 0 and b5l[j] <= lvl + 0.1 * a) or (sd < 0 and b5h[j] >= lvl - 0.1 * a)):
                touched = True
            if touched and (b5c[j] - b5o[j]) * sd > 0 and (b5c[j] - lvl) * sd > 0:
                sec = b5i[j] + 299
                sl = (b5c[j] - stop) * sd
                rows.append((sec, sd, sl, target_r * sl, max(tend - sec, 60), sl))
                break
    s = pd.DataFrame(rows, columns=["sec", "side", "sl", "tp", "hold", "unit"])
    return s[s.sl > 0].sort_values("sec").reset_index(drop=True)
