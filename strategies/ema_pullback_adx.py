"""EMA20/50 + ADX trend, pullback to EMA20 with close back beyond it (M15).

Card: marketplaces-ema-pullback-adx-m15.
Long on a closed 15m bar (07:00-19:00 UTC): EMA20 > EMA50, ADX14 > adx_min, last closed H1 close >
EMA50(H1), low <= EMA20 and close > EMA20. Mirror for shorts. Optional dead-market filter: skip if
ATR14(15m) < its 20-day median. Stop = max(close - (5-bar swing low - 0.5 ATR), stop_atr*ATR).
Exit: trail -> break-even at +1R then 2*ATR trailing stop; fixed_3atr -> target 3*ATR.
Max 2 trades per day; time exit 20:45 UTC. unit = the structural stop distance (R).
exit_mode is a module argument only (not searched): the card's trail/BE is the native exit.
"""
import numpy as np, pandas as pd
import bt1s

PARAMS = {
    "adx_min": [25, 20, 30],
    "stop_atr": [1.5, 1.0, 2.0],
    "dead_filter": [True, False],
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
    return pd.Series(dx).ewm(alpha=al, adjust=False).mean().values


def signals(ctx, adx_min=25, stop_atr=1.5, dead_filter=True, exit_mode="trail"):
    b = ctx.bars(900)
    e20 = bt1s.ema(b.c.values, 20); e50 = bt1s.ema(b.c.values, 50)
    a = bt1s.atr(b, 14); ax = adx(b)
    h1 = ctx.bars(3600)
    hf = pd.DataFrame(dict(cs=h1.close_sec.values, hup=np.sign(h1.c.values - bt1s.ema(h1.c.values, 50))))
    x = pd.merge_asof(pd.DataFrame(dict(cs=b.close_sec.values)), hf, on="cs")
    hup = x.hup.values
    med = pd.Series(a).rolling(20 * 92, min_periods=500).median().shift(1).values
    H, L, C = b.h.values, b.l.values, b.c.values
    swl = pd.Series(L).rolling(5).min().values; swh = pd.Series(H).rolling(5).max().values
    hour = (b.index.values % 86400) / 3600
    base = (ax > adx_min) & (hour >= 7) & (hour < 19) & np.isfinite(a)
    if dead_filter:
        base &= a >= med
    lg = base & (e20 > e50) & (hup > 0) & (L <= e20) & (C > e20)
    sh = base & (e20 < e50) & (hup < 0) & (H >= e20) & (C < e20)
    m = lg | sh
    side = np.where(lg, 1, -1)[m]
    sl = np.where(lg, C - (swl - 0.5 * a), (swh + 0.5 * a) - C)[m]
    sl = np.maximum(sl, stop_atr * a[m])
    s = pd.DataFrame(dict(sec=b.close_sec.values[m].astype(np.int64), side=side, sl=sl,
                          hold=0, unit=sl, atr=a[m]))
    s["hold"] = ((s.sec // 86400) * 86400 + 20 * 3600 + 45 * 60 - s.sec).astype(np.int64)   # time exit 20:45
    if exit_mode == "trail":
        s["tp"] = 0.0; s["tp1"] = s.sl; s["f1"] = 0.0; s["be"] = 1; s["trail"] = 2 * s.atr
    else:
        s["tp"] = 3 * s.atr
    s = s.drop(columns="atr")
    s["day"] = s.sec // 86400
    return s.groupby("day").head(2).drop(columns="day").reset_index(drop=True)
