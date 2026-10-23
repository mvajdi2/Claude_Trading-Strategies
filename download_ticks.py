#!/usr/bin/env python3
"""Download Dukascopy XAUUSD hourly tick files (.bi5) with throttling + retries."""
import os, sys, time, datetime as dt, threading
import requests
from concurrent.futures import ThreadPoolExecutor

SYM = "XAUUSD"
OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data", "bi5")
START = dt.datetime(2025, 1, 1)
END = dt.datetime(2026, 10, 23)
WORKERS = int(os.environ.get("WORKERS", 4))

lock = threading.Lock()
stats = {"ok": 0, "empty": 0, "skip": 0, "fail": 0}

def hours():
    t = START
    while t < END:
        wd = t.weekday()  # Sat closed; Fri after 21h & Sun before 21h mostly closed
        if not (wd == 5 or (wd == 4 and t.hour >= 22) or (wd == 6 and t.hour < 21)):
            yield t
        t += dt.timedelta(hours=1)

local = threading.local()

def session():
    if getattr(local, "s", None) is None:
        local.s = requests.Session()
        local.s.headers["User-Agent"] = "Mozilla/5.0"
    return local.s

def path_for(t):
    return os.path.join(OUT, f"{t:%Y%m%d_%H}.bi5")

def fetch(t):
    p = path_for(t)
    if os.path.exists(p):
        with lock: stats["skip"] += 1
        return
    url = f"https://datafeed.dukascopy.com/datafeed/{SYM}/{t.year}/{t.month-1:02d}/{t.day:02d}/{t.hour:02d}h_ticks.bi5"
    delay = 2.0
    for _ in range(25):
        r = None
        try:
            r = session().get(url, timeout=(15, 30))
            if r.status_code == 200:
                tmp = p + ".tmp"
                with open(tmp, "wb") as f: f.write(r.content)
                os.replace(tmp, p)
                with lock: stats["ok" if r.content else "empty"] += 1
                return
            if r.status_code == 404:
                open(p, "wb").close()
                with lock: stats["empty"] += 1
                return
        except Exception:
            local.s = None
        local.s = None if r is None or r.status_code >= 500 else local.s
        time.sleep(delay); delay = min(delay * 1.5, 20)
    with lock: stats["fail"] += 1

def main():
    hs = list(hours())
    print(f"{len(hs)} hourly files to fetch", flush=True)
    t0 = time.time()
    with ThreadPoolExecutor(WORKERS) as ex:
        futs = [ex.submit(fetch, h) for h in hs]
        for i, _ in enumerate(__import__("concurrent.futures").futures.as_completed(futs), 1):
            if i % 100 == 0:
                print(f"{i}/{len(hs)} {stats} {time.time()-t0:.0f}s", flush=True)
    print("DONE", stats, flush=True)

if __name__ == "__main__":
    main()
