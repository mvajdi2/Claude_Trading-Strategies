"""Gold under-reaction to a broad USD (or cross-asset) impulse, 1m catch-up (card r2-usd-impulse-catchup).

Data: XAU 1m mid bars (ctx.bars(60)); leader closes = Dukascopy 1m BID closes (ctx.m1), put on a
full minute grid with forward fill <= 5 min, read at the XAU bar's minute-start index (close known at
the same close_sec) -> causal.
Leader factor u (log-return units, u > 0 = USD up for the USD leaders):
  USD2 = 0.5*(-r_EURUSD) + 0.5*r_USDJPY; EURUSD = -r_EURUSD; USDJPY = r_USDJPY;
  XAGUSD / USATECH = the leader's own return (card: "use the sign of beta").
U_W = u summed over the last W closed 1m bars; z_U = U_W / sd(U_W), sd = std of U_W at the same UTC
  clock minute over the prior 20 trading days (today excluded).
Two-leg agreement (USD2 only): both legs' W-returns (USD-up signed) beyond 0.5 of their own
  clock-minute sd in the impulse direction.
beta = OLS slope of 1m XAU log returns on 1m u over the prior 20 trading days (07:00-20:30 bars, today
  excluded); E = beta*U_W (expected gold move), G = r_XAU(W), rho = G/E.
Entry when |z_U| >= k, (agreement), rho < rho_max (0.5): side = sign(E). Decision = bar close.
Filters: prior-5-day corr(XAU, u) <= corr_max (-0.2) for USD leaders, >= +0.2 for XAGUSD/USATECH
  (relationship intact; sign-adjusted for positively related leaders); skip if any calendar release
  (all events) falls in [t - 10 min, t + hold_min] (news_skip=True); one trade per 60 min; entries
  07:00-20:00 UTC; skip if the XAU spread at the decision second > 2x its 20-day clock-minute median.
Card exit: stop = max(stop_mult (0.75) * |E| * price, 0.6 * ATR14(1m) * sqrt(W)); target =
  tgt_frac (0.7) * (1 - rho) * |E| * price; time exit hold_min, flat 20:55 UTC.
  stop_mult / tgt_frac only change sl/tp -> exit templates (X4). unit = native stop distance.
Grid (budget 141): W [5,10,30], k [2.5,3,4], hold_min [15,30,60], leader (structural, listed last);
  rho_max 0.5, corr_max -0.2 and news_skip True at card defaults.
"""
import numpy as np, pandas as pd
import bt1s
from strategies import _d1util as U

PARAMS = {
    "W_min": [5, 10, 30],
    "k": [2.5, 3.0, 4.0],
    "hold_min": [15, 30, 60],
    "leader": ["EURUSD", "USATECH", "USD2", "USDJPY", "XAGUSD"],
}
DEFAULTS = dict(W_min=10, k=3.0, hold_min=30, leader="USD2")
EXIT_UNIT = True
RHO_MAX, CORR_MAX, STOP_MULT, TGT_FRAC = 0.5, -0.2, 0.75, 0.7
SYM = {"EURUSD": "EURUSD", "USDJPY": "USDJPY", "XAGUSD": "XAGUSD", "USATECH": "USATECHIDXUSD"}


def _grid_close(ctx, sym, allm):
    return ctx.m1(sym).c.reindex(allm).ffill(limit=5).values


def _base(ctx):
    key = "_d1_usd_base"
    if key in ctx._bars:
        return ctx._bars[key]
    b = ctx.bars(60)[["c", "h", "l", "o", "close_sec"]].copy()
    idx = b.index.values
    allm = np.arange(idx[0] - 86400, idx[-1] + 60, 60, dtype=np.int64)
    pos = np.searchsorted(allm, idx)
    lx = np.log(pd.Series(b.c.values, index=idx).reindex(allm).ffill(limit=5).values)
    logs = {"XAU": lx}
    for k, s in SYM.items():
        logs[k] = np.log(_grid_close(ctx, s, allm))
    b["atr"] = bt1s.atr(b, 14)
    sp = ctx.spread[ctx.k_of(b.close_sec.values)]
    b["sp_ok"] = sp <= 2 * U.clock_baseline(b.close_sec.values, sp, 20, "median")
    ctx._bars[key] = dict(b=b, allm=allm, pos=pos, logs=logs, cache={})
    return ctx._bars[key]


