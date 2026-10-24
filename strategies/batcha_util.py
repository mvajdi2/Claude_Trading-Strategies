"""Shared helpers for Batch A strategies (session ranges, stop-order touches, DST conversion).

Conventions
  * trading day `td` = calendar day index (epoch_sec // 86400) of the session that starts at
    23:00 UTC on the previous calendar day and ends at 21:00 UTC (engine flat time).
  * `at(td, h)` = epoch second of UTC hour h (float) belonging to trading day td; h >= 23 means
    the previous calendar evening.
  * Stop-order fills are detected on the 1s grid: decision second = first live second whose
    high/low touches the level; the engine then fills at the next second (+ costs).
NOTE: do not edit after a Batch A strategy has been frozen (strategies import this file).
"""
import numpy as np, pandas as pd
from numba import njit

DAY = 86400


def tday_of(sec):
    return (np.asarray(sec, np.int64) + 3600) // DAY


def at(td, h):
    td = np.asarray(td, np.int64)
    h = np.asarray(h, np.float64)
    hh = np.where(h >= 23, h - 24, h)
    return td * DAY + np.round(hh * 3600).astype(np.int64)


def local_sec(td, minutes, tz):
    """epoch second of local wall-clock time `minutes` after local midnight of calendar date td."""
    d = pd.DatetimeIndex(pd.to_datetime(np.asarray(td, np.int64) * DAY, unit="s")) \
        + pd.to_timedelta(minutes, unit="min")
    loc = d.tz_localize(tz, ambiguous="NaT", nonexistent="shift_forward").tz_convert("UTC").tz_localize(None)
    return loc.as_unit("s").asi8


def daily(ctx, min_bars=300):
    """23:00-21:00 UTC daily OHLC from 1m bars; index = td."""
    key = "_batcha_daily"
    if key in ctx._bars:
        return ctx._bars[key]
    b = ctx.bars(60)
    hr = (b.index.values % DAY) // 3600
    m = (hr < 21) | (hr >= 23)
    bb = b[m]
    td = tday_of(bb.index.values)
    d = bb.groupby(td).agg(o=("o", "first"), h=("h", "max"), l=("l", "min"), c=("c", "last"), nb=("c", "size"))
    d = d[d.nb >= min_bars].copy()
    d["rng"] = d.h - d.l
    pc = d.c.shift(1)
    tr = np.maximum(d.h - d.l, np.maximum((d.h - pc).abs(), (d.l - pc).abs()))
    d["atr14"] = tr.rolling(14).mean()
    ctx._bars[key] = d
    return d


def window_hl(b, t0, t1, tds, min_frac=0.5, tf=60):
    """High/low/open/last-close of bars with start in [t0[i], t1[i]) for each trading day tds[i].
    Returns DataFrame indexed by td (rows only where enough bars exist)."""
    tds = np.asarray(tds, np.int64); t0 = np.asarray(t0, np.int64); t1 = np.asarray(t1, np.int64)
    idx = b.index.values
    lo_i = np.searchsorted(idx, t0, "left"); hi_i = np.searchsorted(idx, t1, "left")
    H = b.h.values; L = b.l.values; O = b.o.values; C = b.c.values
    rows = []
    for j in range(len(tds)):
        a, z = lo_i[j], hi_i[j]
        need = max(1, int(min_frac * (t1[j] - t0[j]) / tf))
        if z - a < need:
            continue
        rows.append((tds[j], H[a:z].max(), L[a:z].min(), O[a], C[z - 1]))
    return pd.DataFrame(rows, columns=["td", "rh", "rl", "ro", "rc"]).set_index("td")


@njit(cache=True)
def _first_touch(hi, lo, live, k0, k1, up, dn):
    m = len(k0)
    ko = np.full(m, -1, np.int64); so = np.zeros(m, np.int64)
    n = len(hi)
    for j in range(m):
        a = max(k0[j], 0); z = min(k1[j], n)
        for k in range(a, z):
            if not live[k]:
                continue
            u = hi[k] >= up[j]; d = lo[k] <= dn[j]
            if u and d:
                break                       # both sides inside one second: ambiguous, skip day
            if u:
                ko[j] = k; so[j] = 1; break
            if d:
                ko[j] = k; so[j] = -1; break
    return ko, so


def first_touch(ctx, t0, t1, up, dn):
    """First second in [t0, t1) where 1s high >= up (side +1) or low <= dn (side -1).
    Returns (sec or -1, side). Use +inf / -inf to disable a side."""
    k0 = ctx.k_of(t0); k1 = ctx.k_of(t1)
    ko, so = _first_touch(ctx.g["hi"], ctx.g["lo"], ctx.g["live"], k0.astype(np.int64), k1.astype(np.int64),
                          np.asarray(up, np.float64), np.asarray(dn, np.float64))
    sec = np.where(ko >= 0, ctx.sec_of(np.maximum(ko, 0)), -1)
    return sec, so


