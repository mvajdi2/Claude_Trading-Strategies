"""London session range breakout in early New York, plain or break-and-retest (Batch A #6).

Cards marketplaces-london-range-ny-breakout-30m (mode="break", defaults) and
practitioners-london-range-break-retest (mode="retest").
London range = 1m high/low in [london_start, 12:00) UTC.
break : first 30m bar starting 12:30.. (ny_bars bars) that closes beyond the range and (bb_filter)
        not beyond the 30m BB(20,2) band; skip if range > rng_atr_max*ATR14(30m) (card: 2.5). Stop = opposite extreme,
        target target_r*R, flat 20:00 UTC.
retest: first 15m close beyond the range after 12:00 (until 17:00) with bar range >= 0.8*ATR14(15m);
        within `win` 5m bars price comes back to within 0.1*ATR15 of the level, then a 5m bar
        closes back in the breakout direction beyond the level (c>o, c>LH for longs) -> enter at
        that close. Stop = level -/+ 0.5*ATR15, target 2R, flat 19:00 UTC.
win_idx selects ny_bars from [3,2,4] (break) or the retest window from [12,6,24] (retest).
unit = default stop distance (USD).
"""
import numpy as np, pandas as pd
import bt1s
from strategies import batcha_util as U

PARAMS = {
    "mode": ["break", "retest"],
    "london_start": [7, 8],
    "win_idx": [0, 1, 2],
    "bb_filter": [True, False],
    "rng_atr_max": [2.5, 5.0, 99.0],
    "target_r": [1.0],
}
EXIT_UNIT = True


def _break(ctx, tds, LH, LL, ny_bars, bb_filter, target_r, rng_atr_max):
    b30 = ctx.bars(1800).copy()
    c = b30.c.values
    mid = bt1s.sma(c, 20); sd = pd.Series(c).rolling(20).std().values
    b30["ub"], b30["lb"] = mid + 2 * sd, mid - 2 * sd
    b30["atr"] = bt1s.atr(b30, 14)
    b30["td"] = U.tday_of(b30.index.values)
    lv = pd.DataFrame(dict(LH=LH, LL=LL, t0=U.at(tds, 12.5), t1=U.at(tds, 12.5) + ny_bars * 1800), index=tds)
    # ATR at the London close (last 30m bar closed before 12:00)
    i = np.searchsorted(b30.close_sec.values, U.at(tds, 12), "left") - 1
    lv["atr12"] = np.where(i >= 0, b30.atr.values[np.maximum(i, 0)], np.nan)
    x = b30.join(lv, on="td", how="inner")
    x = x[(x.index >= x.t0) & (x.index < x.t1) & (x.LH - x.LL <= rng_atr_max * x.atr12)]
    lc = x.c > x.LH; sc = x.c < x.LL
    if bb_filter:
        lc &= x.c <= x.ub; sc &= x.c >= x.lb
    x = x[lc | sc]
    x = x[~x.td.duplicated()]
    side = np.where(x.c > x.LH, 1, -1)
    sl = np.where(side > 0, x.c - x.LL, x.LH - x.c)
    flat = U.at(x.td.values, 20)
    return pd.DataFrame(dict(sec=x.close_sec.values, side=side, sl=sl, tp=target_r * sl,
                             hold=np.maximum(flat - x.close_sec.values, 60), unit=sl))


def _retest(ctx, tds, LH, LL, win, target_r):
    b15 = ctx.bars(900).copy(); b15["atr"] = bt1s.atr(b15, 14)
    b5 = ctx.bars(300)
    b5i = b5.index.values; b5o, b5h, b5l, b5c = b5.o.values, b5.h.values, b5.l.values, b5.c.values
    b15["td"] = U.tday_of(b15.index.values)
    lv = pd.DataFrame(dict(LH=LH, LL=LL, t0=U.at(tds, 12), t1=U.at(tds, 17)), index=tds)
    x = b15.join(lv, on="td", how="inner")
    a_prev = x.atr.shift(1)                                # ATR of bars before the breakout bar
    x = x.assign(ap=a_prev)
    x = x[(x.index >= x.t0) & (x.index < x.t1)]
    disp = (x.h - x.l) >= 0.8 * x.ap
    x = x[((x.c > x.LH) | (x.c < x.LL)) & disp]
    x = x[~x.td.duplicated()]
    rows = []
    for td, r in zip(x.td.values, x.itertuples()):
        sd = 1 if r.c > r.LH else -1
        lvl = r.LH if sd > 0 else r.LL
        a = r.ap
        stop = lvl - sd * 0.5 * a
        j0 = np.searchsorted(b5i, r.close_sec + 1, "left")
        touched = False
        for j in range(j0, min(j0 + win, len(b5i))):
            if b5i[j] >= U.at(td, 19):
                break
            if (b5c[j] - stop) * sd <= 0:              # closed through the stop level: invalid
                break
            if not touched and ((sd > 0 and b5l[j] <= lvl + 0.1 * a) or (sd < 0 and b5h[j] >= lvl - 0.1 * a)):
                touched = True
            if touched and (b5c[j] - b5o[j]) * sd > 0 and (b5c[j] - lvl) * sd > 0:
                sec = b5i[j] + 299
                sl = (b5c[j] - stop) * sd
                rows.append((sec, sd, sl, target_r * sl, max(U.at(td, 19) - sec, 60), sl))
                break
    return pd.DataFrame(rows, columns=["sec", "side", "sl", "tp", "hold", "unit"])


def signals(ctx, mode="break", london_start=7, win_idx=0, bb_filter=True, rng_atr_max=2.5, target_r=1.0):
    b1 = ctx.bars(60)
    tds = U.trading_days(ctx)
    lr = U.window_hl(b1, U.at(tds, london_start), U.at(tds, 12), tds, min_frac=0.6)
    tds, LH, LL = lr.index.values, lr.rh.values, lr.rl.values
    if mode == "break":
        s = _break(ctx, tds, LH, LL, [3, 2, 4][win_idx], bb_filter, target_r, rng_atr_max)
    else:
        s = _retest(ctx, tds, LH, LL, [12, 6, 24][win_idx], target_r if target_r != 1.0 else 2.0)
    s = s[s.sl > 0]
    return s.sort_values("sec").reset_index(drop=True)
