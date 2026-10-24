"""Asian-range false-break fade, 15m variant (Batch B #1b). Card: practitioners-asian-range-false-break-fade.

Same mechanics as asian_range_fakeout (shared fakeout_core) on 15m closes: range 00:00-asian_end
UTC; first 15m close outside, then a 15m close back inside within max_bars_outside bars -> enter at
that close (market). Stop = full excursion extreme + stop_buf*ATR14(15m); card target = opposite
side or 2R if closer; time exit exit_h UTC (card 16:00); signals 06:00-16:00; range filter: skip if
Asian range > 1.5*ATR14(1h)*6; max 1 trade/day. unit = stop distance (R).
Card defaults: asian_end 6, max_bars_outside 8, stop_buf 0.1, exit_h 16, range_filter True.
"""
from strategies._bxutil import fakeout_core

PARAMS = {
    "asian_end": [5, 6, 7],
    "max_bars_outside": [4, 8, 16],
    "stop_buf": [0.0, 0.1, 0.2],
    "exit_h": [16, 20],
    "range_filter": [False, True],
}
DEFAULTS = dict(asian_end=6, max_bars_outside=8, stop_buf=0.1, exit_h=16, range_filter=True)
EXIT_UNIT = True


def signals(ctx, asian_end=6, max_bars_outside=8, stop_buf=0.1, exit_h=16, range_filter=True):
    return fakeout_core(ctx, 900, asian_end, max_bars_outside, stop_buf, exit_h, sig_end=16,
                        range_filter=range_filter)
