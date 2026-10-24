"""XAU idiosyncratic residual vs a USD common factor, M15 z-score reversion (card r2-common-factor-residual-m15).

15m XAU mid bars = ctx.bars(900). Cross-asset 15m closes = close of the Dukascopy 1m BID bar that starts
in the last minute of the 15m bar (forward-filled within the bar, max 14 min), known at the XAU bar's
close_sec -> causal. Returns are bar-to-bar log returns between consecutive XAU 15m bars (the
return across the daily break is kept, so windows are not blanked for Zwin bars after every break).
  members: XAU, XAG, EURUSD, -USDJPY (+ BRENT), signs so that all rise when USD falls.
  z_i = r_i / sd_i (sd over FactorWin=96 bars); F = equal-weight mean of the z_i;
  (F needs >= 2 members present; a bar with a missing residual adds 0 to C)
  b = rolling OLS slope of z_XAU on F over LoadWin=480 bars; e = z_XAU - b*F;
  C = sum of e over the last Zwin bars; Z = (C - mean C) / sd C over the last 20 trading days
  (20 x 92 = 1840 15m bars).
LONG when Z crosses to <= -EntryZ, SHORT when Z crosses to >= +EntryZ (a fresh cross is required, so a
  stopped-out position is not re-entered on the next bar while Z is still beyond the threshold).
Filters: entries 00:00-20:30 UTC; skip if a tier-1 release (verified calendar, _d1util.TIER1) is
  within the next 30 min; trend de-risk: skip shorts when the 20-day EMA slope of daily XAU closes is
  in the top decile of the prior 250 days, longs when in the bottom decile (prior days only).
Card exit (precomputed into `hold`): |Z| <= ExitZ, i.e. Z back to -ExitZ or beyond for longs
  (+ExitZ for shorts; so ExitZ = 0 means Z crosses 0) (target), Z beyond StopZ=4 against the position
  (score stop), MaxHoldBars=64 bars or 20:55 UTC; hard stop 2*ATR14(15m) (`sl`), no price target.
  unit = the hard-stop distance. One position at a time.
Grid (budget 141): EntryZ, Zwin, ExitZ (card grids) and members (structural, listed last);
  FactorWin, LoadWin, StopZ, MaxHoldBars at card defaults.
"""
import numpy as np, pandas as pd
import bt1s
from strategies import _d1util as U

PARAMS = {
    "EntryZ": [1.5, 2.0, 2.5],
    "Zwin": [8, 16, 32],
    "ExitZ": [0.0, 0.3, 0.6, 1.0],
    "members": ["XAU,XAG,EURUSD", "XAU,XAG,EURUSD,USDJPY", "XAU,XAG,EURUSD,USDJPY,BRENT"],
}
DEFAULTS = dict(EntryZ=2.0, Zwin=32, ExitZ=0.6, members="XAU,XAG,EURUSD,USDJPY")
EXIT_UNIT = True
FACTOR_WIN, LOAD_WIN, STOP_Z, MAX_BARS, ZDAYS_BARS = 96, 480, 4.0, 64, 20 * 92
SYM = {"XAG": ("XAGUSD", 1), "EURUSD": ("EURUSD", 1), "USDJPY": ("USDJPY", -1), "BRENT": ("BRENTCMDUSD", 1)}


