// =================================================================================================
// VClimaxSweepReversal.cs  -  cTrader Automate cBot (C# / .NET 6)
// Standards-compliant upgrade of cbots/reference/MV_Gold_Sub5s_VClimaxReversal_cBot.cs
// (signal reference: cbots/reference/gold_sub5s_reversal_engine.py, detect_v_climax_signals + arch1/arch2).
//
// Signal and exit logic and every original default are unchanged (the configuration behind the cTrader
// tick backtest PF 3.23, cbots/reference/ctrader_cli_12m_ticks_summary.json). Bugs fixed and standard
// features added are listed in cbots/docs/VClimaxSweepReversal.md ("Diff vs original").
//
// Mechanics (1-second mid bars built from ticks, decision when the second closes, entry on the next tick):
//   imp5 >= max(MinImpulse5sUsd, MinImpulseStdMult * s3600), sweep of the W-second structural extreme
//   (shifted 6 s) by > MinSweepUsd, >= MinRejectionRatio of the impulse rejected, close back inside by
//   > MinReEntryUsd on a confirmed 1-second turn bar; volatility gates s900/s3600/s14400; 4h z-score
//   exhaustion aligned with m3600 vs m14400. Exits in multiples of scale = max(s900, MinScaleUsd).
// =================================================================================================

using System;
using System.Collections.Generic;
using cAlgo.API;
using cAlgo.API.Internals;

namespace cAlgo.Robots
{
    [Robot(AccessRights = AccessRights.None, TimeZone = TimeZones.UTC)]
    public class VClimaxSweepReversal : Robot
    {
        public enum RiskModeType { PercentOfEquity, FixedLots, FixedCash }
        public enum SizingBasisType { StopDistance, LegacyScale }

        // ---------------------------------------------------------------- 1. Identity
        [Parameter("Label", Group = "1. Identity", DefaultValue = "VCSR_XAUUSD-CH")]
        public string Label { get; set; }

        [Parameter("Trade Comment", Group = "1. Identity", DefaultValue = "Sub5s_VClimaxSweep")]
        public string TradeComment { get; set; }

        // ---------------------------------------------------------------- 2. Risk & sizing
        [Parameter("Risk Mode", Group = "2. Risk & Sizing", DefaultValue = RiskModeType.PercentOfEquity)]
        public RiskModeType RiskMode { get; set; }

        [Parameter("Risk % of Equity", Group = "2. Risk & Sizing", DefaultValue = 0.5, MinValue = 0.1, MaxValue = 5.0, Step = 0.1)]
        public double RiskPercent { get; set; }

        [Parameter("Sizing Basis (risk measured on)", Group = "2. Risk & Sizing", DefaultValue = SizingBasisType.StopDistance)]
        public SizingBasisType SizingBasis { get; set; }

        [Parameter("Fixed Lots", Group = "2. Risk & Sizing", DefaultValue = 0.10, MinValue = 0.01, MaxValue = 20.0, Step = 0.01)]
        public double FixedLots { get; set; }

        [Parameter("Fixed Cash Risk", Group = "2. Risk & Sizing", DefaultValue = 500.0, MinValue = 10.0, MaxValue = 10000.0, Step = 10.0)]
        public double FixedCashRisk { get; set; }

        [Parameter("Max Lots", Group = "2. Risk & Sizing", DefaultValue = 20.0, MinValue = 0.01, MaxValue = 50.0, Step = 0.01)]
        public double MaxLots { get; set; }

        // ---------------------------------------------------------------- 3. Account protection
        [Parameter("Max Spread Filter (USD)", Group = "3. Account Protection", DefaultValue = 0.35, MinValue = 0.10, MaxValue = 1.50, Step = 0.05)]
        public double MaxSpreadUsd { get; set; }

        [Parameter("Max Daily Loss % (0 = off)", Group = "3. Account Protection", DefaultValue = 3.0, MinValue = 0.0, MaxValue = 10.0, Step = 0.5)]
        public double MaxDailyLossPercent { get; set; }

        [Parameter("Close All On Daily Loss", Group = "3. Account Protection", DefaultValue = false)]
        public bool CloseAllOnDailyLoss { get; set; }

        [Parameter("Max Trades Per Day (0 = off)", Group = "3. Account Protection", DefaultValue = 0, MinValue = 0, MaxValue = 20, Step = 1)]
        public int MaxTradesPerDay { get; set; }

        [Parameter("Max Open Positions", Group = "3. Account Protection", DefaultValue = 1, MinValue = 1, MaxValue = 5, Step = 1)]
        public int MaxOpenPositions { get; set; }

