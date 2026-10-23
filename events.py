"""Causal detection of sub-5-second impulse -> rejection events on the 1s grid.

At the close of second t we look for an extreme E made at second e (t-5 <= e < t) by an
impulse of <= 5 seconds, followed by a rejection that has already retraced >= RHO_MIN of
the impulse by second t.  Everything used is known at the close of second t.

Up-spike rejected  -> SHORT (side = -1)
Down-spike rejected -> LONG (side = +1)

Each candidate carries a wide feature vector; strict filtering happens later.
"""
import numpy as np
from numba import njit

LEVEL_WINDOWS = np.array([60, 300, 900, 1800, 3600, 14400], dtype=np.int64)
FEATURES = [
    "t", "e", "side", "E", "S", "C", "imp", "imp_dur", "rej_dur", "retrace",
    "sig1s_300", "imp_sig", "std900", "std3600", "std14400",
    "tick_rate_imp", "tick_rate_base", "tick_ratio",
    "imb_imp", "imb_rej", "spread_imp", "spread_base", "spread_ratio", "spread_now",
    "sw60", "sw300", "sw900", "sw1800", "sw3600", "sw14400",
    "bk60", "bk300", "bk900", "bk1800", "bk3600", "bk14400",
    "ret300", "ret1800", "ret14400", "z14400", "mean3600_slope",
    "pdh_sw", "pdl_sw", "sess_sw", "round_dist",
]
NF = len(FEATURES)


@njit(cache=True)
def _std(mid_hi, mid_lo, a, b):
    # std of second mid ((hi+lo)/2) over [a, b)
    n = b - a
    s = 0.0; s2 = 0.0
    for k in range(a, b):
        m = 0.5 * (mid_hi[k] + mid_lo[k])
        s += m; s2 += m * m
    mu = s / n
    v = s2 / n - mu * mu
    return np.sqrt(v) if v > 0 else 0.0, mu


@njit(cache=True)
def scan(hi, lo, bid, ask, nt, nup, ndn, spmax, live, day_hi_prev, day_lo_prev, sess_hi, sess_lo,
         imp_min_usd, imp_min_sig, rho_min, start_k):
    n = len(hi)
    cap = 2_000_000
    out = np.empty((cap, NF))
    cnt = 0
    last_e_up = -1
    last_e_dn = -1
    # rolling sums for 1s mid-change sigma over 300s
    for t in range(max(start_k, 14400 + 400), n):
        if not live[t]:
            continue
        c_mid = 0.5 * (bid[t] + ask[t])
        for side in (-1, 1):
            # side -1: look for up-spike extreme in [t-5, t-1]
            ebest = -1
            ex = -1e18 if side == -1 else 1e18
            for e in range(t - 5, t):
                v = hi[e] if side == -1 else lo[e]
                if (side == -1 and v > ex) or (side == 1 and v < ex):
                    ex = v; ebest = e
            e = ebest
            if side == -1 and e == last_e_up:
                continue
            if side == 1 and e == last_e_dn:
                continue
            # impulse start: opposite extreme in [e-5, e-1]
            st = 1e18 if side == -1 else -1e18
            sidx = -1
            for k in range(e - 5, e):
                v = lo[k] if side == -1 else hi[k]
                if (side == -1 and v < st) or (side == 1 and v > st):
                    st = v; sidx = k
            imp = (ex - st) if side == -1 else (st - ex)
            if imp < imp_min_usd:
                continue
            # extreme must also beat the current second (rejection after e)
            if side == -1 and hi[t] >= ex:
                continue
            if side == 1 and lo[t] <= ex:
                continue
            retr = (ex - c_mid) / imp if side == -1 else (c_mid - ex) / imp
            if retr < rho_min:
                continue
            # sigma of 1s mid changes over 300s before impulse start
            a = sidx - 300
            s = 0.0; s2 = 0.0
            for k in range(a, sidx):
                d = 0.5 * (bid[k + 1] + ask[k + 1]) - 0.5 * (bid[k] + ask[k])
                s += d; s2 += d * d
            v = s2 / 300 - (s / 300) ** 2
            sig = max(np.sqrt(v) if v > 0 else 0.0, 0.03)
            imp_sig = imp / (sig * np.sqrt(max(e - sidx, 1)))
            if imp_sig < imp_min_sig:
                continue
            if cnt >= cap:
                break
            row = out[cnt]
            row[:] = np.nan
            row[0] = t; row[1] = e; row[2] = side; row[3] = ex; row[4] = st; row[5] = c_mid
            row[6] = imp; row[7] = e - sidx; row[8] = t - e; row[9] = retr
            row[10] = sig; row[11] = imp_sig
            ref = sidx - 1
            row[12], _ = _std(hi, lo, ref - 900, ref)
            row[13], mu3600 = _std(hi, lo, ref - 3600, ref)
            row[14], mu14400 = _std(hi, lo, ref - 14400, ref)
            # tick activity
            ti = 0
            for k in range(sidx, e + 1):
                ti += nt[k]
            tb = 0
            for k in range(sidx - 300, sidx):
                tb += nt[k]
            row[15] = ti / (e - sidx + 1)
            row[16] = tb / 300.0
            row[17] = row[15] / max(row[16], 0.05)
            up = 0; dn = 0
            for k in range(sidx, e + 1):
                up += nup[k]; dn += ndn[k]
            row[18] = (up - dn) / max(up + dn, 1) * (-side)   # + = with the impulse
            up = 0; dn = 0
            for k in range(e + 1, t + 1):
                up += nup[k]; dn += ndn[k]
            row[19] = (up - dn) / max(up + dn, 1) * side      # + = with the reversal
            spi = 0.0
            for k in range(sidx, e + 1):
                if spmax[k] > spi: spi = spmax[k]
            spb = 0.0; nb = 0
            for k in range(sidx - 300, sidx):
                if live[k]:
                    spb += ask[k] - bid[k]; nb += 1
            spb = spb / max(nb, 1)
            row[20] = spi; row[21] = spb; row[22] = spi / max(spb, 0.01); row[23] = ask[t] - bid[t]
            # rolling structural levels, measured before the impulse (ending at sidx-1)
            for j in range(len(LEVEL_WINDOWS)):
                w = LEVEL_WINDOWS[j]
                if side == -1:
                    L = -1e18
                    for k in range(ref - w, ref):
                        if hi[k] > L: L = hi[k]
                    row[24 + j] = ex - L
                    row[30 + j] = L - c_mid
                else:
                    L = 1e18
                    for k in range(ref - w, ref):
                        if lo[k] < L: L = lo[k]
                    row[24 + j] = L - ex
                    row[30 + j] = c_mid - L
            m300 = 0.5 * (hi[ref - 300] + lo[ref - 300])
            m1800 = 0.5 * (hi[ref - 1800] + lo[ref - 1800])
            m14400 = 0.5 * (hi[ref - 14400] + lo[ref - 14400])
            mref = 0.5 * (hi[ref] + lo[ref])
            # signed so that + = trend in the direction of the impulse
            row[36] = (mref - m300) * (-side)
            row[37] = (mref - m1800) * (-side)
            row[38] = (mref - m14400) * (-side)
            row[39] = (mref - mu14400) / max(row[14], 1e-6) * (-side)
            m3600_prev = 0.0
            _, m3600_prev = _std(hi, lo, ref - 7200, ref - 3600)
            row[40] = (mu3600 - m3600_prev) * (-side)
            if side == -1:
                row[41] = ex - day_hi_prev[t]
                row[42] = np.nan
                row[43] = ex - sess_hi[sidx - 1]
            else:
                row[41] = np.nan
                row[42] = day_lo_prev[t] - ex
                row[43] = sess_lo[sidx - 1] - ex
            r10 = np.round(ex / 10.0) * 10.0
            row[44] = (ex - r10) * (-side)  # + = extreme beyond round number in impulse dir
            cnt += 1
            if side == -1:
                last_e_up = e
            else:
                last_e_dn = e
    return out[:cnt]


