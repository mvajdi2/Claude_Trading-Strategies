"""Shanghai open: 5-minute ORB or open half-hour momentum (Batch A #11).

Cards practitioners-shanghai-open-orb (mode="orb", defaults) and academic-shfe-open-momentum (mode="mom").
Shanghai has no DST, so anchors are fixed UTC.
orb: range = 1m high/low over [start, start+win_min); first 1m close beyond the range until exit_h
     -> market entry; default stop 5 USD, target 2R (10 USD); flat exit_h UTC. unit = range width.
mom: r = mid(start+win_min) - mid(start); sigma = std of r over the prior 60 days; r > q*sigma -> long,
     r < -q*sigma -> short at start+win_min; stop at the start price; no target; flat exit_h UTC.
     unit = sigma (USD). (card default for mom is start 01:00, win 30, exit 06:30)
1 trade/day.
"""
import numpy as np, pandas as pd
from strategies import batcha_util as U

PARAMS = {
    "mode": ["orb", "mom"],
    "start": ["01:30", "01:00", "02:30"],
    "win_min": [5, 15, 30],
    "q": [0.5, 0.0],
    "exit_h": [6.0, 3.5],
    "stop_usd": [5.0],
    "target_r": [2.0],
}
EXIT_UNIT = True


def signals(ctx, mode="orb", start="01:30", win_min=5, q=0.5, exit_h=6.0, stop_usd=5.0, target_r=2.0):
    hh, mm = map(int, start.split(":"))
    tds = U.trading_days(ctx)
    t0 = U.at(tds, hh + mm / 60); t1 = t0 + win_min * 60
    tx = U.at(tds, exit_h)
    b1 = ctx.bars(60)
    r = U.window_hl(b1, t0, t1, tds, min_frac=0.6)
    if mode == "orb":
        tds_r = r.index.values
        pos = pd.Series(np.arange(len(tds)), index=tds).reindex(tds_r).values
        x = U.first_close_cross(b1, tds_r, t1[pos], tx[pos] - 60, r.rh.values, r.rl.values)
        W = (r.rh - r.rl).reindex(x.index).values
        p2 = pd.Series(np.arange(len(tds)), index=tds).reindex(x.index).values
        return pd.DataFrame(dict(sec=x.sec.values, side=x.side.values, sl=stop_usd, tp=target_r * stop_usd,
                                 hold=np.maximum(tx[p2] - x.sec.values, 60), unit=np.maximum(W, 0.3)))
    ok = np.isin(tds, r.index.values)            # market live in the window
    p0 = U.mid_at(ctx, t0 - 1); p1 = U.mid_at(ctx, t1 - 1)
    ret = pd.Series(np.where(ok, p1 - p0, np.nan), index=tds)
    sig = ret.dropna().rolling(60, min_periods=40).std().shift(1).reindex(tds).values
    rr = ret.values
    lg = ok & (rr > q * sig) & np.isfinite(sig); sh = ok & (rr < -q * sig) & np.isfinite(sig)
    f = lg | sh
    side = np.where(lg, 1, -1)[f]
    sec = (t1 - 1)[f]
    return pd.DataFrame(dict(sec=sec, side=side, sl=np.maximum(np.abs(rr[f]), 0.15), tp=0.0,
                             hold=np.maximum(tx[f] - sec, 60), unit=sig[f]))