        [Parameter("Cooldown Seconds (since last entry)", Group = "3. Account Protection", DefaultValue = 180, MinValue = 30, MaxValue = 3600, Step = 30)]
        public int CooldownSeconds { get; set; }

        [Parameter("Cooldown Minutes After Close", Group = "3. Account Protection", DefaultValue = 0, MinValue = 0, MaxValue = 240, Step = 5)]
        public int CooldownMinutes { get; set; }

        [Parameter("Max Signal Latency Sec (0 = off)", Group = "3. Account Protection", DefaultValue = 0, MinValue = 0, MaxValue = 10, Step = 1)]
        public int MaxSignalLatencySec { get; set; }

        // ---------------------------------------------------------------- 4. Session & calendar
        [Parameter("Liquid Hours Only", Group = "4. Session & Calendar", DefaultValue = true)]
        public bool LiquidHoursOnly { get; set; }

        [Parameter("Session Start Hour UTC (incl.)", Group = "4. Session & Calendar", DefaultValue = 6, MinValue = 0, MaxValue = 23, Step = 1)]
        public int SessionStartHourUtc { get; set; }

        [Parameter("Session End Hour UTC (incl.)", Group = "4. Session & Calendar", DefaultValue = 20, MinValue = 0, MaxValue = 23, Step = 1)]
        public int SessionEndHourUtc { get; set; }

        [Parameter("Force Flat Enabled", Group = "4. Session & Calendar", DefaultValue = false)]
        public bool ForceFlatEnabled { get; set; }

        [Parameter("Force Flat Hour UTC", Group = "4. Session & Calendar", DefaultValue = 20, MinValue = 0, MaxValue = 23, Step = 1)]
        public int ForceFlatHourUtc { get; set; }

        [Parameter("Force Flat Minute", Group = "4. Session & Calendar", DefaultValue = 55, MinValue = 0, MaxValue = 59, Step = 5)]
        public int ForceFlatMinute { get; set; }

        [Parameter("Trade Monday", Group = "4. Session & Calendar", DefaultValue = true)]
        public bool TradeMonday { get; set; }

        [Parameter("Trade Tuesday", Group = "4. Session & Calendar", DefaultValue = true)]
        public bool TradeTuesday { get; set; }

        [Parameter("Trade Wednesday", Group = "4. Session & Calendar", DefaultValue = true)]
        public bool TradeWednesday { get; set; }

        [Parameter("Trade Thursday", Group = "4. Session & Calendar", DefaultValue = true)]
        public bool TradeThursday { get; set; }

        [Parameter("Trade Friday", Group = "4. Session & Calendar", DefaultValue = true)]
        public bool TradeFriday { get; set; }

        // ---------------------------------------------------------------- 5. Strategy signal
        [Parameter("Structural Window Seconds", Group = "5. Sub-5s Reversal Signal", DefaultValue = 14400, MinValue = 1800, MaxValue = 14400, Step = 1800)]
        public int StructuralWindowSec { get; set; }

        [Parameter("Min 5s Impulse (USD)", Group = "5. Sub-5s Reversal Signal", DefaultValue = 3.20, MinValue = 2.00, MaxValue = 10.00, Step = 0.20)]
        public double MinImpulse5sUsd { get; set; }

        [Parameter("Min 5s Impulse / 1H StdDev", Group = "5. Sub-5s Reversal Signal", DefaultValue = 0.35, MinValue = 0.20, MaxValue = 1.00, Step = 0.05)]
        public double MinImpulseStdMult { get; set; }

        [Parameter("Min Rejection Ratio", Group = "5. Sub-5s Reversal Signal", DefaultValue = 0.60, MinValue = 0.40, MaxValue = 0.90, Step = 0.05)]
        public double MinRejectionRatio { get; set; }

        [Parameter("Min Structural Sweep (USD)", Group = "5. Sub-5s Reversal Signal", DefaultValue = 0.10, MinValue = 0.05, MaxValue = 1.00, Step = 0.05)]
        public double MinSweepUsd { get; set; }

        [Parameter("Min Re-Entry Inside Level (USD)", Group = "5. Sub-5s Reversal Signal", DefaultValue = 0.15, MinValue = 0.05, MaxValue = 1.00, Step = 0.05)]
        public double MinReEntryUsd { get; set; }

        [Parameter("Min 15m StdDev Floor (USD)", Group = "5. Volatility & Climax Gates", DefaultValue = 5.00, MinValue = 2.00, MaxValue = 15.00, Step = 0.50)]
        public double MinStd900 { get; set; }

