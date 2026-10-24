"""Shared helpers for Batch D2 (macro-calendar) strategy modules.

KEEP STABLE: frozen D2 strategies import this file and its bytes are part of their code hash.
A material change needs a new helper file.

Calendar: ctx.calendar() = data/calendar/us_macro_2025_2026.csv (verified; no tier column).
Rows whose note starts with "SCHEDULED" are future and dropped. Tiers (researcher choice, see
research/results_batchD2.md):
  tier 1  NFP, CPI, FOMC_statement
  tier 2  PCE, GDP_advance, GDP_second, GDP_third, retail_sales, PPI, ISM_manufacturing,
          ISM_services, JOLTS
  claims  jobless_claims (separate)
  FOMC_minutes: never an event (only blocks placebo days)
Releases with the same timestamp are merged into one event typed by the highest-priority member.
"""
import numpy as np, pandas as pd

DAY = 86400
NY = "America/New_York"
TIER1 = ("NFP", "CPI", "FOMC_statement")
TIER2 = ("PCE", "GDP_advance", "GDP_second", "GDP_third", "retail_sales", "PPI",
         "ISM_manufacturing", "ISM_services", "JOLTS")
CLAIMS = ("jobless_claims",)
PRIORITY = ("NFP", "CPI", "FOMC_statement", "PCE", "GDP_advance", "retail_sales", "PPI",
            "ISM_manufacturing", "ISM_services", "JOLTS", "GDP_second", "GDP_third", "jobless_claims",
            "FOMC_minutes")
# NYSE/CME full-day holidays and early closes 2025-2026 (as strategies/last30_momentum.py)
US_HOLIDAYS = pd.to_datetime([
    "2025-01-01", "2025-01-09", "2025-01-20", "2025-02-17", "2025-04-18", "2025-05-26", "2025-06-19",
    "2025-07-03", "2025-07-04", "2025-09-01", "2025-11-27", "2025-11-28", "2025-12-24", "2025-12-25",
    "2026-01-01", "2026-01-19", "2026-02-16", "2026-04-03", "2026-05-25", "2026-06-19", "2026-07-03",
    "2026-09-07", "2026-11-26", "2026-11-27", "2026-12-24", "2026-12-25",
]).date
PLACEBO_OFFSETS = (-7, 7, -1, 1, -2, 2)


def tier_of(ev):
    return 1 if ev in TIER1 else 2 if ev in TIER2 else 3


def calendar_rows(ctx):
    c = ctx.calendar()
    c = c[~c.note.fillna("").astype(str).str.startswith("SCHEDULED")].copy()
    return c


def ny_sec(dates, minutes):
    """epoch second of New-York wall clock `minutes` after midnight on each date (DST aware)."""
    d = pd.DatetimeIndex(pd.to_datetime(pd.Series(dates).astype(str).values)) + pd.to_timedelta(np.asarray(minutes), unit="min")
    return d.tz_localize(NY, ambiguous="NaT", nonexistent="shift_forward").tz_convert("UTC").tz_localize(None).as_unit("s").asi8


def events(ctx, include, placebo=False):
    """Merged release events whose highest-priority member is in `include`.
    Returns DataFrame sorted by sec: sec, type, members, tier, date (NY date), minute (NY minutes).
    A timestamp is assigned to the highest-priority member over ALL its rows (so a claims+CPI
    timestamp is a CPI event, and is dropped if CPI is not included).
    placebo=True moves each event to the same NY clock time on a matched no-release weekday."""
    c = calendar_rows(ctx)
    pr = {e: i for i, e in enumerate(PRIORITY)}
    c["pri"] = c.event.map(pr)
    rows = []
    for sec, g in c.groupby("sec"):
        g = g.sort_values("pri")
        top = g.event.iloc[0]
        hh, mm = map(int, g.time_local.iloc[0].split(":"))
        rows.append((int(sec), top, "+".join(g.event), tier_of(top), g.date_local.iloc[0], hh * 60 + mm))
    ev = pd.DataFrame(rows, columns=["sec", "type", "members", "tier", "date", "minute"])
    ev = ev[ev.type.isin(list(include))].sort_values("sec").reset_index(drop=True)
    if placebo:
        busy = set(pd.to_datetime(c.date_local).dt.date)
        out = []
        for _, r in ev.iterrows():
            d0 = pd.Timestamp(r.date).date()
            for off in PLACEBO_OFFSETS:
                d = d0 + pd.Timedelta(days=off).to_pytimedelta()
                if pd.Timestamp(d).dayofweek < 5 and d not in busy and d not in US_HOLIDAYS:
                    out.append((int(ny_sec([str(d)], [r.minute])[0]), r.type, r.members, r.tier, str(d), r.minute))
                    break
        ev = pd.DataFrame(out, columns=ev.columns).drop_duplicates("sec").sort_values("sec").reset_index(drop=True)
    return ev


def mid_at(ctx, sec):
    k = np.clip(ctx.k_of(sec), 0, ctx.n - 1)
    return ctx.mid[k]


def spread_at(ctx, sec):
    k = np.clip(ctx.k_of(sec), 0, ctx.n - 1)
    return ctx.spread[k]


def hl_between(ctx, s0, s1):
    """max hi / min lo of the 1s grid over seconds [s0, s1] inclusive (per event)."""
    hi, lo = ctx.g["hi"], ctx.g["lo"]
    H = np.full(len(s0), np.nan); L = np.full(len(s0), np.nan)
    for i, (a, b) in enumerate(zip(ctx.k_of(s0), ctx.k_of(s1))):
        if 0 <= a <= b < ctx.n:
            H[i] = hi[a:b + 1].max(); L[i] = lo[a:b + 1].min()
    return H, L


def utc_hhmm(sec, hhmm):
    """epoch second of hh:mm UTC on the UTC calendar day of `sec`."""
    hh, mm = map(int, hhmm.split(":"))
    s = np.asarray(sec, np.int64)
    return s - s % DAY + hh * 3600 + mm * 60


def hold_to(sec, end_sec, flat="20:55"):
    """seconds from sec to min(end_sec, flat UTC same day)."""
    s = np.asarray(sec, np.int64)
    return np.minimum(np.asarray(end_sec, np.int64), utc_hhmm(s, flat)) - s


def prior_stat(values, groups, n, how="median", pooled_min=None):
    """For each row i, statistic of values over the previous n rows of the same group (exclusive).
    If the group has < n prior rows and pooled_min is given, use the previous n rows of all groups
    (pooled) instead, provided at least pooled_min exist. Rows are assumed time-sorted."""
    v = np.asarray(values, float); g = np.asarray(groups)
    f = np.nanmedian if how == "median" else (lambda x: np.nanstd(x, ddof=1))
    out = np.full(len(v), np.nan)
    for i in range(len(v)):
        same = np.where(g[:i] == g[i])[0]
        if len(same) >= n:
            out[i] = f(v[same[-n:]])
        elif pooled_min is not None and i >= pooled_min:
            out[i] = f(v[max(0, i - n):i])
    return out


def side_split(tr):
    """long/short split metrics for a trades frame (for reports)."""
    import bt1s
    rows = {}
    for p in ("IS", "VAL", "OOS"):
        for sd, nm in ((1, "long"), (-1, "short")):
            t = tr[(tr.period == p) & (tr.side == sd)]
            if len(t):
                rows[f"{p}_{nm}"] = bt1s.metrics(t)
    return pd.DataFrame(rows).T
