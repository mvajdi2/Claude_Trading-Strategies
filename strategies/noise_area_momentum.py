"""Noise-area intraday momentum with VWAP trailing exit (Zarattini-Aziz-Barbon adapted) (Batch A #10).

Card academic-noise-area-momentum. O = mid at anchor (UTC). At each check time T = anchor + j*check_every
(j >= 1, T <= 20:30 UTC): move(T) = |p(T)/O - 1|; sigma(T) = mean of move(T) over the prior
lookback_days days; bands O*(1 +- band_mult*sigma). p(T) > upper -> long, < lower -> short (flip
allowed, max 3 entries/day). Exit (evaluated at check times): long when p < max(upper, VWAP from
anchor), short when p > min(lower, VWAP). The exit time is pre-computed from these closed-bar rules
and passed as `hold`; flat 20:55 UTC. Vol-target sizing is not modelled (fixed-fractional on sl).
Default sl = 3 band widths (catastrophe stop, card has none). unit = O*sigma(T) at entry (USD).
Rerun A-5: exit fills 1 s after the decision second (hold = s - e_sec; previously 0 s = look-ahead);
same-check flips are decided at s+1 so the engine no longer drops them; gap_adj = card's gap-adjusted
anchors (upper anchor max(O, prior 21:00 close), lower min(O, prior close)); anchor trimmed to 07:00
(card default) to fit the 141-combo stage-1 budget.
"""
import numpy as np, pandas as pd
from strategies import batcha_util as U

PARAMS = {
    "anchor": ["07:00"],
    "lookback_days": [14, 10, 20],
    "band_mult": [1.0, 0.75, 1.25, 1.5],
    "check_every": [1800, 900, 3600],
    "gap_adj": [False, True],
    "sl_units": [3.0],
}
EXIT_UNIT = True


def signals(ctx, anchor="07:00", lookback_days=14, band_mult=1.0, check_every=1800, gap_adj=False, sl_units=3.0):
    hh, mm = map(int, anchor.split(":"))
    ah = hh + mm / 60
    tds = U.trading_days(ctx)
    ta = U.at(tds, ah)
    J = int((U.at(0, 20.5) - U.at(0, ah)) // check_every)
    T = ta[:, None] + check_every * np.arange(1, J + 1)[None, :]
    b1 = ctx.bars(60)
    bi = b1.index.values
    # require live market at the anchor (a 1m bar within 5 min) to avoid holidays/weekend gaps
    ia = np.searchsorted(bi, ta, "left")
    okd = (ia < len(bi)) & (bi[np.minimum(ia, len(bi) - 1)] - ta < 300)
    O = U.mid_at(ctx, ta - 1)
    P = U.mid_at(ctx, T - 1)
    move = np.abs(P / O[:, None] - 1)
    move[~okd] = np.nan
    mv = pd.DataFrame(move[okd])
    sig = np.full(move.shape, np.nan)
    sig[okd] = mv.rolling(lookback_days, min_periods=lookback_days).mean().shift(1).values   # prior days only
    Ou, Od = O.copy(), O.copy()
    if gap_adj:                                   # prior trading day's 21:00 close
        pc = np.r_[np.nan, U.mid_at(ctx, U.at(tds, 21) - 1)[:-1]]
        pc = np.where(np.isfinite(pc), pc, O)
        Ou, Od = np.maximum(O, pc), np.minimum(O, pc)
    up = Ou[:, None] * (1 + band_mult * sig); dn = Od[:, None] * (1 - band_mult * sig)
    tp_ = ((b1.h + b1.l + b1.c) / 3).values; nn = b1.n.values.astype(float)
    cpv = np.r_[0, np.cumsum(tp_ * nn)]; cv = np.r_[0, np.cumsum(nn)]
    iT = np.searchsorted(bi, T, "left")              # bars with start < T are closed at T
    vw = (cpv[iT] - cpv[ia][:, None]) / np.maximum(cv[iT] - cv[ia][:, None], 1)
    flat = U.at(tds, 20 + 55 / 60)
    rows = []
    for d in range(len(tds)):
        if not okd[d] or not np.isfinite(sig[d]).all():
            continue
        pos = 0; ent = 0; e_sec = 0; e_unit = 0.0
        for j in range(J):
            p = P[d, j]; s = T[d, j] - 1
            exited = False
            if pos == 1 and p < max(up[d, j], vw[d, j]):
                rows.append((e_sec, 1, s - e_sec, e_unit)); pos = 0; exited = True
            elif pos == -1 and p > min(dn[d, j], vw[d, j]):
                rows.append((e_sec, -1, s - e_sec, e_unit)); pos = 0; exited = True
            # exit fills at s+1 (engine: decision + 1 s); a same-check flip is decided at s+1 so
            # that its fill (s+2) comes after the exit fill and is not dropped by the engine
            es = s + 1 if exited else s
            if pos == 0 and ent < 3:
                if p > up[d, j]:
                    pos, e_sec, e_unit = 1, es, O[d] * sig[d, j] * band_mult; ent += 1
                elif p < dn[d, j]:
                    pos, e_sec, e_unit = -1, es, O[d] * sig[d, j] * band_mult; ent += 1
        if pos != 0:
            rows.append((e_sec, pos, flat[d] - e_sec, e_unit))
    s = pd.DataFrame(rows, columns=["sec", "side", "hold", "unit"])
    s = s[(s.hold >= 1) & (s.unit > 0)]
    s["sl"] = sl_units * s.unit
    s["tp"] = 0.0
    return s.sort_values("sec").reset_index(drop=True)