        [Parameter("Min 1H StdDev Floor (USD)", Group = "5. Volatility & Climax Gates", DefaultValue = 7.50, MinValue = 3.00, MaxValue = 20.00, Step = 0.50)]
        public double MinStd3600 { get; set; }

        [Parameter("Max s900/s3600 (Anti-News)", Group = "5. Volatility & Climax Gates", DefaultValue = 1.00, MinValue = 0.70, MaxValue = 1.50, Step = 0.05)]
        public double MaxRatio900To3600 { get; set; }

        [Parameter("Min s3600/s14400 (Anti-Box)", Group = "5. Volatility & Climax Gates", DefaultValue = 0.35, MinValue = 0.20, MaxValue = 0.80, Step = 0.05)]
        public double MinRatio3600To14400 { get; set; }

        [Parameter("Min 4H Climax Z-Score", Group = "5. Volatility & Climax Gates", DefaultValue = 1.50, MinValue = 1.00, MaxValue = 3.00, Step = 0.10)]
        public double MinZ14400 { get; set; }

        // ---------------------------------------------------------------- 6. Exit management (multiples of scale = max(s900, MinScaleUsd))
        [Parameter("Use Arch 2 Cushion+Ratchet Runner", Group = "6. Exit Management", DefaultValue = true)]
        public bool UseCushionRatchetRunner { get; set; }

        [Parameter("Min Scale (USD floor on s900)", Group = "6. Exit Management", DefaultValue = 4.50, MinValue = 2.00, MaxValue = 8.00, Step = 0.50)]
        public double MinScaleUsd { get; set; }

        [Parameter("TP1 Multiple of s900", Group = "6. Exit Management", DefaultValue = 0.70, MinValue = 0.40, MaxValue = 2.00, Step = 0.05)]
        public double Tp1Mult { get; set; }

        [Parameter("TP2 Multiple of s900 (Runner)", Group = "6. Exit Management", DefaultValue = 2.20, MinValue = 1.00, MaxValue = 5.00, Step = 0.10)]
        public double Tp2Mult { get; set; }

        [Parameter("Initial SL Multiple of s900", Group = "6. Exit Management", DefaultValue = 5.50, MinValue = 2.00, MaxValue = 8.00, Step = 0.25)]
        public double SlMult { get; set; }

        [Parameter("TP1 Partial Close Fraction", Group = "6. Exit Management", DefaultValue = 0.65, MinValue = 0.50, MaxValue = 0.90, Step = 0.05)]
        public double Tp1CloseFraction { get; set; }

        [Parameter("Post-TP1 Cushion SL Multiple", Group = "6. Exit Management", DefaultValue = -1.00, MinValue = -1.50, MaxValue = 0.00, Step = 0.10)]
        public double CushionSlMult { get; set; }

        [Parameter("Ratchet Trigger Multiple", Group = "6. Exit Management", DefaultValue = 1.10, MinValue = 0.80, MaxValue = 2.50, Step = 0.10)]
        public double RatchetTriggerMult { get; set; }

        [Parameter("Ratchet Lock Multiple", Group = "6. Exit Management", DefaultValue = 0.50, MinValue = 0.10, MaxValue = 1.50, Step = 0.10)]
        public double RatchetLockMult { get; set; }

        [Parameter("Move To Break-Even After TP1", Group = "6. Exit Management", DefaultValue = false)]
        public bool MoveToBreakEven { get; set; }

        [Parameter("Break-Even Offset (USD)", Group = "6. Exit Management", DefaultValue = 0.0, MinValue = 0.0, MaxValue = 2.0, Step = 0.10)]
        public double BreakEvenOffsetUsd { get; set; }

        [Parameter("Trailing Stop Mult (x scale, 0 = off)", Group = "6. Exit Management", DefaultValue = 0.0, MinValue = 0.0, MaxValue = 3.0, Step = 0.25)]
        public double TrailingStopMult { get; set; }

        [Parameter("Max Hold Seconds", Group = "6. Exit Management", DefaultValue = 3600, MinValue = 300, MaxValue = 14400, Step = 300)]
        public int MaxHoldSeconds { get; set; }

        // ---------------------------------------------------------------- 7. Diagnostics
        [Parameter("Verbose Log", Group = "7. Diagnostics", DefaultValue = false)]
        public bool VerboseLog { get; set; }

        [Parameter("Draw Levels", Group = "7. Diagnostics", DefaultValue = true)]
        public bool DrawLevels { get; set; }

        // ================================================================ 1-second ring buffer
        private struct SecBar
        {
            public long TimestampSec;
            public double MidOpen, MidHigh, MidLow, MidClose, BidClose, AskClose;
        }

