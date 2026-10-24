"""Fade vol-normalised intraday overreactions (5m), Batch B #9. Card: academic-overreaction-fade-volnorm.

z = (C_t / C_{t-window} - 1) / sigma_tod, sigma_tod = stdev of the same-window return at the same
5m time-of-day slot over the previous 60 trading days (min 20). Trigger z < -z_th (long) / > z_th
(short); enter at the close of the first later 5m bar (within 6 bars) that closes up (down).
Stop = move extreme - 0.25*move; target = retrace of the move from the extreme; time exit
max_hold_min or 20:55; session 07:00-20:00 UTC; max 2/day.
Filters: news_skip skips triggers in the 60 min after 08:30 and 10:00 New York time (DST-aware;
proxy for tier-1 US releases, which cannot be listed reliably here); skip days whose prior-day
realised vol is above the 90th pct of the previous 250 days. unit = stop distance (R).
"""
import numpy as np, pandas as pd, bt1s
from strategies._bxutil import DAY, frame, tday, cap_per_day

PARAMS = {
    "z_th": [2.5, 3.0, 3.5, 4.0],
    "window_min": [15, 30, 60],
    "max_hold_min": [90, 180],
    "news_skip": [False, True],
}
DEFAULTS = dict(z_th=3.0, window_min=30, max_hold_min=90, news_skip=True)
EXIT_UNIT = True


def signals(ctx, z_th=3.0, window_min=30, max_hold_min=90, news_skip=True, retrace=0.5,
            tf=300, confirm_bars=6):
    b = ctx.bars(tf)
    O, H, L, C = b.o.values, b.h.values, b.l.values, b.c.values
    idx = b.index.values; cs = b.close_sec.values
    w = window_min * 60 // tf
    n = len(b)
    r = np.full(n, np.nan)
    contig = (idx[w:] - idx[:-w]) == w * tf
    r[w:] = np.where(contig, C[w:] / C[:-w] - 1, np.nan)
    day = idx // DAY; slot = (idx % DAY) // tf
    piv = pd.DataFrame(dict(d=day, s=slot, r=r)).pivot_table(index="d", columns="s", values="r")
    sig = piv.rolling(60, min_periods=20).std().shift(1)
    st = sig.stack()
    look = pd.Series(st.values, index=pd.MultiIndex.from_tuples(st.index))
    sg = look.reindex(pd.MultiIndex.from_arrays([day, slot])).values
    z = r / sg
    # realised-vol regime (prior trading day), top decile vetoed
    td = tday(idx)
    r1 = np.r_[np.nan, np.diff(np.log(C))]
    rv = pd.Series(r1 ** 2).groupby(td).sum() ** 0.5
    thr = rv.rolling(250, min_periods=60).quantile(0.9).shift(1)
    hot = (rv.shift(1) > thr)
    hot_bar = hot.reindex(td).fillna(False).values.astype(bool)
    sod = cs % DAY
    ok = (sod >= 7 * 3600) & (sod < 20 * 3600) & np.isfinite(z) & ~hot_bar
    if news_skip:
        et = pd.to_datetime(cs, unit="s").tz_localize("UTC").tz_convert("America/New_York")
        m_et = et.hour.values * 60 + et.minute.values
        nw = ((m_et >= 8 * 60 + 30) & (m_et < 9 * 60 + 30)) | ((m_et >= 10 * 60) & (m_et < 11 * 60))
        ok &= ~nw
    rows = []
    for side, trig in ((1, ok & (z < -z_th)), (-1, ok & (z > z_th))):
        last = -1
        for i in np.flatnonzero(trig):
            if i <= last:
                continue
            for j in range(i + 1, min(i + 1 + confirm_bars, n)):
                if day[j] != day[i] or (cs[j] % DAY) >= 20 * 3600:
                    break
                if (C[j] > O[j]) if side == 1 else (C[j] < O[j]):
                    p0 = C[i - w]
                    ex = L[i - w + 1:j + 1].min() if side == 1 else H[i - w + 1:j + 1].max()
                    move = side * (p0 - ex)
                    if move <= 0:
                        break
                    stop = ex - side * 0.25 * move
                    tgt = ex + side * retrace * move
                    sl = side * (C[j] - stop); tp = side * (tgt - C[j])
                    if tp > 0:
                        flat = idx[j] - idx[j] % DAY + 20 * 3600 + 55 * 60
                        rows.append(dict(sec=cs[j], side=side, sl=sl, tp=tp, unit=sl,
                                         hold=min(max_hold_min * 60, flat - cs[j])))
                    last = j
                    break
    return cap_per_day(frame(rows), 2)
