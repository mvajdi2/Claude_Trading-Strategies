"""Tick-level trade simulation with latency, spread model, slippage and commission.

Cost model ("ctrader" by default):
    executable quotes are rebuilt around the Dukascopy mid:
        half = 0.5 * max(SP_MIN, SP_K * dukascopy_spread)
        bid' = mid - half,  ask' = mid + half
    market fills (entry, stop, time-exit) pay SLIP extra; TP limits fill at the limit price.
    commission COMM per oz round trip.
Raw mode (SP_K=1, SP_MIN=0) uses Dukascopy's own bid/ask (stress test).
"""
import numpy as np
from numba import njit, prange


class Cost:
    def __init__(self, sp_k=0.30, sp_min=0.10, slip=0.03, comm=0.07, latency_ms=120):
        self.sp_k, self.sp_min, self.slip, self.comm, self.latency_ms = sp_k, sp_min, slip, comm, latency_ms

    def tup(self):
        return (self.sp_k, self.sp_min, self.slip, self.comm)


CTRADER = Cost()
RAW_DUKA = Cost(sp_k=1.0, sp_min=0.0, slip=0.03, comm=0.07)


@njit(cache=True, inline="always")
def _quotes(b, a, sp_k, sp_min):
    mid = 0.5 * (a + b)
    sp = a - b
    h = 0.5 * max(sp_min, sp_k * sp)
    return mid - h, mid + h


@njit(cache=True)
def sim_one(ts, bid, ask, i0, side, sl_d, tp1_d, f1, tp2_d, be_after_tp1, be_off,
            trail_d, max_hold_ms, sp_k, sp_min, slip, comm, entry_px=np.nan):
    """Returns (pnl_per_oz, risk_per_oz, exit_code, hold_ms, mfe, mae).
    Distances are in USD from the entry fill. tp2_d<=0 -> no TP2 (runner exits by stop/trail/time).
    exit_code: 0 SL, 1 TP1+TP2/all TP, 2 TP1 then BE/trail stop, 3 time, 4 TP1 then time.
    """
    n = len(ts)
    b, a = _quotes(bid[i0], ask[i0], sp_k, sp_min)
    if np.isnan(entry_px):
        entry = (a + slip) if side == 1 else (b - slip)
    else:
        entry = entry_px
    sl = entry - side * sl_d
    tp1 = entry + side * tp1_d
    tp2 = entry + side * tp2_d if tp2_d > 0 else np.nan
    t_end = ts[i0] + max_hold_ms
    filled1 = False
    pnl = 0.0
    rem = 1.0
    best = entry
    mfe = 0.0; mae = 0.0
    stop = sl
    code = 3
    hold = 0
    for i in range(i0 + 1, n):
        b, a = _quotes(bid[i], ask[i], sp_k, sp_min)
        px = b if side == 1 else a          # price we can exit at
        fav = (px - entry) * side
        if fav > mfe: mfe = fav
        if -fav > mae: mae = -fav
        hold = ts[i] - ts[i0]
        # stop first (conservative)
        if (side == 1 and px <= stop) or (side == -1 and px >= stop):
            fill = px - side * slip
            pnl += rem * (fill - entry) * side
            rem = 0.0
            code = 2 if filled1 else 0
            break
        if not filled1 and ((side == 1 and px >= tp1) or (side == -1 and px <= tp1)):
            close = f1 if (tp2_d > 0 or trail_d > 0 or f1 < 1.0) else 1.0
            pnl += close * (tp1 - entry) * side
            rem -= close
            filled1 = True
            if rem <= 1e-9:
                code = 1
                break
            if be_after_tp1:
                stop = entry + side * be_off
            best = px
        if filled1:
            if tp2_d > 0 and ((side == 1 and px >= tp2) or (side == -1 and px <= tp2)):
                pnl += rem * (tp2 - entry) * side
                rem = 0.0
                code = 1
                break
            if trail_d > 0:
                if (px - best) * side > 0:
                    best = px
                ts_px = best - side * trail_d
                if (ts_px - stop) * side > 0:
                    stop = ts_px
        if ts[i] >= t_end:
            fill = px - side * slip
            pnl += rem * (fill - entry) * side
            rem = 0.0
            code = 4 if filled1 else 3
            break
    if rem > 0:  # ran out of data
        b, a = _quotes(bid[n - 1], ask[n - 1], sp_k, sp_min)
        px = b if side == 1 else a
        pnl += rem * (px - entry) * side
    pnl -= comm
    return pnl, sl_d + slip, code, hold, mfe, mae