def _leader_logs(base, leader):
    L = base["logs"]
    if leader == "USD2":
        return {"u": 0.5 * (-L["EURUSD"]) + 0.5 * L["USDJPY"], "e": -L["EURUSD"], "j": L["USDJPY"]}
    if leader == "EURUSD":
        return {"u": -L["EURUSD"]}
    return {"u": L[leader]}


def _features(ctx, leader, W):
    base = _base(ctx)
    ck = (leader, W)
    if ck in base["cache"]:
        return base["cache"][ck]
    b = base["b"]; pos = base["pos"]; sec = b.close_sec.values; idx = b.index.values
    ll = _leader_logs(base, leader)
    lx = base["logs"]["XAU"]
    f = {}
    UW = (ll["u"][pos] - ll["u"][pos - W])
    f["UW"] = UW
    f["sdU"] = U.clock_baseline(sec, UW, 20, "std")
    if leader == "USD2":
        for leg in ("e", "j"):
            lw = ll[leg][pos] - ll[leg][pos - W]
            f[leg] = lw; f["sd_" + leg] = U.clock_baseline(sec, lw, 20, "std")
    f["G"] = lx[pos] - lx[pos - W]
    # 20-day beta and 5-day corr of 1m XAU returns on 1m u, prior days only, 07:00-20:30 bars
    rx = lx[pos] - lx[pos - 1]; ru = ll["u"][pos] - ll["u"][pos - 1]
    tod = (idx % 86400) / 3600.0
    m = (tod >= 7) & (tod < 20.5) & np.isfinite(rx) & np.isfinite(ru)
    d = pd.DataFrame({"day": idx[m] // 86400, "x": ru[m], "y": rx[m]})
    d["xy"] = d.x * d.y; d["xx"] = d.x ** 2; d["yy"] = d.y ** 2; d["n"] = 1.0
    S = d.groupby("day")[["x", "y", "xy", "xx", "yy", "n"]].sum()
    def roll(nd):
        R = S.rolling(nd, min_periods=max(3, nd // 2)).sum().shift(1)
        cxy = R.xy - R.x * R.y / R.n; cxx = R.xx - R.x ** 2 / R.n; cyy = R.yy - R.y ** 2 / R.n
        return cxy / cxx, cxy / np.sqrt(cxx * cyy)
    beta20, _ = roll(20); _, corr5 = roll(5)
    days = idx // 86400
    f["beta"] = beta20.reindex(days).values
    f["corr"] = corr5.reindex(days).values
    base["cache"][ck] = f
    return f


def signals(ctx, W_min=10, k=3.0, hold_min=30, leader="USD2"):
    base = _base(ctx); b = base["b"]
    f = _features(ctx, leader, W_min)
    sec = b.close_sec.values
    tod = (sec % 86400) / 3600.0
    zU = f["UW"] / f["sdU"]
    E = f["beta"] * f["UW"]
    rho = f["G"] / E
    cond = (np.abs(zU) >= k) & np.isfinite(E) & (E != 0) & (rho < RHO_MAX)
    if leader == "USD2":
        dirn = np.sign(zU)
        cond &= (dirn * f["e"] > 0.5 * f["sd_e"]) & (dirn * f["j"] > 0.5 * f["sd_j"])
    if leader in ("XAGUSD", "USATECH"):
        cond &= f["corr"] >= -CORR_MAX
    else:
        cond &= f["corr"] <= CORR_MAX
    cond &= (tod >= 7.0) & (tod < 20.0) & b.sp_ok.values & np.isfinite(b.atr.values)
    i = np.flatnonzero(cond)
    rel = U.calendar_secs(ctx, None)
    i = i[~U.near_release(sec[i], rel, 600, hold_min * 60)]
    i = i[U.min_spacing(sec[i], 3600)]
    P = b.c.values[i]; aE = np.abs(E[i])
    sl = np.maximum(STOP_MULT * aE * P, 0.6 * b.atr.values[i] * np.sqrt(W_min))
    tp = TGT_FRAC * (1 - rho[i]) * aE * P
    df = pd.DataFrame(dict(sec=sec[i], side=np.sign(E[i]).astype(int), sl=sl, tp=tp,
                           hold=np.minimum(hold_min * 60, U.end_hold(sec[i], "20:55")), unit=sl))
    df = df[df.tp > 0.05]
    return U.frame(df)