        private const int MaxBufferCapacity = 14416;      // 14,400 s (4h) + 16 s margin, as in the original
        private readonly SecBar[] _ring = new SecBar[MaxBufferCapacity];
        private int _ringHead;                             // next write slot
        private int _ringCount;

        private SecBar Bar(int i) { return _ring[(_ringHead - _ringCount + i + MaxBufferCapacity) % MaxBufferCapacity]; }

        private void PushCompletedSecBar(SecBar bar)
        {
            _ring[_ringHead] = bar;
            _ringHead = (_ringHead + 1) % MaxBufferCapacity;
            if (_ringCount < MaxBufferCapacity) _ringCount++;
        }

        private long _currentSec = -1;
        private SecBar _formingBar;
        private long _lastSignalTimestampSec = -999999;

        // per-position exit state (keyed by Position.Id)
        private sealed class PosState
        {
            public double Scale;
            public long EntrySec;
            public bool Tp1Done, RatchetDone, TrailOn;
            public double Best;
        }
        private readonly Dictionary<int, PosState> _state = new Dictionary<int, PosState>();
        private readonly HashSet<int> _closing = new HashSet<int>();   // close requested, waiting for Positions.Closed

        // day / guard state
        private DateTime _day = DateTime.MinValue;
        private double _dayStartEquity;
        private int _tradesToday;
        private bool _dailyLossHit;
        private DateTime _lastCloseTime = DateTime.MinValue;

        private bool CanDraw { get { return DrawLevels && RunningMode != RunningMode.Optimization; } }

        // ================================================================ lifecycle
        protected override void OnStart()
        {
            Positions.Closed += OnPositionClosed;

            // adopt positions left by a previous run: scale recovered from the (never modified) take-profit
            foreach (var p in Positions.FindAll(Label, SymbolName))
            {
                double tpM = UseCushionRatchetRunner ? Tp2Mult : Tp1Mult;
                if (!p.TakeProfit.HasValue || tpM <= 0) continue;
                double scale = Math.Abs(p.TakeProfit.Value - p.EntryPrice) / tpM;
                int sd = p.TradeType == TradeType.Buy ? 1 : -1;
                var st = new PosState
                {
                    Scale = scale,
                    EntrySec = p.EntryTime.Ticks / TimeSpan.TicksPerSecond,
                    Best = p.EntryPrice
                };
                if (p.StopLoss.HasValue)
                {
                    double slOff = (p.StopLoss.Value - p.EntryPrice) * sd;      // negative = behind entry
                    st.Tp1Done = slOff > -0.9 * SlMult * scale;
                    st.RatchetDone = slOff > 0;
                }
                _state[p.Id] = st;
            }
            Print("VClimaxSweepReversal started on {0} (Digits={1}, PipSize={2}, LotSize={3}); adopted {4} open position(s).",
                SymbolName, Symbol.Digits, Symbol.PipSize, Symbol.LotSize, _state.Count);
        }

        protected override void OnStop()
        {
            Positions.Closed -= OnPositionClosed;
        }

        protected override void OnTick()
        {
            double bid = Symbol.Bid;
            double ask = Symbol.Ask;
            double mid = 0.5 * (bid + ask);
            DateTime now = Server.TimeInUtc;
            long nowSec = now.Ticks / TimeSpan.TicksPerSecond;

            RollDay(now);
            CheckDailyLoss();
            if (ForceFlatEnabled && now.TimeOfDay >= new TimeSpan(ForceFlatHourUtc, ForceFlatMinute, 0))
                FlattenAll("force flat");

            // 1. manage open positions intrabar (max hold, TP1 partial + cushion, ratchet, BE, trailing)
            ManagePositions(bid, ask, nowSec);

            // 2. 1-second bar aggregator
            if (_currentSec == -1)
            {
                InitNewFormingBar(nowSec, mid, bid, ask);
                return;
            }

            if (nowSec == _currentSec)
            {
                if (mid > _formingBar.MidHigh) _formingBar.MidHigh = mid;
                if (mid < _formingBar.MidLow) _formingBar.MidLow = mid;
                _formingBar.MidClose = mid;
                _formingBar.BidClose = bid;
                _formingBar.AskClose = ask;
            }
            else if (nowSec > _currentSec)
            {
                PushCompletedSecBar(_formingBar);
                EvaluateCompletedSecondBar(nowSec, now);
                InitNewFormingBar(nowSec, mid, bid, ask);
            }
        }

        private void InitNewFormingBar(long sec, double mid, double bid, double ask)
        {
            _currentSec = sec;
            _formingBar = new SecBar
            {
                TimestampSec = sec, MidOpen = mid, MidHigh = mid, MidLow = mid, MidClose = mid, BidClose = bid, AskClose = ask
            };
        }