def mid_at(ctx, sec):
    """last mid price at or before second `sec` (grid is forward filled)."""
    k = np.clip(ctx.k_of(sec), 0, ctx.n - 1)
    return ctx.mid[k]


def first_close_cross(b, tds, t0, t1, up, dn):
    """First bar (per td) with close_sec in [t0, t1] closing > up (side +1) or < dn (side -1).
    Returns DataFrame indexed by td with columns sec, side, c, bar (bar start)."""
    lv = pd.DataFrame(dict(t0=np.asarray(t0, np.int64), t1=np.asarray(t1, np.int64),
                           up=np.asarray(up, float), dn=np.asarray(dn, float)), index=np.asarray(tds, np.int64))
    x = b[["c", "close_sec"]].copy()
    x["td"] = tday_of(x.close_sec.values)
    x = x.join(lv, on="td", how="inner")
    x = x[(x.close_sec >= x.t0) & (x.close_sec <= x.t1) & ((x.c > x.up) | (x.c < x.dn))]
    x = x[~x.td.duplicated()]
    return pd.DataFrame(dict(sec=x.close_sec.values, side=np.where(x.c > x.up, 1, -1), c=x.c.values,
                             bar=x.index.values), index=x.td.values)


def realized_var(ctx, tf=300):
    """per-td sum of squared tf-bar log returns 00:00-21:00 UTC."""
    b = ctx.bars(tf)
    r = np.log(b.c).diff()
    hr = (b.index.values % DAY) // 3600
    m = hr < 21
    return (r[m] ** 2).groupby(tday_of(b.index.values[m])).sum()


def trading_days(ctx):
    """all trading days that have any 1m bar (no same-day filtering, so no look-ahead)."""
    return np.unique(tday_of(ctx.bars(60).index.values))


def prev_rows(df, tds):
    """for each td, the last row of df (indexed by td) with index < td (i.e. fully known before td).
    Returns DataFrame indexed by tds (NaN where none)."""
    tds = np.asarray(tds, np.int64)
    i = np.searchsorted(df.index.values, tds, "left") - 1
    out = df.iloc[np.maximum(i, 0)].copy()
    out.index = tds
    out[i < 0] = np.nan
    return out


def vol_state_pct(ctx, tds, lookback=250, min_hist=60):
    """percentile (0-1) of the previous day's realized variance within the trailing `lookback` days."""
    rv = realized_var(ctx)
    pct = rv.rolling(lookback, min_periods=min_hist).rank(pct=True)
    return prev_rows(pct.to_frame("p"), tds)["p"].values


# SHFE / SGE closed weekdays 2025-2026 (PRC State Council holiday schedule; weekends are not listed).
SHFE_HOLIDAYS = pd.to_datetime([
    # 2025: New Year; Spring Festival Jan 28-Feb 4; Qingming Apr 4; Labour Day May 1-5;
    # Dragon Boat May 31-Jun 2; National Day + Mid-Autumn Oct 1-8
    "2025-01-01", "2025-01-28", "2025-01-29", "2025-01-30", "2025-01-31", "2025-02-03", "2025-02-04",
    "2025-04-04", "2025-05-01", "2025-05-02", "2025-05-05", "2025-06-02",
    "2025-10-01", "2025-10-02", "2025-10-03", "2025-10-06", "2025-10-07", "2025-10-08",
    # 2026: New Year Jan 1-3; Spring Festival Feb 15-23; Qingming Apr 4-6; Labour Day May 1-5;
    # Dragon Boat Jun 19-21; Mid-Autumn Sep 25-27; National Day Oct 1-7
    "2026-01-01", "2026-01-02", "2026-02-16", "2026-02-17", "2026-02-18", "2026-02-19", "2026-02-20",
    "2026-02-23", "2026-04-06", "2026-05-01", "2026-05-04", "2026-05-05", "2026-06-19",
    "2026-09-25", "2026-10-01", "2026-10-02", "2026-10-05", "2026-10-06", "2026-10-07",
]).values.astype("datetime64[s]").astype(np.int64) // DAY


def shfe_closed(td, night=False):
    """True if SHFE is closed on calendar day td (Beijing date = UTC date for 01:00-15:00 UTC).
    night=True: the night session (21:00 Beijing) belongs to the next trading day and is not held
    on the evening before a holiday, so also closed if the next weekday is a holiday."""
    td = np.asarray(td, np.int64)
    c = np.isin(td, SHFE_HOLIDAYS)
    if night:
        wd = (td + 3) % 7                     # 0 = Monday (1970-01-01 was a Thursday)
        nxt = td + np.where(wd == 4, 3, 1)    # Friday -> Monday
        c |= np.isin(nxt, SHFE_HOLIDAYS)
    return c
