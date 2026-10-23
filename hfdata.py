"""Shared data loading for the XAUUSD sub-5s research.

Tick arrays (all months concatenated):
    ts   int64  epoch ms
    bid  float64 USD
    ask  float64 USD
1-second calendar grid (index = epoch_second - S0, weekends included, forward-filled):
    hi, lo        float64  max / min mid inside the second (ffill = prev close)
    bid, ask      float64  last quote of the second
    nt            int32    tick count
    nup, ndn      int32    mid up-ticks / down-ticks
    spmax         float32  max spread inside the second
    live          bool     second had >= 1 tick
"""
import os, glob
import numpy as np
from numba import njit

ROOT = os.path.dirname(os.path.abspath(__file__))
TICKS = os.path.join(ROOT, "data", "ticks")
CACHE = os.path.join(ROOT, "data", "grid1s.npz")


def load_ticks():
    files = sorted(glob.glob(os.path.join(TICKS, "ticks_*.npz")))
    ts, bid, ask = [], [], []
    for f in files:
        z = np.load(f)
        ts.append(z["ts"]); bid.append(z["bid"]); ask.append(z["ask"])
    ts = np.concatenate(ts)
    bid = np.concatenate(bid).astype(np.float64) / 1000.0
    ask = np.concatenate(ask).astype(np.float64) / 1000.0
    return ts, bid, ask


@njit(cache=True)
def _aggregate(ts, bid, ask, s0, n):
    hi = np.empty(n); lo = np.empty(n); cb = np.empty(n); ca = np.empty(n)
    nt = np.zeros(n, np.int32); nup = np.zeros(n, np.int32); ndn = np.zeros(n, np.int32)
    spm = np.zeros(n, np.float32); live = np.zeros(n, np.bool_)
    hi[:] = np.nan
    lo[:] = np.nan
    prev_mid = (bid[0] + ask[0]) * 0.5
    for i in range(len(ts)):
        k = ts[i] // 1000 - s0
        m = (bid[i] + ask[i]) * 0.5
        if not live[k]:
            live[k] = True
            hi[k] = m; lo[k] = m
        else:
            if m > hi[k]: hi[k] = m
            if m < lo[k]: lo[k] = m
        cb[k] = bid[i]; ca[k] = ask[i]
        nt[k] += 1
        if m > prev_mid: nup[k] += 1
        elif m < prev_mid: ndn[k] += 1
        sp = ask[i] - bid[i]
        if sp > spm[k]: spm[k] = sp
        prev_mid = m
    # forward fill
    lb = bid[0]; la = ask[0]
    for k in range(n):
        if live[k]:
            lb = cb[k]; la = ca[k]
        else:
            cb[k] = lb; ca[k] = la
            hi[k] = (lb + la) * 0.5; lo[k] = hi[k]
    return hi, lo, cb, ca, nt, nup, ndn, spm, live


def build_grid(ts, bid, ask):
    s0 = int(ts[0] // 1000)
    n = int(ts[-1] // 1000) - s0 + 1
    hi, lo, cb, ca, nt, nup, ndn, spm, live = _aggregate(ts, bid, ask, s0, n)
    return dict(s0=s0, hi=hi, lo=lo, bid=cb, ask=ca, nt=nt, nup=nup, ndn=ndn, spmax=spm, live=live)


def load_all(rebuild=False):
    ts, bid, ask = load_ticks()
    if os.path.exists(CACHE) and not rebuild:
        z = np.load(CACHE)
        g = {k: z[k] for k in z.files}
        g["s0"] = int(g["s0"])
        if g["s0"] == int(ts[0] // 1000) and len(g["hi"]) == int(ts[-1] // 1000) - g["s0"] + 1:
            return ts, bid, ask, g
    g = build_grid(ts, bid, ask)
    np.savez(CACHE, **g)
    return ts, bid, ask, g
