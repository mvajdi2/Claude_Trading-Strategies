"""Initial balance of the NY session: narrow IB -> breakout, wide IB -> fade (Batch A #8).

Card books-ib-extension-ny. IB = 1m high/low over [ib_start, ib_start + ib_minutes). ib_start is
"13:30" UTC (card default), "ny0930" (09:30 America/New_York, DST aware) or "12:00" UTC.
W = IB width, med = median W of the prior 20 days.
  W < narrow_mult*med (breakout): first 5m close beyond the IB (before 18:00 UTC) on the same side of
     the session VWAP anchored at ib_start. Stop = IB mid, target = ext_target*W beyond the broken edge.
  W > wide_mult*med (fade): after a 5m bar probes beyond an IB edge, the first 5m close back inside
     -> fade toward IB mid. Stop = probe extreme + 0.1*ATR14(5m), target = IB mid.
mode restricts to "break" or "fade". Flat 20:00 UTC. 1 trade/day. unit = W.
"""
import numpy as np, pandas as pd
import bt1s
from strategies import batcha_util as U

PARAMS = {
    "ib_start": ["13:30", "ny0930", "12:00"],
    "ib_minutes": [60, 30],
    "narrow_mult": [0.7, 0.85],
    "wide_mult": [1.3, 1.5],
    "mode": ["both", "break", "fade"],
    "ext_target": [1.0],
}
EXIT_UNIT = True


def signals(ctx, ib_start="13:30", ib_minutes=60, narrow_mult=0.7, wide_mult=1.3, mode="both", ext_target=1.0):
    b1 = ctx.bars(60)
    tds = U.trading_days(ctx)
    if ib_start == "ny0930":
        t0 = U.local_sec(tds, 570, "America/New_York")
    else:
        hh, mm = map(int, ib_start.split(":"))
        t0 = U.at(tds, hh + mm / 60)
    t1 = t0 + ib_minutes * 60
    ib = U.window_hl(b1, t0, t1, tds, min_frac=0.6)
    W = ib.rh - ib.rl
    med = W.rolling(20, min_periods=10).median().shift(1)        # prior 20 IBs only
    ib = ib.assign(W=W, med=med).reindex(tds)
    ib["t0"], ib["t1"] = t0, t1
    ib = ib.dropna()
    b5 = ctx.bars(300).copy()
    b5["atr"] = bt1s.atr(b5, 14)
    b5["vw"] = np.nan
    bi = b5.index.values
    O, H, L, C, A = b5.o.values, b5.h.values, b5.l.values, b5.c.values, b5.atr.values
    tp_ = (b5.h + b5.l + b5.c).values / 3; nn = b5.n.values.astype(float)
    rows = []
    for td, r in ib.iterrows():
        narrow = r.W < narrow_mult * r.med
        wide = r.W > wide_mult * r.med
        if (narrow and mode == "fade") or (wide and mode == "break") or not (narrow or wide):
            continue
        a = np.searchsorted(bi, r.t0, "left")
        j0 = np.searchsorted(bi, r.t1, "left")
        jend = np.searchsorted(bi, U.at(td, 18), "left")
        if jend <= j0:
            continue
        cpv = np.cumsum(tp_[a:jend] * nn[a:jend]); cv = np.cumsum(nn[a:jend])
        vw = cpv / np.maximum(cv, 1)
        mid = 0.5 * (r.rh + r.rl)
        probe_hi = probe_lo = False; ext_hi = -np.inf; ext_lo = np.inf
        for j in range(j0, jend):
            sec = bi[j] + 299
            if narrow:
                v = vw[j - a]
                if C[j] > r.rh and C[j] > v:
                    sl = C[j] - mid; tp = r.rh + ext_target * r.W - C[j]
                    rows.append((sec, 1, sl, tp, td, r.W)); break
                if C[j] < r.rl and C[j] < v:
                    sl = mid - C[j]; tp = C[j] - (r.rl - ext_target * r.W)
                    rows.append((sec, -1, sl, tp, td, r.W)); break
            else:
                if H[j] > r.rh:
                    probe_hi = True; ext_hi = max(ext_hi, H[j])
                if L[j] < r.rl:
                    probe_lo = True; ext_lo = min(ext_lo, L[j])
                at_ = A[j - 1] if j > 0 else np.nan
                if probe_hi and C[j] < r.rh and C[j] > mid:
                    sl = ext_hi + 0.1 * at_ - C[j]; tp = C[j] - mid
                    rows.append((sec, -1, sl, tp, td, r.W)); break
                if probe_lo and C[j] > r.rl and C[j] < mid:
                    sl = C[j] - (ext_lo - 0.1 * at_); tp = mid - C[j]
                    rows.append((sec, 1, sl, tp, td, r.W)); break
    s = pd.DataFrame(rows, columns=["sec", "side", "sl", "tp", "td", "unit"])
    s["hold"] = np.maximum(U.at(s.td.values, 20) - s.sec.values, 60)
    s = s[(s.sl > 0) & (s.tp > 0) & np.isfinite(s.sl)]
    return s.drop(columns="td").sort_values("sec").reset_index(drop=True)
