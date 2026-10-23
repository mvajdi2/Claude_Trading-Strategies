#!/usr/bin/env python3
"""Stage D: gradient-boosted model of gross forward reversal move.
Train on IS (2025) with monthly-blocked CV for early stopping; score VAL (Jan-May 2026).
OOS is NOT touched here.
"""
import os, json
import numpy as np, pandas as pd, lightgbm as lgb
import hfdata

D = os.path.join(hfdata.ROOT, "data")
FEATS = ["imp_rel", "imp_px", "imp_sig", "imp_dur", "rej_dur", "retrace", "tick_ratio",
         "tick_rate_imp", "imb_imp", "imb_rej", "spread_ratio", "vol_ratio", "vol_ratio2",
         "ret300_n", "ret1800_n", "ret14400_n", "z14400", "sw60_n", "sw300_n", "sw900_n",
         "sw1800_n", "sw3600_n", "sw14400_n", "pd_sw", "sess_sw_n", "n_levels", "hour",
         "bk300_n", "bk900_n", "std900_px"]
TARGET = os.environ.get("TARGET", "fwd300")


def prep(df):
    df = df.copy()
    df["bk300_n"] = df.bk300 / df.imp
    df["bk900_n"] = df.bk900 / df.imp
    df["std900_px"] = df.std900 / df.C * 1e4
    for c in FEATS:
        df[c] = df[c].replace([np.inf, -np.inf], np.nan).astype(float)
    return df


def main():
    df = prep(pd.read_pickle(os.path.join(D, "events_fwd.pkl")))
    IS = df[df.period == "IS"]; VAL = df[df.period == "VAL"]
    y = IS[TARGET].clip(-15, 15)
    params = dict(objective="huber", alpha=2.0, learning_rate=0.03, num_leaves=15,
                  min_data_in_leaf=400, feature_fraction=0.7, bagging_fraction=0.7,
                  bagging_freq=1, lambda_l2=10.0, verbose=-1, seed=7)
    # monthly blocked CV inside IS for the number of rounds
    months = IS.time.dt.month.values
    folds = [(np.where(months % 4 != k)[0], np.where(months % 4 == k)[0]) for k in range(4)]
    cv = lgb.cv(params, lgb.Dataset(IS[FEATS], y), num_boost_round=1500, folds=folds,
                stratified=False, callbacks=[lgb.early_stopping(100, verbose=False)])
    nround = len(next(iter(cv.values())))
    model = lgb.train(params, lgb.Dataset(IS[FEATS], y), num_boost_round=nround)
    model.save_model(os.path.join(D, f"lgb_{TARGET}.txt"))
    df["score"] = model.predict(df[FEATS])
    df[["score"]].to_pickle(os.path.join(D, f"scores_{TARGET}.pkl"))
    print("rounds", nround)
    imp = pd.Series(model.feature_importance("gain"), index=FEATS).sort_values(ascending=False)
    print((imp / imp.sum()).round(3).head(15).to_string())
    # deciles by IS score cut-points
    cuts = np.quantile(df.loc[df.period == "IS", "score"], [0.5, 0.8, 0.9, 0.95, 0.98, 0.99, 0.995])
    print("\nscore threshold -> mean gross forward move (IS | VAL)")
    for q, c in zip([50, 80, 90, 95, 98, 99, 99.5], cuts):
        row = []
        for p in ("IS", "VAL"):
            s = df[(df.period == p) & (df.score >= c)]
            row.append(f"{p}: n={len(s):5d} f60={s.fwd60.mean():+.3f} f120={s.fwd120.mean():+.3f} "
                       f"f300={s.fwd300.mean():+.3f} f900={s.fwd900.mean():+.3f}")
        print(f"top {100-q:>4}% (>= {c:+.3f}) | " + " | ".join(row))
    json.dump(dict(cuts=cuts.tolist(), nround=nround), open(os.path.join(D, f"lgb_{TARGET}.json"), "w"))


if __name__ == "__main__":
    main()
