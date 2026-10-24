"""Rest-of-day return predicts the last 30 min before COMEX settlement (Baltussen et al. 2021).

Card: academic-rest-of-day-last30-momentum.
Session day D = 18:00 NY on the previous evening -> signal_end NY on D (DST-aware).
At signal_end: r_rod = ln(P_signal / P_open), P_open = first 1m open at/after 18:00 NY that starts the
session. Trade sign(r_rod) if |r_rod| > k * sigma_60 (stdev of the previous 60 r_rod values).
vol_filter: also require realised vol of the session so far (sum of squared 1m log returns,
18:00 NY -> signal_end) > median of the previous 60 sessions' values.
US exchange holidays and early-close days (2025-2026) are skipped.
Time exit at exit_ny (13:30 NY settlement, 14:00 NY) or "close" = 20:55 UTC.
Disaster stop 2.5 * ATR14(1m); unit = that stop distance.
"""
import numpy as np, pandas as pd
import bt1s

NY = "America/New_York"
# NYSE/CME US holidays and early closes, 2025-2026 (incl. 2025-01-09 national day of mourning)
US_SKIP = pd.to_datetime([
    "2025-01-01", "2025-01-09", "2025-01-20", "2025-02-17", "2025-04-18", "2025-05-26", "2025-06-19",
    "2025-07-03", "2025-07-04", "2025-09-01", "2025-11-27", "2025-11-28", "2025-12-24", "2025-12-25",
    "2026-01-01", "2026-01-19", "2026-02-16", "2026-04-03", "2026-05-25", "2026-06-19", "2026-07-03",
    "2026-09-07", "2026-11-26", "2026-11-27", "2026-12-24", "2026-12-25",
])

PARAMS = {
    "k": [0.5, 0.0, 0.25, 1.0],
    "signal_end": ["13:00", "12:30"],
    "exit_ny": ["13:30", "14:00", "close"],
    "vol_filter": [False, True],
}
EXIT_UNIT = True


def _hm(s):
    h, m = s.split(":"); return int(h) * 60 + int(m)


def _epoch(local_naive, tz):
    t = pd.DatetimeIndex(local_naive).tz_localize(tz, ambiguous="NaT", nonexistent="NaT").tz_convert("UTC")
    return np.asarray((t - pd.Timestamp(0, tz="UTC")) // pd.Timedelta(seconds=1), dtype=np.float64)


def signals(ctx, k=0.5, signal_end="13:00", exit_ny="13:30", vol_filter=False):
    b = ctx.bars(60)
    a = bt1s.atr(b, 14)
    lt = b.time.dt.tz_localize("UTC").dt.tz_convert(NY).dt.tz_localize(None)
    d = lt.dt.normalize()
    mn = (lt.dt.hour * 60 + lt.dt.minute).values
    se = _hm(signal_end)
    eve = mn >= 18 * 60
    sday = (d + pd.to_timedelta(eve.astype(int), unit="D")).values      # session day
    insess = eve | (mn < se)                                            # bars of the session up to signal
    lr = np.log(b.c).diff().to_numpy().copy()
    first = np.r_[True, sday[1:] != sday[:-1]]
    lr[first] = np.nan                                                  # no return across sessions
    df = pd.DataFrame(dict(sday=sday[insess], o=b.o.values[insess], c=b.c.values[insess],
                           sec=b.close_sec.values[insess], atr=a[insess], r2=np.nan_to_num(lr[insess]) ** 2,
                           mn=mn[insess], eve=eve[insess]))
    g = df.groupby("sday").agg(o=("o", "first"), eve0=("eve", "first"), mn0=("mn", "first"), c=("c", "last"),
                               sec=("sec", "last"), atr=("atr", "last"), mnl=("mn", "last"), rv=("r2", "sum"))
    # session must start in the 18:00-20:00 NY hour and the signal bar must be within 10 min of signal_end
    g = g[g.eve0 & (g.mn0 < 20 * 60) & (g.mnl >= se - 10) & (g.mnl < se)]
    g = g[~g.index.isin(US_SKIP) & (pd.DatetimeIndex(g.index).dayofweek < 5)]
    g["r"] = np.log(g.c / g.o)
    sigma = g.r.rolling(60, min_periods=40).std().shift(1)
    rv_med = g.rv.rolling(60, min_periods=40).median().shift(1)
    keep = (g.r.abs() > k * sigma) & sigma.notna() & np.isfinite(g.atr) & (g.r != 0)
    if vol_filter:
        keep &= g.rv > rv_med
    s = g[keep]
    if exit_ny == "close":
        ex = (s.sec.values // 86400) * 86400 + 20 * 3600 + 55 * 60
    else:
        ex = _epoch(pd.DatetimeIndex(s.index) + pd.to_timedelta(_hm(exit_ny), unit="min"), NY)
    hold = (ex - s.sec.values).astype(np.int64)
    stop = 2.5 * s.atr.values
    return pd.DataFrame(dict(sec=s.sec.values.astype(np.int64), side=np.sign(s.r.values).astype(int),
                             sl=stop, tp=0.0, hold=hold, unit=stop))
