#!/usr/bin/env python3
"""Stage E: rule grid on robust features (IS + VAL only), one trade at a time via cooldown."""
import os, itertools
import numpy as np, pandas as pd
import hfdata

D = os.path.join(hfdata.ROOT, "data")


def dedupe(s, cooldown=120):
    """keep first event, then skip events within cooldown seconds"""
    keep = []
    last = -10**12
    for i, t in zip(s.index.values, s.sec.values):
        if t - last >= cooldown:
            keep.append(i); last = t
    return s.loc[keep]


def main():
    df = pd.read_pickle(os.path.join(D, "events_fwd.pkl"))
    df = df[df.period != "OOS"].sort_values("sec")
    res = []
    grid = dict(sw=[("sw900_n", 0.0), ("sw1800_n", 0.0), ("sw1800_n", 0.3), ("sw3600_n", 0.0), ("sw3600_n", 0.3)],
                imp_rel=[0, 1.0, 1.5, 2.0, 3.0],
                spread_ratio=[0, 1.2, 1.4, 1.7],
                retrace=[0.3, 0.5],
                hours=["all", "07-20"])
    for (swf, swt), ir, sr, rt, hr in itertools.product(*grid.values()):
        m = (df[swf] > swt) & (df.imp_rel >= ir) & (df.spread_ratio >= sr) & (df.retrace >= rt)
        if hr != "all":
            m &= df.hour.between(7, 19)
        s = dedupe(df[m])
        row = dict(sw=f"{swf}>{swt}", imp_rel=ir, spread=sr, retr=rt, hours=hr)
        for p in ("IS", "VAL"):
            q = s[s.period == p]
            row[f"n_{p}"] = len(q)
            for h in (60, 120, 300, 900):
                row[f"f{h}_{p}"] = q[f"fwd{h}"].mean()
        res.append(row)
    r = pd.DataFrame(res)
    r["min300"] = r[["f300_IS", "f300_VAL"]].min(axis=1)
    r["min120"] = r[["f120_IS", "f120_VAL"]].min(axis=1)
    r.to_csv(os.path.join(D, "rule_grid.csv"), index=False)
    pd.set_option("display.width", 250)
    ok = r[(r.n_IS >= 150) & (r.n_VAL >= 80)]
    print(ok.sort_values("min300", ascending=False).head(25).round(3).to_string())
    print()
    print(ok.sort_values("min120", ascending=False).head(15).round(3).to_string())


if __name__ == "__main__":
    main()
