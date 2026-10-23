#!/usr/bin/env python3
"""Stage H: trade-management grid (partial TP, break-even, trailing, time stop) at tick level.
Selection on IS; VAL shown alongside. Produces the WR / PF / frequency / DD trade-off table."""
import os, itertools, time
import numpy as np, pandas as pd
import hfdata, simulate as S
from stage_e_rules import dedupe
from stage_f_exits import RULES

D = os.path.join(hfdata.ROOT, "data")


def sim(ts, bid, ask, s, sl_m, tp1_m, f1, tp2_m, be, trail_m, hold_s, cost=S.CTRADER):
    sd = s.side.values.astype(np.int64)
    imp = s.imp.values
    i0 = S.entry_index(ts, s.sec.values, cost.latency_ms)
    tp2 = tp2_m * imp if tp2_m > 0 else np.zeros(len(s))
    return S.sim_many(ts, bid, ask, i0, sd, sl_m * imp, tp1_m * imp, f1, tp2, be, 0.0,
                      trail_m * imp, hold_s * 1000, *cost.tup())


def stats(s, r, periods=("IS", "VAL")):
    out = {}
    for p in periods:
        m = s.period.values == p
        x = r[m]
        met = S.metrics(x[:, 0], risk=x[:, 1])
        weeks = max((s.time[m].max() - s.time[m].min()).days / 7, 1) if m.any() else 1
        out.update({f"n_{p}": met["n"], f"pw_{p}": met["n"] / weeks, f"wr_{p}": met["wr"],
                    f"pf_{p}": met["pf"], f"avg_{p}": met["avg"], f"R_{p}": met["tot"], f"ddR_{p}": met["dd"]})
    return out


def main():
    t0 = time.time()
    ts, bid, ask = hfdata.load_ticks()
    df = pd.read_pickle(os.path.join(D, "events_fwd.pkl"))
    df = df[df.period != "OOS"].sort_values("sec")
    rows = []
    for rule in ("R900b", "R1800", "R900"):
        s = dedupe(df[RULES[rule](df)])
        for sl_m, tp1_m, f1, tp2_m, be, trail_m, hold_s in itertools.product(
                (1.5, 2.0, 3.0, 4.0), (0.25, 0.4, 0.6, 1.0), (1.0, 0.5, 0.7), (0, 1.5, 2.5),
                (False, True), (0.0, 0.75), (300, 900)):
            if f1 == 1.0 and (tp2_m > 0 or be or trail_m > 0):
                continue
            if f1 < 1.0 and tp2_m == 0 and trail_m == 0:
                continue
            r = sim(ts, bid, ask, s, sl_m, tp1_m, f1, tp2_m, be, trail_m, hold_s)
            row = dict(rule=rule, sl=sl_m, tp1=tp1_m, f1=f1, tp2=tp2_m, be=be, trail=trail_m, hold=hold_s)
            row.update(stats(s, r))
            rows.append(row)
        print(rule, len(s), len(rows), f"{time.time()-t0:.0f}s", flush=True)
    out = pd.DataFrame(rows)
    out.to_csv(os.path.join(D, "mgmt_grid.csv"), index=False)


if __name__ == "__main__":
    main()
