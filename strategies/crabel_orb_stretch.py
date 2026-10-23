"""Crabel opening range breakout with stretch offset at the London open (Batch A #2).

Card books-crabel-orb-stretch-london. OR = 07:00-07:00+or_minutes UTC. stretch = mean over the
prior `stretch_lookback` days of min(H-O, O-L) inside 07:00-12:00 (O = 07:00 open). Stop orders at
OR_high + k*stretch / OR_low - k*stretch live from OR end to 12:00 UTC, OCO, 1 trade/day.
Filters: prior day NR4/NR7 (23:00-21:00 bars), skip if OR width > 4*ATR14(15m).
Default exit: stop at the opposite OR side (capped 1.5*ATR14(15m)), no target, flat 12:00 UTC.
unit = default stop distance (USD).
"""
import numpy as np, pandas as pd
import bt1s
from strategies import batcha_util as U

PARAMS = {
    "or_minutes": [15, 5, 30],
    "stretch_mult": [1.0, 0.5, 1.5],
    "stretch_lookback": [10, 20],
    "nr_filter": ["NR4", "none", "NR7"],
    "exit_h": [12],
}
EXIT_UNIT = True


def signals(ctx, or_minutes=15, stretch_mult=1.0, stretch_lookback=10, nr_filter="NR4", exit_h=12):
    b = ctx.bars(60)
    tds = U.trading_days(ctx)
    # daily stretch from the 07:00-12:00 window (known after 12:00 -> used from next day on)
    lw = U.window_hl(b, U.at(tds, 7), U.at(tds, 12), tds, min_frac=0.6)
    s_day = np.minimum(lw.rh - lw.ro, lw.ro - lw.rl)
    stretch = s_day.rolling(stretch_lookback).mean()
    st = U.prev_rows(stretch.to_frame("s"), tds)["s"].values
    t_or_end = U.at(tds, 7) + or_minutes * 60
    orr = U.window_hl(b, U.at(tds, 7), t_or_end, tds, min_frac=0.6).reindex(tds)
    d = U.daily(ctx)
    nr = pd.DataFrame(dict(nr4=d.rng <= d.rng.rolling(4).min(), nr7=d.rng <= d.rng.rolling(7).min()))
    pnr = U.prev_rows(nr.astype(float), tds)
    b15 = ctx.bars(900)
    a15 = bt1s.atr(b15, 14)
    i15 = np.searchsorted(b15.close_sec.values, t_or_end, "left") - 1     # last 15m bar closed before OR end
    atr15 = np.where(i15 >= 0, a15[np.maximum(i15, 0)], np.nan)
    rh, rl = orr.rh.values, orr.rl.values
    w = rh - rl
    ok = np.isfinite(w) & np.isfinite(st) & np.isfinite(atr15) & (w <= 4 * atr15)
    if nr_filter == "NR4":
        ok &= pnr.nr4.values == 1
    elif nr_filter == "NR7":
        ok &= pnr.nr7.values == 1
    up = rh + stretch_mult * st; dn = rl - stretch_mult * st
    m0 = U.mid_at(ctx, t_or_end - 1)
    ok &= (m0 < up) & (m0 > dn)
    tds, up, dn, rh, rl, atr15, t0 = tds[ok], up[ok], dn[ok], rh[ok], rl[ok], atr15[ok], t_or_end[ok]
    sec, side = U.first_touch(ctx, t0, U.at(tds, 12), up, dn)
    f = sec > 0
    sec, side, up, dn, rh, rl, atr15, tds = sec[f], side[f], up[f], dn[f], rh[f], rl[f], atr15[f], tds[f]
    sl = np.where(side > 0, up - rl, rh - dn)
    sl = np.minimum(sl, 1.5 * atr15)
    flat = U.at(tds, exit_h)
    return pd.DataFrame(dict(sec=sec, side=side, sl=sl, tp=0.0, hold=np.maximum(flat - sec, 60), unit=sl))
