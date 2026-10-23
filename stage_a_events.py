#!/usr/bin/env python3
"""Stage A: detect all candidate sub-5s impulse/rejection events on the full tick set and
attach first-passage labels for market entry (latency 120 ms, cTrader cost model).

Outputs data/events.pkl (features) and data/fp.npz (first-passage matrices).
"""
import os, time
import numpy as np, pandas as pd
import hfdata, events, labels, simulate as S

OUT = os.path.join(hfdata.ROOT, "data")
LAT_MS = 120
HORIZON_MS = 1800_000

IS_END = pd.Timestamp("2026-01-01")
VAL_END = pd.Timestamp("2026-06-01")


def period(t):
    return np.where(t < IS_END, "IS", np.where(t < VAL_END, "VAL", "OOS"))


def main():
    t0 = time.time()
    ts, bid, ask, g = hfdata.load_all()
    print(f"ticks {len(ts):,}  grid {len(g['hi']):,}s  load {time.time()-t0:.0f}s", flush=True)
    df = events.detect(g, imp_min_usd=1.0, imp_min_sig=2.5, rho_min=0.30)
    df = df[(df.spread_base > 0) & (df.tick_rate_base > 0.2)].reset_index(drop=True)
    df["period"] = period(df.time)
    print(f"events {len(df):,}  detect {time.time()-t0:.0f}s", flush=True)
    print(df.groupby("period").size(), flush=True)

    c = S.CTRADER
    i0 = S.entry_index(ts, df.sec.values, LAT_MS)
    ok = i0 < len(ts) - 1
    df = df[ok].reset_index(drop=True); i0 = i0[ok]
    sides = df.side.values.astype(np.int64)
    e_px = labels.market_entry_px(bid, ask, i0, sides, c)
    df["i0"] = i0
    df["entry_px"] = e_px
    df["entry_lag_ms"] = ts[i0] - (df.sec.values + 1) * 1000
    # distance from entry to the spike extreme (natural invalidation)
    df["dist_ext"] = (df.E.values - e_px) * (-sides)   # >0: extreme is beyond entry on the stop side
    fav, adv = labels.first_passage(ts, bid, ask, i0, sides, e_px, HORIZON_MS, labels.GRID, c.sp_k, c.sp_min)
    print(f"first passage done {time.time()-t0:.0f}s", flush=True)
    df.to_pickle(os.path.join(OUT, "events.pkl"))
    np.savez_compressed(os.path.join(OUT, "fp.npz"), fav=fav, adv=adv)
    print("saved", flush=True)


if __name__ == "__main__":
    main()
