#!/usr/bin/env python3
"""Batch D2 finalist selector (rule committed before any D2 grid was run; see results_batchD2.md). Same rule as research/d1_select.py, copied so later edits there cannot change D2.

    python3 research/d2_select.py <id>          # IS columns only -> finalist
    python3 research/d2_select.py <id> --val    # additionally prints the finalist's VAL row (final look)

Rule
  1. Stage 1 (card exit, full sorted grid): finalist setting = highest plateau score
     (harness: median IS PF(R) over the setting and its sorted +-1 neighbours with n_IS >= 60),
     among settings with n_IS >= 60. Ties: higher own IS PF(R).
  2. Exit: among the stage-2 templates of that setting, a template is eligible if the median IS
     PF(R) of its template neighbours (same family; +-1 step in sl with the rest fixed; +-1 step in
     the final tp with tp1/f1/be fixed; trail family: +-1 step in sl and in trail; the template
     itself excluded) is >= 1.30. The best eligible template replaces the card exit only if its
     IS PF(R) is higher than the card exit's. Ties within 0.005: the lower sl, then the card exit.
  3. Freeze + single OOS only if the finalist has IS PF(R) >= 1.30 and VAL PF >= 1.30.
"""
import os, sys, json
import numpy as np, pandas as pd

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RES = os.path.join(ROOT, "results")
FAM_KEYS = {"fixed": ["sl", "tp"], "scalp_be": ["sl", "tp1", "f1", "tp"], "trail": ["sl", "trail"]}
STEP_KEYS = {"fixed": ["sl", "tp"], "scalp_be": ["sl", "tp"], "trail": ["sl", "trail"]}
IS_COLS = ["n_IS", "wr_IS", "pf_IS", "pfR_IS", "dd_pct_IS", "per_wk_IS"]
VAL_COLS = ["n_VAL", "wr_VAL", "pf_VAL", "pfR_VAL", "dd_pct_VAL", "per_wk_VAL"]


def tpl_neighbours(fam, tpl, all_tpls):
    keys = FAM_KEYS[fam]
    out = []
    for k in STEP_KEYS[fam]:
        vals = sorted({t[k] for t in all_tpls})
        i = vals.index(tpl[k])
        for j in (i - 1, i + 1):
            if 0 <= j < len(vals):
                q = dict(tpl); q[k] = vals[j]
                for t in all_tpls:
                    if all(t[kk] == q[kk] for kk in keys):
                        out.append(t)
    return out


def select(sid, min_n=60, thr=1.30):
    s1 = pd.read_csv(os.path.join(RES, f"{sid}_opt_stage1.csv"))
    meta = {"exit_kind", "exit", "plateau"} | {c for c in s1.columns if c.endswith(("_IS", "_VAL"))}
    keys = [c for c in s1.columns if c not in meta]
    el = s1[(s1.n_IS >= min_n) & s1.plateau.notna()]
    print(f"[{sid}] stage-1 rows {len(s1)}, eligible (n_IS >= {min_n}) {len(el)}")
    if not len(el):
        print("no stage-1 setting with n_IS >= 60 -> no finalist (ineligible by trade count)")
        return None
    el = el.sort_values(["plateau", "pfR_IS"], ascending=False)
    print(el[keys + ["plateau"] + IS_COLS].head(5).round(3).to_string())
    fin = el.iloc[0]
    params = {k: fin[k] for k in keys}
    card = dict(exit=None, pfR_IS=fin.pfR_IS, row=fin)
    best = card
    fp = os.path.join(RES, f"{sid}_opt_exits.csv")
    if os.path.exists(fp):
        s2 = pd.read_csv(fp)
        m = np.ones(len(s2), bool)
        for k in keys:
            m &= (s2[k].astype(str) == str(fin[k])).values
        s2 = s2[m].copy()
        s2["tpl"] = s2.exit.map(json.loads)
        cands = []
        for fam, g in s2.groupby("exit_kind"):
            tpls = list(g.tpl)
            pf = {json.dumps(t, sort_keys=True): v for t, v in zip(g.tpl, g.pfR_IS)}
            for _, r in g.iterrows():
                nb = [pf[json.dumps(t, sort_keys=True)] for t in tpl_neighbours(fam, r.tpl, tpls)]
                med = float(np.nanmedian(nb)) if nb else np.nan
                cands.append((r.pfR_IS, med, fam, r.tpl, r))
        ok = [c for c in cands if c[1] >= thr and c[4].n_IS >= min_n]
        print(f"stage-2 templates for finalist: {len(cands)}, eligible (neighbour median >= {thr}): {len(ok)}")
        if ok:
            ok.sort(key=lambda c: (-round(c[0], 3), c[3]["sl"]))
            top = ok[0]
            print(f"best eligible template: {top[2]} {top[3]} IS PF(R) {top[0]:.3f} (neighbour median {top[1]:.3f})")
            if top[0] > card["pfR_IS"] + 0.005:
                best = dict(exit=top[3], kind=top[2], pfR_IS=top[0], row=top[4])
    r = best["row"]
    print(f"FINALIST params={params} exit={'card' if best['exit'] is None else best['exit']}")
    print("IS: " + ", ".join(f"{c}={r[c]:.3f}" for c in IS_COLS))
    return params, best


if __name__ == "__main__":
    sid = sys.argv[1]
    out = select(sid)
    if out and "--val" in sys.argv:
        r = out[1]["row"]
        print("VAL (final look): " + ", ".join(f"{c}={r[c]:.3f}" for c in VAL_COLS if c in r))
