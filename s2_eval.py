#!/usr/bin/env python3
"""Study 2, step 2: grid of simple anchor strategies on per-day snapshots.

Families (decision only uses prices known at the decision time):
  MOM   : at T+m go WITH the move from T to T+m, exit at T+e
  FADE  : at T+m go AGAINST that move, exit at T+e
  PREC  : at T go WITH the run-up from T-p to T, exit at T+e
  PRER  : at T go AGAINST that run-up, exit at T+e
A move filter |move| >= thr * atr1h selects only decisive days.
Net PnL per oz = gross - cost, cost = 0.30 + 0.3 * max(spread_at_T - 0.5, 0).
"""
import os, itertools
import numpy as np, pandas as pd
import hfdata

D = os.path.join(hfdata.ROOT, "data")
EXITS = [300, 600, 900, 1800, 3600, 7200, 14400]


def tstat(x):
    return x.mean() / (x.std(ddof=1) / np.sqrt(len(x))) if len(x) > 2 and x.std() > 0 else 0.0


def main():
    a = pd.read_pickle(os.path.join(D, "anchors.pkl"))
    a["cost"] = 0.30 + 0.3 * np.maximum(a.spread0 - 0.5, 0)
    rows = []
    for anc, g in a.groupby("anchor"):
        for fam in ("MOM", "FADE", "PREC", "PRER"):
            decs = (60, 300, 900) if fam in ("MOM", "FADE") else (-300, -900, -1800, -3600, -7200)
            for dm, ex, thr in itertools.product(decs, EXITS, (0.0, 0.25, 0.5, 1.0)):
                if fam in ("MOM", "FADE"):
                    if ex <= dm:
                        continue
                    move = g[f"m{dm}"] - g["m0"]
                    entry = g[f"m{dm}"]
                else:
                    move = g["m0"] - g[f"m{dm}"]
                    entry = g["m0"]
                sgn = np.sign(move) * (1 if fam in ("MOM", "PREC") else -1)
                ok = (np.abs(move) >= thr * g.atr1h) & (sgn != 0)
                pnl = (sgn * (g[f"m{ex}"] - entry) - g.cost)[ok]
                per = g.period[ok]
                row = dict(anchor=anc, fam=fam, dec=dm, exit=ex, thr=thr)
                for p in ("IS", "VAL"):
                    x = pnl[per == p].values
                    row[f"n_{p}"] = len(x)
                    row[f"avg_{p}"] = x.mean() if len(x) else np.nan
                    row[f"wr_{p}"] = (x > 0).mean() * 100 if len(x) else np.nan
                    row[f"pf_{p}"] = x[x > 0].sum() / max(-x[x <= 0].sum(), 1e-9) if len(x) else np.nan
                    row[f"t_{p}"] = tstat(x)
                rows.append(row)
    r = pd.DataFrame(rows)
    r.to_csv(os.path.join(D, "s2_grid.csv"), index=False)
    print("tests:", len(r))
    pd.set_option("display.width", 250); pd.set_option("display.max_rows", 200)
    sel = r[(r.n_IS >= 40) & (r.n_VAL >= 20) & (r.t_IS > 2.0) & (r.pf_VAL > 1.2) & (r.avg_VAL > 0)]
    print(f"IS t>2 and VAL PF>1.2: {len(sel)}  (expected false positives at t>2 one-sided ~2.3% of tests -> {0.023*len(r):.0f})")
    print(sel.sort_values("t_IS", ascending=False).round(2).to_string())


if __name__ == "__main__":
    main()
