#!/usr/bin/env python3
"""Study 2, step 1: per-day price snapshots around scheduled anchors (local exchange times).

For each anchor and trading day we store mid prices at offsets (seconds) relative to the
anchor, the high/low of the opening window, the daily ATR proxy and the modeled spread.
Output: data/anchors.pkl
"""
import os
import numpy as np, pandas as pd
import hfdata

D = os.path.join(hfdata.ROOT, "data")

ANCHORS = {
    "tokyo_0900":   ("Asia/Tokyo", 9, 0),
    "london_0800":  ("Europe/London", 8, 0),
    "lbma_am_1030": ("Europe/London", 10, 30),
    "comex_0820":   ("America/New_York", 8, 20),
    "us_data_0830": ("America/New_York", 8, 30),
    "nyse_0930":    ("America/New_York", 9, 30),
    "us_data_1000": ("America/New_York", 10, 0),
    "comex_1330":   ("America/New_York", 13, 30),
    "lbma_pm_1500": ("Europe/London", 15, 0),
    "london_1600":  ("Europe/London", 16, 0),
}
OFFS = np.array([-7200, -3600, -1800, -900, -300, -60, 0, 60, 120, 300, 600, 900, 1800, 2700,
                 3600, 5400, 7200, 10800, 14400])
RANGES = (60, 300, 900, 1800)     # opening-range lengths


def main():
    z = np.load(hfdata.CACHE)
    s0 = int(z["s0"]); bid = z["bid"]; ask = z["ask"]; hi = z["hi"]; lo = z["lo"]; live = z["live"]
    mid = 0.5 * (bid + ask)
    n = len(mid)
    days = pd.date_range("2025-01-02", "2026-10-22", freq="D")
    # daily ATR proxy: mean absolute 1h mid change over previous 5 days (computed per anchor time)
    rows = []
    for name, (tz, hh, mm) in ANCHORS.items():
        loc = pd.DatetimeIndex([pd.Timestamp(d.date()).tz_localize(tz) + pd.Timedelta(hours=hh, minutes=mm)
                                for d in days])
        sec = loc.tz_convert("UTC").as_unit("s").asi8.astype(np.int64)
        k = sec - s0
        for d, kk, ss in zip(days, k, sec):
            if kk - 7200 - 5 * 86400 < 0 or kk + 14400 >= n:
                continue
            if pd.Timestamp(ss, unit="s").dayofweek >= 5:
                continue
            # require market live around anchor (>= 60% live seconds in +-5 min)
            if live[kk - 300:kk + 300].mean() < 0.6:
                continue
            r = dict(anchor=name, date=d, sec=ss, k=kk)
            for o in OFFS:
                r[f"m{o}"] = mid[kk + o]
            for L in RANGES:
                r[f"rh{L}"] = hi[kk:kk + L].max()
                r[f"rl{L}"] = lo[kk:kk + L].min()
            r["pre_h3600"] = hi[kk - 3600:kk].max()
            r["pre_l3600"] = lo[kk - 3600:kk].min()
            # ATR proxy: mean of |hourly change| over previous 5 days, same hours
            hrs = mid[kk - 5 * 86400:kk:3600]
            dif = np.abs(np.diff(hrs))
            r["atr1h"] = float(np.nanmean(dif[dif > 0])) if (dif > 0).any() else np.nan
            r["spread0"] = ask[kk] - bid[kk]
            rows.append(r)
        print(name, sum(1 for x in rows if x["anchor"] == name), flush=True)
    df = pd.DataFrame(rows)
    df["period"] = np.where(df.date < "2026-01-01", "IS", np.where(df.date < "2026-06-01", "VAL", "OOS"))
    df.to_pickle(os.path.join(D, "anchors.pkl"))


if __name__ == "__main__":
    main()
