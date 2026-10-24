"""Month-end WM/R 4pm fix equity-hedge USD flow (Melvin-Prins): pre-fix follow + post-fix fade (Batch D2-6).

Card r2-month-end-fix-hedge-flow. Screen + sign check + placebo only (pre-declared; ~12 events/yr).
Event day: last London business day of the month (weekday, not a UK bank holiday).
m = USA500 (Dukascopy USA500IDXUSD 1m BID) return from the last close of the prior month to the close
of the second-to-last business day (daily close = last 1m close before 21:00 UTC).
Leg 1: m >= m_min -> BUY XAU at entry_london (15:00 London, DST aware), m <= -m_min -> SELL; exit 16:03
London (after the 15:57:30-16:02:30 fix window). Stop 0.75*ATR14(15m) (last closed 15m bar), no target.
Leg 2 (post_fix_fade): the opposite direction at 16:05 London, exit 20:55 UTC, same stop rule.
Filters: |USD2 return over the hour before entry| < 1.5 sd (sd of the same clock window over the
previous 20 weekdays; USD2 = 0.5*(-r EURUSD) + 0.5*r USDJPY); qe_boost: quarter-end months use m_min/2.
leg: "both" | "1" | "2" (reporting). placebo=True: the same weekday one week earlier (m measured up to
the business day before it).
unit = native stop distance.
"""
import numpy as np, pandas as pd
import bt1s
from strategies import _d2util as D

PARAMS = {
    "m_min": [0.0, 0.01, 0.02, 0.04],
    "entry_london": ["14:30", "15:00", "15:30"],
}
DEFAULTS = dict(m_min=0.02, entry_london="15:00")
EXIT_UNIT = True
UK_HOLIDAYS = set(pd.to_datetime([
    "2025-01-01", "2025-04-18", "2025-04-21", "2025-05-05", "2025-05-26", "2025-08-25", "2025-12-25",
    "2025-12-26", "2026-01-01", "2026-04-03", "2026-04-06", "2026-05-04", "2026-05-25", "2026-08-31",
    "2026-12-25", "2026-12-28",
]).date)


def lon_sec(dates, minutes):
    d = pd.DatetimeIndex(pd.to_datetime([str(x) for x in dates])) + pd.to_timedelta(np.asarray(minutes), unit="min")
    return d.tz_localize("Europe/London").tz_convert("UTC").tz_localize(None).as_unit("s").asi8


def _daily_close(m1):
    t = m1.index.values
    day = t // 86400
    ok = (t % 86400) < 21 * 3600
    s = pd.Series(m1.c.values[ok], index=day[ok])
    return s.groupby(level=0).last()


def signals(ctx, m_min=0.02, entry_london="15:00", post_fix_fade=True, qe_boost=True, leg="both", placebo=False):
    bd = [x.date() for x in pd.bdate_range("2024-12-01", "2026-12-31") if x.date() not in UK_HOLIDAYS]
    bds = pd.Series(bd)
    grp = bds.groupby(pd.Series([x.year * 100 + x.month for x in bd]))
    spx = _daily_close(ctx.m1("USA500IDXUSD"))
    eur = ctx.m1("EURUSD").c; jpy = ctx.m1("USDJPY").c
    hh, mm = map(int, entry_london.split(":"))
    b15 = ctx.bars(900); a15 = bt1s.atr(b15, 14); c15 = b15.close_sec.values
    rows = []
    for ym, idx in grp.groups.items():
        mo = ym % 100
        days = list(bds[idx])
        if len(days) < 3:
            continue
        ev = days[-1]
        if placebo:
            i = bd.index(ev)
            ev = bd[i - 5]
            prevs = [x for x in bd if x < ev]
            ref_end = prevs[-1]
        else:
            ref_end = days[-2]
        prior_month_end = [x for x in bd if x < days[0]]
        if not prior_month_end:
            continue
        d0 = pd.Timestamp(prior_month_end[-1]).value // 10**9 // 86400
        d1 = pd.Timestamp(ref_end).value // 10**9 // 86400
        if d0 not in spx.index or d1 not in spx.index:
            continue
        m = spx[d1] / spx[d0] - 1
        thr = m_min / 2 if (qe_boost and mo in (3, 6, 9, 12)) else m_min
        if m >= thr and m > 0:
            sd = 1
        elif m <= -thr and m < 0:
            sd = -1
        else:
            continue
        t_in = int(lon_sec([ev], [hh * 60 + mm])[0])
        t_out = int(lon_sec([ev], [16 * 60 + 3])[0])
        t_in2 = int(lon_sec([ev], [16 * 60 + 5])[0])
        # USD2 shock filter over the hour before entry vs the previous 20 weekdays
        def usd2(t):
            a, b = t - 3600 - 60, t - 60                    # bars closing at t-3601 and t-1
            if a in eur.index and b in eur.index and a in jpy.index and b in jpy.index:
                return 0.5 * -np.log(eur[b] / eur[a]) + 0.5 * np.log(jpy[b] / jpy[a])
            return np.nan
        u = usd2(t_in)
        hist = [usd2(t_in - k * 86400) for k in range(1, 29)
                if pd.Timestamp((t_in - k * 86400), unit="s").dayofweek < 5][:20]
        sdu = np.nanstd(hist, ddof=1) if np.isfinite(hist).sum() >= 10 else np.nan
        if not np.isfinite(u) or not np.isfinite(sdu) or abs(u) >= 1.5 * sdu:
            continue
        j = np.searchsorted(c15, t_in - 1, "right") - 1
        stop = 0.75 * a15[j]
        if leg in ("both", "1"):
            rows.append((t_in, sd, stop, t_out - t_in))
        if post_fix_fade and leg in ("both", "2"):
            j2 = np.searchsorted(c15, t_in2 - 1, "right") - 1
            rows.append((t_in2, -sd, 0.75 * a15[j2], int(D.hold_to(np.array([t_in2]), np.array([t_in2 + 86400]))[0])))
    s = pd.DataFrame(rows, columns=["sec", "side", "sl", "hold"]).astype({"sec": np.int64, "side": int, "sl": float, "hold": np.int64})
    s["tp"] = 0.0
    s["unit"] = s.sl
    return s[np.isfinite(s.sl) & (s.sl > 0)].sort_values("sec").reset_index(drop=True)
