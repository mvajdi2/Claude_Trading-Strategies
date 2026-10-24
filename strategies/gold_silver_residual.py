"""Gold/silver relative-value residual reversion, gold leg only, 5m (card r2-gold-silver-residual-revert).

5m XAU bars = ctx.bars(300) (mid). 5m XAG close = close of the XAGUSD 1m BID bar that starts in the
last minute of the 5m bar (known at the XAU bar's close_sec), forward-filled within the bar (max 4 min).
  beta  = rolling OLS slope of 5m r_XAU on r_XAG over L_beta bars (576)
  e     = r_XAU - beta*r_XAG; CR = sum of e over the last N bars; zR = CR / sd(CR over L_z=288 bars)
  zQ    = (log(XAU/XAG) - mean_M) / sd_M over the last M=60 bars
  S     = w*zR + (1-w)*zQ
LONG when S[i-1] <= -S_in and S[i] - S[i-1] >= 0.25; SHORT mirror. Decision = close of bar i.
Filters: rolling corr(r_XAU, r_XAG) over 288 bars >= corr_min (0.6) and beta in [0.25, 1.0];
  entries 01:00-20:30 UTC; skip if a US release is within 10 min either side of the decision
  (tier-1 releases of the verified calendar, _d1util.TIER1); cooldown 6 bars
  after the native exit; one position at a time.
Card exit (precomputed into `hold`): exit at the close of the first later bar with |S| <= S_out,
  i.e. S back to -S_out or beyond for longs (+S_out for shorts; S_out = 0 means S crosses 0)
  (target), or S a further 1.25 beyond its entry value (score stop), or after max_bars (48) bars,
  or 20:55 UTC. Hard stop 1.5*ATR14(5m) as `sl`; no price target. unit = the hard-stop distance.
  Fix 2026-10-24: the first run tested |S| <= S_out literally, so S_out = 0 never triggered
  (no target); rerun after the fix (see results_batchD1.md).
Grid: N, S_in, w, S_out from the card grid; L_beta, L_z, M, max_bars, corr_min at card defaults
  (budget 141).
"""
import numpy as np, pandas as pd
import bt1s
from strategies import _d1util as U

PARAMS = {
    "N": [6, 12, 24],
    "S_in": [1.75, 2.0, 2.5, 3.0],
    "w": [0.5, 0.75, 1.0],
    "S_out": [0.0, 0.5, 1.0],
}
DEFAULTS = dict(N=12, S_in=2.0, w=0.5, S_out=0.5)
EXIT_UNIT = True
L_BETA, L_Z, M_WIN, MAX_BARS, CORR_MIN = 576, 288, 60, 48, 0.6


def _base(ctx):
    key = "_d1_gs_base"
    if key in ctx._bars:
        return ctx._bars[key]
    b = ctx.bars(300).copy()
    xm = ctx.m1("XAGUSD").c
    allm = np.arange(b.index[0] - 3600, b.index[-1] + 600, 60, dtype=np.int64)
    xs = xm.reindex(allm).ffill(limit=4)
    b["s"] = xs.reindex(b.index.values + 240).values
    # consecutive-bar returns only (no return across a gap)
    gap = np.r_[False, np.diff(b.index.values) == 300]
    rX = np.log(b.c).diff().where(gap)
    rS = np.log(b.s).diff().where(gap)
    cov = (rX * rS).rolling(L_BETA, min_periods=L_BETA // 2).mean() - \
        rX.rolling(L_BETA, min_periods=L_BETA // 2).mean() * rS.rolling(L_BETA, min_periods=L_BETA // 2).mean()
    var = rS.rolling(L_BETA, min_periods=L_BETA // 2).var(ddof=0)
    b["beta"] = cov / var
    b["corr"] = rX.rolling(288, min_periods=144).corr(rS)
    b["e"] = rX - b.beta * rS
    q = np.log(b.c / b.s)
    b["zQ"] = (q - q.rolling(M_WIN).mean()) / q.rolling(M_WIN).std()
    b["atr"] = bt1s.atr(b, 14)
    rel = U.calendar_secs(ctx)
    b["news"] = U.near_release(b.close_sec.values, rel, 600, 600)
    ctx._bars[key] = b
    return b


def signals(ctx, N=12, S_in=2.0, w=0.5, S_out=0.5):
    b = _base(ctx)
    CR = b.e.rolling(N, min_periods=N).sum()
    zR = CR / CR.rolling(L_Z, min_periods=L_Z // 2).std()
    S = (w * zR + (1 - w) * b.zQ).values
    cs = b.close_sec.values
    tod = (cs % 86400) / 3600.0
    ok = (b["corr"].values >= CORR_MIN) & (b.beta.values >= 0.25) & (b.beta.values <= 1.0) & \
        (tod >= 1.0) & (tod <= 20.5) & ~b.news.values & np.isfinite(b.atr.values)
    Sp = np.r_[np.nan, S[:-1]]
    up = ok & (Sp <= -S_in) & (S - Sp >= 0.25)
    dn = ok & (Sp >= S_in) & (Sp - S >= 0.25)
    cand = np.flatnonzero(up | dn)
    atr = b.atr.values
    rows = []; free_from = -1
    n = len(b)
    for i in cand:
        if i < free_from:
            continue
        side = 1 if up[i] else -1
        end_s = U.utc_sec(U.tday(cs[i]), "20:55")
        s0 = S[i]; j_exit = None
        for j in range(i + 1, min(i + MAX_BARS, n - 1) + 1):
            if cs[j] > end_s:
                break
            sj = S[j]
            if not np.isfinite(sj):
                continue
            if side * sj >= -S_out or (side == 1 and sj <= s0 - 1.25) or (side == -1 and sj >= s0 + 1.25):
                j_exit = j; break
            j_exit = j
        if j_exit is None:
            continue
        hold = min(cs[j_exit], end_s) - cs[i]
        if hold < 60:
            continue
        sl = 1.5 * atr[i]
        rows.append(dict(sec=cs[i], side=side, sl=sl, tp=0.0, hold=hold, unit=sl))
        free_from = j_exit + 1 + 6
    return U.frame(rows)
