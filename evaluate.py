#!/usr/bin/env python3
"""Evaluation harness: screen -> optimise (IS) -> confirm (VAL) -> freeze -> single OOS + stress.

The protocol is enforced in code:
  * screen() and optimise() never simulate signals dated on/after VAL_END (OOS is invisible).
  * oos() refuses to run unless strategy_cards/<id>.frozen.json exists, and records that it ran;
    a second OOS run for the same frozen hash is refused.

Strategy modules live in strategies/<id>.py and expose
    signals(ctx, **params) -> DataFrame with bt1s SIGNAL COLUMNS, plus optional `unit` (USD)
    PARAMS = {name: [grid values]}         # first value = published default
    EXIT_UNIT = True/False                 # True: exits are re-built from `unit` by exit templates

CLI
    python3 evaluate.py screen   <id>
    python3 evaluate.py optimise <id> [--max 300]
    python3 evaluate.py freeze   <id> '<json params>'
    python3 evaluate.py oos      <id>
"""
import os, sys, json, hashlib, itertools, importlib, time
import numpy as np, pandas as pd
import bt1s

ROOT = os.path.dirname(os.path.abspath(__file__))
CARDS = os.path.join(ROOT, "strategy_cards")
RESULTS = os.path.join(ROOT, "results")
os.makedirs(CARDS, exist_ok=True); os.makedirs(RESULTS, exist_ok=True)
VAL_END_SEC = int(bt1s.VAL_END.timestamp())

# exit templates applied when a strategy provides `unit` (risk unit in USD, e.g. ATR or range)
EXIT_TEMPLATES = {
    "fixed":     [dict(sl=a, tp=b) for a in (0.5, 1.0, 1.5, 2.0) for b in (0.5, 1.0, 1.5, 2.0, 3.0)],
    "scalp_be":  [dict(sl=a, tp1=b, f1=f, tp=c, be=1) for a in (1.0, 2.0, 3.0) for b in (0.25, 0.5)
                  for f in (0.5, 0.7) for c in (1.5, 3.0)],
    "trail":     [dict(sl=a, trail=t, tp=0) for a in (0.5, 1.0, 2.0) for t in (0.5, 1.0, 1.5)],
}

_CTX = None


def ctx():
    global _CTX
    if _CTX is None:
        _CTX = bt1s.Context.load()
    return _CTX


def load_strategy(sid):
    return importlib.import_module(f"strategies.{sid}")


def apply_exit(sig, tpl):
    s = sig.copy()
    u = s["unit"].values
    for c in ("tp1", "f1", "be", "be_off", "trail"):
        s[c] = 0.0
    for k, v in tpl.items():
        s[k] = v * u if k in ("sl", "tp", "tp1", "trail", "be_off") else v
    s["sl"] = np.maximum(s["sl"], 0.15)
    return s


def visible(sig):
    return sig[sig.sec < VAL_END_SEC]


def summarize(tr, periods=("IS", "VAL")):
    out = {}
    for p in periods:
        m = bt1s.metrics(tr[tr.period == p]) if len(tr) else {"n": 0}
        for k, v in m.items():
            out[f"{k}_{p}"] = v
    return out


def screen(sid):
    mod = load_strategy(sid)
    params = {k: v[0] for k, v in mod.PARAMS.items()}
    sig = visible(mod.signals(ctx(), **params))
    tr = bt1s.run(ctx(), sig)
    rep = bt1s.report(tr, ("IS", "VAL"))
    print(f"[screen] {sid} defaults={params}\n{rep.round(2).to_string()}")
    return rep


def optimise(sid, max_combos=300, objective="pfR_IS", min_n_is=60):
    mod = load_strategy(sid)
    keys = list(mod.PARAMS)
    combos = list(itertools.product(*[mod.PARAMS[k] for k in keys]))
    exit_mode = getattr(mod, "EXIT_UNIT", False)
    exits = [None]
    if exit_mode:
        exits = [(n, t) for n, ts in EXIT_TEMPLATES.items() for t in ts]
    total = len(combos) * len(exits)
    rng = np.random.default_rng(0)
    if total > max_combos:
        pick = rng.choice(total, max_combos, replace=False)
    else:
        pick = np.arange(total)
    rows = []
    cache = {}
    t0 = time.time()
    for idx in pick:
        ci, ei = divmod(int(idx), len(exits))
        p = dict(zip(keys, combos[ci]))
        key = tuple(combos[ci])
        if key not in cache:
            cache[key] = visible(mod.signals(ctx(), **p))
        sig = cache[key]
        ex = exits[ei]
        if ex is not None:
            if len(sig) == 0:
                continue
            sig = apply_exit(sig, ex[1])
        tr = bt1s.run(ctx(), sig)
        row = dict(p); row["exit"] = json.dumps(ex[1]) if ex else ""
        row["exit_kind"] = ex[0] if ex else ""
        row.update(summarize(tr))
        rows.append(row)
    res = pd.DataFrame(rows)
    res.to_csv(os.path.join(RESULTS, f"{sid}_opt.csv"), index=False)
    ok = res[res.get("n_IS", 0) >= min_n_is] if "n_IS" in res else res.iloc[0:0]
    print(f"[optimise] {sid}: {len(res)} combos tested ({time.time()-t0:.0f}s); {len(ok)} with n_IS >= {min_n_is}")
    if len(ok):
        cols = keys + ["exit", "n_IS", "wr_IS", "pf_IS", "pfR_IS", "dd_pct_IS", "per_wk_IS",
                       "n_VAL", "wr_VAL", "pf_VAL", "pfR_VAL", "dd_pct_VAL"]
        pd.set_option("display.width", 260); pd.set_option("display.max_colwidth", 60)
        print(ok.sort_values(objective, ascending=False)[cols].head(15).round(2).to_string())
        gate = ok[(ok.wr_IS > 75) & (ok.pf_IS > 3) & (ok.dd_pct_IS < 5)]
        print(f"IS gate passers: {len(gate)}; of those also passing on VAL: "
              f"{len(gate[(gate.wr_VAL > 75) & (gate.pf_VAL > 3) & (gate.dd_pct_VAL < 5)])}")
    return res


