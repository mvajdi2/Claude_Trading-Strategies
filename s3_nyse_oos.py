#!/usr/bin/env python3
"""Frozen NYSE-open momentum (frozen 2026-10-23 before OOS): d=60s, thr=0.25*atr1h,
SL=2.5*atr1h, TP=1.0*atr1h, time exit 1800s. Single OOS run + stress tests."""
import os
import numpy as np, pandas as pd
import hfdata, simulate as S
from s3_nyse import run, stats

D = os.path.join(hfdata.ROOT, "data")
FROZEN = dict(d=60, thr=0.25, sl_k=2.5, tp_k=1.0, hold_s=1800)
P = ("IS", "VAL", "OOS")

ts, bid, ask = hfdata.load_ticks()
a = pd.read_pickle(os.path.join(D, "nyse_days.pkl"))
res = {}
for name, c in {"base": S.CTRADER, "latency 500ms": S.Cost(latency_ms=500),
                "spread x1.5 + slip 0.10": S.Cost(sp_k=0.45, sp_min=0.15, slip=0.10),
                "raw Dukascopy": S.RAW_DUKA}.items():
    s, r = run(ts, bid, ask, a, cost=c, periods=P, **FROZEN)
    res[name] = stats(s, r, P)
    if name == "base":
        tr = s.assign(dir=np.sign(s.mv60), pnl_oz=r[:, 0], R=r[:, 0] / r[:, 1], code=r[:, 2], hold_s=r[:, 3] / 1000)
        tr.to_csv(os.path.join(D, "nyse_frozen_trades.csv"), index=False)
pd.set_option("display.width", 250)
print(pd.DataFrame(res).T.round(2).to_string())
m = tr.assign(month=pd.to_datetime(tr.date).dt.to_period("M")).groupby("month").agg(n=("R", "size"), sumR=("R", "sum"), wr=("R", lambda x: (x > 0).mean() * 100))
print(m.round(2).to_string())
print("long/short split:", tr.groupby(["period", "dir"]).R.agg(["size", "mean"]).round(3).to_string())
