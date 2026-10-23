#!/usr/bin/env python3
"""Stage G: retest limit entries and time exits, tick-level simulation (IS + VAL)."""
import os, itertools, time
import numpy as np, pandas as pd
import hfdata, simulate as S
from stage_e_rules import dedupe
from stage_f_exits import RULES

D = os.path.join(hfdata.ROOT, "data")


def run_limit(ts, bid, ask, s, k, b, a, wait_s, hold_s, f1=1.0, a2=None, be=False, cost=S.CTRADER):
    """limit at C + k*imp toward the extreme, SL = E + b*imp beyond extreme,
    TP1 = C - a*imp (reversal direction), optional TP2 = C - a2*imp with BE after TP1."""
    sd = s.side.values.astype(np.int64)
    imp = s.imp.values; C = s.C.values; E = s.E.values
    lim = C - sd * k * imp
    sl = E - sd * b * imp
    tp1 = C + sd * a * imp
    tp2 = C + sd * a2 * imp if a2 else np.full(len(s), np.nan)
    cancel = tp1
    i0 = S.entry_index(ts, s.sec.values, cost.latency_ms)
    r = S.sim_many_limit(ts, bid, ask, i0, sd, lim, cancel, wait_s * 1000, sl, tp1, f1, tp2,
                         be, 0.0, np.zeros(len(s)), hold_s * 1000, *cost.tup())
    return r


def run_time(ts, bid, ask, s, hold_s, sl_m, tp_m, cost=S.CTRADER):
    sd = s.side.values.astype(np.int64)
    imp = s.imp.values
    i0 = S.entry_index(ts, s.sec.values, cost.latency_ms)
    z = np.zeros(len(s))
    return S.sim_many(ts, bid, ask, i0, sd, sl_m * imp, tp_m * imp, 1.0, z, False, 0.0, z,
                      hold_s * 1000, *cost.tup())


def summarize(s, r, tag):
    row = dict(tag)
    for p in ("IS", "VAL"):
        m = (s.period.values == p) & ~np.isnan(r[:, 0])
        met = S.metrics(r[m, 0], risk=r[m, 1])
        row.update({f"n_{p}": met["n"], f"fill_{p}": m.sum() / max((s.period.values == p).sum(), 1),
                    f"wr_{p}": met["wr"], f"pf_{p}": met["pf"], f"avg_{p}": met["avg"],
                    f"R_{p}": met["tot"], f"ddR_{p}": met["dd"]})
    return row


def main():
    t0 = time.time()
    ts, bid, ask = hfdata.load_ticks()
    df = pd.read_pickle(os.path.join(D, "events_fwd.pkl"))
    df = df[df.period != "OOS"].sort_values("sec")
    rows = []
    for rule in ("R900", "R900b", "R1800"):
        s = dedupe(df[RULES[rule](df)])
        for hold_s, sl_m, tp_m in itertools.product((60, 120, 300, 600), (2.0, 3.0, 5.0), (1.0, 2.0, 99)):
            r = run_time(ts, bid, ask, s, hold_s, sl_m, tp_m)
            rows.append(summarize(s, r, dict(rule=rule, kind="time", hold=hold_s, sl=sl_m, tp=tp_m)))
        for k, b, a, wait_s, hold_s in itertools.product((0.1, 0.25, 0.4, 0.6), (0.1, 0.3, 0.6),
                                                          (0.3, 0.6, 1.0), (30, 120), (300, 900)):
            r = run_limit(ts, bid, ask, s, k, b, a, wait_s, hold_s)
            rows.append(summarize(s, r, dict(rule=rule, kind="limit", k=k, b=b, a=a, wait=wait_s, hold=hold_s)))
        print(rule, len(s), f"{time.time()-t0:.0f}s", flush=True)
    out = pd.DataFrame(rows)
    out.to_csv(os.path.join(D, "limit_time_grid.csv"), index=False)
    out["minpf"] = out[["pf_IS", "pf_VAL"]].min(axis=1)
    pd.set_option("display.width", 260); pd.set_option("display.max_rows", 200)
    ok = out[(out.n_IS >= 100) & (out.n_VAL >= 60)]
    print(ok.sort_values("pf_IS", ascending=False).head(30).round(2).to_string())
    print(ok.sort_values("minpf", ascending=False).head(20).round(2).to_string())


if __name__ == "__main__":
    main()