        // ================================================================ signal (unchanged logic)
        private void EvaluateCompletedSecondBar(long nowSec, DateTime now)
        {
            int n = _ringCount;
            int minReq = Math.Max(14406, StructuralWindowSec + 6);
            if (n < minReq)
                return;

            if (Positions.FindAll(Label, SymbolName).Length >= MaxOpenPositions)
                return;

            SecBar cur = Bar(n - 1);
            SecBar prev = Bar(n - 2);

            if (cur.TimestampSec - _lastSignalTimestampSec < CooldownSeconds)
                return;

            int hourUtc = (int)((cur.TimestampSec / 3600) % 24);
            if (hourUtc == 21)
                return;                                   // never trade the 21:00 UTC rollover hour
            if (LiquidHoursOnly && (hourUtc < SessionStartHourUtc || hourUtc > SessionEndHourUtc))
                return;

            double barSpread = cur.AskClose - cur.BidClose;
            if (barSpread > MaxSpreadUsd)
                return;

            long dt5 = cur.TimestampSec - Bar(n - 6).TimestampSec;
            if (dt5 <= 0 || dt5 > 6)
                return;

            double h5 = double.MinValue, l5 = double.MaxValue;
            for (int i = n - 5; i < n; i++)
            {
                var b = Bar(i);
                if (b.MidHigh > h5) h5 = b.MidHigh;
                if (b.MidLow < l5) l5 = b.MidLow;
            }
            var b6 = Bar(n - 6);
            double h6 = Math.Max(h5, b6.MidHigh);
            double l6 = Math.Min(l5, b6.MidLow);

            double impUp = h5 - l6;
            double impDn = h6 - l5;
            double rejUp = h5 - cur.MidClose;
            double rejDn = cur.MidClose - l5;

            bool candShort = impUp >= MinImpulse5sUsd && rejUp >= MinRejectionRatio * impUp &&
                             cur.MidClose < cur.MidOpen && cur.MidHigh < prev.MidHigh;
            bool candLong = impDn >= MinImpulse5sUsd && rejDn >= MinRejectionRatio * impDn &&
                            cur.MidClose > cur.MidOpen && cur.MidLow > prev.MidLow;
            if (!candShort && !candLong)
                return;

            ComputeWindowStats(n - 900, n, out _, out double s900);
            ComputeWindowStats(n - 3600, n, out double m3600, out double s3600);
            ComputeWindowStats(n - 14400, n, out double m14400, out double s14400);

            if (s3600 < MinStd3600 || s900 < MinStd900) return;
            if (s900 > MaxRatio900To3600 * s3600) return;      // anti-news-shock maturity gate
            if (s3600 < MinRatio3600To14400 * s14400) return;  // anti-box consolidation gate

            int structEnd = n - 6;
            int structStart = structEnd - StructuralWindowSec;
            double hPre = double.MinValue, lPre = double.MaxValue;
            for (int i = structStart; i < structEnd; i++)
            {
                var b = Bar(i);
                if (b.MidHigh > hPre) hPre = b.MidHigh;
                if (b.MidLow < lPre) lPre = b.MidLow;
            }

            double z14400 = (cur.MidClose - m14400) / Math.Max(s14400, 0.10);

            TradeType? side = null;
            double level = 0;
            if (candShort && impUp >= MinImpulseStdMult * s3600 && h5 > hPre + MinSweepUsd &&
                cur.MidClose < hPre - MinReEntryUsd && m3600 > m14400 && z14400 >= MinZ14400)
            { side = TradeType.Sell; level = hPre; }
            else if (candLong && impDn >= MinImpulseStdMult * s3600 && l5 < lPre - MinSweepUsd &&
                     cur.MidClose > lPre + MinReEntryUsd && m3600 < m14400 && z14400 <= -MinZ14400)
            { side = TradeType.Buy; level = lPre; }
            if (side == null) return;

            Log("SIGNAL {0} sec={1:HH:mm:ss} imp5={2:F2} s900={3:F2} s3600={4:F2} s14400={5:F2} z={6:F2} level={7:F2}",
                side, new DateTime(cur.TimestampSec * TimeSpan.TicksPerSecond), side == TradeType.Sell ? impUp : impDn,
                s900, s3600, s14400, z14400, level);

            if (MaxSignalLatencySec > 0 && nowSec - cur.TimestampSec > MaxSignalLatencySec)
            {
                Log("skip: signal is {0}s old (MaxSignalLatencySec)", nowSec - cur.TimestampSec);
                return;
            }
            ExecuteReversalEntry(side.Value, s900, cur.TimestampSec, level, now);
        }

