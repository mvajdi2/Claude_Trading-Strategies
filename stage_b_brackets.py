#!/usr/bin/env python3
"""Stage B: bracket families on all candidate events, per period.

Family F (fixed USD), family X (stop beyond spike extreme, target as fraction of impulse).
Prints the WR / PF / avg per period so the trade-off is visible before any filtering.
"""
import os, sys
import numpy as np, pandas as pd
import hfdata, labels, simulate as S

D = os.path.join(hfdata.ROOT, "data")


def load():
    df = pd.read_pickle(os.path.join(D, "events.pkl"))
    z = np.load(os.path.join(D, "fp.npz"))
    return df, z["fav"], z["adv"]


def summarize(pnl, periods):
    rows = {}
    for p in ("IS", "VAL", "OOS"):
        x = pnl[(periods == p) & ~np.isnan(pnl)]
        m = S.metrics(x)
        rows[p] = f"n={m['n']:5d} WR={m['wr']:5.1f} PF={m['pf']:5.2f} avg={m['avg']:+.3f}"
    return rows


def bracket_tables(df, fav, adv, mask=None, title=""):
    c = S.CTRADER
    if mask is None:
        mask = np.ones(len(df), bool)
    d = df[mask]; f = fav[mask]; a = adv[mask]
    per = d.period.values
    print(f"\n=== {title}  ({len(d)} events) ===")
    print("-- fixed USD brackets --")
    for tp in (0.5, 1.0, 1.5, 2.0, 3.0):
        for sl in (1.0, 2.0, 3.0, 5.0):
            r = summarize(labels.bracket(f, a, tp, sl, c), per)
            print(f"TP {tp:>4} SL {sl:>4} | " + " | ".join(f"{k}: {v}" for k, v in r.items()))
    print("-- stop beyond spike extreme (+b*imp), target a*imp --")
    for aa in (0.3, 0.5, 0.75, 1.0):
        for bb in (0.1, 0.3, 0.6):
            sl = np.maximum(d.dist_ext.values + bb * d.imp.values, 0.2)
            tp = np.maximum(aa * d.imp.values, 0.1)
            r = summarize(labels.bracket(f, a, tp, sl, c), per)
            print(f"a {aa:>4} b {bb:>4} | " + " | ".join(f"{k}: {v}" for k, v in r.items()))


if __name__ == "__main__":
    df, fav, adv = load()
    bracket_tables(df, fav, adv, title="ALL candidates")
