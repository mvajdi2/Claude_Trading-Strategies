"""Weekend / holiday / daily-reopen gap fade after spreads normalise (card r2-reopen-gap-fade).

Breaks = gaps of >= 30 min between live seconds of the XAUUSD 1s grid:
  daily break (~60 min, 17:00-18:00 New York), holiday early closes (2-24 h), weekends (> 24 h).
  include_daily=False uses weekend + holiday breaks only.
p_pre  = mid of the last live second before the break.
p0     = "first valid price": mid of the first live second after the reopen whose spread is
         <= 3x the baseline spread of minute 0 (baseline defined below).
g = p0 - p_pre, gN = g / ATR14(1h) of the last 1h bar closed before the break.
Spread gate: minute m after the reopen (m = 0, 1, ...) is "normal" when its median 1s spread is
  <= 1.5x the baseline for minute m, where the baseline is the median over the previous 20 reopens
  (all break types) of that minute's median spread. The card's "20-day median for that clock minute"
  is implemented on minutes-since-reopen so that the DST shift of the reopen (22:00 vs 23:00 UTC)
  does not misalign it.
Entry decision: close of the first minute m >= delay_min - 1 that ends a run of 5 consecutive normal
  minutes (m <= 180), with |gN| >= g_min, |gN| <= g_cap and less than fill_max of the gap already
  filled at that second. fade: side = -sign(g); follow (control, not part of the search): side = sign(g).
Card exit (fade): stop = post-reopen extreme (low for longs, high for shorts, from the reopen to the
  decision second) -/+ 0.5*ATR14(1h); target = fill tgt_frac (1.0) of the gap, i.e. back to
  p0 - tgt_frac*g; time exit at exit_utc of the trading day (03:00 / 07:00 / 12:00 / 20:55 UTC).
  The card's alternative stop "stop_mult*|g| from entry" and the tgt_frac grid only change sl/tp,
  so they are left to the exit templates (X4); unit = native (structural) stop distance.
Grid: card grid, except g_min adds 0.1 and 0.2 (researcher count variants: at the card's 0.3-1.0
  only 7-30 IS+VAL trades exist, X7) and delay_min drops 120 (stage-1 budget 141).
Follow control: same entry second, opposite side, same sl/tp distances (pure sign test).
"""
import numpy as np, pandas as pd
import bt1s
from strategies import _d1util as U

PARAMS = {
    "g_min": [0.1, 0.2, 0.3, 0.5, 1.0],
    "delay_min": [10, 30, 60],
    "exit_utc": ["03:00", "07:00", "12:00", "20:55"],
    "include_daily": [False, True],
}
DEFAULTS = dict(g_min=0.5, delay_min=30, exit_utc="07:00", include_daily=False)
EXIT_UNIT = True
G_CAP = 4.0          # card default (skip continuation-regime shocks)
FILL_MAX = 0.5       # card default
TGT_FRAC = 1.0       # card default
MAXM = 181


def _events(ctx):
    key = "_d1_reopen_events"
    if key in ctx._bars:
        return ctx._bars[key]
    live = ctx.g["live"]; idx = np.flatnonzero(live)
    gaps = np.diff(idx)
    big = np.flatnonzero(gaps >= 30 * 60)
    sp = ctx.spread
    h1 = ctx.bars(3600); a1 = bt1s.atr(h1, 14); h1cs = h1.close_sec.values
    ev = []
    for j in big:
        ka, kb = idx[j], idx[j + 1]
        dur = (kb - ka) / 60
        kind = "daily" if dur < 120 else ("holiday" if dur < 24 * 60 else "weekend")
        # per-minute median spread for minutes 0..MAXM-1 after the reopen (live seconds only)
        msp = np.full(MAXM, np.nan)
        for m in range(MAXM):
            a = kb + 60 * m; z = min(a + 60, ctx.n)
            lv = live[a:z]
            if lv.any():
                msp[m] = np.median(sp[a:z][lv])
        i = np.searchsorted(h1cs, ctx.sec_of(ka), "right") - 1
        ev.append(dict(ka=ka, kb=kb, kind=kind, msp=msp, atr=a1[i] if i >= 0 else np.nan,
                       p_pre=ctx.mid[ka]))
    # baseline: median over previous 20 events of each minute's median spread
    M = np.array([e["msp"] for e in ev])
    for n, e in enumerate(ev):
        lo = max(0, n - 20)
        e["base"] = np.nanmedian(M[lo:n], axis=0) if n >= 10 else np.full(MAXM, np.nan)
    ctx._bars[key] = ev
    return ev


def signals(ctx, g_min=0.5, delay_min=30, exit_utc="07:00", include_daily=False, mode="fade"):
    ev = _events(ctx)
    live = ctx.g["live"]; sp = ctx.spread; mid = ctx.mid
    HI, LO = ctx.g["hi"], ctx.g["lo"]
    rows = []
    for e in ev:
        if e["kind"] == "daily" and not include_daily:
            continue
        base = e["base"]; A = e["atr"]
        if not np.isfinite(base[0]) or not np.isfinite(A) or A <= 0:
            continue
        kb = e["kb"]
        # first valid price: first live second with spread <= 3x minute-0 baseline (within 30 min)
        w = np.arange(kb, min(kb + 1800, ctx.n))
        ok = live[w] & (sp[w] <= 3 * base[0])
        if not ok.any():
            continue
        k0 = w[np.argmax(ok)]
        p0 = mid[k0]
        g = p0 - e["p_pre"]
        gN = g / A
        if abs(gN) < g_min or abs(gN) > G_CAP:
            continue
        normal = np.isfinite(e["msp"]) & np.isfinite(base) & (e["msp"] <= 1.5 * base)
        run = 0; mdec = -1
        for m in range(MAXM):
            run = run + 1 if normal[m] else 0
            if run >= 5 and m >= delay_min - 1:
                mdec = m; break
        if mdec < 0:
            continue
        kd = kb + 60 * mdec + 59
        if kd <= k0:
            continue
        P = mid[kd]
        filled = (P - p0) / (e["p_pre"] - p0)
        if filled >= FILL_MAX:
            continue
        fade_side = -int(np.sign(g))
        tgt_px = p0 - TGT_FRAC * g
        tp = fade_side * (tgt_px - P)
        if fade_side == 1:
            sl = P - (LO[kb:kd + 1].min() - 0.5 * A)
        else:
            sl = (HI[kb:kd + 1].max() + 0.5 * A) - P
        if tp <= 0.05 or sl <= 0:
            continue
        sec = int(ctx.sec_of(kd))
        td = (sec + 4 * 3600) // U.DAY          # reopen 22:00/23:00 UTC belongs to the next date
        hold = int(U.utc_sec(td, exit_utc) - sec)
        side = fade_side if mode == "fade" else -fade_side
        rows.append(dict(sec=sec, side=side, sl=sl, tp=tp, hold=hold, unit=sl, gN=gN, kind=e["kind"],
                         minute=mdec))
    return U.frame(rows)
