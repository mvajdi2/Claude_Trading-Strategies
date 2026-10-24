"""Minute-level quote-intensity surge with directional quote imbalance, spread-regime gated
(card r2-tick-intensity-imbalance-follow).

Per 1m bar from the 1s grid (data/grid1s.npz, built from Dukascopy ticks):
  N   = number of quote updates (sum of nt); IMB = (mid upticks - mid downticks)/(upticks + downticks)
        (nup/ndn = tick-to-tick mid changes counted in hfdata._aggregate);
  s   = median of the 1s (last-quote) spread over the live seconds of the bar;
  ret = bar mid close - bar mid open.
  zN  = (N - median N at that UTC clock minute over the prior 20 days) / (MAD*1.4826 of the same).
  liquid = s <= s_cap * (20-day median of s at that clock minute).
Trigger (bar i): zN >= zN_min and |IMB| >= imb_min with sign(IMB) = sign(ret) != 0.
Persistence: bar i+1 is the next minute and keeps IMB of the same sign (> 0 for longs).
Decision = close of bar i+1 (entry at the open of the following bar).
mode follow   : liquid surge -> trade in the move's direction.
mode fade_wide: illiquid surge (s > s_cap * median) -> fade the move (structural branch, listed last).
Filters: decisions 07:00-20:00 UTC; skip if any release of the verified calendar (all events) is in
  [decision - 10 min, decision + 2 min] (card: [-2, +10] min around releases); max 1 trade per 15 min.
Card exit: stop at the trigger bar's low - 0.25*ATR14(1m) (high + 0.25*ATR for shorts), target
  tgt_r (1.5) x stop distance, time exit hold_min minutes, flat 20:55 UTC.
  tgt_r only changes tp, so it is left to the exit templates (X4); unit = native stop distance.
Grid: card grid except (a) imb_min = [0.1, 0.15, 0.2] instead of [0.2, 0.3, 0.45]: on Dukascopy quote
  data the 1m IMB has sd 0.097 and |IMB| >= 0.3 occurs in 0.2 % of zN >= 3 bars (IS), so the card
  default gives 8 IS trades (0.26/wk) against the card's 1-4 per day; 0.1-0.2 restores the card's
  frequency (researcher calibration, disclosed); (b) s_cap drops 1.2 (stage-1 budget 141).
  DEFAULTS keep the card default imb_min 0.3 (screen).
"""
import numpy as np, pandas as pd
import bt1s, hfdata
from strategies import _d1util as U

PARAMS = {
    "zN_min": [2.0, 3.0, 4.0],
    "imb_min": [0.1, 0.15, 0.2],
    "s_cap": [1.5, 2.0],
    "hold_min": [5, 10, 20],
    "mode": ["fade_wide", "follow"],
}
DEFAULTS = dict(zN_min=3.0, imb_min=0.3, s_cap=1.5, hold_min=10, mode="follow")
EXIT_UNIT = True
TGT_R = 1.5


def _base(ctx):
    key = "_d1_tick_base"
    if key in ctx._bars:
        return ctx._bars[key]
    z = np.load(hfdata.CACHE)
    nup = z["nup"]; ndn = z["ndn"]
    pad = ctx.s0 % 60
    n = ctx.n + pad; m = (n + 59) // 60 * 60

    def rs(a, fill, dt):
        out = np.full(m, fill, dtype=dt); out[pad:pad + ctx.n] = a
        return out.reshape(-1, 60)
    up = rs(nup, 0, np.int64).sum(1); dn = rs(ndn, 0, np.int64).sum(1)
    del nup, ndn, z
    sp = rs(np.where(ctx.g["live"], ctx.spread, np.nan), np.nan, np.float64)
    smed = np.nanmedian(sp, axis=1)
    del sp
    idx0 = ctx.s0 - pad + np.arange(len(up), dtype=np.int64) * 60
    agg = pd.DataFrame({"up": up, "dn": dn, "s": smed}, index=idx0)
    b = ctx.bars(60)[["o", "h", "l", "c", "n", "close_sec"]].copy()
    b = b.join(agg)
    b["imb"] = (b.up - b.dn) / np.maximum(b.up + b.dn, 1)
    sec = b.index.values
    b["n_med"] = U.clock_baseline(sec, b.n.values, 20, "median")
    b["n_mad"] = U.clock_baseline(sec, b.n.values, 20, "mad")
    b["s_med"] = U.clock_baseline(sec, b.s.values, 20, "median")
    b["zN"] = (b.n - b.n_med) / b.n_mad.where(b.n_mad > 0)
    b["atr"] = bt1s.atr(b, 14)
    b["news"] = U.near_release(b.close_sec.values + 60, U.calendar_secs(ctx, None), 600, 120)
    ctx._bars[key] = b
    return b


def signals(ctx, zN_min=3.0, imb_min=0.3, s_cap=1.5, hold_min=10, mode="follow"):
    b = _base(ctx)
    idx = b.index.values
    imb = b.imb.values; ret = (b.c - b.o).values
    nxt_ok = np.r_[idx[1:] - idx[:-1] == 60, False]
    imb1 = np.r_[imb[1:], np.nan]
    liquid = b.s.values <= s_cap * b.s_med.values
    illiq = b.s.values > s_cap * b.s_med.values
    trig = (b.zN.values >= zN_min) & (np.abs(imb) >= imb_min) & (np.sign(imb) == np.sign(ret)) & (ret != 0) & \
        nxt_ok & (np.sign(imb1) == np.sign(imb)) & np.isfinite(b.atr.values)
    trig &= liquid if mode == "follow" else illiq
    i = np.flatnonzero(trig)
    j = i + 1                                   # persistence bar; decision at its close
    dec = b.close_sec.values[j]
    tod = (dec % 86400) / 3600.0
    keep = (tod >= 7.0) & (tod < 20.0) & ~b.news.values[i]
    i, j, dec = i[keep], j[keep], dec[keep]
    move = np.sign(imb[i]).astype(int)
    side = move if mode == "follow" else -move
    a = b.atr.values[i]
    C = b.c.values[j]
    sl = np.where(side == 1, C - (b.l.values[i] - 0.25 * a), (b.h.values[i] + 0.25 * a) - C)
    df = pd.DataFrame(dict(sec=dec, side=side, sl=sl, tp=TGT_R * sl,
                           hold=np.minimum(hold_min * 60, U.end_hold(dec, "20:55")), unit=sl))
    df = df[(df.sl > 0.05)]
    df = df[U.min_spacing(df.sec.values, 900)]
    return U.frame(df)