        private void ComputeWindowStats(int startIdx, int endIdx, out double mean, out double std)
        {
            int count = endIdx - startIdx;
            if (count <= 0) { mean = 0; std = 0; return; }
            double sum = 0.0, sumSq = 0.0;
            for (int i = startIdx; i < endIdx; i++)
            {
                double v = Bar(i).MidClose;
                sum += v;
                sumSq += v * v;
            }
            mean = sum / count;
            double variance = Math.Max(0.0, (sumSq / count) - (mean * mean));   // population variance (as original)
            std = Math.Sqrt(variance);
        }

        // ================================================================ entry
        private void ExecuteReversalEntry(TradeType side, double s900, long signalSec, double level, DateTime now)
        {
            if (!DayAllowed(now.DayOfWeek)) { Log("skip: weekday disabled"); return; }
            if (_dailyLossHit) { Log("skip: daily loss limit"); return; }
            if (MaxTradesPerDay > 0 && _tradesToday >= MaxTradesPerDay) { Log("skip: MaxTradesPerDay"); return; }
            if (CooldownMinutes > 0 && now < _lastCloseTime.AddMinutes(CooldownMinutes)) { Log("skip: cooldown after close"); return; }
            if (ForceFlatEnabled && now.TimeOfDay >= new TimeSpan(ForceFlatHourUtc, ForceFlatMinute, 0)) { Log("skip: after force-flat time"); return; }
            double spread = Symbol.Ask - Symbol.Bid;
            if (spread > MaxSpreadUsd) { Log("skip: entry spread {0:F2} > {1:F2}", spread, MaxSpreadUsd); return; }

            double scale = Math.Max(s900, MinScaleUsd);
            double slDist = Math.Max(SlMult * scale, MinStopDistance());
            double finalTpDist = UseCushionRatchetRunner ? (Tp2Mult * scale) : (Tp1Mult * scale);
            finalTpDist = Math.Max(finalTpDist, MinTpDistance());

            double sizingDist = SizingBasis == SizingBasisType.LegacyScale ? Math.Max(scale, 5.0) : slDist;
            double units = ComputeVolume(sizingDist);
            if (units <= 0) { Log("skip: volume below minimum"); return; }

            double slPips = Math.Round(slDist / Symbol.PipSize, 1);
            double tpPips = Math.Round(finalTpDist / Symbol.PipSize, 1);

            var result = ExecuteMarketOrder(side, SymbolName, units, Label, slPips, tpPips, TradeComment);
            if (!result.IsSuccessful || result.Position == null)
            {
                Print("[VCSR] ORDER FAILED {0} {1} units: {2}", side, units, result.Error);
                return;
            }
            var pos = result.Position;
            _lastSignalTimestampSec = signalSec;
            _tradesToday++;
            _state[pos.Id] = new PosState { Scale = scale, EntrySec = signalSec, Best = pos.EntryPrice };
            Log("[VCSR ENTRY] {0} {1} units @ {2:F2} | scale=${3:F2} | SL={4:F1}p | TP={5:F1}p",
                side, units, pos.EntryPrice, scale, slPips, tpPips);

            if (CanDraw)
            {
                string id = "VCSR_" + pos.Id;
                DateTime end = now.AddSeconds(MaxHoldSeconds);
                DateTime start = now.AddSeconds(-StructuralWindowSec);
                Chart.DrawTrendLine(id + "_lvl", start, level, now, level, Color.Orange, 1, LineStyle.Lines);
                Chart.DrawTrendLine(id + "_e", now, pos.EntryPrice, end, pos.EntryPrice, Color.Gray, 1, LineStyle.Dots);
                if (pos.StopLoss.HasValue) Chart.DrawTrendLine(id + "_sl", now, pos.StopLoss.Value, end, pos.StopLoss.Value, Color.Red, 1, LineStyle.Solid);
                if (pos.TakeProfit.HasValue) Chart.DrawTrendLine(id + "_tp", now, pos.TakeProfit.Value, end, pos.TakeProfit.Value, Color.LimeGreen, 1, LineStyle.Solid);
                if (UseCushionRatchetRunner)
                {
                    double t1 = pos.EntryPrice + (side == TradeType.Buy ? 1 : -1) * Tp1Mult * scale;
                    Chart.DrawTrendLine(id + "_tp1", now, t1, end, t1, Color.Gold, 1, LineStyle.Lines);
                }
            }
        }

