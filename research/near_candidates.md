# Closest candidates to the targets (WR > 75%, PF > 3, DD < 5%)

**None meets all three targets on unseen data.** These are the closest, ranked by how well they
held up across all three periods. They're for **cTrader backtesting and demo trading only**, not
live money.

Data: Dukascopy XAUUSD, 1-second bars, cTrader-equivalent costs (spread 0.30× Dukascopy, min
$0.10; $0.03 slippage per market fill; $7 per lot round-trip commission). IS = 2025,
VAL = Jan–May 2026, OOS = Jun–Oct 2026 (blind, run once after freezing). DD is at 0.5% risk per
trade, compounding.

## Summary

| # | Strategy | IS PF / WR / DD | VAL PF / WR / DD | **OOS PF / WR / DD / n** | Trades/wk | Gap to targets |
|---|---|---|---|---|---|---|
| 0 | V-Climax sweep reversal (Antigravity cBot) | in-sample only | – | cTrader tick backtest Oct 25–Oct 26: PF 3.23, WR 92% (deal legs), DD 3.9%, 63 legs | ~0.7 | Meets all three, but **never tested out of sample**: the parameters were fitted on the same 12 months. Lowest frequency. |
| 1 | Asian-range breakout | 2.13 / 62% / 1.0% | 2.40 / 63% / 0.4% | **2.11 / 69% / 0.5% / 16** | ~1–2 | WR −6 pts, PF −0.9, too few OOS trades. Most consistent PF. |
| 2 | NY initial-balance fade | 1.58 / 52% / 4.6% | 2.13 / 53% / 2.3% | **1.88 / 53% / 1.5% / 32** | ~1.7 | WR −22 pts, PF −1.1 |
| 3 | Anchored-VWAP London pullback | 1.20 / 45% / 2.4% | 1.35 / 48% / 1.1% | **1.56 / 46% / 0.8% / 61** | ~3 | WR −29 pts, PF −1.4; IS setting was a peak, not a plateau |
| P | Portfolio of 1+2+3 | 1.61 / 51% / 3.8% | 1.82 / 54% / 2.7% | **1.77 / 51% / 1.4% / 109** | ~5.5 | Steadiest overall; PF ≈ 1.6–1.8 in every period |

Excluded because they collapsed out of sample: EMA pullback + ADX (VAL PF 3.35 / WR 91%, then
OOS PF 0.99), London range→NY break (OOS 0.47), Bollinger pin-bar fade (OOS 0.52).

Drawdown is the easy target here. All three keep DD under 2% on OOS at 0.5% risk. Win rate and PF
are what's missing.

## Exact rules (frozen settings) for cTrader

All times UTC unless marked New York (NY = America/New_York, DST-aware). One trade per strategy
per day. Risk 0.5% of equity per trade, with size set from the stop distance.

### 1. Asian-range breakout (`strategies/asian_range_breakout.py`, `strategy_cards/asian_range_breakout.frozen.json`)
- **Range:** high/low of 1-minute bars 00:00–06:00 UTC. Width W = high − low.
- **Day filter:**
  - 0.2 × ATR14(daily) ≤ W ≤ 1.0 × ATR14(daily). Daily bars run 23:00–21:00 UTC; use yesterday's ATR.
  - Yesterday's realised variance (sum of squared 5-minute log returns, 00:00–21:00) is in the
    **top third** of the last 250 days.
- **Entry:** at 06:00, if price is still inside, place a buy stop at high + $2.00 and a sell stop at
  low − $2.00, active until 12:00 UTC. The first one filled cancels the other.
- **Exit:** stop = 2.0 × W from entry. Target = 1.0 × W from entry. Close everything at 16:00 UTC.

### 2. NY initial-balance fade (`strategies/ib_fade_ny.py`, `strategy_cards/ib_fade_ny.frozen.json`)
- **Initial balance (IB):** high/low of 1-minute bars from **08:20 to 08:50 New York** (COMEX open
  + 30 min). Width W.
- **Day filter:** W > 1.2 × median width of the previous 20 IBs.
- **Setup:** after the IB, a 5-minute bar trades above the IB high (or below the IB low). Track that
  probe's extreme.
- **Entry:** the first 5-minute close back inside the IB but not past its midpoint. Fade toward the
  midpoint: short after a probe above, long after a probe below. Only 5-minute bars that close
  before 18:00 UTC count.
- **Exit:**
  - d = distance from the entry close to (probe extreme + 0.1 × ATR14 on 5m).
  - Stop = 2.0 × d. Target = 3.0 × d.
  - Close at 20:00 UTC.

### 3. Anchored-VWAP London pullback (`strategies/avwap_london.py`, `strategy_cards/avwap_london.frozen.json`)
- **VWAP:** anchored at **23:00 UTC** (the session start), on 5-minute bars, weighted by tick
  volume, with σ bands.
- **Uptrend:** at least 70% of 5-minute closes since the anchor are above VWAP, and VWAP is higher
  than 12 bars ago. Downtrend is the mirror.
- **Entry (long):** signals only 08:00–20:00 UTC.
  - A bar's low touches VWAP during the uptrend.
  - Then the first bar that closes above VWAP **and** above its open triggers the entry.
  - Shorts are the mirror. Maximum 2 trades per day.
- **Exit:**
  - d = max(close − (VWAP − 1.5σ), 0.5 × ATR14 on 5m).
  - Stop = 2.0 × d. Trailing stop 1.0 × d. No fixed target.
  - Close at 20:55 UTC.

### 0. V-Climax sweep reversal
Use the existing `MV_Gold_Sub5s_VClimaxReversal_cBot.algo` and `.cbotset` from the Antigravity
folder. Its parameters are in the `.cbotset` (StructuralWindowSec 14400, MinImpulse5sUsd 3.2, …).

## Suggested cTrader backtest settings
- Symbol XAUUSD. Data: **tick data from server**. Start with the m1 chart period.
- Dates: 01/01/2025 → today. Also look at Jun–Oct 2026 on its own, which is the period these
  strategies never saw while being tuned.
- Commission $7 per lot round trip, spread from the broker. Starting balance and risk as in the
  table (0.5% per trade).
- Compare cTrader's numbers with the table. If the OOS period is much worse in cTrader, drop the
  strategy.

## Honest caveat
Candidates 1–3 are profitable in all three periods, but PF is about 1.6–1.9 and WR is 46–69%.
They are nowhere near the targets. The only thing that hits the targets, V-Climax, has never been
tested out of sample. The only clean test left is **forward demo trading** (Nov 2026 onwards).