def _base(ctx):
    key = "_d1_cf_base"
    if key in ctx._bars:
        return ctx._bars[key]
    b = ctx.bars(900).copy()
    allm = np.arange(b.index[0] - 3600, b.index[-1] + 1800, 60, dtype=np.int64)
    rets = {"XAU": np.log(b.c).diff()}
    for k, (sym, sg) in SYM.items():
        c = ctx.m1(sym).c.reindex(allm).ffill(limit=14).reindex(b.index.values + 840).values
        rets[k] = sg * pd.Series(np.log(c), index=b.index).diff()
    b["atr"] = bt1s.atr(b, 14)
    b["news"] = U.near_release(b.close_sec.values, U.calendar_secs(ctx), 0, 1800)
    # trend de-risk: 20-day EMA slope of daily closes (23:00-21:00 sessions), decile vs prior 250 days
    h = ctx.bars(3600)
    hr = (h.index.values % 86400) // 3600
    hh = h[(hr < 21) | (hr >= 23)]
    dc = hh.c.groupby(U.tday(hh.index.values)).last()
    slope = pd.Series(bt1s.ema(dc.values, 20), index=dc.index).diff()
    pct = slope.rolling(250, min_periods=60).rank(pct=True)
    prev = pct.shift(1)                          # known before the trading day starts
    td = U.tday(b.close_sec.values)
    p = prev.reindex(td).values
    b["no_short"] = p >= 0.9
    b["no_long"] = p <= 0.1
    ctx._bars[key] = dict(b=b, rets=rets, cache={})
    return ctx._bars[key]


def _Z(base, members, Zwin):
    ck = (members, Zwin)
    if ck in base["cache"]:
        return base["cache"][ck]
    rets = base["rets"]
    zs = []
    for m in members.split(","):
        r = rets[m]
        zs.append(r / r.rolling(FACTOR_WIN, min_periods=FACTOR_WIN // 2).std())
    zx = zs[0]
    Zm = pd.concat(zs, axis=1)
    F = Zm.mean(axis=1).where(Zm.notna().sum(axis=1) >= 2)
    mp = LOAD_WIN // 2
    cov = (zx * F).rolling(LOAD_WIN, min_periods=mp).mean() - zx.rolling(LOAD_WIN, min_periods=mp).mean() * \
        F.rolling(LOAD_WIN, min_periods=mp).mean()
    bb = cov / F.rolling(LOAD_WIN, min_periods=mp).var(ddof=0)
    e = zx - bb * F
    C = e.fillna(0.0).rolling(Zwin, min_periods=Zwin).sum()
    Z = (C - C.rolling(ZDAYS_BARS, min_periods=ZDAYS_BARS // 2).mean()) / C.rolling(ZDAYS_BARS, min_periods=ZDAYS_BARS // 2).std()
    base["cache"][ck] = Z.values
    return Z.values


def signals(ctx, EntryZ=2.0, Zwin=32, ExitZ=0.6, members="XAU,XAG,EURUSD,USDJPY"):
    base = _base(ctx); b = base["b"]
    Z = _Z(base, members, Zwin)
    Zp = np.r_[np.nan, Z[:-1]]
    cs = b.close_sec.values
    tod = (cs % 86400) / 3600.0
    ok = (tod <= 20.5) & ~b.news.values & np.isfinite(b.atr.values)
    lg = ok & (Z <= -EntryZ) & (Zp > -EntryZ) & ~b.no_long.values
    sh = ok & (Z >= EntryZ) & (Zp < EntryZ) & ~b.no_short.values
    cand = np.flatnonzero(lg | sh)
    atr = b.atr.values; n = len(b)
    rows = []; free_from = -1
    for i in cand:
        if i < free_from:
            continue
        side = 1 if lg[i] else -1
        end_s = U.utc_sec(U.tday(cs[i]), "20:55")
        j_exit = None
        for j in range(i + 1, min(i + MAX_BARS, n - 1) + 1):
            if cs[j] > end_s:
                break
            j_exit = j
            zj = Z[j]
            if not np.isfinite(zj):
                continue
            if side * zj >= -ExitZ or side * zj <= -STOP_Z:
                break
        if j_exit is None:
            continue
        hold = min(cs[j_exit], end_s) - cs[i]
        if hold < 60:
            continue
        sl = 2.0 * atr[i]
        rows.append(dict(sec=cs[i], side=side, sl=sl, tp=0.0, hold=hold, unit=sl))
        free_from = j_exit + 1
    return U.frame(rows)