        // ================================================================ exit management (original two-stage logic + standard extras)
        private void ManagePositions(double bid, double ask, long nowSec)
        {
            if (_state.Count == 0) return;
            foreach (var pos in Positions.FindAll(Label, SymbolName))
            {
                PosState st;
                if (_closing.Contains(pos.Id) || !_state.TryGetValue(pos.Id, out st)) continue;
                int sd = pos.TradeType == TradeType.Buy ? 1 : -1;
                double exitPx = sd == 1 ? bid : ask;

                // 1. time exit after MaxHoldSeconds
                if (nowSec - st.EntrySec >= MaxHoldSeconds)
                {
                    CloseChecked(pos, "max hold");
                    continue;
                }

                double favExcursion = (exitPx - pos.EntryPrice) * sd;

                if (UseCushionRatchetRunner)
                {
                    // 2. stage 1: TP1 partial close, runner stop to the cushion level
                    if (!st.Tp1Done && favExcursion >= Tp1Mult * st.Scale)
                    {
                        st.Tp1Done = true;
                        double closeUnits = Symbol.NormalizeVolumeInUnits(pos.VolumeInUnits * Tp1CloseFraction, RoundingMode.Down);
                        if (closeUnits >= Symbol.VolumeInUnitsMin && (pos.VolumeInUnits - closeUnits) >= Symbol.VolumeInUnitsMin)
                        {
                            var r = ClosePosition(pos, closeUnits);
                            if (!r.IsSuccessful) Print("[VCSR] TP1 partial close failed on {0}: {1}", pos.Id, r.Error);
                        }
                        else
                            Print("[VCSR] TP1 partial skipped on {0}: {1} units cannot be split above the minimum volume", pos.Id, pos.VolumeInUnits);

                        double cushionSl = pos.EntryPrice + sd * CushionSlMult * st.Scale;   // CushionSlMult <= 0: behind entry
                        TightenStop(pos, cushionSl, exitPx, "TP1 + cushion");
                        if (TrailingStopMult > 0) { st.TrailOn = true; st.Best = exitPx; }
                        Log("[VCSR TP1 + CUSHION] Pos {0} banked {1:P0} at +${2:F2}/oz; runner SL -> {3:F2}",
                            pos.Id, Tp1CloseFraction, favExcursion, cushionSl);
                    }

                    // 3. stage 2: ratchet the runner stop into profit
                    if (st.Tp1Done && !st.RatchetDone && favExcursion >= RatchetTriggerMult * st.Scale)
                    {
                        st.RatchetDone = true;
                        double ratchetSl = pos.EntryPrice + sd * RatchetLockMult * st.Scale;
                        TightenStop(pos, ratchetSl, exitPx, "ratchet lock");
                    }

                    // optional extras (off by default)
                    if (st.Tp1Done && MoveToBreakEven)
                        TightenStop(pos, pos.EntryPrice + sd * BreakEvenOffsetUsd, exitPx, null);
                    if (st.TrailOn && TrailingStopMult > 0)
                    {
                        if ((exitPx - st.Best) * sd > 0) st.Best = exitPx;
                        TightenStop(pos, st.Best - sd * TrailingStopMult * st.Scale, exitPx, null);
                    }
                }
            }
        }

        /// <summary>Move the stop only in the favourable direction; if the level is already crossed, close at market.</summary>
        private void TightenStop(Position p, double newSl, double exitPx, string why)
        {
            if (_closing.Contains(p.Id)) return;
            if (!_state.ContainsKey(p.Id)) return;
            int sd = p.TradeType == TradeType.Buy ? 1 : -1;
            newSl = Math.Round(newSl, Symbol.Digits);
            if (p.StopLoss.HasValue && (newSl - p.StopLoss.Value) * sd <= 0) return;
            double room = (exitPx - newSl) * sd;
            if (room <= 0)
            {
                CloseChecked(p, (why ?? "stop") + " level already crossed");
                return;
            }
            if (room < MinStopDistance()) return;           // retried on the next tick (BE / trailing only)
            var r = ModifyPosition(p, newSl, p.TakeProfit, ProtectionType.Absolute);
            if (!r.IsSuccessful) Print("[VCSR] ModifyPosition failed on {0}: {1}", p.Id, r.Error);
            else if (why != null) Log("[VCSR] {0}: stop of {1} -> {2}", why, p.Id, newSl);
        }

        private void FlattenAll(string why)
        {
            foreach (var p in Positions.FindAll(Label, SymbolName))
                CloseChecked(p, why);
            foreach (var o in PendingOrders)
                if (o.Label == Label && o.SymbolName == SymbolName)
                {
                    var r = CancelPendingOrder(o);
                    if (!r.IsSuccessful) Print("[VCSR] cancel failed: {0}", r.Error);
                }
        }

