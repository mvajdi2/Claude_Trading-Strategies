"""London open -> PM fix, conditioned on the Asian-session move (fade or follow).

Card: academic-london-pmfix-short.
At 07:00 London (DST-aware): r_asia = ln(P(07:00 London) / P(00:00 UTC)); sigma = stdev of the
previous 60 r_asia values. If |r_asia| > a * sigma:
  fade   : trade against r_asia (card default: short after a strong Asia)
  follow : trade with r_asia
Stop: beyond the Asian extreme on the protective side + 0.25 * ATR14(D1) (min 0.25 ATR).
Time exit: 15:00 London (PM auction), 10:30 London (AM fix) or 20:55 UTC. unit = stop distance.
"""
import numpy as np, pandas as pd
import bt1s

LON = "Europe/London"

PARAMS = {
    "a": [0.5, 0.0, 1.0, 1.5],
    "exit_at": ["15:00", "10:30", "close"],
    "direction_mode": ["fade", "follow"],
}
EXIT_UNIT = True


def _epoch(local_naive, tz):
    t = pd.DatetimeIndex(local_naive).tz_localize(tz, ambiguous="NaT", nonexistent="NaT").tz_convert("UTC")
    return np.asarray((t - pd.Timestamp(0, tz="UTC")) // pd.Timedelta(seconds=1), dtype=np.float64)


def signals(ctx, a=0.5, exit_at="15:00", direction_mode="fade"):
    b = ctx.bars(60)
    sec = b.index.values
    day = sec // 86400
    # 07:00 London in UTC epoch for each UTC day
    days = np.unique(day)
    dts = pd.to_datetime(days * 86400, unit="s")
    t_ent = _epoch(dts + pd.Timedelta(hours=7), LON).astype(np.int64)
    ent_by_day = pd.Series(t_ent, index=days)
    te = ent_by_day.reindex(day).values
    mn = (sec % 86400) // 60
    asia = (mn >= 0) & (sec < te)                       # 00:00 UTC -> 07:00 London
    g = pd.DataFrame(dict(day=day[asia], o=b.o.values[asia], h=b.h.values[asia], l=b.l.values[asia],
                          c=b.c.values[asia], cs=b.close_sec.values[asia], n=1))
    g = g.groupby("day").agg(o=("o", "first"), h=("h", "max"), l=("l", "min"), c=("c", "last"),
                             cs=("cs", "last"), n=("n", "sum"))
    g = g[g.n >= 240]
    g["te"] = ent_by_day.reindex(g.index).values
    g = g[(g.te - 1 - g.cs) <= 300]                    # last Asian bar must close right before entry
    d = ctx.bars(86400)
    atr_d = pd.Series(bt1s.atr(d, 14), index=d.index.values // 86400).shift(1)
    g["atr"] = atr_d.reindex(g.index).values
    g["r"] = np.log(g.c / g.o)
    g["sig"] = g.r.rolling(60, min_periods=40).std().shift(1)
    g = g.dropna(subset=["atr", "sig"])
    g = g[(g.r.abs() > a * g.sig) & (g.r != 0)]
    side = np.sign(g.r.values).astype(int)
    if direction_mode == "fade":
        side = -side
    px = g.c.values
    stop = np.where(side == -1, g.h.values + 0.25 * g.atr.values - px, px - (g.l.values - 0.25 * g.atr.values))
    stop = np.maximum(stop, 0.25 * g.atr.values)
    dsec = (g.te.values - 1).astype(np.int64)
    if exit_at == "close":
        hold = ((dsec // 86400) * 86400 + 20 * 3600 + 55 * 60 - dsec).astype(np.int64)
    else:
        hh, mm = (int(x) for x in exit_at.split(":"))
        dts_g = pd.to_datetime(g.index.values * 86400, unit="s")
        hold = (_epoch(dts_g + pd.Timedelta(minutes=hh * 60 + mm), LON) - dsec).astype(np.int64)
    return pd.DataFrame(dict(sec=dsec, side=side, sl=stop, tp=0.0, hold=hold, unit=stop))
