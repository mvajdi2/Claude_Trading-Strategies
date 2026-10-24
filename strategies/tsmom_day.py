"""Daily trend sign held intraday only, with a realised-semivariance reversal filter.

Card: academic-tsmom-daysession-volscaled.
Daily close = last 1h close before 21:00 UTC. At session_start (UTC hour) trade
sign(EMA_fast - EMA_slow) of daily closes up to the previous day, skipped if RS_share > rs_th, where
RS_share = semivariance of 5m returns against the trend direction / total variance over the
previous 5 full days (>= 12 h of bars). Stop 1.5 * ATR14(1h) * sqrt(14); exit 20:55 UTC. unit = stop distance.
(Vol-targeted sizing in the card is replaced by the engine's fixed-fractional risk.)
"""
import numpy as np, pandas as pd
import bt1s

PARAMS = {
    "fast_slow": ["20_100", "10_50", "50_200"],
    "rs_th": [0.6, 0.5, 0.7, 1.0],
    "session_start": [7, 0],
}
EXIT_UNIT = True


def signals(ctx, fast_slow="20_100", rs_th=0.6, session_start=7):
    f, s_ = (int(x) for x in fast_slow.split("_"))
    h = ctx.bars(3600)
    hd = h.index.values // 86400
    hh = (h.index.values % 86400) // 3600
    dc = h[hh <= 20].groupby(hd[hh <= 20]).c.last()            # daily close at 21:00 UTC
    trend = pd.Series(bt1s.ema(dc.values, f) - bt1s.ema(dc.values, s_), index=dc.index)
    trend[np.arange(len(trend)) < s_] = np.nan                    # warm-up
    b5 = ctx.bars(300)
    r5 = np.log(b5.c).diff()
    d5 = b5.index.values // 86400
    full = pd.Series(1, index=d5).groupby(d5).size() >= 144          # >= 12 h of 5m bars
    neg = (r5.clip(upper=0) ** 2).groupby(d5).sum()[full]
    pos = (r5.clip(lower=0) ** 2).groupby(d5).sum()[full]
    neg5 = neg.rolling(5).sum(); pos5 = pos.rolling(5).sum()
    a1 = pd.Series(bt1s.atr(h, 14), index=h.index)
    # decision at the close of the 1h bar ending at session_start (bar start = session_start-1)
    dec = h[hh == (session_start - 1) % 24]
    dday = dec.index.values // 86400 + (1 if session_start == 0 else 0)
    df = pd.DataFrame(dict(day=dday, sec=dec.close_sec.values, atr=a1.reindex(dec.index).values))
    prev = df.day - 1
    # previous completed day values (map through the last available day < current day)
    tr_s = trend.reindex(range(int(df.day.min()) - 10, int(df.day.max()) + 1)).ffill()
    df["trend"] = tr_s.reindex(prev).values
    n5 = neg5.reindex(range(int(df.day.min()) - 10, int(df.day.max()) + 1)).ffill()
    p5 = pos5.reindex(range(int(df.day.min()) - 10, int(df.day.max()) + 1)).ffill()
    df["neg"] = n5.reindex(prev).values; df["pos"] = p5.reindex(prev).values
    df = df.dropna()
    side = np.sign(df.trend.values).astype(int)
    against = np.where(side > 0, df.neg.values, df.pos.values)
    rs = against / (df.neg.values + df.pos.values)
    keep = (side != 0) & (rs <= rs_th) & (pd.to_datetime(df.day * 86400, unit="s").dt.dayofweek < 5).values
    df = df[keep]; side = side[keep]
    stop = 1.5 * df.atr.values * np.sqrt(14)
    sec = df.sec.values.astype(np.int64)
    exit_sec = (df.day.values.astype(np.int64)) * 86400 + 20 * 3600 + 55 * 60   # 20:55 UTC of the trade day
    hold = (exit_sec - sec).astype(np.int64)
    return pd.DataFrame(dict(sec=df.sec.values.astype(np.int64), side=side, sl=stop, tp=0.0,
                             hold=hold, unit=stop))
