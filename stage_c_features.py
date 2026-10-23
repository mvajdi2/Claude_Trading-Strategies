#!/usr/bin/env python3
"""Stage C: univariate feature scan.
Gross forward move (mid, reversal direction) after the entry second at several horizons.
Deciles fitted on IS; the same cut-points applied to VAL. Features where the top/bottom
decile beats cost (~$0.30) in BOTH periods are printed first.
"""
import os
import numpy as np, pandas as pd
import hfdata, events

D = os.path.join(hfdata.ROOT, "data")
H = (10, 30, 60, 120, 300, 900)


def add_forward(df, g):
    mid = 0.5 * (g["bid"] + g["ask"])
    t = df.t.values + 1          # entry second (after latency)
    sd = df.side.values
    m0 = mid[t]
    for h in H:
        df[f"fwd{h}"] = (mid[np.minimum(t + h, len(mid) - 1)] - m0) * sd
    return df


def main():
    df = pd.read_pickle(os.path.join(D, "events.pkl"))
    _, _, _, g = hfdata.load_all()
    df = add_forward(df, g)
    # derived, scale-free features
    df["imp_rel"] = df.imp / df.std900.clip(lower=0.05)
    df["imp_px"] = df.imp / df.C * 1e4                 # bp of price
    df["ret300_n"] = df.ret300 / df.std900.clip(lower=0.05)
    df["ret1800_n"] = df.ret1800 / df.std3600.clip(lower=0.05)
    df["ret14400_n"] = df.ret14400 / df.std14400.clip(lower=0.05)
    df["vol_ratio"] = df.std900 / df.std3600.clip(lower=0.05)
    df["vol_ratio2"] = df.std3600 / df.std14400.clip(lower=0.05)
    for w in (60, 300, 900, 1800, 3600, 14400):
        df[f"sw{w}_n"] = df[f"sw{w}"] / df.imp
    df["pd_sw"] = np.where(df.side == -1, df.pdh_sw, df.pdl_sw) / df.imp
    df["sess_sw_n"] = df.sess_sw / df.imp
    df["n_levels"] = sum((df[f"sw{w}"] > 0).astype(int) for w in (300, 900, 1800, 3600, 14400))
    df.to_pickle(os.path.join(D, "events_fwd.pkl"))

    feats = ["imp", "imp_rel", "imp_px", "imp_sig", "imp_dur", "rej_dur", "retrace", "tick_ratio",
             "tick_rate_imp", "imb_imp", "imb_rej", "spread_ratio", "spread_now", "std900",
             "vol_ratio", "vol_ratio2", "ret300_n", "ret1800_n", "ret14400_n", "z14400",
             "mean3600_slope", "sw60_n", "sw300_n", "sw900_n", "sw1800_n", "sw3600_n", "sw14400_n",
             "pd_sw", "sess_sw_n", "n_levels", "round_dist", "hour"]
    IS = df[df.period == "IS"]; VAL = df[df.period == "VAL"]
    rows = []
    for f in feats:
        x = IS[f].replace([np.inf, -np.inf], np.nan).dropna()
        if x.nunique() < 5:
            cuts = np.unique(x)
            binf = lambda s: s
        else:
            cuts = np.unique(np.quantile(x, np.linspace(0, 1, 11)))
            binf = lambda s, c=cuts: np.clip(np.searchsorted(c, s, side="right") - 1, 0, len(c) - 2)
        for name, part in (("IS", IS), ("VAL", VAL)):
            s = part[f].replace([np.inf, -np.inf], np.nan)
            ok = s.notna()
            b = binf(s[ok].values)
            grp = part[ok].groupby(b)
            for k, gq in grp:
                rows.append(dict(feat=f, period=name, bin=int(k), n=len(gq),
                                 lo=float(cuts[int(k)]) if len(cuts) > int(k) else np.nan,
                                 f30=gq.fwd30.mean(), f120=gq.fwd120.mean(), f300=gq.fwd300.mean(),
                                 f900=gq.fwd900.mean()))
    t = pd.DataFrame(rows)
    t.to_csv(os.path.join(D, "feature_scan.csv"), index=False)
    piv = t.pivot_table(index=["feat", "bin"], columns="period", values=["f120", "f300", "n", "lo"])
    pd.set_option("display.width", 250); pd.set_option("display.max_rows", 500)
    print(piv.round(3).to_string())


if __name__ == "__main__":
    main()
