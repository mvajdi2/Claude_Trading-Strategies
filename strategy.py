"""FROZEN strategy definition (VCSR-HF: sub-5s V-Climax Sweep Reversal, high-frequency variant).
Frozen on 2026-10-23 before the out-of-sample test. Do not tune on OOS results.
"""
import numpy as np, pandas as pd

# ---- signal ----
IMP_MIN_USD = 2.0        # 5s impulse size, USD
IMP_MIN_SIG = 2.5        # impulse / (sigma_1s(300s) * sqrt(dur))
RETRACE_MIN = 0.30       # share of impulse already rejected at the signal second
IMB_REJ_MIN = 0.20       # tick imbalance in the reversal direction during the rejection
SPREAD_RATIO_MIN = 1.4   # max spread during impulse / mean spread previous 300s
SESSION_HOURS = (7, 19)  # UTC hour inclusive (07:00-19:59)
COOLDOWN_S = 120

# level-sweep variants (either qualifies)
#   A: extreme beyond prior 15-min high/low, impulse >= 2.0 x std900
#   B: extreme beyond prior 30-min high/low by >= 0.3 x impulse, impulse >= 1.5 x std900

# ---- exit (multiples of the impulse size) ----
EXIT = dict(sl_m=4.0, tp1_m=0.25, f1=0.5, tp2_m=2.5, be=True, trail_m=0.0, hold_s=900)


def signal_mask(d: pd.DataFrame) -> pd.Series:
    a = (d.sw900_n > 0) & (d.imp_rel >= 2.0)
    b = (d.sw1800_n > 0.3) & (d.imp_rel >= 1.5)
    return ((a | b) & (d.spread_ratio >= SPREAD_RATIO_MIN) & d.hour.between(*SESSION_HOURS)
            & (d.imb_rej >= IMB_REJ_MIN) & (d.imp >= IMP_MIN_USD) & (d.retrace >= RETRACE_MIN)
            & (d.imp_sig >= IMP_MIN_SIG))