@njit(cache=True, parallel=True)
def sim_many(ts, bid, ask, i0s, sides, sl_ds, tp1_ds, f1, tp2_ds, be_after_tp1, be_off,
             trail_ds, max_hold_ms, sp_k, sp_min, slip, comm):
    m = len(i0s)
    out = np.empty((m, 6))
    for j in prange(m):
        r = sim_one(ts, bid, ask, i0s[j], sides[j], sl_ds[j], tp1_ds[j], f1, tp2_ds[j],
                    be_after_tp1, be_off, trail_ds[j], max_hold_ms, sp_k, sp_min, slip, comm)
        out[j, 0] = r[0]; out[j, 1] = r[1]; out[j, 2] = r[2]
        out[j, 3] = r[3]; out[j, 4] = r[4]; out[j, 5] = r[5]
    return out


@njit(cache=True)
def limit_fill(ts, bid, ask, i0, side, limit_px, cancel_px, wait_ms, sp_k, sp_min):
    """Resting limit order placed at tick i0. Long: buy limit fills when ask' <= limit.
    Short: sell limit fills when bid' >= limit. Cancelled if price trades through
    cancel_px in the trade direction first (target already reached) or after wait_ms.
    Returns fill tick index or -1."""
    t_end = ts[i0] + wait_ms
    for i in range(i0, len(ts)):
        if ts[i] > t_end:
            return -1
        b, a = _quotes(bid[i], ask[i], sp_k, sp_min)
        if side == 1:
            if a <= limit_px:
                return i
            if b >= cancel_px:
                return -1
        else:
            if b >= limit_px:
                return i
            if a <= cancel_px:
                return -1
    return -1


@njit(cache=True, parallel=True)
def sim_many_limit(ts, bid, ask, i0s, sides, lim_px, cancel_px, wait_ms, sl_px, tp1_px, f1, tp2_px,
                   be_after_tp1, be_off, trail_ds, max_hold_ms, sp_k, sp_min, slip, comm):
    """Limit-entry version: SL/TP given as absolute prices. Row of NaN when unfilled."""
    m = len(i0s)
    out = np.full((m, 7), np.nan)
    for j in prange(m):
        i = limit_fill(ts, bid, ask, i0s[j], sides[j], lim_px[j], cancel_px[j], wait_ms, sp_k, sp_min)
        if i < 0:
            continue
        e = lim_px[j]
        sd = sides[j]
        sl_d = (e - sl_px[j]) * sd
        tp1_d = (tp1_px[j] - e) * sd
        tp2_d = (tp2_px[j] - e) * sd if not np.isnan(tp2_px[j]) else 0.0
        r = sim_one(ts, bid, ask, i, sd, sl_d, tp1_d, f1, tp2_d, be_after_tp1, be_off,
                    trail_ds[j], max_hold_ms, sp_k, sp_min, slip, comm, e)
        out[j, 0] = r[0]; out[j, 1] = r[1]; out[j, 2] = r[2]
        out[j, 3] = r[3]; out[j, 4] = r[4]; out[j, 5] = r[5]; out[j, 6] = ts[i]
    return out


def entry_index(ts, signal_sec, latency_ms):
    """First tick at or after (end of signal second + latency)."""
    target = (np.asarray(signal_sec, np.int64) + 1) * 1000 + int(latency_ms)
    return np.searchsorted(ts, target, side="left")


def metrics(pnl, risk=None):
    pnl = np.asarray(pnl, float)
    n = len(pnl)
    if n == 0:
        return dict(n=0, wr=np.nan, pf=np.nan, avg=np.nan, tot=0.0, dd=0.0)
    w = pnl[pnl > 0].sum(); l = -pnl[pnl <= 0].sum()
    r = pnl / risk if risk is not None else pnl
    eq = np.cumsum(r)
    dd = float(np.max(np.maximum.accumulate(np.concatenate([[0], eq]))[1:] - eq)) if n else 0.0
    return dict(n=n, wr=float((pnl > 0).mean() * 100), pf=float(w / l) if l > 0 else np.inf,
                avg=float(pnl.mean()), tot=float(r.sum()), dd=dd)
