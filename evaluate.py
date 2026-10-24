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
    params = dict(getattr(mod, "DEFAULTS", {k: v[0] for k, v in mod.PARAMS.items()}))
    sig = visible(mod.signals(ctx(), **params))
    tr = bt1s.run(ctx(), sig)
    rep = bt1s.report(tr, ("IS", "VAL"))
    print(f"[screen] {sid} defaults={params}\n{rep.round(2).to_string()}")
    return rep


def _sorted_grid(grid):
    try:
        return sorted(grid)
    except TypeError:
        return list(grid)


def _neighbours(mod, params):
    """+-1 step neighbours of each parameter, in sorted value order (X3)."""
    out = []
    for k, grid in mod.PARAMS.items():
        g = _sorted_grid(grid)
        if params.get(k) not in g:
            continue
        i = g.index(params[k])
        for j in (i - 1, i + 1):
            if 0 <= j < len(g):
                q = dict(params); q[k] = g[j]; out.append(q)
    return out


def optimise(sid, max_combos=300, objective="pfR_IS", min_n_is=60, top_k=3):
    """Staged search (X1/X2):
      stage 1: full parameter grid with the strategy's own (card) exit  -> results/<id>_opt_stage1.csv
      stage 2: exit templates on the top_k plateau settings of stage 1   -> results/<id>_opt_exits.csv
    Plateau score = median IS objective over the setting and its sorted +-1 neighbours.
    Both stages are counted; total combos are printed and capped at max_combos."""
    mod = load_strategy(sid)
    keys = list(mod.PARAMS)
    combos = list(itertools.product(*[_sorted_grid(mod.PARAMS[k]) for k in keys]))
    t0 = time.time()
    exit_mode = getattr(mod, "EXIT_UNIT", False)
    n_tpl = sum(len(v) for v in EXIT_TEMPLATES.values()) if exit_mode else 0
    budget1 = max_combos - (top_k * n_tpl if exit_mode else 0)
    if len(combos) > max(budget1, 1):
        raise SystemExit(f"{sid}: stage-1 grid has {len(combos)} combos > budget {budget1}; shrink PARAMS")
    rows = []
    cache = {}
    for c in combos:
        p = dict(zip(keys, c))
        cache[c] = visible(mod.signals(ctx(), **p))
        tr = bt1s.run(ctx(), cache[c]) if len(cache[c]) else pd.DataFrame()
        row = dict(p); row["exit_kind"] = "card"; row["exit"] = ""
        row.update(summarize(tr)); rows.append(row)
    s1 = pd.DataFrame(rows)
    # plateau score
    def score(p):
        vals = []
        for q in [p] + _neighbours(mod, p):
            m = s1
            for k in keys:
                m = m[m[k] == q[k]]
            if len(m) and m.iloc[0].get("n_IS", 0) >= min_n_is:
                vals.append(m.iloc[0][objective])
        return float(np.nanmedian(vals)) if vals else np.nan
    s1["plateau"] = [score({k: r[k] for k in keys}) for _, r in s1.iterrows()]
    s1.to_csv(os.path.join(RESULTS, f"{sid}_opt_stage1.csv"), index=False)
    total = len(s1)
    s2 = pd.DataFrame()
    if exit_mode:
        elig = s1[(s1.get("n_IS", 0) >= min_n_is)] if "n_IS" in s1 else s1.iloc[0:0]
        best = elig.dropna(subset=["plateau"]).sort_values("plateau", ascending=False).head(top_k)
        rows = []
        for _, b in best.iterrows():
            c = tuple(b[k] for k in keys)
            sig0 = cache.get(c)
            if sig0 is None or len(sig0) == 0:
                continue
            for kind, tpls in EXIT_TEMPLATES.items():
                for tpl in tpls:
                    tr = bt1s.run(ctx(), apply_exit(sig0, tpl))
                    row = {k: b[k] for k in keys}; row["exit_kind"] = kind; row["exit"] = json.dumps(tpl)
                    row.update(summarize(tr)); rows.append(row)
        s2 = pd.DataFrame(rows)
        s2.to_csv(os.path.join(RESULTS, f"{sid}_opt_exits.csv"), index=False)
        total += len(s2)
    res = pd.concat([s1, s2], ignore_index=True)
    res.to_csv(os.path.join(RESULTS, f"{sid}_opt.csv"), index=False)
    ok = res[res["n_IS"] >= min_n_is] if "n_IS" in res else res.iloc[0:0]
    print(f"[optimise] {sid}: {total} combos tested ({len(s1)} stage-1 + {len(s2)} exit) in {time.time()-t0:.0f}s; "
          f"{len(ok)} with n_IS >= {min_n_is}")
    if len(ok):
        cols = keys + ["exit_kind", "exit", "plateau", "n_IS", "wr_IS", "pf_IS", "pfR_IS", "dd_pct_IS", "per_wk_IS",
                       "n_VAL", "wr_VAL", "pf_VAL", "pfR_VAL", "dd_pct_VAL"]
        cols = [c for c in cols if c in ok]
        pd.set_option("display.width", 280); pd.set_option("display.max_colwidth", 60)
        print(ok.sort_values(objective, ascending=False)[cols].head(15).round(2).to_string())
        gate = ok[(ok.wr_IS > 75) & (ok.pf_IS > 3) & (ok.dd_pct_IS < 5)]
        print(f"IS gate passers: {len(gate)}; of those also passing on VAL: "
              f"{len(gate[(gate.wr_VAL > 75) & (gate.pf_VAL > 3) & (gate.dd_pct_VAL < 5)])}")
    return res


