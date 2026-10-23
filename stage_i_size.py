#!/usr/bin/env python3
"""Stage I: R-normalised (fixed-fractional) evaluation; minimum impulse size in USD / bp."""
import os, itertools
import numpy as np, pandas as pd
import hfdata, simulate as S
from stage_e_rules import dedupe
from stage_h_mgmt import sim

D = os.path.join(hfdata.ROOT, "data")


def rstats(s, r, periods=("IS", "VAL")):
    out = {}
    for p in periods:
        m = s.period.values == p
        x = r[m]
        if len(x) == 0:
            out.update({f"n_{p}": 0}); continue
        R = x[:, 0] / x[:, 1]
        w = R[R > 0].sum(); l = -R[R <= 0].sum()
        eq = np.cumsum(R); dd = np.max(np.maximum.accumulate(np.r_[0, eq])[1:] - eq)
        weeks = max((s.time[m].max() - s.time[m].min()).days / 7, 1)
        out.update({f"n_{p}": len(R), f"pw_{p}": len(R) / weeks, f"wr_{p}": (R > 0).mean() * 100,
                    f"pfR_{p}": w / l if l > 0 else np.inf, f"expR_{p}": R.mean(), f"ddR_{p}": dd,
                    f"pf$_{p}": x[x[:, 0] > 0, 0].sum() / max(-x[x[:, 0] <= 0, 0].sum(), 1e-9)})
    return out


BASES = {
    "sw900":  lambda d: (d.sw900_n > 0),
    "sw1800": lambda d: (d.sw1800_n > 0.3),
    "sw3600": lambda d: (d.sw3600_n > 0),
    "any":    lambda d: (d.sw300_n > 0),
}
EXITS = {
    "scalp_be":  (3.0, 0.25, 0.7, 2.5, True, 0.0, 900),
    "tp04_sl3":  (3.0, 0.4, 1.0, 0, False, 0.0, 900),
    "half_run":  (2.0, 0.5, 0.5, 2.0, True, 0.0, 900),
    "tp1_sl15":  (1.5, 1.0, 1.0, 0, False, 0.0, 900),
    "time300":   (3.0, 99, 1.0, 0, False, 0.0, 300),
}


def main():
    ts, bid, ask = hfdata.load_ticks()
    df = pd.read_pickle(os.path.join(D, "events_fwd.pkl"))
    df = df[df.period != "OOS"].sort_values("sec")
    rows = []
    for (bn, bf), imin, sr, hrs in itertools.product(BASES.items(), (2.0, 3.0, 4.0, 5.0), (0, 1.3), ("all", "07-20")):
        m = bf(df) & (df.imp >= imin) & (df.spread_ratio >= sr)
        if hrs != "all":
            m &= df.hour.between(7, 19)
        s = dedupe(df[m])
        if len(s) < 60:
            continue
        for en, ep in EXITS.items():
            r = sim(ts, bid, ask, s, *ep)
            row = dict(base=bn, imin=imin, spread=sr, hours=hrs, exit=en)
            row.update(rstats(s, r))
            rows.append(row)
    out = pd.DataFrame(rows)
    out["minpfR"] = out[["pfR_IS", "pfR_VAL"]].min(axis=1)
    out.to_csv(os.path.join(D, "size_grid.csv"), index=False)
    pd.set_option("display.width", 260); pd.set_option("display.max_rows", 100)
    print(out[out.n_IS >= 80].sort_values("pfR_IS", ascending=False).head(30).round(2).to_string())


if __name__ == "__main__":
    main()
