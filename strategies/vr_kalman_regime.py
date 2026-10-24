"""Variance-ratio regime switch with a Kalman-level z-score, 5m (card r2-vr-regime-kalman-revert).

5m mid bars = ctx.bars(300); r = 5m log return (consecutive bars only).
  VR  = Var(overlapping q-bar sums of r) / (q * Var(r)), both over the last L_vr=576 bars,
        smoothed with EMA(12)  (Lo-MacKinlay style).
  Kalman local level on 5m closes, R = 1, Q = snr (0.01, card default); residual z =
        (close - level) / sd(close - level over the last 288 bars).
  Regime: REVERT if VR < 1 - vr_band, TREND if VR > 1 + vr_band (card vr_lo/vr_hi = 0.85/1.15 is
        vr_band 0.15; the card grids 0.8-0.9 / 1.1-1.25 are covered by vr_band 0.10/0.15/0.25),
        and the regime must have held for >= 6 bars (incl. the signal bar).
  REVERT: BUY when z crosses back above -z_in from below; SELL when z crosses back below +z_in.
  TREND : BUY when z crosses above +z_in; SELL when z crosses below -z_in.
  regime_branch: both | revert_only | trend_only (structural switch, listed last).
Filters: entries 01:00-20:30 UTC; skip if a tier-1 release (verified calendar, _d1util.TIER1) is
  within 15 min either side; one position at a time (signals inside a native holding period dropped).
Card exit (precomputed into `hold`, max 48 bars, flat 20:55 UTC):
  REVERT: target z back to 0, score stop |z| >= z_stop (3.5); TREND: exit when z crosses back
  through 0, trail 1.0*ATR14(5m) once +1 ATR in profit (engine: tp1 = 1 ATR with f1 = 0, trail).
  Hard stop 1.5*ATR14(5m) on both branches (`sl`; the card gives it for TREND, it is the price stop
  that backs the score stop for REVERT). unit = that hard-stop distance.
Benchmark (not in the search): regime gate off (gate="none") = unconditional Kalman z fade.
"""
import numpy as np, pandas as pd
import bt1s
from strategies import _d1util as U

PARAMS = {
    "q": [3, 6, 12],
    "vr_band": [0.10, 0.15, 0.25],
    "z_in": [1.5, 2.0, 2.5],
    "regime_branch": ["both", "revert_only", "trend_only"],
}
DEFAULTS = dict(q=6, vr_band=0.15, z_in=2.0, regime_branch="both")
EXIT_UNIT = True
L_VR, SNR, Z_STOP, MAX_BARS = 576, 0.01, 3.5, 48


def _kalman(y, snr):
    lvl = np.empty(len(y)); x = y[0]; P = 1.0
    for i in range(len(y)):
        Pp = P + snr
        K = Pp / (Pp + 1.0)
        x = x + K * (y[i] - x)
        P = (1 - K) * Pp
        lvl[i] = x
    return lvl


def _base(ctx):
    key = "_d1_vr_base"
    if key in ctx._bars:
        return ctx._bars[key]
    b = ctx.bars(300).copy()
    b["atr"] = bt1s.atr(b, 14)
    res = b.c.values - _kalman(b.c.values, SNR)
    b["z"] = res / pd.Series(res).rolling(288, min_periods=144).std().values
    b["news"] = U.near_release(b.close_sec.values, U.calendar_secs(ctx), 900, 900)
    gap = np.r_[False, np.diff(b.index.values) == 300]
    b["r"] = np.log(b.c).diff().where(gap)
    ctx._bars[key] = b
    return b


def _vr(b, q):
    key = f"vr{q}"
    if key not in b:
        r = b.r
        qs = r.rolling(q, min_periods=q).sum()
        vr = qs.rolling(L_VR, min_periods=L_VR // 2).var() / (q * r.rolling(L_VR, min_periods=L_VR // 2).var())
        b[key] = vr.ewm(span=12, adjust=False, ignore_na=True).mean().values
    return b[key].values


def signals(ctx, q=6, vr_band=0.15, z_in=2.0, regime_branch="both", gate="vr"):
    b = _base(ctx)
    vr = _vr(b, q)
    z = b.z.values; zp = np.r_[np.nan, z[:-1]]
    cs = b.close_sec.values
    tod = (cs % 86400) / 3600.0
    rev = vr < 1 - vr_band; trd = vr > 1 + vr_band
    hold6 = lambda m: pd.Series(m.astype(float)).rolling(6, min_periods=6).min().values == 1
    if gate == "none":
        rev6 = np.ones(len(b), bool); trd6 = np.zeros(len(b), bool)
    else:
        rev6 = hold6(rev); trd6 = hold6(trd)
    if regime_branch == "revert_only":
        trd6 = np.zeros(len(b), bool)
    elif regime_branch == "trend_only":
        rev6 = np.zeros(len(b), bool)
    ok = (tod >= 1.0) & (tod <= 20.5) & ~b.news.values & np.isfinite(b.atr.values)
    r_long = ok & rev6 & (zp < -z_in) & (z >= -z_in)
    r_short = ok & rev6 & (zp > z_in) & (z <= z_in)
    t_long = ok & trd6 & (zp < z_in) & (z >= z_in)
    t_short = ok & trd6 & (zp > -z_in) & (z <= -z_in)
    cand = np.flatnonzero(r_long | r_short | t_long | t_short)
    atr = b.atr.values; n = len(b)
    rows = []; free_from = -1
    for i in cand:
        if i < free_from:
            continue
        trend = bool(t_long[i] or t_short[i])
        side = 1 if (r_long[i] or t_long[i]) else -1
        end_s = U.utc_sec(U.tday(cs[i]), "20:55")
        j_exit = None
        for j in range(i + 1, min(i + MAX_BARS, n - 1) + 1):
            if cs[j] > end_s:
                break
            zj = z[j]
            j_exit = j
            if not np.isfinite(zj):
                continue
            if trend:
                if (side == 1 and zj <= 0) or (side == -1 and zj >= 0):
                    break
            else:
                if (side == 1 and (zj >= 0 or zj <= -Z_STOP)) or (side == -1 and (zj <= 0 or zj >= Z_STOP)):
                    break
        if j_exit is None:
            continue
        hold = min(cs[j_exit], end_s) - cs[i]
        if hold < 60:
            continue
        a = atr[i]
        row = dict(sec=cs[i], side=side, sl=1.5 * a, tp=0.0, hold=hold, unit=1.5 * a,
                   tp1=a if trend else 0.0, f1=0.0, trail=a if trend else 0.0, branch="T" if trend else "R")
        rows.append(row)
        free_from = j_exit + 1
    return U.frame(rows)
