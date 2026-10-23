#!/usr/bin/env python3
"""Stage F: exit grid for candidate rule sets (IS for selection, VAL for confirmation).
Static brackets via first-passage matrices, units relative to the impulse size.
"""
import os, itertools
import numpy as np, pandas as pd
import hfdata, labels, simulate as S
from stage_e_rules import dedupe

D = os.path.join(hfdata.ROOT, "data")

RULES = {
    "R900":  lambda d: (d.sw900_n > 0) & (d.imp_rel >= 1.5) & (d.spread_ratio >= 1.4) & d.hour.between(7, 19),
    "R900b": lambda d: (d.sw900_n > 0) & (d.imp_rel >= 2.0) & (d.spread_ratio >= 1.4) & d.hour.between(7, 19),
    "R1800": lambda d: (d.sw1800_n > 0.3) & (d.imp_rel >= 1.5) & (d.spread_ratio >= 1.4) & d.hour.between(7, 19),
    "R3600": lambda d: (d.sw3600_n > 0) & (d.imp_rel >= 1.5) & (d.spread_ratio >= 1.4),
    "Rwide": lambda d: (d.sw900_n > 0) & (d.imp_rel >= 1.0) & (d.spread_ratio >= 1.2) & d.hour.between(7, 19),
}


def load():
    df = pd.read_pickle(os.path.join(D, "events_fwd.pkl"))
    z = np.load(os.path.join(D, "fp.npz"))
    return df, z["fav"], z["adv"]


def evaluate(df, fav, adv, rule, periods=("IS", "VAL")):
    c = S.CTRADER
    s = dedupe(df[RULES[rule](df) & df.period.isin(periods)].sort_values("sec"))
    idx = s.index.values
    f, a = fav[idx], adv[idx]
    imp = s.imp.values; de = np.maximum(s.dist_ext.values, 0)
    out = []
    for tpm, slm, slmode in itertools.product((0.25, 0.4, 0.6, 0.8, 1.0, 1.5),
                                               (0.5, 0.75, 1.0, 1.5, 2.0, 3.0),
                                               ("imp", "ext")):
        tp = np.maximum(tpm * imp, 0.1)
        sl = np.maximum(slm * imp if slmode == "imp" else de + (slm - 0.5) * imp, 0.2)
        pnl = labels.bracket(f, a, tp, sl, c)
        row = dict(rule=rule, tp=tpm, sl=slm, mode=slmode)
        for p in periods:
            m = (s.period.values == p) & ~np.isnan(pnl)
            x = pnl[m]
            met = S.metrics(x, risk=sl[m] + c.slip + c.comm)
            row.update({f"n_{p}": met["n"], f"wr_{p}": met["wr"], f"pf_{p}": met["pf"],
                        f"avg_{p}": met["avg"], f"R_{p}": met["tot"], f"ddR_{p}": met["dd"]})
        out.append(row)
    return pd.DataFrame(out)


if __name__ == "__main__":
    df, fav, adv = load()
    pd.set_option("display.width", 250); pd.set_option("display.max_rows", 200)
    allr = []
    for r in RULES:
        t = evaluate(df, fav, adv, r)
        allr.append(t)
        t["minpf"] = t[["pf_IS", "pf_VAL"]].min(axis=1)
        print(f"\n##### {r}")
        print(t.sort_values("pf_IS", ascending=False).head(8).round(2).to_string())
    pd.concat(allr).to_csv(os.path.join(D, "exit_grid.csv"), index=False)
