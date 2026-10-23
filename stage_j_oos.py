#!/usr/bin/env python3
"""Stage J: single blind OOS run of the frozen strategy + stress tests + monthly walk-forward table."""
import os, json
import numpy as np, pandas as pd
import hfdata, simulate as S, strategy as ST
from stage_e_rules import dedupe
from stage_h_mgmt import sim
from stage_i_size import rstats

D = os.path.join(hfdata.ROOT, "data")


def run(ts, bid, ask, s, cost):
    e = ST.EXIT
    return sim(ts, bid, ask, s, e["sl_m"], e["tp1_m"], e["f1"], e["tp2_m"], e["be"], e["trail_m"], e["hold_s"], cost)


def main():
    ts, bid, ask = hfdata.load_ticks()
    df = pd.read_pickle(os.path.join(D, "events_fwd.pkl")).sort_values("sec")
    s = dedupe(df[ST.signal_mask(df)], ST.COOLDOWN_S)
    per = ("IS", "VAL", "OOS")
    scen = {
        "base (cTrader cost, 120ms)": S.CTRADER,
        "latency 250ms": S.Cost(latency_ms=250),
        "latency 50ms": S.Cost(latency_ms=50),
        "spread x1.5 + slip 0.06": S.Cost(sp_k=0.45, sp_min=0.15, slip=0.06),
        "raw Dukascopy quotes": S.RAW_DUKA,
    }
    res = {}
    trades = None
    for name, c in scen.items():
        r = run(ts, bid, ask, s, c)
        res[name] = rstats(s, r, per)
        if trades is None:
            trades = s.assign(pnl_oz=r[:, 0], risk_oz=r[:, 1], R=r[:, 0] / r[:, 1], code=r[:, 2],
                              hold_s=r[:, 3] / 1000, mfe=r[:, 4], mae=r[:, 5])
    t = pd.DataFrame(res).T
    pd.set_option("display.width", 260)
    print(t.round(2).to_string())
    trades.to_csv(os.path.join(D, "frozen_trades.csv"), index=False)
    m = trades.assign(month=trades.time.dt.to_period("M")).groupby("month").agg(
        n=("R", "size"), wr=("R", lambda x: (x > 0).mean() * 100), sumR=("R", "sum"),
        pf=("R", lambda x: x[x > 0].sum() / max(-x[x <= 0].sum(), 1e-9)))
    print(m.round(2).to_string())
    json.dump({k: {kk: float(vv) for kk, vv in v.items()} for k, v in res.items()},
              open(os.path.join(D, "frozen_results.json"), "w"), indent=1)


if __name__ == "__main__":
    main()
