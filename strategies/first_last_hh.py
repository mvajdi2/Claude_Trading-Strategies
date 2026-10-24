"""First half-hour of the COMEX day predicts the last half-hour (Gao-Han-Li-Zhou adapted to gold).

Card: academic-first-hh-last-hh-comex.
r1 = return over the first window (08:20-08:50 NY default; variants 07:00-07:30 UTC and the
Globex reopen 18:00-18:30 NY of the previous evening). At 13:00 NY trade sign(r1) if
|r1| > rolling 60-day percentile (vol_filter_pct) of |r1|; optional mid-window confirmation
(return window_end -> 13:00 NY has the same sign). Time exit 13:30 NY (variant: 20:55 UTC).
US exchange holidays / early closes are skipped.
Disaster stop 2.5 * ATR14(1m); unit = that stop distance.
"""
import numpy as np, pandas as pd
import bt1s

NY = "America/New_York"
# NYSE/CME US holidays and early closes, 2025-2026 (same list as last30_momentum)
US_SKIP = pd.to_datetime([
    "2025-01-01", "2025-01-09", "2025-01-20", "2025-02-17", "2025-04-18", "2025-05-26", "2025-06-19",
    "2025-07-03", "2025-07-04", "2025-09-01", "2025-11-27", "2025-11-28", "2025-12-24", "2025-12-25",
    "2026-01-01", "2026-01-19", "2026-02-16", "2026-04-03", "2026-05-25", "2026-06-19", "2026-07-03",
    "2026-09-07", "2026-11-26", "2026-11-27", "2026-12-24", "2026-12-25",
])

PARAMS = {
    "first_window": ["ny0820", "utc0700", "ny1800"],
    "mid_confirm": [False, True],
    "vol_filter_pct": [50, 0, 75],
    "exit_ny": ["13:30", "close"],
}
EXIT_UNIT = True


def _local(b, tz):
    lt = b.time.dt.tz_localize("UTC").dt.tz_convert(tz).dt.tz_localize(None)
    return lt.dt.normalize(), (lt.dt.hour * 60 + lt.dt.minute).values


def _epoch(local_naive, tz):
    t = pd.DatetimeIndex(local_naive).tz_localize(tz, ambiguous="NaT", nonexistent="NaT").tz_convert("UTC")
    return np.asarray((t - pd.Timestamp(0, tz="UTC")) // pd.Timedelta(seconds=1), dtype=np.float64)


def _last_before(day, mn, b, target, look=10):
    m = (mn >= target - look) & (mn < target)
    return pd.DataFrame(dict(day=day[m].values, c=b.c.values[m], sec=b.close_sec.values[m])).groupby("day").last()


def _first_at(day, mn, b, target, look=10):
    m = (mn >= target) & (mn < target + look)
    return pd.DataFrame(dict(day=day[m].values, o=b.o.values[m])).groupby("day").first()


def signals(ctx, first_window="ny0820", mid_confirm=False, vol_filter_pct=50, exit_ny="13:30"):
    b = ctx.bars(60)
    a = pd.Series(bt1s.atr(b, 14), index=b.index)
    d, mn = _local(b, NY)
    sig = _last_before(d, mn, b, 13 * 60)                      # price at 13:00 NY, decision sec
    sig["atr"] = a.reindex(sig.sec.values - 59).values
    if first_window == "ny0820":
        p0 = _first_at(d, mn, b, 8 * 60 + 20).o
        p1 = _last_before(d, mn, b, 8 * 60 + 50).c
        r1 = np.log(p1 / p0)
    elif first_window == "utc0700":
        du, mu = _local(b, "UTC")
        # map UTC date to NY date: 07:00 UTC is always on the same NY calendar date
        p0 = _first_at(du, mu, b, 7 * 60).o
        p1 = _last_before(du, mu, b, 7 * 60 + 30).c
        r1 = np.log(p1 / p0)
    else:  # Globex reopen 18:00-18:30 NY of the previous evening -> shift to next NY date with a signal
        p0 = _first_at(d, mn, b, 18 * 60).o
        p1 = _last_before(d, mn, b, 18 * 60 + 30).c
        r = np.log(p1 / p0).dropna()
        rr = pd.DataFrame(dict(oday=r.index, r1=r.values))
        s2 = pd.merge_asof(pd.DataFrame(dict(day=sig.index)), rr, left_on="day", right_on="oday",
                           allow_exact_matches=False)
        s2 = s2[(s2.day - s2.oday) <= pd.Timedelta(days=3)]
        r1 = pd.Series(s2.r1.values, index=s2.day.values)
        p1 = None
    sig["r1"] = r1.reindex(sig.index)
    if mid_confirm:
        if first_window == "ny1800":
            pstart = _first_at(d, mn, b, 0).o  # NY midnight as mid-window start for the overnight variant
        else:
            pstart = p1
        sig["rmid"] = np.log(sig.c / pstart.reindex(sig.index))
    sig = sig.dropna(subset=["r1", "atr"])
    thr = sig.r1.abs().rolling(60, min_periods=40).quantile(vol_filter_pct / 100).shift(1)
    keep = thr.notna() & (sig.r1.abs() > thr if vol_filter_pct > 0 else True) & (sig.r1 != 0)
    if mid_confirm:
        keep &= np.sign(sig.rmid) == np.sign(sig.r1)
    keep &= ~sig.index.isin(US_SKIP)
    s = sig[keep]
    if exit_ny == "close":
        hold = ((s.sec.values // 86400) * 86400 + 20 * 3600 + 55 * 60 - s.sec.values).astype(np.int64)
    else:
        ex = _epoch(pd.DatetimeIndex(s.index) + pd.Timedelta(minutes=13 * 60 + 30), NY)
        hold = (ex - s.sec.values).astype(np.int64)
    stop = 2.5 * s.atr.values
    return pd.DataFrame(dict(sec=s.sec.values.astype(np.int64), side=np.sign(s.r1.values).astype(int),
                             sl=stop, tp=0.0, hold=hold, unit=stop))
