"""Gold New York opening range breakout (Batch A #5).

Card marketplaces-ny-orb-15m-5m. OR = 09:30 to 09:30+or_minutes America/New_York (DST aware).
Entry: first entry_tf-bar close above OR high (long) / below OR low (short) after the OR, until
cutoff_ny (NY local minutes). Default exit: stop stop_x*W from entry, target target_x*W, flat at
15:00 NY. Optional filter: skip if W > 1.5*ATR14(15m). unit = OR width W (USD).
"""
import numpy as np, pandas as pd
import bt1s
from strategies import batcha_util as U

PARAMS = {
    "or_minutes": [15, 5, 30],
    "width_filter": [False, True],
    "entry_tf": [300, 60],
    "cutoff_ny": [720, 660],
    "exit_ny": [900],
    "target_x": [2.0],
    "stop_x": [0.5],
}
EXIT_UNIT = True
TZ = "America/New_York"


def signals(ctx, or_minutes=15, width_filter=False, entry_tf=300, cutoff_ny=720, exit_ny=900,
            target_x=2.0, stop_x=0.5):
    b1 = ctx.bars(60)
    tds = U.trading_days(ctx)
    t_or = U.local_sec(tds, 570, TZ)
    ok = t_or > 0
    tds, t_or = tds[ok], t_or[ok]
    t_end = t_or + or_minutes * 60
    orr = U.window_hl(b1, t_or, t_end, tds, min_frac=0.6).reindex(tds)
    W = (orr.rh - orr.rl).values
    good = np.isfinite(W) & (W > 0)
    if width_filter:
        b15 = ctx.bars(900); a15 = bt1s.atr(b15, 14)
        i = np.searchsorted(b15.close_sec.values, t_end, "left") - 1
        atr15 = np.where(i >= 0, a15[np.maximum(i, 0)], np.nan)
        good &= W <= 1.5 * atr15
    tds, t_end, W, rh, rl = tds[good], t_end[good], W[good], orr.rh.values[good], orr.rl.values[good]
    t_cut = U.local_sec(tds, cutoff_ny, TZ)
    t_x = U.local_sec(tds, exit_ny, TZ)
    be = ctx.bars(entry_tf)
    x = U.first_close_cross(be, tds, t_end, t_cut, rh, rl)
    pos = pd.Series(np.arange(len(tds)), index=tds).reindex(x.index).values
    Wx = W[pos]
    return pd.DataFrame(dict(sec=x.sec.values, side=x.side.values, sl=stop_x * Wx, tp=target_x * Wx,
                             hold=np.maximum(t_x[pos] - x.sec.values, 60), unit=Wx))
