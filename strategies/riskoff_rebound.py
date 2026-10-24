"""Gold rebound after a joint Nasdaq-and-gold liquidation (card r2-riskoff-coliquidation-rebound).

Data: XAU 1m mid bars; USATECHIDXUSD (Nasdaq-100 CFD) Dukascopy 1m BID closes on a full minute grid
(forward fill <= 5 min), read at the XAU bar's minute-start index (known at the same close_sec).
rN, rG = W-minute log returns of USATECH and XAU ending at the 1m bar close.
zN, zG = (r - mean) / sd, with mean/sd of that W-minute return pooled over all 07:00-20:00 UTC
  minutes of the prior 20 trading days (today excluded).
Trigger (1m bar close t, 07:00-20:00 UTC): zN <= -kN and zG <= -kG (joint sell-off).
  Max 1 trade per day; while a trigger waits for stabilisation (<= 60 min) new triggers are ignored,
  and a cancelled trigger lets the next trigger of the day arm again.
Stabilisation: the first 5m XAU bar closing after t, within 60 min of t, whose close > its open and
  > the prior 5m bar's high. Decision = that 5m bar's close (entry at the next 1m open); none -> cancel.
mirror=True also trades the symmetric risk-on melt-up (zN >= kN and zG >= kG, 5m close < open and
  < prior 5m low -> SHORT gold) (structural, listed last; the day's first trigger of either side).
Filters: skip if a tier-1 release (verified calendar, _d1util.TIER1) falls inside the trigger window
  [t - W, t] (news_skip, card default True).
Card exit: stop = lowest XAU 1s low from t to the decision second - 0.25*ATR14(5m) (mirror: highest
  high + 0.25 ATR); target = retrace tgt_frac (0.5) of the drop from the window high (max 1s high over
  [t - W, t]) to that post-trigger low; time exit hold_min, flat 20:55 UTC.
  tgt_frac only changes tp -> exit templates (X4). unit = native stop distance.
Grid (budget 141): W [15,30,60], kN [2,2.5,3], kG [1.5,2] (2.5 dropped), hold_min [60,120,240],
  mirror [False, True].
"""
import numpy as np, pandas as pd
import bt1s
from strategies import _d1util as U

PARAMS = {
    "W_min": [15, 30, 60],
    "kN": [2.0, 2.5, 3.0],
    "kG": [1.5, 2.0],
    "hold_min": [60, 120, 240],
    "mirror": [False, True],
}
DEFAULTS = dict(W_min=30, kN=2.5, kG=2.0, hold_min=120, mirror=False)
EXIT_UNIT = True
TGT_FRAC = 0.5
RISK = "USATECHIDXUSD"


def _base(ctx):
    key = "_d1_ro_base"
    if key in ctx._bars:
        return ctx._bars[key]
    b = ctx.bars(60)[["c", "close_sec"]].copy()
    idx = b.index.values
    allm = np.arange(idx[0] - 86400, idx[-1] + 60, 60, dtype=np.int64)
    pos = np.searchsorted(allm, idx)
    lx = np.log(pd.Series(b.c.values, index=idx).reindex(allm).ffill(limit=5).values)
    ln = np.log(ctx.m1(RISK).c.reindex(allm).ffill(limit=5).values)
    b5 = ctx.bars(300).copy()
    b5["atr"] = bt1s.atr(b5, 14)
    b5["ph"] = b5.h.shift(1); b5["pl"] = b5.l.shift(1)
    b5.loc[np.r_[True, np.diff(b5.index.values) != 300], ["ph", "pl"]] = np.nan
    ctx._bars[key] = dict(b=b, pos=pos, lx=lx, ln=ln, b5=b5, rel=U.calendar_secs(ctx), cache={})
    return ctx._bars[key]


def _z(base, W):
    if W in base["cache"]:
        return base["cache"][W]
    b = base["b"]; pos = base["pos"]; idx = b.index.values
    tod = (idx % 86400) / 3600.0
    out = {}
    for nm, L in (("N", base["ln"]), ("G", base["lx"])):
        r = L[pos] - L[pos - W]
        m = (tod >= 7) & (tod < 20) & np.isfinite(r)
        d = pd.DataFrame({"day": idx[m] // 86400, "x": r[m], "xx": r[m] ** 2, "n": 1.0}).groupby("day").sum()
        R = d.rolling(20, min_periods=10).sum().shift(1)
        mu = R.x / R.n; sd = np.sqrt(R.xx / R.n - mu ** 2)
        days = idx // 86400
        out[nm] = (r - mu.reindex(days).values) / sd.reindex(days).values
    base["cache"][W] = out
    return out


def signals(ctx, W_min=30, kN=2.5, kG=2.0, hold_min=120, mirror=False):
    base = _base(ctx); b = base["b"]; b5 = base["b5"]
    z = _z(base, W_min)
    sec = b.close_sec.values
    tod = (sec % 86400) / 3600.0
    sess = (tod >= 7) & (tod < 20)
    dn = sess & (z["N"] <= -kN) & (z["G"] <= -kG)
    up = sess & (z["N"] >= kN) & (z["G"] >= kG) if mirror else np.zeros(len(b), bool)
    trig = np.flatnonzero(dn | up)
    if len(trig) == 0:
        return U.frame([])
    rel = base["rel"]
    cs5 = b5.close_sec.values; o5 = b5.o.values; c5 = b5.c.values
    ph = b5.ph.values; pl = b5.pl.values; a5 = b5.atr.values
    rows = []; done_td = -1; busy_until = -1
    for i in trig:
        t = int(sec[i]); side = 1 if dn[i] else -1
        if U.tday(t) == done_td or t <= busy_until:
            continue
        if U.near_release([t], rel, W_min * 60, 0)[0]:
            continue
        busy_until = t + 3600                  # waiting for stabilisation (or cancelled after 60 min)
        j0 = np.searchsorted(cs5, t, "right")
        jz = np.searchsorted(cs5, t + 3600, "right")
        end_s = int(U.utc_sec(U.tday(t), "20:55"))
        for j in range(j0, jz):
            if side == 1:
                ok = c5[j] > o5[j] and c5[j] > ph[j]
            else:
                ok = c5[j] < o5[j] and c5[j] < pl[j]
            if not ok:
                continue
            d = int(cs5[j])
            a = a5[j]
            if not np.isfinite(a) or d >= end_s:
                break
            k0, k1 = ctx.k_of(t), ctx.k_of(d) + 1
            kw = ctx.k_of(t - W_min * 60)
            P = ctx.mid[ctx.k_of(d)]
            if side == 1:
                low = ctx.g["lo"][k0:k1].min(); wh = ctx.g["hi"][kw:k0 + 1].max()
                sl = P - (low - 0.25 * a); tp = low + TGT_FRAC * (wh - low) - P
            else:
                hi = ctx.g["hi"][k0:k1].max(); wl = ctx.g["lo"][kw:k0 + 1].min()
                sl = (hi + 0.25 * a) - P; tp = P - (hi - TGT_FRAC * (hi - wl))
            if sl > 0 and tp > 0.05:
                rows.append(dict(sec=d, side=side, sl=sl, tp=tp, hold=min(hold_min * 60, end_s - d), unit=sl))
                done_td = U.tday(t)
            break
    return U.frame(rows)
