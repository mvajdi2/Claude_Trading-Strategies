"""Market Profile 80% rule (30m), Batch B #5. Card: books-mp-80pct-rule.

Prior trading day (23:00-21:00 UTC) profile in $0.50 bins: tick_volume = 1m tick counts at the 1m
typical price; TPO = one count per 30m bar per bin touched. Value area = va_pct of the profile grown
from the POC. Today: price at the reference time (07:00 / 23:00 / 13:30 UTC) below VAL (and not more
than 1 VA width below); then confirm_bars consecutive 30m closes inside the value area -> buy at the
close of the last one (market), before 16:00 UTC. Stop = today's low - 0.1*ATR14(30m), capped at
1 VA width; target = VAH; time exit 20:55; max 1/day. Mirror for shorts. unit = stop distance.
"""
import numpy as np, pandas as pd, bt1s
from strategies._bxutil import DAY, frame, tday

PARAMS = {
    "va_pct": [0.68, 0.70, 0.80],
    "confirm_bars": [1, 2],
    "ref_hour": [7, 13.5, 23],      # 23 = trading-day open (23:00 UTC)
    "profile": ["tick_volume", "TPO"],
}
DEFAULTS = dict(va_pct=0.70, confirm_bars=2, ref_hour=7, profile="tick_volume")
EXIT_UNIT = True
BIN = 0.5


def _value_area(prices_bins, w, va_pct):
    lo = prices_bins.min(); hist = np.bincount(prices_bins - lo, weights=w)
    tot = hist.sum()
    if tot <= 0:
        return np.nan, np.nan, np.nan
    p = int(np.argmax(hist)); i = j = p; acc = hist[p]
    while acc < va_pct * tot:
        up = hist[j + 1] if j + 1 < len(hist) else -1
        dn = hist[i - 1] if i - 1 >= 0 else -1
        if up < 0 and dn < 0:
            break
        if up >= dn:
            j += 1; acc += up
        else:
            i -= 1; acc += dn
    return (lo + i) * BIN, (lo + j + 1) * BIN, (lo + p + 0.5) * BIN


def _profiles(ctx, va_pct, profile):
    if profile == "tick_volume":
        m = ctx.bars(60)
        hr = (m.index.values % DAY) // 3600
        m = m[(hr < 21) | (hr >= 23)]
        tp = ((m.h + m.l + m.c) / 3).values
        bins = np.floor(tp / BIN).astype(np.int64); w = m.n.values.astype(float)
        dd = tday(m.index.values)
        out = {}
        st = np.r_[0, np.flatnonzero(np.diff(dd)) + 1, len(dd)]
        for s, e in zip(st[:-1], st[1:]):
            if e - s < 600:
                continue
            out[dd[s]] = _value_area(bins[s:e], w[s:e], va_pct)
        return out
    b = ctx.bars(1800)
    hr = (b.index.values % DAY) // 3600
    b = b[(hr < 21) | (hr >= 23)]
    dd = tday(b.index.values)
    out = {}
    st = np.r_[0, np.flatnonzero(np.diff(dd)) + 1, len(dd)]
    for s, e in zip(st[:-1], st[1:]):
        if e - s < 20:
            continue
        bl = []
        for h, l in zip(b.h.values[s:e], b.l.values[s:e]):
            bl.append(np.arange(int(np.floor(l / BIN)), int(np.floor(h / BIN)) + 1))
        bins = np.concatenate(bl)
        out[dd[s]] = _value_area(bins, np.ones(len(bins)), va_pct)
    return out


def signals(ctx, va_pct=0.70, confirm_bars=2, ref_hour=7, profile="tick_volume", last_entry=16):
    prof = _profiles(ctx, va_pct, profile)
    b = ctx.bars(1800)
    a = bt1s.atr(b, 14)
    idx = b.index.values; cs = b.close_sec.values
    H, L, C, O = b.h.values, b.l.values, b.c.values, b.o.values
    dd = tday(idx)
    days = sorted(prof)
    prev = {days[i]: days[i - 1] for i in range(1, len(days)) if days[i] - days[i - 1] <= 3}
    rows = []
    st = np.r_[0, np.flatnonzero(np.diff(dd)) + 1, len(dd)]
    for s, e in zip(st[:-1], st[1:]):
        td = dd[s]
        if td not in prev:
            continue
        val, vah, poc = prof[prev[td]]
        if not np.isfinite(val):
            continue
        w = vah - val
        ref_sec = td * DAY - 3600 if ref_hour == 23 else td * DAY + int(ref_hour * 3600)
        j0 = np.searchsorted(idx[s:e], ref_sec) + s
        if j0 >= e or idx[j0] - ref_sec > 1800:
            continue
        ref_px = O[j0]
        if ref_px < val:
            side = 1
            if val - ref_px > w:
                continue
        elif ref_px > vah:
            side = -1
            if ref_px - vah > w:
                continue
        else:
            continue
        cnt = 0
        for i in range(j0, e):
            if cs[i] > td * DAY + last_entry * 3600:
                break
            inside = val < C[i] < vah
            cnt = cnt + 1 if inside else 0
            if cnt >= confirm_bars:
                day0 = td * DAY - 3600
                k0 = np.searchsorted(idx[s:e], day0) + s
                if side == 1:
                    stop = L[k0:i + 1].min() - 0.1 * a[i]
                    sl = min(C[i] - stop, w); tp = vah - C[i]
                else:
                    stop = H[k0:i + 1].max() + 0.1 * a[i]
                    sl = min(stop - C[i], w); tp = C[i] - val
                if tp > 0 and np.isfinite(sl):
                    rows.append(dict(sec=cs[i], side=side, sl=sl, tp=tp, unit=sl,
                                     hold=td * DAY + 20 * 3600 + 55 * 60 - cs[i]))
                break
    return frame(rows)
