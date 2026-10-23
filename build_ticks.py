#!/usr/bin/env python3
"""Decode Dukascopy .bi5 hourly tick files into monthly tick arrays.

Output: data/ticks/ticks_YYYYMM.npz with
    ts   int64   epoch milliseconds (UTC)
    bid  int32   price in 0.001 USD
    ask  int32   price in 0.001 USD
Cleaning:
    - drop crossed / zero quotes and spreads > $3.00
    - drop isolated spikes: mid jumps > $4 from both neighbours and reverts
"""
import os, sys, glob, lzma, datetime as dt
import numpy as np

ROOT = os.path.dirname(os.path.abspath(__file__))
SRC = os.path.join(ROOT, "data", "bi5")
DST = os.path.join(ROOT, "data", "ticks")
REC = np.dtype([("ms", ">u4"), ("ask", ">u4"), ("bid", ">u4"), ("av", ">f4"), ("bv", ">f4")])
EPOCH = dt.datetime(1970, 1, 1)


def decode(path):
    raw = open(path, "rb").read()
    if not raw:
        return None
    a = np.frombuffer(lzma.decompress(raw), dtype=REC)
    name = os.path.basename(path)[:-4]
    t0 = dt.datetime.strptime(name, "%Y%m%d_%H")
    base = int((t0 - EPOCH).total_seconds() * 1000)
    return base + a["ms"].astype(np.int64), a["bid"].astype(np.int32), a["ask"].astype(np.int32)


def clean(ts, bid, ask):
    ok = (bid > 0) & (ask >= bid) & ((ask - bid) <= 3000)
    ts, bid, ask = ts[ok], bid[ok], ask[ok]
    mid = (bid.astype(np.int64) + ask) // 2
    if len(mid) > 2:
        d_prev = np.abs(mid[1:-1] - mid[:-2])
        d_next = np.abs(mid[1:-1] - mid[2:])
        d_span = np.abs(mid[2:] - mid[:-2])
        spike = (d_prev > 4000) & (d_next > 4000) & (d_span < 1000)
        keep = np.ones(len(mid), bool)
        keep[1:-1] = ~spike
        ts, bid, ask = ts[keep], bid[keep], ask[keep]
    order = np.argsort(ts, kind="stable")
    return ts[order], bid[order], ask[order]


def main():
    os.makedirs(DST, exist_ok=True)
    files = sorted(glob.glob(os.path.join(SRC, "*.bi5")))
    months = sorted({os.path.basename(f)[:6] for f in files})
    force = "--force" in sys.argv
    for m in months:
        out = os.path.join(DST, f"ticks_{m}.npz")
        if os.path.exists(out) and not force:
            continue
        parts = [decode(f) for f in files if os.path.basename(f).startswith(m)]
        parts = [p for p in parts if p is not None]
        if not parts:
            continue
        ts = np.concatenate([p[0] for p in parts])
        bid = np.concatenate([p[1] for p in parts])
        ask = np.concatenate([p[2] for p in parts])
        n0 = len(ts)
        ts, bid, ask = clean(ts, bid, ask)
        np.savez(out, ts=ts, bid=bid, ask=ask)
        print(f"{m}: {n0:,} ticks -> {len(ts):,} kept", flush=True)


if __name__ == "__main__":
    main()
