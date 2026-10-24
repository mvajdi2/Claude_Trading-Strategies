"""Bollinger-inside-Keltner squeeze release breakout (Batch A #9; rerun A-4).

Cards marketplaces-bbkc-squeeze-breakout-15m (defaults) and practitioners-bbkc-squeeze-release.
On tf bars: BB = SMA20 +- 2 sd, KC = SMA20 +- kc_mult*ATR20 (KC midline = SMA20). Squeeze on = BB
inside KC. Signal on the first bar with squeeze off after >= min_sq consecutive squeeze bars, close
beyond the BB band (long: close > upper BB) and SMA20 rising (falling for shorts) (card-1 slope rule).
Entries on bars closing 06:00-18:00 UTC, max 2 signals per day.
Stop (stop_mode): "squeeze_range" = opposite side of the squeeze-bar range (card 1);
                  "kc_or_1.5atr" = nearer of the opposite KC band and 1.5*ATR14(tf) (card 2).
Exit (exit_mode): "trail" (card default) = exit at the close of the first later closed bar that closes
back through the SMA20/KC midline (precomputed and passed as `hold`, filled >= 1 s after that close),
no target; "2R" = target 2*stop. Both flat 20:45 UTC. unit = stop distance (USD).
"""
import numpy as np, pandas as pd
import bt1s
from strategies import batcha_util as U

PARAMS = {
    "tf": [900, 300, 3600],
    "min_sq": [6, 4, 10],
    "kc_mult": [1.5, 1.0, 2.0],
    "exit_mode": ["trail", "2R"],
    "stop_mode": ["squeeze_range", "kc_or_1.5atr"],
}
EXIT_UNIT = True


def signals(ctx, tf=900, min_sq=6, kc_mult=1.5, exit_mode="trail", stop_mode="squeeze_range"):
    b = ctx.bars(tf)
    c = b.c.values; h = b.h.values; l = b.l.values
    m = bt1s.sma(c, 20); sd = pd.Series(c).rolling(20).std().values
    a20 = bt1s.atr(b, 20); a14 = bt1s.atr(b, 14)
    ub, lb = m + 2 * sd, m - 2 * sd
    uk, lk = m + kc_mult * a20, m - kc_mult * a20
    sq = (ub < uk) & (lb > lk)
    run = np.zeros(len(c), np.int64)
    for i in range(1, len(c)):
        run[i] = run[i - 1] + 1 if sq[i] else 0
    prev_run = np.r_[0, run[:-1]]
    rel = (~sq) & (prev_run >= min_sq)
    slope = np.r_[0, np.diff(m)]
    lg = rel & (c > ub) & (slope > 0)
    sh = rel & (c < lb) & (slope < 0)
    cs = b.close_sec.values
    sod = (cs + 1) % 86400
    win = (sod > 6 * 3600) & (sod <= 18 * 3600)
    idx = np.where((lg | sh) & win)[0]
    td_all = U.tday_of(cs)
    rows = []
    for i in idx:
        sd_ = 1 if lg[i] else -1
        if stop_mode == "squeeze_range":
            k = prev_run[i]
            ref = l[i - k:i].min() if sd_ > 0 else h[i - k:i].max()
            sl = (c[i] - ref) * sd_
        else:
            kc_d = (c[i] - lk[i]) if sd_ > 0 else (uk[i] - c[i])
            sl = min(kc_d, 1.5 * a14[i])
        if not np.isfinite(sl) or sl <= 0:
            continue
        flat = U.at(td_all[i], 20.75)
        hold = flat - cs[i]
        if exit_mode == "trail":
            j = i + 1
            while j < len(c) and cs[j] < flat and td_all[j] == td_all[i]:
                if (c[j] - m[j]) * sd_ < 0:
                    hold = cs[j] - cs[i]
                    break
                j += 1
            tp = 0.0
        else:
            tp = 2 * sl
        rows.append((cs[i], sd_, sl, tp, max(hold, 1), sl))
    s = pd.DataFrame(rows, columns=["sec", "side", "sl", "tp", "hold", "unit"])
    td = U.tday_of(s.sec.values)
    s = s[pd.Series(td).groupby(td).cumcount().values < 2]
    return s.reset_index(drop=True)
