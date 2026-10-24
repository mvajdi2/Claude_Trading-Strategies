"""Fade the initial XAU reaction to US data releases when the reaction is small (Batch D2-1).

Card r2-post-release-small-surprise-revert (Yamada & Ito: reversal after small surprises).
Events: every 08:30 ET release in the verified calendar (NFP, CPI, PPI, retail sales, jobless claims,
GDP, PCE) plus the 10:00 ET tier-1/2 releases (ISM manufacturing/services, JOLTS, PCE when at 10:00).
Same-timestamp releases are one event typed by the highest-tier member (_d2util). FOMC statement days
are skipped. Durable goods and housing starts are not in the calendar (documented deviation).

Surprise proxy (no consensus data): R0 = mid(T+s0) - mid(T-60s). q = |R0| / med20, where med20 is the
median |R0| of the previous 20 events of the same type, pooled over all types (previous 20 events)
when the type has < 20 history (needs >= 10 prior events). Trade if q <= q_max and
|R0| >= r_min * ATR14(1m at T) * sqrt(s0/60). FADE at T+s0+delay: R0 < 0 -> long, R0 > 0 -> short.
Card exit: stop = most extreme price between T and the decision second -/+ 1.0*|R0| (stop_mult 1.0),
target = full retrace to mid(T-60s) (tgt_frac 1.0), time exit T+hold_min (180) or 20:55 UTC.
unit = native stop distance; stop_mult / tgt_frac are exit-only and therefore left to the templates.
large_mode="follow" (q > q_max, continuation, stop at mid(T-60s), target 1R) is a control, not in PARAMS.
Grid deviation (frequency, decided from signal counts before any grid): at XAU scale ATR14(1m) ~ $2.4
while the median |R0| is ~ $3, so q <= q_max and |R0| >= r_min*ATR*sqrt(s0/60) are nearly exclusive:
the card defaults give 4 trades in 22 months. r_min 2.0 (zero trades) is replaced by 0.0, and q_max 0.5
(<= ~18 IS trades at any setting, ~115 IS events) by 1.25, so that n_IS >= 60 is reachable at all.
placebo=True moves every event to a matched no-release weekday at the same NY clock time.
"""
import numpy as np, pandas as pd
import bt1s
from strategies import _d2util as D

PARAMS = {
    "s0_sec": [30, 60, 120, 300],
    "delay_sec": [0, 60, 180],
    "q_max": [0.75, 1.0, 1.25],
    "r_min": [0.0, 0.5, 1.0],
}
DEFAULTS = dict(s0_sec=120, delay_sec=0, q_max=0.75, r_min=1.0)
EXIT_UNIT = True


def event_table(ctx, placebo=False):
    ev = D.events(ctx, D.TIER1 + D.TIER2 + D.CLAIMS, placebo=placebo)
    ev = ev[(ev.minute == 8 * 60 + 30) | ((ev.minute == 10 * 60) & (ev.tier <= 2))]
    fomc = set(D.events(ctx, ("FOMC_statement",), placebo=False).date)
    ev = ev[~ev.date.isin(fomc)]
    return ev.reset_index(drop=True)


def signals(ctx, s0_sec=120, delay_sec=0, q_max=0.75, r_min=1.0, hold_min=180, large_mode="none",
            placebo=False):
    ev = event_table(ctx, placebo)
    T = ev.sec.values.astype(np.int64)
    pre = D.mid_at(ctx, T - 60)
    p0 = D.mid_at(ctx, T + s0_sec)
    R0 = p0 - pre
    med = D.prior_stat(np.abs(R0), ev.type.values, 20, "median", pooled_min=10)
    q = np.abs(R0) / med
    b1 = ctx.bars(60)
    a1 = bt1s.atr(b1, 14)
    j = np.searchsorted(b1.close_sec.values, T - 1, "right") - 1   # last 1m bar closed by T-1
    atr = np.where(j >= 0, a1[np.clip(j, 0, None)], np.nan)
    big = np.abs(R0) >= r_min * atr * np.sqrt(s0_sec / 60.0)
    dec = T + s0_sec + delay_sec
    px = D.mid_at(ctx, dec)
    H, L = D.hl_between(ctx, T, dec)
    if large_mode == "follow":
        keep = big & (q > q_max)
        side = np.sign(R0)
        sl = side * (px - pre)
        tp = sl.copy()
    else:
        keep = big & (q <= q_max)
        side = -np.sign(R0)
        ext = np.where(side > 0, L, H)
        stop = ext - side * 1.0 * np.abs(R0)
        sl = side * (px - stop)
        tgt = p0 - 1.0 * R0                       # = pre-release mid
        tp = side * (tgt - px)
    hold = D.hold_to(dec, T + hold_min * 60)
    s = pd.DataFrame(dict(sec=dec, side=side.astype(int), sl=sl, tp=tp, hold=hold, unit=sl))
    ok = keep & np.isfinite(q) & (side != 0) & (sl > 0.05) & (tp > 0.05) & (hold > 60) & np.isfinite(sl)
    return s[ok].sort_values("sec").reset_index(drop=True)