def robustness(sid, params, exit_tpl=None):
    """median IS PF over the sorted +-1-step neighbourhood of each parameter (X3)"""
    mod = load_strategy(sid)
    pfs = []
    for q in _neighbours(mod, params):
        sig = visible(mod.signals(ctx(), **q))
        if exit_tpl:
            sig = apply_exit(sig, exit_tpl)
        tr = bt1s.run(ctx(), sig)
        m = bt1s.metrics(tr[tr.period == "IS"])
        pfs.append(m.get("pf", np.nan))
    return float(np.nanmedian(pfs)) if pfs else np.nan, pfs


def code_hash_v3(sid):
    """hash of the strategy file, the strategies/ helper modules it imports, and bt1s.py"""
    import re
    path = os.path.join(ROOT, "strategies", f"{sid}.py")
    src = open(path).read()
    mods = set(re.findall(r"from\s+strategies\.(\w+)\s+import|from\s+\.(\w+)\s+import|import\s+strategies\.(\w+)", src))
    names = sorted({m for t in mods for m in t if m} |
                   set(re.findall(r"from\s+strategies\s+import\s+(\w+)", src)))
    h = hashlib.sha256(open(path, "rb").read())
    for n in names:
        f = os.path.join(ROOT, "strategies", f"{n}.py")
        if os.path.exists(f) and n != sid:
            h.update(open(f, "rb").read())
    h.update(open(os.path.join(ROOT, "bt1s.py"), "rb").read())
    return h.hexdigest()[:16], names


def code_hash(sid):
    """hash of the strategy file plus shared helper modules in strategies/ (X6)"""
    import glob
    h = hashlib.sha256()
    files = [os.path.join(ROOT, "strategies", f"{sid}.py")]
    files += sorted(f for f in glob.glob(os.path.join(ROOT, "strategies", "*.py"))
                    if os.path.basename(f).startswith("_") or "util" in os.path.basename(f))
    files += [os.path.join(ROOT, "bt1s.py")]
    for f in files:
        h.update(open(f, "rb").read())
    return h.hexdigest()[:16]


def frozen_path(sid):
    return os.path.join(CARDS, f"{sid}.frozen.json")


def freeze(sid, params, exit_tpl=None, note=""):
    rec = dict(id=sid, params=params, exit=exit_tpl, note=note,
               code_sha=code_hash_v3(sid)[0], hash_scheme="v3", hashed_helpers=code_hash_v3(sid)[1],
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
    if rec.get("oos_run"):
        print("[oos] already run once; showing stored result")
        print(pd.DataFrame(rec["oos_result"]).round(2).to_string())
        return rec
    if rec.get("hash_scheme") == "v3":
        ok_hash = code_hash_v3(sid)[0] == rec["code_sha"]
    elif rec.get("hash_scheme") == "v2":
        ok_hash = code_hash(sid) == rec["code_sha"]
    else:
        src = open(os.path.join(ROOT, "strategies", f"{sid}.py")).read()
        ok_hash = hashlib.sha256(src.encode()).hexdigest()[:16] == rec["code_sha"]
    if not ok_hash:
        raise SystemExit("strategy/helper/engine code changed after freezing; refusing to run OOS")
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
