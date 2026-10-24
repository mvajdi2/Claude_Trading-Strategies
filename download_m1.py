#!/usr/bin/env python3
"""Download Dukascopy 1-minute BID candles for cross-asset symbols (daily .bi5 files) and save
data/m1/<SYMBOL>.npz with ts (epoch s, minute start), o, h, l, c (float64), v (float32).

Usage: python3 download_m1.py EURUSD XAGUSD USDJPY USATECHIDXUSD BRENTCMDUSD USA500IDXUSD
"""
import os, sys, lzma, time, datetime as dt, threading
from concurrent.futures import ThreadPoolExecutor
import numpy as np, requests

ROOT = os.path.dirname(os.path.abspath(__file__))
RAW = os.path.join(ROOT, "data", "m1raw")
OUT = os.path.join(ROOT, "data", "m1")
START, END = dt.date(2024, 12, 1), dt.date(2026, 10, 23)
REC = np.dtype([("t", ">u4"), ("o", ">u4"), ("c", ">u4"), ("l", ">u4"), ("h", ">u4"), ("v", ">f4")])
# Dukascopy integer price scale per symbol
SCALE = {"EURUSD": 1e5, "XAGUSD": 1e3, "USDJPY": 1e3, "USATECHIDXUSD": 1e3, "USA500IDXUSD": 1e3,
         "BRENTCMDUSD": 1e3, "XAUUSD": 1e3, "DOLLARIDXUSD": 1e3, "USTBONDTRUSD": 1e3}
local = threading.local()


def sess():
    if getattr(local, "s", None) is None:
        local.s = requests.Session(); local.s.headers["User-Agent"] = "Mozilla/5.0"
    return local.s


def fetch(sym, d):
    p = os.path.join(RAW, sym, f"{d:%Y%m%d}.bi5")
    if os.path.exists(p):
        return
    url = f"https://datafeed.dukascopy.com/datafeed/{sym}/{d.year}/{d.month-1:02d}/{d.day:02d}/BID_candles_min_1.bi5"
    delay = 2
    for _ in range(20):
        try:
            r = sess().get(url, timeout=(15, 30))
            if r.status_code in (200, 404):
                with open(p + ".tmp", "wb") as f:
                    f.write(r.content if r.status_code == 200 else b"")
                os.replace(p + ".tmp", p)
                return
        except Exception:
            local.s = None
        time.sleep(delay); delay = min(delay * 1.5, 20)


def build(sym):
    files = sorted(os.listdir(os.path.join(RAW, sym)))
    parts = []
    for f in files:
        raw = open(os.path.join(RAW, sym, f), "rb").read()
        if not raw:
            continue
        a = np.frombuffer(lzma.decompress(raw), dtype=REC)
        base = int(dt.datetime.strptime(f[:8], "%Y%m%d").replace(tzinfo=dt.timezone.utc).timestamp())
        parts.append((base + a["t"].astype(np.int64), a))
    ts = np.concatenate([p[0] for p in parts]); a = np.concatenate([p[1] for p in parts])
    sc = SCALE.get(sym, 1e3)
    keep = a["v"] > 0          # flat minutes (market closed) carry zero volume
    np.savez(os.path.join(OUT, f"{sym}.npz"), ts=ts[keep],
             o=a["o"][keep] / sc, h=a["h"][keep] / sc, l=a["l"][keep] / sc, c=a["c"][keep] / sc,
             v=a["v"][keep].astype(np.float32))
    print(sym, keep.sum(), "minutes; last close", a["c"][keep][-1] / sc, flush=True)


def main(syms):
    os.makedirs(OUT, exist_ok=True)
    days = [START + dt.timedelta(i) for i in range((END - START).days + 1)]
    days = [d for d in days if d.weekday() != 5]
    for sym in syms:
        os.makedirs(os.path.join(RAW, sym), exist_ok=True)
        with ThreadPoolExecutor(8) as ex:
            list(ex.map(lambda d: fetch(sym, d), days))
        build(sym)


if __name__ == "__main__":
    main(sys.argv[1:])
