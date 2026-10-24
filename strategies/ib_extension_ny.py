"""Initial balance of the NY session, narrow IB -> breakout (Batch A #8, break mode; rerun A-3).

Card books-ib-extension-ny (breakout half; the fade half is strategies/ib_fade_ny.py).
IB = 1m high/low over [ib_start, ib_start + ib_minutes). ib_start: "13:30" UTC (card default),
"ny0820" (08:20 America/New_York = COMEX open, DST aware) or "ny0930" (09:30 New York, DST aware).
W = IB width, med = median W of the prior 20 IBs. Trade only if W < narrow_mult*med.
Entry: first 5m close beyond the IB (bars closing before 18:00 UTC) on the same side of the session
VWAP (tick-weighted) anchored at ib_start.
Card exit: stop at IB mid, target ext_target*W beyond the broken edge, flat 20:00 UTC. 1 trade/day.
unit = native stop distance (entry to IB mid, USD).
"""
import numpy as np, pandas as pd
from strategies import batcha_util as U

PARAMS = {
    "ib_start": ["13:30", "ny0820", "ny0930"],
    "ib_minutes": [60, 30],
    "narrow_mult": [0.7, 0.5, 0.85],
    "ext_target": [1.0, 0.5, 1.5],
}
EXIT_UNIT = True


def _ib_start(tds, ib_start):
    if ib_start.startswith("ny"):
        return U.local_sec(tds, int(ib_start[2:4]) * 60 + int(ib_start[4:6]), "America/New_York")
    hh, mm = map(int, ib_start.split(":"))
    return U.at(tds, hh + mm / 60)


def signals(ctx, ib_start="13:30", ib_minutes=60, narrow_mult=0.7, ext_target=1.0):
    b1 = ctx.bars(60)
    tds = U.trading_days(ctx)
    t0 = _ib_start(tds, ib_start)
    t1 = t0 + ib_minutes * 60
    ib = U.window_hl(b1, t0, t1, tds, min_frac=0.6)
    W = ib.rh - ib.rl
    med = W.rolling(20, min_periods=10).median().shift(1)
    ib = ib.assign(W=W, med=med).reindex(tds)
    ib["t0"], ib["t1"] = t0, t1
    ib = ib.dropna()
    ib = ib[ib.W < narrow_mult * ib.med]
    b5 = ctx.bars(300)
    bi = b5.index.values; C = b5.c.values
    tp_ = ((b5.h + b5.l + b5.c) / 3).values; nn = b5.n.values.astype(float)
    rows = []
    for td, r in ib.iterrows():
        a = np.searchsorted(bi, r.t0, "left")
        j0 = np.searchsorted(bi, r.t1, "left")
        jend = np.searchsorted(bi, U.at(td, 18) - 300, "right")
        if jend <= j0:
            continue
        vw = np.cumsum(tp_[a:jend] * nn[a:jend]) / np.maximum(np.cumsum(nn[a:jend]), 1)
        mid = 0.5 * (r.rh + r.rl)
        for j in range(j0, jend):
            v = vw[j - a]
            if C[j] > r.rh and C[j] > v:
                rows.append((bi[j] + 299, 1, C[j] - mid, r.rh + ext_target * r.W - C[j], td)); break
            if C[j] < r.rl and C[j] < v:
                rows.append((bi[j] + 299, -1, mid - C[j], C[j] - (r.rl - ext_target * r.W), td)); break
    s = pd.DataFrame(rows, columns=["sec", "side", "sl", "tp", "td"])
    s["hold"] = np.maximum(U.at(s.td.values, 20) - s.sec.values, 60)
    s["unit"] = s.sl
    s = s[(s.sl > 0) & (s.tp > 0)]
    return s.drop(columns="td").sort_values("sec").reset_index(drop=True)
