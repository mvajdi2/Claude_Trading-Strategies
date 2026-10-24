"""Session-VWAP cross with H1/H4 EMA trend filter (5m).

Card: marketplaces-vwap-cross-mtf-ema-5m.
Long at the close of a 5m bar (07:00-19:00 UTC) that crosses above the anchored session VWAP
(tick-count weighted, anchor UTC hour) while the last closed H1 and H4 closes are above their
EMA(ema_len); mirror for shorts. Stop stop_atr*ATR14(5m); TP1 1.5 ATR (50%), TP2 3 ATR, stop to
break-even after TP1. Max 3 trades per day, no new signal within 6 bars of the previous one;
signals only >= 1 bar after the same-day VWAP anchor; time exit 20:45 UTC. stop_atr is a module
argument only (templates span it).
unit = ATR14(5m).
"""
import numpy as np, pandas as pd
import bt1s

PARAMS = {
    "ema_len": [50, 20, 100, 200],
    "vwap_anchor": [0.0, 7.0, 13.5],
}
EXIT_UNIT = True


def _vwap(b, anchor_h):
    tp = (b.h + b.l + b.c) / 3
    grp = ((b.index.values - int(anchor_h * 3600)) // 86400)
    v = b.n.astype(float).values
    cpv = pd.Series(tp.values * v).groupby(grp).cumsum().values
    cv = pd.Series(v).groupby(grp).cumsum().values
    return cpv / np.maximum(cv, 1)


def _htf_side(ctx, b, tf, n):
    h = ctx.bars(tf)
    hf = pd.DataFrame(dict(cs=h.close_sec.values, s=np.sign(h.c.values - bt1s.ema(h.c.values, n))))
    return pd.merge_asof(pd.DataFrame(dict(cs=b.close_sec.values)), hf, on="cs").s.values


def signals(ctx, ema_len=50, vwap_anchor=0.0, stop_atr=1.5):
    b = ctx.bars(300)
    vw = _vwap(b, vwap_anchor)
    a = bt1s.atr(b, 14)
    C = b.c.values
    cp = np.r_[np.nan, C[:-1]]; vp = np.r_[np.nan, vw[:-1]]
    same = np.r_[False, ((b.index.values[1:] - int(vwap_anchor * 3600)) // 86400) ==
                 ((b.index.values[:-1] - int(vwap_anchor * 3600)) // 86400)]
    s1 = _htf_side(ctx, b, 3600, ema_len); s4 = _htf_side(ctx, b, 14400, ema_len)
    hour = (b.index.values % 86400) / 3600
    tod = b.index.values % 86400
    after_anchor = (tod - int(vwap_anchor * 3600)) >= 300          # >= 1 bar after the same-day anchor
    base = same & after_anchor & (hour >= 7) & (hour < 19) & np.isfinite(a)
    lg = base & (C > vw) & (cp <= vp) & (s1 > 0) & (s4 > 0)
    sh = base & (C < vw) & (cp >= vp) & (s1 < 0) & (s4 < 0)
    m = lg | sh
    s = pd.DataFrame(dict(sec=b.close_sec.values[m].astype(np.int64), side=np.where(lg, 1, -1)[m],
                          unit=a[m]))
    # spacing >= 6 bars and max 3 per day
    keep, last, cnt, lastday = [], -10**12, 0, -1
    for sec in s.sec.values:
        d = sec // 86400
        if d != lastday:
            cnt, lastday = 0, d
        if sec - last >= 6 * 300 and cnt < 3:
            keep.append(True); last = sec; cnt += 1
        else:
            keep.append(False)
    s = s[np.array(keep, bool)].reset_index(drop=True)
    s["sl"] = stop_atr * s.unit; s["tp1"] = 1.5 * s.unit; s["f1"] = 0.5; s["be"] = 1
    s["tp"] = 3.0 * s.unit
    s["hold"] = ((s.sec // 86400) * 86400 + 20 * 3600 + 45 * 60 - s.sec).astype(np.int64)   # time exit 20:45
    return s
