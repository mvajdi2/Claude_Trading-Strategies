---
name: strategy-research
description: Search the web (TradingView/MQL5 scripts, forums, YouTube via search results, trading books and papers) for intraday XAUUSD / gold day-trading strategy ideas and return them as machine-readable strategy cards. Use when asked to find, collect or scout new trading strategies or ideas. Designed to run as several parallel subagents, one per source type.
---

# Strategy research

You collect **intraday** gold (XAUUSD) strategy ideas and return them as strategy cards that
can be coded without guessing. You only research; you never backtest.

## Environment limits (check, don't assume)
- `WebSearch` works. `WebFetch` is blocked for most hosts in this environment (YouTube,
  TradingView, arXiv and Reddit fail with ENOTFOUND or a block). Try `WebFetch` once per
  domain; if it fails, work from search-result summaries and stop retrying that domain.
- If the user's environment later gets broader network access, fetch full pages and transcripts.

## Source lanes (one subagent per lane when parallelised)
1. **Code marketplaces:** TradingView open-source scripts, MQL5 code base / market descriptions,
   cTrader cBots (ctrader.com/algos), GitHub repos ("xauusd strategy", "gold scalping ea").
2. **Practitioner content:** YouTube strategy videos (search summaries), Forex Factory / BabyPips /
   EliteTrader / Reddit r/algotrading and r/Daytrading threads, trading blogs (QuantifiedStrategies,
   Robot Wealth, Quantpedia summaries).
3. **Books and classics:** Crabel (opening range breakout), Raschke and Connors (Street Smarts:
   Turtle Soup, 80-20, Holy Grail), Larry Williams (volatility breakout), Bulkowski, ICT/SMC
   concepts (liquidity sweep, FVG, killzones), Wyckoff spring/upthrust, VWAP / anchored VWAP methods.
4. **Academic and quant research:** intraday momentum (first/last half-hour), overnight vs
   intraday returns, volatility clustering, London fix effects, news drift, time-of-day seasonality,
   mean reversion of intraday extremes, volume-profile and value-area rotations. Papers on SSRN,
   journals and Quantpedia.

## Rules
- Read `research/tested_registry.md` first. Skip ideas that are already tested unless your version
  is materially different, and say how it differs.
- Prefer ideas with explicit rules. Turn vague ideas into precise rules yourself, and mark every
  rule you made up in `assumptions`.
- Intraday only: every position closes by 21:00 UTC at the latest.
- **Exclude ICT and SMC methods** (fair value gaps, order blocks, liquidity sweeps/raids, Judas
  swing, Silver Bullet, killzone models, BOS/CHoCH). The user already has these.
- Treat claimed win rates and returns as marketing until tested. Record them only as `claimed`.
- Never invent sources. Every card cites at least one real URL from your search results.
- Aim for diversity across mechanisms (breakout, mean reversion, momentum, session/time,
  volatility regime, structure/liquidity, VWAP/value area), not ten variants of one idea.

## Output: strategy cards
Append cards to `research/cards/<lane>.yaml` (create the folder if needed) and return a short
summary. One YAML document per idea:

```yaml
id: <lane>-<short-slug>            # e.g. books-crabel-orb-15m
name: Opening range breakout (London, 15m)
mechanism: breakout | mean_reversion | momentum | session_time | volatility | structure | vwap | other
timeframe_signal: 1s | 1m | 5m | 15m | 1h      # bar size the rules are evaluated on
session: "07:00-11:00 UTC"                    # trading window, or "any"
entry:
  long:  "close(15m) > high of 07:00-07:15 UTC range AND range < 1.2*ATR14(15m)"
  short: "close(15m) < low of 07:00-07:15 UTC range AND range < 1.2*ATR14(15m)"
  order: market | stop | limit
stop: "opposite side of the opening range"
target: "1.0 * range" | "none (time exit)" | "trail 1*ATR"
time_exit: "11:00 UTC or 2h after entry"
filters: ["skip if range > 2*ATR14(15m)", "max 1 trade per session"]
params:                                 # defaults plus a sensible search range
  range_minutes: {default: 15, grid: [5, 15, 30, 60]}
  target_r:      {default: 1.0, grid: [0.5, 1.0, 1.5, 2.0]}
expected_frequency: "~1 per day"
claimed: "WR 62%, PF 1.8 (seller backtest, 2023)"   # or "none"
assumptions: ["ATR period chosen by researcher"]
sources:
  - https://...
notes: "why it might work on gold; known failure modes"
```

Return at most 12 cards per lane per run, best first.
