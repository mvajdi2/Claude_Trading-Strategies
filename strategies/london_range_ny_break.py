"""London session range breakout in the first New York 30m bars (Batch A #6, break mode; rerun A-1).

Card marketplaces-london-range-ny-breakout-30m.
London range = 1m high/low in [london_start, 12:00) UTC.
Entry window: the first `ny_bars` 30m bars starting at ny_start ("12:30" fixed UTC, or "ny0830" =
08:30 America/New_York, DST aware). Long: a 30m close > London high whose close is not above the
30m upper BB(20,2); short mirrored.
BB-zone interpretation (card's "red/green zone" rule is not defined exactly): a breakout bar that
closes beyond the outer band is skipped and the next bar in the window may still trigger.
Skip the day if London range > rng_atr_max * ATR14(30m) measured at 12:00 (card: 2.5).
Card exit: stop at the opposite London extreme; target = target_r*R or the outer BB at the entry bar,
whichever is nearer ("1R or outer band, whichever first"; band frozen at entry); flat 20:00 UTC.
1 trade/day. unit = stop distance (USD).
"""
import numpy as np, pandas as pd
import bt1s
from strategies import batcha_util as U

PARAMS = {
    "london_start": [7, 6, 8],
    "ny_start": ["12:30", "ny0830"],
    "ny_bars": [3, 2, 4],
    "rng_atr_max": [2.5, 5.0],
    "target_r": [1.0, 1.5, 2.0],
}
EXIT_UNIT = True


def signals(ctx, london_start=7, ny_start="12:30", ny_bars=3, rng_atr_max=2.5, target_r=1.0):
    b1 = ctx.bars(60)
    tds = U.trading_days(ctx)
    lr = U.window_hl(b1, U.at(tds, london_start), U.at(tds, 12), tds, min_frac=0.6)
    tds, LH, LL = lr.index.values, lr.rh.values, lr.rl.values
    b30 = ctx.bars(1800).copy()
    c = b30.c.values
    mid = bt1s.sma(c, 20); sd = pd.Series(c).rolling(20).std().values
    b30["ub"], b30["lb"] = mid + 2 * sd, mid - 2 * sd
    b30["atr"] = bt1s.atr(b30, 14)
    b30["td"] = U.tday_of(b30.index.values)
    t0 = U.local_sec(tds, 510, "America/New_York") if ny_start == "ny0830" else U.at(tds, 12.5)
    lv = pd.DataFrame(dict(LH=LH, LL=LL, t0=t0, t1=t0 + ny_bars * 1800), index=tds)
    i = np.searchsorted(b30.close_sec.values, U.at(tds, 12), "left") - 1
    lv["atr12"] = np.where(i >= 0, b30.atr.values[np.maximum(i, 0)], np.nan)
    x = b30.join(lv, on="td", how="inner")
    x = x[(x.index >= x.t0) & (x.index < x.t1) & (x.LH - x.LL <= rng_atr_max * x.atr12)]
    lc = (x.c > x.LH) & (x.c <= x.ub)
    sc = (x.c < x.LL) & (x.c >= x.lb)
    x = x[lc | sc]
    x = x[~x.td.duplicated()]
    side = np.where(x.c > x.LH, 1, -1)
    sl = np.where(side > 0, x.c - x.LL, x.LH - x.c)
    band = np.where(side > 0, x.ub - x.c, x.c - x.lb)
    tp = np.maximum(np.minimum(target_r * sl, band), 0.10)
    flat = U.at(x.td.values, 20)
    s = pd.DataFrame(dict(sec=x.close_sec.values, side=side, sl=sl, tp=tp,
                          hold=np.maximum(flat - x.close_sec.values, 60), unit=sl))
    return s[s.sl > 0].sort_values("sec").reset_index(drop=True)
