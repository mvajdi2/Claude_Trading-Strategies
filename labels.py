"""First-passage labels: for each trade entry, the time (ms) at which the exit-side quote
first reaches +x (favourable) and -x (adverse) USD from the entry fill, for x on a grid.
Lets us evaluate any static TP/SL bracket for every event in vectorized form.
"""
import numpy as np
from numba import njit, prange
from simulate import _quotes

GRID = np.round(np.arange(0.1, 12.01, 0.1), 2)   # USD
NEVER = np.int64(2**62)


@njit(cache=True, parallel=True)
def first_passage(ts, bid, ask, i0s, sides, entry_px, horizon_ms, grid, sp_k, sp_min):
    m = len(i0s); g = len(grid)
    fav = np.full((m, g), NEVER, np.int64)
    adv = np.full((m, g), NEVER, np.int64)
    for j in prange(m):
        i0 = i0s[j]; sd = sides[j]; e = entry_px[j]
        t0 = ts[i0]
        kf = 0; ka = 0
        for i in range(i0 + 1, len(ts)):
            dt = ts[i] - t0
            if dt > horizon_ms:
                break
            b, a = _quotes(bid[i], ask[i], sp_k, sp_min)
            px = b if sd == 1 else a
            x = (px - e) * sd
            while kf < g and x >= grid[kf]:
                fav[j, kf] = dt; kf += 1
            while ka < g and -x >= grid[ka]:
                adv[j, ka] = dt; ka += 1
            if kf == g and ka == g:
                break
    return fav, adv


def market_entry_px(bid, ask, i0s, sides, cost):
    mid = 0.5 * (bid[i0s] + ask[i0s])
    h = 0.5 * np.maximum(cost.sp_min, cost.sp_k * (ask[i0s] - bid[i0s]))
    return np.where(sides == 1, mid + h + cost.slip, mid - h - cost.slip)


def bracket(fav, adv, tp, sl, cost):
    """Static bracket outcome per event: +tp (win), -sl-slip (loss), or NaN (neither in horizon).
    tp, sl may be scalars or per-event arrays (USD)."""
    gi = lambda x: np.clip(np.round(np.asarray(x) / 0.1).astype(int) - 1, 0, len(GRID) - 1)
    m = fav.shape[0]
    it = np.broadcast_to(gi(tp), (m,)); il = np.broadcast_to(gi(sl), (m,))
    ft = fav[np.arange(m), it]; at = adv[np.arange(m), il]
    win = ft < at
    loss = at < ft
    out = np.full(m, np.nan)
    tpv = GRID[it]; slv = GRID[il]
    out[win] = tpv[win] - cost.comm
    out[loss] = -slv[loss] - cost.slip - cost.comm
    return out
