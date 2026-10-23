"""Asian range OCO stop breakout (Batch A #1).

Merges cards marketplaces-asian-range-oco-breakout (defaults), practitioners-asian-range-london-breakout
(range end / %-range filter variants) and academic-asian-range-orb-volstate (vol-state filter).
Range = high/low of 1m bars in [range_start, range_end) UTC. Stop orders at range high + buffer /
range low - buffer, live from range_end to `cutoff` UTC; first touch wins (OCO), 1 trade per day.
Default exit: stop at the opposite side of the range, target tgt_x * range, flat at flat_h UTC.
unit = range width (USD).
"""
import numpy as np, pandas as pd
from strategies import batcha_util as U

PARAMS = {
    "range_end": [6, 5, 7],
    "buffer_usd": [0.5, 2.0],
    "cutoff": [12, 9],
    "vol_state": ["all", "midtop", "top"],
    "rng_filter": ["usd", "atr"],
    "range_start": [0],
    "flat_h": [16],
    "tgt_x": [1.5],
}
EXIT_UNIT = True


def signals(ctx, range_end=6, buffer_usd=0.5, cutoff=12, vol_state="all", rng_filter="usd",
            range_start=0, flat_h=16, tgt_x=1.5):
    b = ctx.bars(60)
    tds = U.trading_days(ctx)
    r = U.window_hl(b, U.at(tds, range_start), U.at(tds, range_end), tds, min_frac=0.6)
    tds = r.index.values
    rng = (r.rh - r.rl).values
    pd_ = U.prev_rows(U.daily(ctx), tds)
    atr = pd_["atr14"].values
    if rng_filter == "usd":
        ok = (rng >= 3.0) & (rng <= 20.0)
    elif rng_filter == "atr":
        ok = (rng >= 0.2 * atr) & (rng <= 1.0 * atr)
    elif rng_filter == "pct":
        p = rng / r.rc.values * 100
        ok = (p >= 0.3) & (p <= 1.6)
    else:
        ok = np.isfinite(rng) & (rng > 0)
    if vol_state != "all":
        vp = U.vol_state_pct(ctx, tds)
        ok &= vp >= (2 / 3 if vol_state == "top" else 1 / 3)
    tds, rh, rl, rng = tds[ok], r.rh.values[ok], r.rl.values[ok], rng[ok]
    up, dn = rh + buffer_usd, rl - buffer_usd
    start = U.at(tds, range_end)
    # skip if price already outside the levels when orders are placed
    m0 = U.mid_at(ctx, start - 1)
    inside = (m0 < up) & (m0 > dn)
    sec, side = U.first_touch(ctx, start, U.at(tds, cutoff), up, dn)
    f = inside & (sec > 0)
    sec, side, up, dn, rng, tds = sec[f], side[f], up[f], dn[f], rng[f], tds[f]
    sl = up - dn                     # from the triggered level to the opposite level
    flat = U.at(tds, flat_h)
    return pd.DataFrame(dict(sec=sec, side=side, sl=sl, tp=tgt_x * rng,
                             hold=np.maximum(flat - sec, 60), unit=rng))
