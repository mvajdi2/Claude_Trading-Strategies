"""SHFE open half-hour momentum (rerun A-6, split from shanghai_open).

Card academic-shfe-open-momentum. Fixed UTC (no DST in China).
anchor "day_01:00": r = mid(01:30) - mid(01:00) (SHFE day open 09:00 Beijing); exit at exit_utc.
anchor "night_13:00": r = mid(13:30) - mid(13:00) (SHFE night open 21:00 Beijing); exit 15:00 UTC
       (exit_utc is ignored). The card's "exclude US data days" note is not implemented (no release
       calendar in the repo).
sigma = std of r over the prior 60 eligible days. r > q*sigma -> long, r < -q*sigma -> short, entered at
the end of the half hour. SHFE holidays skipped (night: also the evening before a holiday).
Card exit: stop at the start price (distance |r|, floor $0.15), no target. 1 trade/day.
unit = native stop distance (USD).
"""
import numpy as np, pandas as pd
from strategies import batcha_util as U

PARAMS = {
    "anchor": ["day_01:00", "night_13:00"],
    "q": [0.5, 0.0, 1.0],
    "exit_utc": ["06:30", "03:30", "05:00"],
}
EXIT_UNIT = True


def signals(ctx, anchor="day_01:00", q=0.5, exit_utc="06:30"):
    night = anchor.startswith("night")
    tds = U.trading_days(ctx)
    tds = tds[~U.shfe_closed(tds, night=night)]
    t0 = U.at(tds, 13.0 if night else 1.0); t1 = t0 + 1800
    if night:
        tx = U.at(tds, 15.0)
    else:
        hh, mm = map(int, exit_utc.split(":"))
        tx = U.at(tds, hh + mm / 60)
    r = U.window_hl(ctx.bars(60), t0, t1, tds, min_frac=0.6)
    ok = np.isin(tds, r.index.values)
    p0 = U.mid_at(ctx, t0 - 1); p1 = U.mid_at(ctx, t1 - 1)
    ret = pd.Series(np.where(ok, p1 - p0, np.nan), index=tds)
    sig = ret.dropna().rolling(60, min_periods=40).std().shift(1).reindex(tds).values
    rr = ret.values
    lg = ok & np.isfinite(sig) & (rr > q * sig)
    sh = ok & np.isfinite(sig) & (rr < -q * sig)
    f = lg | sh
    side = np.where(lg, 1, -1)[f]
    sec = (t1 - 1)[f]
    sl = np.maximum(np.abs(rr[f]), 0.15)
    return pd.DataFrame(dict(sec=sec, side=side, sl=sl, tp=0.0, hold=np.maximum(tx[f] - sec, 60), unit=sl))
