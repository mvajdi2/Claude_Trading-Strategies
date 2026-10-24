"""Shared helpers for Batch B strategy modules (keep stable: frozen strategies import this)."""
import numpy as np, pandas as pd

DAY = 86400


def tday(sec):
    """trading-day id: day starts 23:00 UTC (23:00 belongs to the next calendar date)."""
    return (np.asarray(sec, np.int64) + 3600) // DAY


def hour_of(sec):
    """UTC hour (float) of an epoch second."""
    return (np.asarray(sec, np.int64) % DAY) / 3600.0


def day_sec(sec, hour):
    """epoch second of `hour` UTC on the calendar date of `sec`."""
    s = np.asarray(sec, np.int64)
    return s - s % DAY + int(round(hour * 3600))


def align(htf, vals, t):
    """value of the last higher-timeframe bar that has CLOSED by second t (close_sec <= t)."""
    i = np.searchsorted(htf.close_sec.values, np.asarray(t, np.int64), side="right") - 1
    v = np.asarray(vals, np.float64)
    return np.where(i >= 0, v[np.maximum(i, 0)], np.nan)


def daily_bars(ctx):
    """23:00-21:00 UTC daily OHLC (index = trading-day id), built from 1h bars."""
    h = ctx.bars(3600)
    hr = (h.index.values % DAY) // 3600
    h = h[(hr < 21) | (hr >= 23)]
    d = h.groupby(tday(h.index.values)).agg(o=("o", "first"), h=("h", "max"), l=("l", "min"),
                                             c=("c", "last"), nb=("o", "size"))
    d = d[d.nb >= 12]
    return d


def daily_atr(d, n=14):
    pc = d.c.shift(1)
    tr = np.maximum(d.h - d.l, np.maximum((d.h - pc).abs(), (d.l - pc).abs()))
    return tr.rolling(n).mean()


def first_hit(ctx, s_from, s_to, level, up):
    """first epoch second in [s_from, s_to] whose 1s high >= level (up) / low <= level (down); -1 if none"""
    k0 = max(int(s_from) - ctx.s0, 0); k1 = min(int(s_to) - ctx.s0 + 1, ctx.n)
    if k1 <= k0:
        return -1
    a = ctx.g["hi"][k0:k1] if up else ctx.g["lo"][k0:k1]
    m = (a >= level) if up else (a <= level)
    if not m.any():
        return -1
    return int(np.argmax(m)) + k0 + ctx.s0


def ext(ctx, s_from, s_to, up):
    """max 1s high (up) / min 1s low over [s_from, s_to]"""
    k0 = max(int(s_from) - ctx.s0, 0); k1 = min(int(s_to) - ctx.s0 + 1, ctx.n)
    a = ctx.g["hi"][k0:k1] if up else ctx.g["lo"][k0:k1]
    return float(np.nanmax(a)) if up else float(np.nanmin(a))


def mid_at(ctx, sec):
    k = int(sec) - ctx.s0
    return float(ctx.mid[k])


def frame(rows):
    cols = ["sec", "side", "sl", "tp", "hold", "unit"]
    if not rows:
        return pd.DataFrame(columns=cols)
    df = pd.DataFrame(rows)
    df = df[(df.sl > 0) & np.isfinite(df.sl) & (df.hold > 0)]
    df["sec"] = df.sec.astype(np.int64); df["side"] = df.side.astype(np.int64)
    df["hold"] = df.hold.astype(np.int64)
    return df.sort_values("sec").reset_index(drop=True)


def cap_per_day(df, n):
    """keep only the first n signals per trading day"""
    if len(df) == 0:
        return df
    d = tday(df.sec.values)
    rk = pd.Series(d).groupby(d).cumcount().values
    return df[rk < n].reset_index(drop=True)


