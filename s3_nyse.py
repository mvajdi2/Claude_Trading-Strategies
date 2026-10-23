#!/usr/bin/env python3
"""Study 2, step 3: NYSE-open first-minute momentum at tick level.

Signal: at T+d (T = 09:30:00 America/New_York), direction = sign(mid[T+d] - mid[T]);
trade only if |move| >= thr * atr1h. Market entry after latency.
Exits: SL = sl_k * atr1h, TP = tp_k * atr1h (0 = none), time exit hold_s.
Selection on IS, VAL alongside, OOS only via --oos once frozen.
"""
import os, sys, itertools
import numpy as np, pandas as pd
import hfdata, simulate as S

D = os.path.join(hfdata.ROOT, "data")


def build(anchor="nyse_0930"):
    a = pd.read_pickle(os.path.join(D, "anchors.pkl"))
    a = a[a.anchor == anchor].reset_index(drop=True)
    z = np.load(hfdata.CACHE)
    mid = 0.5 * (z["bid"] + z["ask"])
    for d in (30, 60, 90, 120):
        a[f"mv{d}"] = mid[a.k.values + d] - mid[a.k.values]
    a["rng60"] = [z["hi"][k:k + 60].max() - z["lo"][k:k + 60].min() for k in a.k.values]
    return a


def run(ts, bid, ask, a, d, thr, sl_k, tp_k, hold_s, cost=S.CTRADER, periods=("IS", "VAL")):
    mv = a[f"mv{d}"].values
    ok = (np.abs(mv) >= thr * a.atr1h.values) & (mv != 0) & a.period.isin(periods).values
    s = a[ok]
    sd = np.sign(mv[ok]).astype(np.int64)
    i0 = S.entry_index(ts, s.sec.values + d - 1, cost.latency_ms)
    atr = s.atr1h.values
    tp = tp_k * atr if tp_k > 0 else np.full(len(s), 1e6)
    z0 = np.zeros(len(s))
    r = S.sim_many(ts, bid, ask, i0, sd, sl_k * atr, tp, 1.0, z0, False, 0.0, z0, hold_s * 1000, *cost.tup())
    return s, r


def stats(s, r, periods):
    out = {}
    for p in periods:
        m = s.period.values == p
        x = r[m]
        R = x[:, 0] / x[:, 1]
        if len(R) == 0:
            continue
        eq = np.cumsum(R); dd = np.max(np.maximum.accumulate(np.r_[0, eq])[1:] - eq)
        out.update({f"n_{p}": len(R), f"wr_{p}": (R > 0).mean() * 100,
                    f"pfR_{p}": R[R > 0].sum() / max(-R[R <= 0].sum(), 1e-9),
                    f"expR_{p}": R.mean(), f"ddR_{p}": dd, f"avg$_{p}": x[:, 0].mean()})
    return out


def main():
    ts, bid, ask = hfdata.load_ticks()
    a = build()
    a.to_pickle(os.path.join(D, "nyse_days.pkl"))
    rows = []
    for d, thr, sl_k, tp_k, hold_s in itertools.product((30, 60, 90, 120), (0.0, 0.15, 0.25, 0.4),
                                                        (0.5, 1.0, 1.5, 2.5), (0, 1.0, 2.0, 3.0),
                                                        (900, 1800, 3600, 7200)):
        s, r = run(ts, bid, ask, a, d, thr, sl_k, tp_k, hold_s)
        row = dict(d=d, thr=thr, sl=sl_k, tp=tp_k, hold=hold_s)
        row.update(stats(s, r, ("IS", "VAL")))
        rows.append(row)
    t = pd.DataFrame(rows)
    t.to_csv(os.path.join(D, "nyse_grid.csv"), index=False)
    pd.set_option("display.width", 250); pd.set_option("display.max_rows", 200)
    print(t.sort_values("pfR_IS", ascending=False).head(25).round(2).to_string())
    print("\nmedian over the whole grid by decision delay / threshold (robustness):")
    print(t.groupby(["d", "thr"])[["pfR_IS", "pfR_VAL", "expR_IS", "expR_VAL"]].median().round(2).to_string())


if __name__ == "__main__":
    main()
