"""Asian-range failed-breakout fade, H1 variant (Batch B #1a). Card: marketplaces-asian-range-fakeout-h1.

ICT Judas/FVG component dropped (user excluded ICT/SMC). 15m variant: asian_range_fakeout_15m.
Range = 00:00-asian_end UTC high/low (complete before any signal). An H1 bar closes outside the
range; if a later H1 bar closes back inside within max_bars_outside bars of the first outside close,
enter at that close, opposite to the break (market). An excursion that expires while still outside
must close back inside before a new break can arm (audit re-arm fix); stop = full excursion extreme
+ stop_buf*ATR14(H1); card target = opposite side of the range or 2R, whichever is closer; time exit
exit_h UTC (card 20:00); signals until 17:00 (or exit_h); skip the day if the opposite side was closed
outside first; max 1 trade/day. unit = stop distance (R).
Card defaults: asian_end 6, max_bars_outside 3, stop_buf 0.2, exit_h 20.
"""
from strategies._bxutil import fakeout_core

PARAMS = {
    "asian_end": [5, 6, 7],
    "max_bars_outside": [1, 2, 3, 5],
    "stop_buf": [0.0, 0.1, 0.2, 0.5],
    "exit_h": [16, 20],
}
DEFAULTS = dict(asian_end=6, max_bars_outside=3, stop_buf=0.2, exit_h=20)
EXIT_UNIT = True


def signals(ctx, asian_end=6, max_bars_outside=3, stop_buf=0.2, exit_h=20):
    return fakeout_core(ctx, 3600, asian_end, max_bars_outside, stop_buf, exit_h, sig_end=17,
                        range_filter=False)
