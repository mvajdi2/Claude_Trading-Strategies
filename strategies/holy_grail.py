"""Raschke/Connors Holy Grail: first pullback to the MA in a strong ADX trend, stop-order entry.

Card: books-holy-grail-15m.
Setup bar (closed, 07:00-19:00 UTC): ADX14 > adx_threshold, ADX rising over the 3 bars before it,
+DI > -DI (long) and the bar's low <= MA (first touch since ADX last crossed above the threshold).
Buy stop at setup high + 0.05*ATR14, valid for the next 3 bars; the trigger second is found on the
1s grid (decision = first second whose high reaches the level); no triggers after 20:00 UTC.
Stop = lowest low from the setup bar to the trigger second (pullback swing, min 0.2 ATR), target =
highest high of the 20 bars before the setup (prior trend extreme). Mirror for shorts. Max 2
trades per day, flat 20:55 UTC. unit = stop distance (R).
"""
import numpy as np, pandas as pd
from numba import njit
import bt1s

PARAMS = {
    "adx_threshold": [30, 25, 35],
    "ma_len": [20, 34],
    "ma_type": ["EMA", "SMA"],
    "tf": [900, 300, 3600],
}
EXIT_UNIT = True


def adx(b, n=14):
    up = b.h.diff(); dn = -b.l.diff()
    pdm = np.where((up > dn) & (up > 0), up, 0.0); mdm = np.where((dn > up) & (dn > 0), dn, 0.0)
    pc = b.c.shift(1)
    tr = np.maximum(b.h - b.l, np.maximum((b.h - pc).abs(), (b.l - pc).abs()))
    al = 1 / n
    atrw = tr.ewm(alpha=al, adjust=False).mean().values
    pdi = 100 * pd.Series(pdm).ewm(alpha=al, adjust=False).mean().values / atrw
    mdi = 100 * pd.Series(mdm).ewm(alpha=al, adjust=False).mean().values / atrw
    dx = 100 * np.abs(pdi - mdi) / np.maximum(pdi + mdi, 1e-9)
    return pd.Series(dx).ewm(alpha=al, adjust=False).mean().values, pdi, mdi


@njit(cache=True)
def _first_cross(hi, lo, k0, k1, lvl, side):
    for k in range(k0, k1):
        if side == 1 and hi[k] >= lvl:
            return k
        if side == -1 and lo[k] <= lvl:
            return k
    return -1


def signals(ctx, adx_threshold=30, ma_len=20, ma_type="EMA", tf=900):
    b = ctx.bars(tf)
    ma = bt1s.ema(b.c.values, ma_len) if ma_type == "EMA" else bt1s.sma(b.c.values, ma_len)
    a = bt1s.atr(b, 14)
    ax, pdi, mdi = adx(b)
    hh = pd.Series(b.h.values).rolling(20).max().shift(1).values
    ll = pd.Series(b.l.values).rolling(20).min().shift(1).values
    hour = (b.index.values % 86400) / 3600
    above = ax > adx_threshold
    regime = np.cumsum(np.r_[0, (above[1:] & ~above[:-1])])     # id of the current ADX>th episode
    rising = np.r_[np.nan, ax[:-1]] > np.r_[np.full(4, np.nan), ax[:-4]]   # ADX rose into the pullback
    H, L, C = b.h.values, b.l.values, b.c.values
    setups = []
    used = set()
    for i in np.flatnonzero(above & rising & (hour >= 7) & (hour < 19) & np.isfinite(a) & np.isfinite(hh)):
        if regime[i] in used:
            continue
        if pdi[i] > mdi[i] and L[i] <= ma[i]:
            used.add(regime[i]); setups.append((i, 1))
        elif mdi[i] > pdi[i] and H[i] >= ma[i]:
            used.add(regime[i]); setups.append((i, -1))
    hi1, lo1 = ctx.g["hi"], ctx.g["lo"]
    rows = []
    for i, sd in setups:
        lvl = H[i] + 0.05 * a[i] if sd == 1 else L[i] - 0.05 * a[i]
        cs = int(b.close_sec.values[i])
        k0 = int(ctx.k_of(cs)) + 1
        cap = int(ctx.k_of((cs // 86400) * 86400 + 20 * 3600))      # no triggers after 20:00 UTC
        k1 = min(k0 + 3 * tf, cap, len(hi1))
        if k1 <= k0:
            continue
        k = _first_cross(hi1, lo1, k0, k1, lvl, sd)
        if k < 0:
            continue
        # swing stop: lowest low (highest high) from the setup bar to the trigger second
        if sd == 1:
            swing = min(L[i], lo1[k0:k + 1].min()); stop = lvl - swing
        else:
            swing = max(H[i], hi1[k0:k + 1].max()); stop = swing - lvl
        stop = max(stop, 0.2 * a[i])
        tgt = (hh[i] - lvl) if sd == 1 else (lvl - ll[i])
        if tgt <= 0.2 * a[i]:
            tgt = stop                                            # no room to the prior extreme: 1R
        sec = int(ctx.sec_of(k))
        hold = (sec // 86400) * 86400 + 20 * 3600 + 55 * 60 - sec   # flat 20:55 UTC
        rows.append(dict(sec=sec, side=sd, sl=stop, tp=tgt, hold=hold, unit=stop))
    s = pd.DataFrame(rows, columns=["sec", "side", "sl", "tp", "hold", "unit"])
    if len(s):
        s["day"] = s.sec // 86400
        s = s.groupby("day").head(2).drop(columns="day")
    return s.reset_index(drop=True)
