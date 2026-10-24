"""Post-release volatility crush: fade re-tests of the 15-minute release impulse range (Batch D2-3).

Card r2-post-release-range-crush-fade.
Events (event_set):
  "t1card"    = the card's tier-1 list: NFP, CPI, PCE (personal income/core PCE), GDP_advance,
                retail_sales, FOMC_statement, plus the FOMC press conference (statement + 30 min,
                treated as its own event; not in the calendar file, always 14:30 ET).
  "t1card_t2" = t1card + PPI, ISM_manufacturing, ISM_services, JOLTS, GDP_second, GDP_third
                (researcher widening for the trade-count gate; the card allows "tier-1/2").
Merged same-timestamp releases are one event typed by the highest-tier member (_d2util).
IR = [low, high] of the 1s grid over [T, T+15min); W = width, mid = midpoint. PV = RMS of the five
1m mid-close returns T..T+5min. From the 1m bar closing at T+20min to the one closing at T+150min:
a bar whose low <= IR_low + tol*W, whose close is back inside the IR, and whose trailing 10-bar RMS
1m return <= crush*PV -> BUY at its close (mirror at IR high -> SELL).
Card exit: stop = IR extreme -/+ 0.25*W (stop_frac 0.25), target = IR mid (tgt=mid), time exit T+180min
or 20:55 UTC. Filter: W >= w_min*ATR14(15m) at T. Max one long and one short per event; once a trade
on an event would have been stopped (1s mid path), no further trades on that event; the second side is
only looked for after the first trade's (modelled) exit.
unit = native stop distance; stop_frac and tgt (mid/fib) are exit-only -> templates.
mode="break" (control, not in PARAMS): 1m close beyond IR extreme + tol*W after the crush, stop back
inside at extreme -/+ 0.25*W, target 0.5*W beyond the extreme.
placebo=True: same rules at matched no-release weekdays at the same NY clock time.
"""
import numpy as np, pandas as pd
import bt1s
from strategies import _d2util as D

PARAMS = {
    "tol": [0.0, 0.05, 0.1],
    "crush": [0.33, 0.5, 0.7],
    "w_min": [0.3, 0.5, 1.0],
    "event_set": ["t1card", "t1card_t2"],
}
DEFAULTS = dict(tol=0.05, crush=0.5, w_min=0.5, event_set="t1card")
EXIT_UNIT = True
SETS = {
    "t1card": ("NFP", "CPI", "PCE", "GDP_advance", "retail_sales", "FOMC_statement"),
    "t1card_t2": ("NFP", "CPI", "PCE", "GDP_advance", "retail_sales", "FOMC_statement", "PPI",
                  "ISM_manufacturing", "ISM_services", "JOLTS", "GDP_second", "GDP_third"),
}


def event_table(ctx, event_set="t1card", placebo=False):
    ev = D.events(ctx, SETS[event_set], placebo=placebo)
    pc = ev[ev.type == "FOMC_statement"].copy()
    pc["sec"] += 1800; pc["type"] = "FOMC_presser"; pc["minute"] += 30
    return pd.concat([ev, pc]).sort_values("sec").reset_index(drop=True)


def _first_exit(hi, lo, k0, k1, side, stop, tgt):
    """'stop' / 'tgt' / 'time' and exit index along the 1s mid path from k0+1 to k1 (stop first)."""
    for k in range(k0 + 1, k1 + 1):
        if (side > 0 and lo[k] <= stop) or (side < 0 and hi[k] >= stop):
            return "stop", k
        if (side > 0 and hi[k] >= tgt) or (side < 0 and lo[k] <= tgt):
            return "tgt", k
    return "time", k1


def signals(ctx, tol=0.05, crush=0.5, w_min=0.5, event_set="t1card", mode="fade", placebo=False):
    ev = event_table(ctx, event_set, placebo)
    b1 = ctx.bars(60)
    bi = b1.index.values; C = b1.c.values; Hb = b1.h.values; Lb = b1.l.values
    r = np.r_[np.nan, np.diff(np.log(C))]
    r[1:][np.diff(bi) != 60] = np.nan                      # no returns across gaps
    rv10 = np.sqrt(pd.Series(r ** 2).rolling(10, min_periods=8).mean().values)
    b15 = ctx.bars(900); a15 = bt1s.atr(b15, 14); c15 = b15.close_sec.values
    hi, lo = ctx.g["hi"], ctx.g["lo"]
    rows = []
    for _, e in ev.iterrows():
        T = int(e.sec)
        IRh, IRl = D.hl_between(ctx, np.array([T]), np.array([T + 899]))
        IRh, IRl = IRh[0], IRl[0]
        W = IRh - IRl
        j15 = np.searchsorted(c15, T - 1, "right") - 1
        if not np.isfinite(W) or j15 < 0 or not np.isfinite(a15[j15]) or W < w_min * a15[j15]:
            continue
        jT = np.searchsorted(bi, T)
        if jT + 5 >= len(bi) or jT < 1 or bi[jT] != T:
            continue
        rr = r[jT:jT + 5]                                    # 1m returns of the bars T .. T+4min
        PV = np.sqrt(np.nanmean(rr ** 2)) if np.isfinite(rr).sum() >= 4 else np.nan
        if not np.isfinite(PV) or PV <= 0:
            continue
        mid = 0.5 * (IRh + IRl)
        j0 = np.searchsorted(bi, T + 20 * 60 - 60)            # bar closing at T+20min - 1s
        j1 = np.searchsorted(bi, T + 150 * 60 - 60, "right")
        t_end = T + 180 * 60
        used = set(); free_from = 0
        for j in range(j0, min(j1, len(bi))):
            dec = int(bi[j] + 59)
            if dec <= free_from or not np.isfinite(rv10[j]) or rv10[j] > crush * PV:
                continue
            c = C[j]; sig = None
            if mode == "fade":
                if 1 not in used and Lb[j] <= IRl + tol * W and IRl < c < IRh:
                    sig = (1, c - (IRl - 0.25 * W), mid - c)
                elif -1 not in used and Hb[j] >= IRh - tol * W and IRl < c < IRh:
                    sig = (-1, (IRh + 0.25 * W) - c, c - mid)
            else:
                if 1 not in used and c > IRh + tol * W:
                    sig = (1, c - (IRh - 0.25 * W), IRh + 0.5 * W - c)
                elif -1 not in used and c < IRl - tol * W:
                    sig = (-1, (IRl + 0.25 * W) - c, c - (IRl - 0.5 * W))
            if sig is None or sig[1] <= 0.05 or sig[2] <= 0.05:
                continue
            sd, sl, tp = sig
            hold = int(D.hold_to(np.array([dec]), np.array([t_end]))[0])
            if hold <= 60:
                break
            rows.append((dec, sd, sl, tp, hold))
            used.add(sd)
            k0 = int(ctx.k_of(dec)) + 1
            how, kx = _first_exit(hi, lo, k0, min(k0 + hold, ctx.n - 1), sd, c - sd * sl, c + sd * tp)
            if how == "stop" or len(used) == 2:
                break
            free_from = int(ctx.sec_of(kx))
    s = pd.DataFrame(rows, columns=["sec", "side", "sl", "tp", "hold"])
    s["unit"] = s.sl
    return s.sort_values("sec").reset_index(drop=True)
