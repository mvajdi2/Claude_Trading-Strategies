"""Shanghai-open opening range breakout on 1m closes (rerun A-6, split from shanghai_open).

Card practitioners-shanghai-open-orb. Shanghai has no DST, so anchors are fixed UTC.
Range = 1m high/low over [range_start, range_start + range_minutes). First 1m close above the range
high (long) / below the range low (short) after the range, until 06:00 UTC -> market entry.
Days when SHFE/SGE is closed (Chinese public holidays, batcha_util.SHFE_HOLIDAYS) are skipped.
Card exit: stop stop_usd from entry (stop_usd = -1 means the opposite side of the range), target
target_r * stop, flat exit_h UTC. 1 trade/day. unit = native stop distance (USD).
"""
import numpy as np, pandas as pd
from strategies import batcha_util as U

PARAMS = {
    "range_start": ["01:30", "01:00", "02:30"],
    "range_minutes": [5, 15, 30],
    "stop_usd": [5.0, 2.5, 7.5, -1],
    "target_r": [2.0, 1.0, 1.5],
    "exit_h": [6.0],
}
EXIT_UNIT = True


def signals(ctx, range_start="01:30", range_minutes=5, stop_usd=5.0, target_r=2.0, exit_h=6.0):
    hh, mm = map(int, range_start.split(":"))
    tds = U.trading_days(ctx)
    tds = tds[~U.shfe_closed(tds)]
    t0 = U.at(tds, hh + mm / 60); t1 = t0 + range_minutes * 60
    tx = U.at(tds, exit_h)
    b1 = ctx.bars(60)
    r = U.window_hl(b1, t0, t1, tds, min_frac=0.6)
    pos = pd.Series(np.arange(len(tds)), index=tds)
    p = pos.reindex(r.index).values
    x = U.first_close_cross(b1, r.index.values, t1[p], tx[p] - 60, r.rh.values, r.rl.values)
    rr = r.reindex(x.index)
    if stop_usd > 0:
        sl = np.full(len(x), float(stop_usd))
    else:
        sl = np.where(x.side.values > 0, x.c.values - rr.rl.values, rr.rh.values - x.c.values)
    p2 = pos.reindex(x.index).values
    s = pd.DataFrame(dict(sec=x.sec.values, side=x.side.values, sl=sl, tp=target_r * sl,
                          hold=np.maximum(tx[p2] - x.sec.values, 60), unit=sl))
    return s[s.sl > 0].reset_index(drop=True)
