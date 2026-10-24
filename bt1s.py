"""Generic 1-second bar backtester for intraday XAUUSD strategies.

Usage
-----
    import bt1s
    ctx = bt1s.Context.load()                  # 1s grid + helpers (~2.6 GB RAM)
    m15 = ctx.bars(900)                        # OHLC bars resampled from 1s
    sig = my_strategy.signals(ctx, **params)   # DataFrame, see SIGNAL COLUMNS
    trades = bt1s.run(ctx, sig)                # one position at a time, flat by 21:00 UTC
    print(bt1s.report(trades))

SIGNAL COLUMNS (one row per entry decision)
    sec      int    epoch second at which the decision is known (bar close); entry is filled at
                    the close of the next second (>= 1 s latency) at the modeled ask/bid + slippage
    side     int    +1 long, -1 short
    sl       float  stop distance in USD from the entry fill (> 0)
    tp       float  target distance in USD (<= 0 or NaN: no target)
    hold     int    max holding time in seconds (time exit); engine also forces flat at 21:00 UTC
  optional:
    tp1      float  first target distance (partial close), with f1 the fraction closed (0-1)
    f1       float
    be       int    1: move stop to break-even (+be_off) after tp1
    be_off   float
    trail    float  trailing-stop distance in USD (active from entry, or after tp1 if tp1 given)

COST MODEL (cTrader-equivalent, see simulate.py): half-spread = 0.5*max(SP_MIN, SP_K*dukascopy
spread); market fills (entry, stop, time exit) pay SLIP; limit targets fill at the limit;
commission per oz round trip. When a stop and a target are both touched inside the same second,
the stop is assumed first.
"""
import os
import numpy as np, pandas as pd
from numba import njit
import hfdata

IS_END = pd.Timestamp("2026-01-01")
VAL_END = pd.Timestamp("2026-06-01")
FLAT_HOUR_UTC = 21


class Cost:
    def __init__(self, sp_k=0.30, sp_min=0.10, slip=0.03, comm=0.07, extra_latency_s=0):
        self.sp_k, self.sp_min, self.slip, self.comm = sp_k, sp_min, slip, comm
        self.extra_latency_s = extra_latency_s


CTRADER = Cost()
STRESS = Cost(sp_k=0.45, sp_min=0.15, slip=0.10, extra_latency_s=1)


