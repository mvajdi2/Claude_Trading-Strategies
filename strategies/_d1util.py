"""Shared helpers for Batch D1 strategy modules (cross-asset, statistical, microstructure).

KEEP STABLE: frozen D1 strategies import this file and its bytes are part of their code hash.
A material change needs a new helper file.

Conventions
  * XAU 1m bars = ctx.bars(60) (mid OHLC), index = minute-start epoch second, close known at +59.
  * Cross-asset 1m bars = ctx.m1(sym) (Dukascopy BID), same minute-start index convention, so the
    close of the cross-asset bar that starts at t is known at t+59, the same second as the XAU bar's
    close. Joining both on the minute-start index and deciding at close_sec is therefore causal.
  * Trading day td = (sec + 3600) // 86400 (session 23:00 UTC prev. day -> 21:00 UTC).
"""
import os
import numpy as np, pandas as pd
import hfdata

DAY = 86400
CAL_PATH = os.path.join(hfdata.ROOT, "data", "calendar", "us_macro_2025_2026.csv")
# Scheduled FOMC statement days, 14:00 New York (federalreserve.gov, as in strategies/fomc_drift.py)
FOMC_DATES = ["2025-01-29", "2025-03-19", "2025-05-07", "2025-06-18", "2025-07-30", "2025-09-17",
              "2025-10-29", "2025-12-10", "2026-01-28", "2026-03-18", "2026-04-29", "2026-06-17",
              "2026-07-29", "2026-09-16", "2026-10-28", "2026-12-09"]


def tday(sec):
    return (np.asarray(sec, np.int64) + 3600) // DAY


def utc_sec(td, hhmm):
    """epoch second of UTC wall time hh:mm on calendar day td (hh >= 21 is NOT shifted)."""
    hh, mm = map(int, hhmm.split(":"))
    return np.asarray(td, np.int64) * DAY + hh * 3600 + mm * 60


def local_sec(days, minutes, tz):
    """epoch second of local wall-clock `minutes` after local midnight of calendar day index `days`."""
    d = pd.DatetimeIndex(pd.to_datetime(np.asarray(days, np.int64) * DAY, unit="s")) \
        + pd.to_timedelta(minutes, unit="min")
    loc = d.tz_localize(tz, ambiguous="NaT", nonexistent="shift_forward").tz_convert("UTC").tz_localize(None)
    return loc.as_unit("s").asi8


def end_hold(sec, hhmm="20:55"):
    """seconds from `sec` to hh:mm UTC of the trading day of `sec` (td date)."""
    s = np.asarray(sec, np.int64)
    return utc_sec(tday(s), hhmm) - s


# ------------------------------------------------------------------ cross-asset minute frame
def cross_close(ctx, sym, index):
    """close of the cross-asset 1m bar starting at each minute-start second in `index` (NaN if absent)."""
    m = ctx.m1(sym)
    return m.c.reindex(np.asarray(index, np.int64)).values


def lag_values(index, values, lag_sec):
    """values at (index - lag_sec), matched exactly on the minute grid (NaN where absent)."""
    s = pd.Series(np.asarray(values, np.float64), index=np.asarray(index, np.int64))
    s = s[~s.index.duplicated()]
    return s.reindex(np.asarray(index, np.int64) - int(lag_sec)).values


def clock_baseline(sec, x, ndays=20, how="median", min_days=10):
    """For each row, the statistic of x at the same UTC clock second-of-day over the previous
    `ndays` calendar days that have data (today excluded). how: median | std | mad (MAD*1.4826)."""
    sec = np.asarray(sec, np.int64)
    df = pd.DataFrame({"d": sec // DAY, "m": sec % DAY, "x": np.asarray(x, np.float64)})
    p = df.pivot_table(index="d", columns="m", values="x", aggfunc="last")
    if how == "median":
        st = p.rolling(ndays, min_periods=min_days).median()
    elif how == "std":
        st = p.rolling(ndays, min_periods=min_days).std()
    elif how == "mad":
        med = p.rolling(ndays, min_periods=min_days).median()
        st = (p - med).abs().rolling(ndays, min_periods=min_days).median() * 1.4826
    else:
        raise ValueError(how)
    st = st.shift(1)                       # previous days only
    di = np.searchsorted(p.index.values, df.d.values)
    mi = np.searchsorted(p.columns.values, df.m.values)
    return st.values[di, mi]


# ------------------------------------------------------------------ news
# Tier-1 set used by D1 (the calendar file has no tier column): the market-moving releases for gold.
TIER1 = ("NFP", "CPI", "PPI", "FOMC_statement", "retail_sales", "GDP_advance", "PCE",
         "ISM_manufacturing", "ISM_services", "JOLTS")


def calendar_secs(ctx, events=TIER1):
    """release epoch seconds from the verified US macro calendar (data/calendar/us_macro_2025_2026.csv).
    events=TIER1 (default) or None for every row (adds jobless claims, FOMC minutes, GDP 2nd/3rd)."""
    c = ctx.calendar()
    if events is not None:
        c = c[c.event.isin(list(events))]
    return np.unique(c.sec.values.astype(np.int64))


def proxy_release_secs(ctx):
    """(Unused fallback.) DST-aware proxy for tier-1 US releases when no calendar is available: every weekday 08:30 and
    10:00 New York, plus 14:00 New York on scheduled FOMC days."""
    days = np.unique(ctx.bars(3600).index.values // DAY)
    wd = (days + 3) % 7                        # 0 = Monday
    days = days[wd < 5]
    out = [local_sec(days, 8 * 60 + 30, "America/New_York"), local_sec(days, 10 * 60, "America/New_York")]
    fd = pd.to_datetime(FOMC_DATES).values.astype("datetime64[s]").astype(np.int64) // DAY
    out.append(local_sec(fd, 14 * 60, "America/New_York"))
    return np.unique(np.concatenate(out))


def near_release(sec, rel, before_sec, after_sec):
    """True where some release r satisfies sec - before_sec <= r <= sec + after_sec."""
    sec = np.asarray(sec, np.int64); rel = np.sort(np.asarray(rel, np.int64))
    if len(rel) == 0 or len(sec) == 0:
        return np.zeros(len(sec), bool)
    i = np.searchsorted(rel, sec - before_sec, "left")
    ok = i < len(rel)
    out = np.zeros(len(sec), bool)
    out[ok] = rel[i[ok]] <= sec[ok] + after_sec
    return out


# ------------------------------------------------------------------ signal frames
def min_spacing(sec, gap_sec):
    """boolean mask keeping signals at least gap_sec after the previously kept one (sec sorted)."""
    sec = np.asarray(sec, np.int64)
    keep = np.zeros(len(sec), bool); last = -10 ** 12
    for i, s in enumerate(sec):
        if s - last >= gap_sec:
            keep[i] = True; last = s
    return keep


def frame(rows, cols=("sec", "side", "sl", "tp", "hold", "unit")):
    if not len(rows):
        return pd.DataFrame(columns=list(cols))
    df = pd.DataFrame(rows) if not isinstance(rows, pd.DataFrame) else rows.copy()
    df = df[(df.sl > 0) & np.isfinite(df.sl) & (df.hold >= 60)]
    df["sec"] = df.sec.astype(np.int64); df["side"] = df.side.astype(np.int64)
    df["hold"] = df.hold.astype(np.int64)
    return df.sort_values("sec").reset_index(drop=True)
