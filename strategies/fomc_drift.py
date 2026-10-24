"""Post-FOMC statement drift into the close (follow / fade).

Card: academic-fomc-post-announcement-drift.
Scheduled FOMC statement days (14:00 New York), taken from
https://www.federalreserve.gov/monetarypolicy/fomccalendars.htm (checked 2026-10-23; the
2025-08-22 notation vote is not a scheduled statement and is excluded).
At statement + wait_min: r = P(stmt+wait) - P(stmt-1min). If |r| > m * ATR14(5m) * sqrt(wait/5),
follow: trade sign(r), stop at the pre-announcement level (distance |r|);
fade:   trade -sign(r), stop |r| beyond entry.
Exit: 21:00 UTC flat (engine). unit = stop distance.
"""
import numpy as np, pandas as pd
import bt1s

NY = "America/New_York"
FOMC_DATES = [
    "2025-01-29", "2025-03-19", "2025-05-07", "2025-06-18", "2025-07-30", "2025-09-17",
    "2025-10-29", "2025-12-10",
    "2026-01-28", "2026-03-18", "2026-04-29", "2026-06-17", "2026-07-29", "2026-09-16",
    "2026-10-28", "2026-12-09",
]

PARAMS = {
    "wait_min": [30, 5, 15, 60],
    "m": [1.0, 0.5, 1.5],
    "direction_mode": ["follow", "fade"],
}
EXIT_UNIT = True


def signals(ctx, wait_min=30, m=1.0, direction_mode="follow"):
    b1 = ctx.bars(60)
    b5 = ctx.bars(300)
    a5 = pd.Series(bt1s.atr(b5, 14), index=b5.index)
    rows = []
    for ds in FOMC_DATES:
        st = int(pd.Timestamp(ds + " 14:00").tz_localize(NY).timestamp())
        pre = b1[(b1.index >= st - 600) & (b1.index < st - 60)]       # bars ending by stmt-1min
        post = b1[(b1.index >= st) & (b1.close_sec <= st + wait_min * 60 - 1)]
        if len(pre) == 0 or len(post) == 0:
            continue
        p0 = pre.c.iloc[-1]; p1 = post.c.iloc[-1]; dsec = int(post.close_sec.iloc[-1])
        av = a5[a5.index < st - 300]
        if len(av) == 0 or not np.isfinite(av.iloc[-1]):
            continue
        thr = m * av.iloc[-1] * np.sqrt(wait_min / 5)
        r = p1 - p0
        if abs(r) <= thr:
            continue
        side = int(np.sign(r)) * (1 if direction_mode == "follow" else -1)
        stop = max(abs(r), 0.5)
        rows.append(dict(sec=dsec, side=side, sl=stop, tp=0.0, hold=8 * 3600, unit=stop))
    return pd.DataFrame(rows, columns=["sec", "side", "sl", "tp", "hold", "unit"])