def ny_blackout(sec, windows=((8 * 60, 9 * 60), (9 * 60 + 45, 10 * 60 + 30))):
    """True where the epoch second falls in any [start, end) New York local-time window (minutes
    of the day, DST-aware via America/New_York). Default = 08:00-09:00 and 09:45-10:30 NY,
    i.e. 30 min either side of the 08:30 and 10:00 ET US releases."""
    s = np.asarray(sec, np.int64)
    if len(s) == 0:
        return np.zeros(0, bool)
    et = pd.to_datetime(s, unit="s").tz_localize("UTC").tz_convert("America/New_York")
    m = et.hour.values * 60 + et.minute.values
    out = np.zeros(len(s), bool)
    for a, b in windows:
        out |= (m >= a) & (m < b)
    return out


def fakeout_core(ctx, tf, asian_end, max_bars_outside, stop_buf, exit_h, sig_end, range_filter):
    """Asian-range (00:00-asian_end UTC) close-outside / close-back-inside fade.
    Excursion = run of consecutive closes outside one side. Entry only if the close back inside
    comes within max_bars_outside bars of the first outside close; an excursion that expires while
    still outside must close back inside (no trade) before a new break can arm. ext = full extreme
    of the excursion. Opposite side closed outside first -> skip the day. Max 1 trade/day.
    range_filter: skip days with Asian range > 1.5*ATR14(1h)*6 (ATR of the last closed H1 bar)."""
    import bt1s
    b = ctx.bars(tf)
    a = bt1s.atr(b, 14)
    h1 = ctx.bars(3600); a1 = bt1s.atr(h1, 14)
    idx = b.index.values
    date = idx // DAY
    hr = (idx % DAY) / 3600.0
    H, L, C = b.h.values, b.l.values, b.c.values
    cs = b.close_sec.values
    sig_end = min(sig_end, exit_h)
    rows = []
    starts = np.r_[0, np.flatnonzero(np.diff(date)) + 1, len(b)]
    for s, e in zip(starts[:-1], starts[1:]):
        hh = hr[s:e]
        rng = np.flatnonzero(hh < asian_end)
        if len(rng) < max(1, int(asian_end * 3600 / tf * 0.7)):
            continue
        ah = H[s + rng].max(); al = L[s + rng].min()
        if range_filter:
            ref = align(h1, a1, [date[s] * DAY + int(asian_end * 3600) - 1])[0]
            if not np.isfinite(ref) or ah - al > 1.5 * ref * 6:
                continue
        post = np.flatnonzero((hh >= asian_end) & (hh + tf / 3600.0 <= sig_end))
        state = 0; first_i = -1; ex = np.nan; broke = set(); expired = False
        for j in post:
            i = s + j
            if state == 0:
                if C[i] < al:
                    if 1 in broke:
                        break
                    state, first_i, ex, expired = -1, i, L[i], False; broke.add(-1)
                elif C[i] > ah:
                    if -1 in broke:
                        break
                    state, first_i, ex, expired = 1, i, H[i], False; broke.add(1)
                continue
            if state == -1:
                ex = min(ex, L[i])
                if C[i] > ah:          # crossed the whole range: opposite side broken
                    break
                if C[i] >= al:         # back inside
                    if not expired and i - first_i <= max_bars_outside:
                        sl = C[i] - (ex - stop_buf * a[i])
                        tp = min(ah - C[i], 2 * sl)
                        rows.append(dict(sec=cs[i], side=1, sl=sl, tp=tp, unit=sl,
                                         hold=date[i] * DAY + exit_h * 3600 - cs[i]))
                        break
                    state = 0          # expired excursion ended: may re-arm on a new break
            else:
                ex = max(ex, H[i])
                if C[i] < al:
                    break
                if C[i] <= ah:
                    if not expired and i - first_i <= max_bars_outside:
                        sl = (ex + stop_buf * a[i]) - C[i]
                        tp = min(C[i] - al, 2 * sl)
                        rows.append(dict(sec=cs[i], side=-1, sl=sl, tp=tp, unit=sl,
                                         hold=date[i] * DAY + exit_h * 3600 - cs[i]))
                        break
                    state = 0
            if state != 0 and i - first_i >= max_bars_outside:
                expired = True         # next close back inside cannot trade
    df = frame(rows)
    return df[df.tp > 0].reset_index(drop=True) if len(df) else df