def robustness(sid, params, exit_tpl=None):
    """median IS PF over the +-1-step neighbourhood of each parameter"""
    mod = load_strategy(sid)
    pfs = []
    for k, grid in mod.PARAMS.items():
        if params[k] not in grid:
            continue
        i = grid.index(params[k])
        for j in (i - 1, i + 1):
            if 0 <= j < len(grid):
                q = dict(params); q[k] = grid[j]
                sig = visible(mod.signals(ctx(), **q))
                if exit_tpl:
                    sig = apply_exit(sig, exit_tpl)
                tr = bt1s.run(ctx(), sig)
                m = bt1s.metrics(tr[tr.period == "IS"])
                pfs.append(m.get("pf", np.nan))
    return float(np.nanmedian(pfs)) if pfs else np.nan, pfs


def frozen_path(sid):
    return os.path.join(CARDS, f"{sid}.frozen.json")


def freeze(sid, params, exit_tpl=None, note=""):
    src = open(os.path.join(ROOT, "strategies", f"{sid}.py")).read()
    rec = dict(id=sid, params=params, exit=exit_tpl, note=note,
               code_sha=hashlib.sha256(src.encode()).hexdigest()[:16],
               frozen_at=pd.Timestamp.utcnow().isoformat(), oos_run=False)
    med, pfs = robustness(sid, params, exit_tpl)
    rec["robust_median_pf_IS"] = med
    json.dump(rec, open(frozen_path(sid), "w"), indent=1)
    print(f"[freeze] {sid} frozen; neighbourhood median IS PF = {med:.2f}")
    return rec


def oos(sid):
    fp = frozen_path(sid)
    if not os.path.exists(fp):
        raise SystemExit(f"{sid} is not frozen; refusing to run OOS")
    rec = json.load(open(fp))
    src = open(os.path.join(ROOT, "strategies", f"{sid}.py")).read()
    if hashlib.sha256(src.encode()).hexdigest()[:16] != rec["code_sha"]:
        raise SystemExit("strategy code changed after freezing; refusing to run OOS")
    if rec.get("oos_run"):
        print("[oos] already run once; showing stored result")
        print(pd.DataFrame(rec["oos_result"]).round(2).to_string())
        return rec
    mod = load_strategy(sid)
    sig = mod.signals(ctx(), **rec["params"])
    if rec.get("exit"):
        sig = apply_exit(sig, rec["exit"])
    out = {}
    for name, cost in (("base", bt1s.CTRADER), ("stress", bt1s.STRESS)):
        tr = bt1s.run(ctx(), sig, cost)
        rep = bt1s.report(tr)
        for p in rep.index:
            out[f"{name}_{p}"] = rep.loc[p].to_dict()
        if name == "base":
            tr.to_csv(os.path.join(RESULTS, f"{sid}_trades.csv"), index=False)
    b = {p: out.get(f"base_{p}", {"n": 0}) for p in ("IS", "VAL", "OOS")}
    st = out.get("stress_OOS", {"n": 0})
    verdict = all(bt1s.passes(b[p]) for p in ("IS", "VAL", "OOS")) and b["OOS"].get("n", 0) >= 25 \
        and st.get("pf", 0) > 2.0 and st.get("dd_pct", 99) < 7.0 \
        and (b["IS"].get("n", 0) + b["VAL"].get("n", 0)) >= 100 \
        and rec.get("robust_median_pf_IS", 0) > 2.0
    rec.update(oos_run=True, oos_result=out, verdict="PASS" if verdict else "FAIL",
               oos_at=pd.Timestamp.utcnow().isoformat())
    json.dump(rec, open(fp, "w"), indent=1)
    print(f"[oos] {sid}: {rec['verdict']}")
    print(pd.DataFrame(out).T.round(2).to_string())
    return rec


if __name__ == "__main__":
    cmd, sid = sys.argv[1], sys.argv[2]
    if cmd == "screen":
        screen(sid)
    elif cmd == "optimise":
        mx = int(sys.argv[sys.argv.index("--max") + 1]) if "--max" in sys.argv else 300
        optimise(sid, mx)
    elif cmd == "freeze":
        spec = json.loads(sys.argv[3])
        freeze(sid, spec["params"], spec.get("exit"), spec.get("note", ""))
    elif cmd == "oos":
        oos(sid)
