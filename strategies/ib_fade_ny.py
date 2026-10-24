"""Initial balance of the NY session, wide IB -> fade back to IB mid (rerun A-3, split from ib_extension_ny).

Card books-ib-extension-ny (fade half).
IB = 1m high/low over [ib_start, ib_start + ib_minutes). ib_start: "13:30" UTC (card default),
"ny0820" (08:20 America/New_York = COMEX open, DST aware) or "ny0930" (09:30 New York, DST aware).
W = IB width, med = median W of the prior 20 IBs. Trade only if W > wide_mult*med.
After a 5m bar probes beyond an IB edge, the first 5m close back inside the IB (and not past the
mid) -> fade toward the mid (short after a probe above IB high, long after a probe below IB low).
Signals only on 5m bars closing before 18:00 UTC.
Card exit: stop at the probe extreme + 0.1*ATR14(5m), target IB mid, flat 20:00 UTC. 1 trade/day.
unit = native stop distance (USD).
"""
import numpy as np, pandas as pd
import bt1s
from strategies import batcha_util as U

PARAMS = {
    "ib_start": ["13:30", "ny0820", "ny0930"],
    "ib_minutes": [60, 30],
    "wide_mult": [1.3, 1.2, 1.5],
}
EXIT_UNIT = True


def _ib_start(tds, ib_start):
    if ib_start.startswith("ny"):
        return U.local_sec(tds, int(ib_start[2:4]) * 60 + int(ib_start[4:6]), "America/New_York")
    hh, mm = map(int, ib_start.split(":"))
    return U.at(tds, hh + mm / 60)


def signals(ctx, ib_start="13:30", ib_minutes=60, wide_mult=1.3):
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
    ib = ib[ib.W > wide_mult * ib.med]
    b5 = ctx.bars(300)
    bi = b5.index.values
    H, L, C = b5.h.values, b5.l.values, b5.c.values
    A = bt1s.atr(b5, 14)
    rows = []
    for td, r in ib.iterrows():
        j0 = np.searchsorted(bi, r.t1, "left")
        jend = np.searchsorted(bi, U.at(td, 18) - 300, "right")
        mid = 0.5 * (r.rh + r.rl)
        probe_hi = probe_lo = False; ext_hi = -np.inf; ext_lo = np.inf
        for j in range(j0, jend):
            if H[j] > r.rh:
                probe_hi = True; ext_hi = max(ext_hi, H[j])
            if L[j] < r.rl:
                probe_lo = True; ext_lo = min(ext_lo, L[j])
            a = A[j - 1]
            if probe_hi and mid < C[j] < r.rh:
                rows.append((bi[j] + 299, -1, ext_hi + 0.1 * a - C[j], C[j] - mid, td)); break
            if probe_lo and r.rl < C[j] < mid:
                rows.append((bi[j] + 299, 1, C[j] - (ext_lo - 0.1 * a), mid - C[j], td)); break
    s = pd.DataFrame(rows, columns=["sec", "side", "sl", "tp", "td"])
    s["hold"] = np.maximum(U.at(s.td.values, 20) - s.sec.values, 60)
    s["unit"] = s.sl
    s = s[(s.sl > 0) & (s.tp > 0) & np.isfinite(s.sl)]
    return s.drop(columns="td").sort_values("sec").reset_index(drop=True)