@njit(cache=True)
def day_levels(hi, lo, s0):
    """Previous trading day high/low (day boundary 22:00 UTC) and current-session-so-far H/L.
    Sessions (UTC): Asia 22-07, London 07-12, NY 12-22."""
    n = len(hi)
    pdh = np.full(n, np.nan); pdl = np.full(n, np.nan)
    sh = np.full(n, np.nan); sl = np.full(n, np.nan)
    cur_dh = -1e18; cur_dl = 1e18
    prev_dh = np.nan; prev_dl = np.nan
    cur_sh = -1e18; cur_sl = 1e18
    for k in range(n):
        sec = s0 + k
        hour = (sec // 3600) % 24
        new_hour = (sec % 3600) == 0
        if new_hour and hour == 22:
            if cur_dh > -1e17:
                prev_dh = cur_dh; prev_dl = cur_dl
            cur_dh = -1e18; cur_dl = 1e18
        if new_hour and (hour == 22 or hour == 7 or hour == 12):
            cur_sh = -1e18; cur_sl = 1e18
        if hi[k] > cur_dh: cur_dh = hi[k]
        if lo[k] < cur_dl: cur_dl = lo[k]
        if hi[k] > cur_sh: cur_sh = hi[k]
        if lo[k] < cur_sl: cur_sl = lo[k]
        pdh[k] = prev_dh; pdl[k] = prev_dl
        sh[k] = cur_sh; sl[k] = cur_sl
    return pdh, pdl, sh, sl


def detect(g, imp_min_usd=1.0, imp_min_sig=2.0, rho_min=0.30):
    import pandas as pd
    pdh, pdl, sh, sl = day_levels(g["hi"], g["lo"], g["s0"])
    arr = scan(g["hi"], g["lo"], g["bid"], g["ask"], g["nt"], g["nup"], g["ndn"], g["spmax"],
               g["live"], pdh, pdl, sh, sl, imp_min_usd, imp_min_sig, rho_min, 0)
    df = pd.DataFrame(arr, columns=FEATURES)
    for c in ("t", "e", "side", "imp_dur", "rej_dur"):
        df[c] = df[c].astype(np.int64)
    df["sec"] = df["t"] + g["s0"]
    dtm = pd.to_datetime(df["sec"], unit="s")
    df["time"] = dtm
    df["hour"] = dtm.dt.hour
    df["dow"] = dtm.dt.dayofweek
    return df