        private void CloseChecked(Position p, string why)
        {
            if (_closing.Contains(p.Id)) return;
            var r = ClosePosition(p);
            if (!r.IsSuccessful) Print("[VCSR] close {0} ({1}) failed: {2}", p.Id, why, r.Error);
            else { _closing.Add(p.Id); Log("[VCSR] CLOSE {0}: {1}", p.Id, why); }
        }

        private void OnPositionClosed(PositionClosedEventArgs args)
        {
            var p = args.Position;
            if (p.Label != Label || p.SymbolName != SymbolName) return;
            _state.Remove(p.Id);
            _closing.Remove(p.Id);
            _lastCloseTime = Server.Time;
            if (CanDraw)
                foreach (var s in new[] { "_lvl", "_e", "_sl", "_tp", "_tp1" }) Chart.RemoveObject("VCSR_" + p.Id + s);
        }

        // ================================================================ risk & guards
        private double ComputeVolume(double riskDist)
        {
            if (!(riskDist > 0) || Symbol.PipSize <= 0) return 0;
            // account-currency value of a 1 USD price move for one unit (= 1 for a USD account)
            double perUnit = Symbol.PipValue > 0 ? Symbol.PipValue / Symbol.PipSize : 1.0;
            double units;
            switch (RiskMode)
            {
                case RiskModeType.FixedLots: units = Symbol.QuantityToVolumeInUnits(FixedLots); break;
                case RiskModeType.FixedCash: units = FixedCashRisk / (riskDist * perUnit); break;
                default: units = Account.Equity * RiskPercent / 100.0 / (riskDist * perUnit); break;
            }
            // lots = units / Symbol.LotSize   (USD account: lots = cash / (distance x LotSize))
            double maxUnits = Math.Min(Symbol.VolumeInUnitsMax, MaxLots * Symbol.LotSize);
            units = Math.Min(units, maxUnits);
            units = Symbol.NormalizeVolumeInUnits(units, RoundingMode.Down);
            if (double.IsNaN(units) || units < Symbol.VolumeInUnitsMin) return 0;
            return units;
        }

        private double MinStopDistance()
        {
            if (Symbol.MinDistanceType == SymbolMinDistanceType.Pips) return Symbol.MinStopLossDistance * Symbol.PipSize;
            return Symbol.MinStopLossDistance / 100.0 * Symbol.Bid;
        }

        private double MinTpDistance()
        {
            if (Symbol.MinDistanceType == SymbolMinDistanceType.Pips) return Symbol.MinTakeProfitDistance * Symbol.PipSize;
            return Symbol.MinTakeProfitDistance / 100.0 * Symbol.Bid;
        }

        private void RollDay(DateTime now)
        {
            if (now.Date == _day) return;
            _day = now.Date;
            _dayStartEquity = Account.Equity;
            _tradesToday = 0; _dailyLossHit = false;
        }

        private void CheckDailyLoss()
        {
            if (MaxDailyLossPercent <= 0 || _dailyLossHit || _dayStartEquity <= 0) return;
            double unreal = 0;
            foreach (var p in Positions.FindAll(Label, SymbolName)) unreal += p.NetProfit;
            double loss = -(RealisedToday() + unreal);
            if (loss > _dayStartEquity * MaxDailyLossPercent / 100.0)
            {
                _dailyLossHit = true;
                Print("[VCSR] daily loss limit hit ({0:F2} > {1}% of {2:F2}); no new entries today.", loss, MaxDailyLossPercent, _dayStartEquity);
                if (CloseAllOnDailyLoss) FlattenAll("daily loss limit");
            }
        }

        /// <summary>Realised net P&amp;L of this label+symbol since the UTC day start, from History
        /// (includes partial closes such as TP1, which do not raise Positions.Closed).</summary>
        private double RealisedToday()
        {
            double sum = 0;
            for (int i = History.Count - 1; i >= 0; i--)
            {
                var t = History[i];
                if (t.ClosingTime < _day) break;               // History is ordered by closing time
                if (t.Label == Label && t.SymbolName == SymbolName) sum += t.NetProfit;
            }
            return sum;
        }

        private bool DayAllowed(DayOfWeek d)
        {
            switch (d)
            {
                case DayOfWeek.Monday: return TradeMonday;
                case DayOfWeek.Tuesday: return TradeTuesday;
                case DayOfWeek.Wednesday: return TradeWednesday;
                case DayOfWeek.Thursday: return TradeThursday;
                case DayOfWeek.Friday: return TradeFriday;
                default: return false;
            }
        }

        private void Log(string fmt, params object[] args)
        {
            if (VerboseLog) Print(fmt, args);
        }
    }
}
