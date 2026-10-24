"""Asian-hours drift ("hat-shaped" gold seasonality), unconditional and adaptive-sign versions.

Cards: practitioners-asia-hours-drift + academic-asian-drift-adaptive.
window "HH-HH" (UTC): enter at the open of the window, exit at its end.
  lookback = 0  -> unconditional: long for Asian windows, short for the 08-20 day leg
                   (practitioner card, default buy 00:00, exit 07:00).
  lookback > 0  -> adaptive: sign of the trailing `lookback`-day mean window return, traded only
                   if |t-stat| > t_min (academic card).
(lookback=0 ignores t_min: only t_min=1.0 returns signals, other values are empty duplicates.)
Stop: 1.0 * ATR14(D1) (prior completed UTC days); unit = that stop distance.
"""
import numpy as np, pandas as pd
import bt1s

PARAMS = {
    "lookback": [0, 60, 20, 120, 250],
    "t_min": [1.0, 0.0],
    "window": ["00-07", "00-06", "01-07", "08-20"],
}
EXIT_UNIT = True


def signals(ctx, lookback=0, t_min=1.0, window="00-07"):
    h0, h1 = (int(x) for x in window.split("-"))
    b = ctx.bars(60)
    hr = (b.index.values % 86400) // 60  # minute of UTC day
    day = b.index.values // 86400
    # entry decision: close of the last 1m bar before h0 (within 10 min) else first bar after h0 open
    m0 = (hr >= h0 * 60) & (hr < h0 * 60 + 10)
    ent = pd.DataFrame(dict(day=day[m0], sec=b.index.values[m0] - 1, o=b.o.values[m0])).groupby("day").first()
    # entry decision second = open second of first bar in window minus 1 (fill at bar's first second)
    m1 = (hr >= h1 * 60 - 10) & (hr < h1 * 60)
    ex = pd.DataFrame(dict(day=day[m1], c=b.c.values[m1])).groupby("day").last()
    df = ent.join(ex, how="inner")
    df["r"] = np.log(df.c / df.o)
    d = ctx.bars(86400)
    atr_d = pd.Series(bt1s.atr(d, 14), index=d.index.values // 86400).shift(1)  # prior completed days
    df["atr"] = atr_d.reindex(df.index).values
    df = df.dropna(subset=["atr"])
    if lookback == 0 and t_min != PARAMS["t_min"][0]:
        return pd.DataFrame(columns=["sec", "side", "sl", "tp", "hold", "unit"])  # duplicate of t_min default
    if lookback == 0:
        side = np.full(len(df), -1 if h0 >= 8 else 1)
        keep = np.ones(len(df), bool)
    else:
        past = df.r.shift(1)
        mu = past.rolling(lookback, min_periods=max(10, lookback // 2)).mean()
        sd = past.rolling(lookback, min_periods=max(10, lookback // 2)).std()
        n = past.rolling(lookback, min_periods=max(10, lookback // 2)).count()
        t = mu / (sd / np.sqrt(n))
        side = np.sign(mu).fillna(0).values.astype(int)
        keep = (t.abs() > t_min).values & (side != 0)
    s = df[keep]
    side = side[keep]
    hold = np.full(len(s), (h1 - h0) * 3600 - 60)
    stop = 1.0 * s.atr.values
    return pd.DataFrame(dict(sec=s.sec.values.astype(np.int64), side=side, sl=stop, tp=0.0,
                             hold=hold.astype(np.int64), unit=stop))