class Context:
    """Holds the 1s grid and caches resampled bars and indicators."""

    def __init__(self, g):
        self.g = g
        self.s0 = int(g["s0"])
        self.n = len(g["hi"])
        self.mid = 0.5 * (g["bid"] + g["ask"])
        self.spread = (g["ask"] - g["bid"]).astype(np.float64)
        self._bars = {}

    @classmethod
    def load(cls):
        z = np.load(hfdata.CACHE)
        g = {k: z[k] for k in ("s0", "hi", "lo", "bid", "ask", "nt", "live")}
        return cls(g)

    # ---------- time helpers ----------
    def k_of(self, sec):
        return np.asarray(sec, np.int64) - self.s0

    def sec_of(self, k):
        return np.asarray(k, np.int64) + self.s0

    # ---------- bars ----------
    def bars(self, tf):
        """OHLC of mid at `tf` seconds (tf divides 86400). Index = bar start epoch second.
        Columns: o h l c n (tick count) live (bool). Bars with no ticks are dropped."""
        if tf in self._bars:
            return self._bars[tf]
        g = self.g
        pad = self.s0 % tf
        n = self.n + pad
        m = (n + tf - 1) // tf * tf
        def padarr(a, fill):
            out = np.full(m, fill, dtype=a.dtype if a.dtype != np.bool_ else np.bool_)
            out[pad:pad + self.n] = a
            return out.reshape(-1, tf)
        hi = padarr(g["hi"], -np.inf); lo = padarr(g["lo"], np.inf)
        mid = padarr(self.mid, np.nan); nt = padarr(g["nt"].astype(np.int64), 0)
        live = padarr(g["live"], False)
        o = mid[:, 0].copy()
        if pad:
            o[0] = mid[0, pad]
        df = pd.DataFrame({"o": o, "h": hi.max(1), "l": lo.min(1), "c": mid[:, -1],
                           "n": nt.sum(1), "live": live.any(1)})
        df.index = (self.s0 - pad) + np.arange(len(df), dtype=np.int64) * tf
        df = df[df.live & (df.n >= max(1, tf // 60))].drop(columns="live")
        df["time"] = pd.to_datetime(df.index, unit="s")
        df["close_sec"] = df.index + tf - 1      # decision time = last second of the bar
        self._bars[tf] = df
        return df


    # ---------- cross-asset 1-minute data ----------
    def m1(self, sym):
        """Dukascopy 1-minute BID candles for another symbol (data/m1/<sym>.npz, see download_m1.py).
        Index = minute-start epoch second; columns o h l c v time close_sec. Use only bars whose
        close_sec <= the XAUUSD decision second (no look-ahead)."""
        key = f"m1:{sym}"
        if key not in self._bars:
            z = np.load(os.path.join(hfdata.ROOT, "data", "m1", f"{sym}.npz"))
            df = pd.DataFrame({k: z[k] for k in ("o", "h", "l", "c", "v")}, index=z["ts"].astype(np.int64))
            df = df[~df.index.duplicated()].sort_index()
            df["time"] = pd.to_datetime(df.index, unit="s")
            df["close_sec"] = df.index + 59
            self._bars[key] = df
        return self._bars[key]

    def calendar(self):
        """Verified US macro release calendar (data/calendar/us_macro_2025_2026.csv) with an
        epoch-second column `sec`."""
        if "calendar" not in self._bars:
            c = pd.read_csv(os.path.join(hfdata.ROOT, "data", "calendar", "us_macro_2025_2026.csv"))
            c["sec"] = pd.to_datetime(c.datetime_utc, utc=True).dt.tz_localize(None).astype("datetime64[s]").astype(np.int64)
            self._bars["calendar"] = c
        return self._bars["calendar"]


# ---------------------------------------------------------------- indicators
def ema(x, n):
    return pd.Series(x).ewm(span=n, adjust=False).mean().values


def sma(x, n):
    return pd.Series(x).rolling(n).mean().values


def atr(b, n=14):
    pc = b.c.shift(1)
    tr = np.maximum(b.h - b.l, np.maximum((b.h - pc).abs(), (b.l - pc).abs()))
    return tr.rolling(n).mean().values


def rsi(x, n=14):
    d = pd.Series(x).diff()
    up = d.clip(lower=0).ewm(alpha=1 / n, adjust=False).mean()
    dn = (-d.clip(upper=0)).ewm(alpha=1 / n, adjust=False).mean()
    return (100 - 100 / (1 + up / dn.replace(0, np.nan))).values


def session_vwap(b, start_hour=0):
    """VWAP of typical price with tick count as volume, reset each UTC day at start_hour."""
    tp = (b.h + b.l + b.c) / 3
    day = ((b.index.values - start_hour * 3600) // 86400)
    v = b.n.astype(float)
    cpv = pd.Series(tp.values * v.values).groupby(day).cumsum().values
    cv = pd.Series(v.values).groupby(day).cumsum().values
    return cpv / np.maximum(cv, 1)


# ---------------------------------------------------------------- engine
@njit(cache=True)
def _run(hi, lo, bid, ask, k_dec, side, sl, tp, hold, tp1, f1, be, be_off, trail,
         sp_k, sp_min, slip, comm, lat, flat_k):
    n = len(hi)
    m = len(k_dec)
    out = np.full((m, 8), np.nan)  # k_entry, k_exit, entry_px, pnl, risk, code, mfe, mae
    busy_until = -1
    for j in range(m):
        k0 = k_dec[j] + 1 + lat
        if k0 <= busy_until or k0 >= n - 1:
            continue
        sd = side[j]
        mid0 = 0.5 * (bid[k0] + ask[k0]); h0 = 0.5 * max(sp_min, sp_k * (ask[k0] - bid[k0]))
        entry = mid0 + sd * (h0 + slip)
        stop = entry - sd * sl[j]
        tgt = entry + sd * tp[j] if tp[j] > 0 else np.nan
        t1 = entry + sd * tp1[j] if tp1[j] > 0 else np.nan
        kend = min(k0 + hold[j], flat_k[j], n - 1)
        rem = 1.0; pnl = 0.0; got1 = False; best = entry
        mfe = 0.0; mae = 0.0; code = 3; kx = kend
        trail_on = trail[j] > 0 and not (tp1[j] > 0)
        for k in range(k0 + 1, kend + 1):
            h = 0.5 * max(sp_min, sp_k * (ask[k] - bid[k]))
            # exit-side extremes inside second k (long exits at bid, short at ask)
            if sd == 1:
                worst = lo[k] - h; bestp = hi[k] - h; close = 0.5 * (bid[k] + ask[k]) - h
            else:
                worst = hi[k] + h; bestp = lo[k] + h; close = 0.5 * (bid[k] + ask[k]) + h
            fav = (bestp - entry) * sd; adv = (entry - worst) * sd
            if fav > mfe: mfe = fav
            if adv > mae: mae = adv
            # 1) stop first
            if (worst - stop) * sd <= 0:
                fill = min(stop, worst) if sd == 1 else max(stop, worst)
                pnl += rem * ((fill - sd * slip) - entry) * sd
                rem = 0.0; code = 2 if got1 else 0; kx = k
                break
            # 2) partial target
            if not got1 and t1 == t1 and (bestp - t1) * sd >= 0:
                pnl += f1[j] * (t1 - entry) * sd
                rem -= f1[j]; got1 = True
                if be[j] == 1:
                    ns = entry + sd * be_off[j]
                    if (ns - stop) * sd > 0: stop = ns
                if trail[j] > 0: trail_on = True; best = bestp
                if rem <= 1e-9:
                    code = 1; kx = k; break
            # 3) final target
            if tgt == tgt and (bestp - tgt) * sd >= 0:
                pnl += rem * (tgt - entry) * sd
                rem = 0.0; code = 1; kx = k
                break
            # 4) trailing stop update (applies from next second)
            if trail_on:
                if (bestp - best) * sd > 0: best = bestp
                ns = best - sd * trail[j]
                if (ns - stop) * sd > 0: stop = ns
            if k == kend:
                pnl += rem * ((close - sd * slip) - entry) * sd
                rem = 0.0; code = 4 if got1 else 3; kx = k
        pnl -= comm
        out[j, 0] = k0; out[j, 1] = kx; out[j, 2] = entry; out[j, 3] = pnl
        out[j, 4] = sl[j] + slip + comm; out[j, 5] = code; out[j, 6] = mfe; out[j, 7] = mae
        busy_until = kx
    return out


def run(ctx, sig, cost=CTRADER):
    """Simulate signals; returns one row per executed trade."""
    if len(sig) == 0:
        return pd.DataFrame()
    s = sig.sort_values("sec").reset_index(drop=True)
    m = len(s)
    col = lambda c, d: s[c].fillna(d).values.astype(np.float64) if c in s else np.full(m, d, np.float64)
    k_dec = ctx.k_of(s.sec.values)
    sec = s.sec.values.astype(np.int64)
    day_start = sec - sec % 86400
    flat_sec = day_start + FLAT_HOUR_UTC * 3600 - 1
    flat_sec = np.where(sec >= flat_sec, flat_sec + 86400, flat_sec)   # decisions after 21:00 -> next day close
    flat_k = ctx.k_of(flat_sec)
    out = _run(ctx.g["hi"], ctx.g["lo"], ctx.g["bid"], ctx.g["ask"], k_dec,
               s.side.values.astype(np.int64), col("sl", np.nan), col("tp", 0.0),
               s.hold.values.astype(np.int64), col("tp1", 0.0), col("f1", 0.0),
               col("be", 0).astype(np.int64), col("be_off", 0.0), col("trail", 0.0),
               cost.sp_k, cost.sp_min, cost.slip, cost.comm, int(cost.extra_latency_s), flat_k)
    t = pd.DataFrame(out, columns=["k_entry", "k_exit", "entry_px", "pnl", "risk", "code", "mfe", "mae"])
    t = pd.concat([s, t], axis=1).dropna(subset=["k_entry"])
    t["entry_time"] = pd.to_datetime(ctx.sec_of(t.k_entry.astype(np.int64)), unit="s")
    t["hold_s"] = t.k_exit - t.k_entry
    t["R"] = t.pnl / t.risk
    t["period"] = np.where(t.entry_time < IS_END, "IS", np.where(t.entry_time < VAL_END, "VAL", "OOS"))
    return t.reset_index(drop=True)


def metrics(t, risk_pct=0.5):
    """WR, $PF, R-PF, compounding equity DD at risk_pct% per trade, trades/week."""
    if len(t) == 0:
        return dict(n=0)
    pnl = t.pnl.values; R = t.R.values
    eq = np.cumprod(1 + risk_pct / 100 * R)
    peak = np.maximum.accumulate(np.r_[1.0, eq])[1:]
    dd = float(np.max(1 - eq / peak)) * 100
    weeks = max((t.entry_time.max() - t.entry_time.min()).days / 7, 1)
    return dict(n=len(t), per_wk=len(t) / weeks, wr=(pnl > 0).mean() * 100,
                pf=pnl[pnl > 0].sum() / max(-pnl[pnl <= 0].sum(), 1e-9),
                pfR=R[R > 0].sum() / max(-R[R <= 0].sum(), 1e-9),
                expR=R.mean(), ret_pct=(eq[-1] - 1) * 100, dd_pct=dd,
                avg_hold_min=t.hold_s.mean() / 60)


def report(t, periods=("IS", "VAL", "OOS"), risk_pct=0.5):
    rows = {p: metrics(t[t.period == p], risk_pct) for p in periods if (t.period == p).any()}
    return pd.DataFrame(rows).T


GATES = dict(wr=75.0, pf=3.0, dd_pct=5.0)


def passes(m):
    return m.get("n", 0) > 0 and m["wr"] > GATES["wr"] and m["pf"] > GATES["pf"] and m["dd_pct"] < GATES["dd_pct"]
