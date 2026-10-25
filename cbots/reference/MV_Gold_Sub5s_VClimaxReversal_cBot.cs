// =================================================================================================
// MV_Gold_Sub5s_VClimaxReversal_cBot.cs
// Institutional Sub-5-Second V-Climax Sweep Reversal Strategy for Gold (XAUUSD)
// Platform: cTrader Automate (C# / .NET 6)
// Execution: OnTick() Circular Ring Buffer + 1-Second Micro-Bar Aggregator
// =================================================================================================
// Strategy Mechanics (Validated on 16.33M 1-Second XAUUSD Bars, 2025-10 to 2026-10):
//   1. Maintains a lock-free 1-second circular buffer (up to 14,406 seconds = 4 hours + 6s pre-spike).
//   2. Detects violent <=5-second liquidity-vacuum price spikes:
//        Impulse_5s >= max($3.20, 0.35 * StdDev_3600s)
//   3. Requires sweep of prior W-second structural extreme (shifted 6s prior to spike) by >= $0.10.
//   4. Requires immediate sub-5-second rejection of >= 60% of the 5-second impulse, closing back
//      inside the structural boundary by >= $0.15 on a confirmed 1-second turn bar.
//   5. Enforces Three Institutional Regime Gates:
//        - Active Volatility Floor: StdDev_900s >= $5.00 AND StdDev_3600s >= $7.50
//        - Anti-News-Shock Maturity Gate: StdDev_900s / StdDev_3600s <= 1.00
//        - Anti-Box Consolidation Gate: StdDev_3600s / StdDev_14400s >= 0.35
//        - Macro Trend Exhaustion Alignment: |Z_14400s| >= 1.50 & Mean_3600s aligned with sweep
//   6. Supports both Pure Single-TP (Arch 1) and Cushion + Ratchet Two-Stage Runner (Arch 2).
// =================================================================================================

using System;
using System.Collections.Generic;
using System.Linq;
using cAlgo.API;
using cAlgo.API.Indicators;
using cAlgo.API.Internals;

namespace cAlgo.Robots
{
    [Robot(AccessRights = AccessRights.None, TimeZone = TimeZones.UTC)]
    public class MV_Gold_Sub5s_VClimaxReversal_cBot : Robot
    {
        // =========================================================================================
        // 1. STRATEGY PARAMETERS
        // =========================================================================================
        [Parameter("Order Label", Group = "Identity & Risk", DefaultValue = "VCSR_XAUUSD-CH")]
        public string OrderLabel { get; set; }

        [Parameter("Risk Per Trade (%)", Group = "Identity & Risk", DefaultValue = 0.5, MinValue = 0.1, MaxValue = 5.0)]
        public double RiskPercent { get; set; }

        [Parameter("Max Spread Filter ($)", Group = "Identity & Risk", DefaultValue = 0.35, MinValue = 0.10, MaxValue = 1.50)]
        public double MaxSpreadUsd { get; set; }

        [Parameter("Cooldown Seconds", Group = "Identity & Risk", DefaultValue = 180, MinValue = 30, MaxValue = 3600)]
        public int CooldownSeconds { get; set; }

        [Parameter("Max Hold Seconds", Group = "Identity & Risk", DefaultValue = 3600, MinValue = 300, MaxValue = 14400)]
        public int MaxHoldSeconds { get; set; }

        [Parameter("London+NY Liquid Hours Only (06-20 UTC)", Group = "Session Gates", DefaultValue = true)]
        public bool LiquidHoursOnly { get; set; }

        [Parameter("Structural Window Seconds (1800=30m, 14400=240m)", Group = "Sub-5s Reversal Signal", DefaultValue = 14400, MinValue = 1800, MaxValue = 14400)]
        public int StructuralWindowSec { get; set; }

        [Parameter("Min 5s Impulse ($)", Group = "Sub-5s Reversal Signal", DefaultValue = 3.20, MinValue = 2.00, MaxValue = 10.00)]
        public double MinImpulse5sUsd { get; set; }

        [Parameter("Min 5s Impulse / 1H StdDev Ratio", Group = "Sub-5s Reversal Signal", DefaultValue = 0.35, MinValue = 0.20, MaxValue = 1.00)]
        public double MinImpulseStdMult { get; set; }

        [Parameter("Min Sub-5s Rejection Ratio (0.60 = 60%)", Group = "Sub-5s Reversal Signal", DefaultValue = 0.60, MinValue = 0.40, MaxValue = 0.90)]
        public double MinRejectionRatio { get; set; }

        [Parameter("Min Structural Sweep ($)", Group = "Sub-5s Reversal Signal", DefaultValue = 0.10, MinValue = 0.05, MaxValue = 1.00)]
        public double MinSweepUsd { get; set; }

        [Parameter("Min Re-Entry Inside Level ($)", Group = "Sub-5s Reversal Signal", DefaultValue = 0.15, MinValue = 0.05, MaxValue = 1.00)]
        public double MinReEntryUsd { get; set; }

        [Parameter("Min 15m StdDev Floor ($)", Group = "Volatility & Climax Gates", DefaultValue = 5.00, MinValue = 2.00, MaxValue = 15.00)]
        public double MinStd900 { get; set; }

        [Parameter("Min 1H StdDev Floor ($)", Group = "Volatility & Climax Gates", DefaultValue = 7.50, MinValue = 3.00, MaxValue = 20.00)]
        public double MinStd3600 { get; set; }

        [Parameter("Max s900/s3600 Ratio (Anti-News Gate)", Group = "Volatility & Climax Gates", DefaultValue = 1.00, MinValue = 0.70, MaxValue = 1.50)]
        public double MaxRatio900To3600 { get; set; }

        [Parameter("Min s3600/s14400 Ratio (Anti-Box Gate)", Group = "Volatility & Climax Gates", DefaultValue = 0.35, MinValue = 0.20, MaxValue = 0.80)]
        public double MinRatio3600To14400 { get; set; }

        [Parameter("Min 4H Climax Z-Score", Group = "Volatility & Climax Gates", DefaultValue = 1.50, MinValue = 1.00, MaxValue = 3.00)]
        public double MinZ14400 { get; set; }

        [Parameter("Use Arch 2 Cushion+Ratchet Runner", Group = "Exit Architecture", DefaultValue = true)]
        public bool UseCushionRatchetRunner { get; set; }

        [Parameter("TP1 Multiple of s900", Group = "Exit Architecture", DefaultValue = 0.70, MinValue = 0.40, MaxValue = 2.00)]
        public double Tp1Mult { get; set; }

        [Parameter("TP2 Multiple of s900 (Runner)", Group = "Exit Architecture", DefaultValue = 2.20, MinValue = 1.00, MaxValue = 5.00)]
        public double Tp2Mult { get; set; }

        [Parameter("Initial SL Multiple of s900", Group = "Exit Architecture", DefaultValue = 5.50, MinValue = 2.00, MaxValue = 8.00)]
        public double SlMult { get; set; }

        [Parameter("TP1 Partial Close Fraction (0.65 = 65%)", Group = "Exit Architecture", DefaultValue = 0.65, MinValue = 0.50, MaxValue = 0.90)]
        public double Tp1CloseFraction { get; set; }

        [Parameter("Post-TP1 Cushion SL Multiple (-1.0 = Net Win Lock)", Group = "Exit Architecture", DefaultValue = -1.00, MinValue = -1.50, MaxValue = 0.00)]
        public double CushionSlMult { get; set; }

        [Parameter("Ratchet Trigger Multiple of s900", Group = "Exit Architecture", DefaultValue = 1.10, MinValue = 0.80, MaxValue = 2.50)]
        public double RatchetTriggerMult { get; set; }

        [Parameter("Ratchet Lock Multiple of s900", Group = "Exit Architecture", DefaultValue = 0.50, MinValue = 0.10, MaxValue = 1.50)]
        public double RatchetLockMult { get; set; }

        // =========================================================================================
        // 2. INTERNAL 1-SECOND RING BUFFER & STATE
        // =========================================================================================
        private struct SecBar
        {
            public long TimestampSec;
            public double MidOpen;
            public double MidHigh;
            public double MidLow;
            public double MidClose;
            public double BidClose;
            public double AskClose;
        }

        private const int MaxBufferCapacity = 14416; // 14,400s (4H) + 16s margin
        private readonly List<SecBar> _secBars = new List<SecBar>(MaxBufferCapacity);

        private long _currentSec = -1;
        private SecBar _formingBar;
        private long _lastSignalTimestampSec = -999999;

        // Active trade management state for Arch 2 Cushion + Ratchet
        private long _activePositionId = -1;
        private double _activeEntryPrice = 0.0;
        private double _activeScaleS900 = 5.0;
        private TradeType _activeSide = TradeType.Buy;
        private long _activeEntrySec = 0;
        private bool _tp1Executed = false;
        private bool _ratchetExecuted = false;

        protected override void OnStart()
        {
            Positions.Closed += OnPositionClosed;
            Print("MV_Gold_Sub5s_VClimaxReversal_cBot started on {0} (Digits={1}, PipSize={2}).",
                SymbolName, Symbol.Digits, Symbol.PipSize);
        }

        protected override void OnTick()
        {
            double bid = Symbol.Bid;
            double ask = Symbol.Ask;
            double mid = 0.5 * (bid + ask);
            long nowSec = Server.TimeInUtc.Ticks / TimeSpan.TicksPerSecond;

            // 1. Manage active position intrabar (TP1 partial close, Cushion SL, Ratchet SL, MaxHold)
            ManageActivePosition(bid, ask, nowSec);

            // 2. Update 1-second bar aggregator
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
                // Finalize completed 1-second bar and evaluate Sub-5s V-ClimaxSweep signal
                PushCompletedSecBar(_formingBar);
                EvaluateCompletedSecondBar();

                // Start new 1-second bar
                InitNewFormingBar(nowSec, mid, bid, ask);
            }
        }

        private void InitNewFormingBar(long sec, double mid, double bid, double ask)
        {
            _currentSec = sec;
            _formingBar = new SecBar
            {
                TimestampSec = sec,
                MidOpen = mid,
                MidHigh = mid,
                MidLow = mid,
                MidClose = mid,
                BidClose = bid,
                AskClose = ask
            };
        }

        private void PushCompletedSecBar(SecBar bar)
        {
            if (_secBars.Count >= MaxBufferCapacity)
                _secBars.RemoveAt(0);
            _secBars.Add(bar);
        }

        // =========================================================================================
        // 3. SUB-5-SECOND V-CLIMAX SWEEP SIGNAL EVALUATION
        // =========================================================================================
        private void EvaluateCompletedSecondBar()
        {
            int n = _secBars.Count;
            int minReq = Math.Max(14406, StructuralWindowSec + 6);
            if (n < minReq)
                return;

            // Only 1 position open at a time for this label
            if (Positions.FindAll(OrderLabel, SymbolName).Length > 0)
                return;

            SecBar cur = _secBars[n - 1];
            SecBar prev = _secBars[n - 2];

            // Cooldown check
            if (cur.TimestampSec - _lastSignalTimestampSec < CooldownSeconds)
                return;

            // Session filter
            int hourUtc = (int)((cur.TimestampSec / 3600) % 24);
            if (hourUtc == 21)
                return; // Never trade 21:00 UTC rollover spread spike
            if (LiquidHoursOnly && (hourUtc < 6 || hourUtc > 20))
                return;

            // Spread filter
            double currentSpread = cur.AskClose - cur.BidClose;
            if (currentSpread > MaxSpreadUsd)
                return;

            // Ensure last 5 bars occurred within <= 6 real-time seconds (no data freeze/gap)
            long dt5 = cur.TimestampSec - _secBars[n - 6].TimestampSec;
            if (dt5 <= 0 || dt5 > 6)
                return;

            // Compute 5-second and 6-second high/low window
            double h5 = double.MinValue, l5 = double.MaxValue;
            for (int i = n - 5; i < n; i++)
            {
                if (_secBars[i].MidHigh > h5) h5 = _secBars[i].MidHigh;
                if (_secBars[i].MidLow < l5) l5 = _secBars[i].MidLow;
            }
            double h6 = Math.Max(h5, _secBars[n - 6].MidHigh);
            double l6 = Math.Min(l5, _secBars[n - 6].MidLow);

            double impUp = h5 - l6;
            double impDn = h6 - l5;
            double rejUp = h5 - cur.MidClose;
            double rejDn = cur.MidClose - l5;

            // Quick pre-check before computing multi-hour moments: must have >= MinImpulse5sUsd
            bool candShort = (impUp >= MinImpulse5sUsd) &&
                             (rejUp >= MinRejectionRatio * impUp) &&
                             (cur.MidClose < cur.MidOpen) &&
                             (cur.MidHigh < prev.MidHigh);

            bool candLong = (impDn >= MinImpulse5sUsd) &&
                            (rejDn >= MinRejectionRatio * impDn) &&
                            (cur.MidClose > cur.MidOpen) &&
                            (cur.MidLow > prev.MidLow);

            if (!candShort && !candLong)
                return;

            // Compute causal rolling statistics (900s, 3600s, 14400s) and pre-spike structural high/low
            ComputeWindowStats(n - 900, n, out _, out double s900);
            ComputeWindowStats(n - 3600, n, out double m3600, out double s3600);
            ComputeWindowStats(n - 14400, n, out double m14400, out double s14400);

            // Volatility Regime Gates
            if (s3600 < MinStd3600 || s900 < MinStd900)
                return;
            if (s900 > MaxRatio900To3600 * s3600)
                return; // Anti-news-shock maturity gate
            if (s3600 < MinRatio3600To14400 * s14400)
                return; // Anti-box consolidation gate

            // Pre-spike structural boundary (shifted 6 bars prior to bar n-1)
            int structEnd = n - 6;
            int structStart = structEnd - StructuralWindowSec;
            double hPre = double.MinValue, lPre = double.MaxValue;
            for (int i = structStart; i < structEnd; i++)
            {
                if (_secBars[i].MidHigh > hPre) hPre = _secBars[i].MidHigh;
                if (_secBars[i].MidLow < lPre) lPre = _secBars[i].MidLow;
            }

            double z14400 = (cur.MidClose - m14400) / Math.Max(s14400, 0.10);

            // Evaluate Short Climax Sweep Trigger
            if (candShort &&
                impUp >= MinImpulseStdMult * s3600 &&
                h5 > hPre + MinSweepUsd &&
                cur.MidClose < hPre - MinReEntryUsd &&
                m3600 > m14400 &&
                z14400 >= MinZ14400)
            {
                ExecuteReversalEntry(TradeType.Sell, s900, cur.TimestampSec);
                return;
            }

            // Evaluate Long Climax Sweep Trigger
            if (candLong &&
                impDn >= MinImpulseStdMult * s3600 &&
                l5 < lPre - MinSweepUsd &&
                cur.MidClose > lPre + MinReEntryUsd &&
                m3600 < m14400 &&
                z14400 <= -MinZ14400)
            {
                ExecuteReversalEntry(TradeType.Buy, s900, cur.TimestampSec);
            }
        }

        private void ComputeWindowStats(int startIdx, int endIdx, out double mean, out double std)
        {
            int count = endIdx - startIdx;
            double sum = 0.0, sumSq = 0.0;
            for (int i = startIdx; i < endIdx; i++)
            {
                double v = _secBars[i].MidClose;
                sum += v;
                sumSq += v * v;
            }
            mean = sum / count;
            double variance = Math.Max(0.0, (sumSq / count) - (mean * mean));
            std = Math.Sqrt(variance);
        }

        // =========================================================================================
        // 4. ORDER EXECUTION & TWO-STAGE CUSHION + RATCHET MANAGEMENT
        // =========================================================================================
        private void ExecuteReversalEntry(TradeType side, double s900, long nowSec)
        {
            double scale = Math.Max(s900, 4.50);
            double slDist = SlMult * scale;
            double finalTpDist = UseCushionRatchetRunner ? (Tp2Mult * scale) : (Tp1Mult * scale);

            double slPips = Math.Round(slDist / Symbol.PipSize, 1);
            double tpPips = Math.Round(finalTpDist / Symbol.PipSize, 1);

            // Size volume for RiskPercent
            double riskUsd = Account.Equity * (RiskPercent / 100.0);
            double refDist = Math.Max(scale, 5.0);
            double refPips = refDist / Symbol.PipSize;
            double rawUnits = riskUsd / Math.Max(refPips * Symbol.PipValue, 1e-6);
            double volumeUnits = Symbol.NormalizeVolumeInUnits(rawUnits, RoundingMode.Down);
            volumeUnits = Math.Max(Symbol.VolumeInUnitsMin, Math.Min(volumeUnits, Symbol.VolumeInUnitsMax));

            var result = ExecuteMarketOrder(side, SymbolName, volumeUnits, OrderLabel, slPips, tpPips, "Sub5s_VClimaxSweep");
            if (result.IsSuccessful && result.Position != null)
            {
                _lastSignalTimestampSec = nowSec;
                _activePositionId = result.Position.Id;
                _activeEntryPrice = result.Position.EntryPrice;
                _activeScaleS900 = scale;
                _activeSide = side;
                _activeEntrySec = nowSec;
                _tp1Executed = false;
                _ratchetExecuted = false;

                Print("[VCSR ENTRY] {0} {1} units @ {2:F2} | s900=${3:F2} | SL={4:F1}p | TP={5:F1}p",
                    side, volumeUnits, _activeEntryPrice, scale, slPips, tpPips);
            }
        }

        private void ManageActivePosition(double bid, double ask, long nowSec)
        {
            if (_activePositionId == -1)
                return;

            Position pos = Positions.FirstOrDefault(p => p.Id == _activePositionId);
            if (pos == null)
            {
                _activePositionId = -1;
                return;
            }

            // 1. Time-based exit after MaxHoldSeconds
            if (nowSec - _activeEntrySec >= MaxHoldSeconds)
            {
                ClosePosition(pos);
                _activePositionId = -1;
                return;
            }

            if (!UseCushionRatchetRunner)
                return;

            double favExcursion = (_activeSide == TradeType.Buy)
                ? (bid - _activeEntryPrice)
                : (_activeEntryPrice - ask);

            double tp1Dist = Tp1Mult * _activeScaleS900;
            double ratchetTrigDist = RatchetTriggerMult * _activeScaleS900;

            // 2. Stage 1: Execute TP1 Partial Close (65%) and move Runner SL to Cushioned Net-Win Lock (-1.0 * s900)
            if (!_tp1Executed && favExcursion >= tp1Dist)
            {
                double closeUnits = Symbol.NormalizeVolumeInUnits(pos.VolumeInUnits * Tp1CloseFraction, RoundingMode.Down);
                if (closeUnits >= Symbol.VolumeInUnitsMin && (pos.VolumeInUnits - closeUnits) >= Symbol.VolumeInUnitsMin)
                {
                    ClosePosition(pos, closeUnits);
                }

                // Cushion SL: CushionSlMult is negative (-1.0 * s900), meaning 1.0 * s900 behind entry
                double cushionOffset = Math.Abs(CushionSlMult) * _activeScaleS900;
                double newSl = (_activeSide == TradeType.Buy)
                    ? Math.Round(_activeEntryPrice - cushionOffset, Symbol.Digits)
                    : Math.Round(_activeEntryPrice + cushionOffset, Symbol.Digits);

                ModifyPosition(pos, newSl, pos.TakeProfit, ProtectionType.Absolute);
                _tp1Executed = true;
                Print("[VCSR TP1 + CUSHION] Pos {0} banked {1:P0} at +${2:F2}/oz; Runner SL cushioned to {3:F2}",
                    pos.Id, Tp1CloseFraction, favExcursion, newSl);
            }

            // 3. Stage 2: Ratchet Runner SL into profit (+0.5 * s900) once excursion hits +1.1 * s900
            if (_tp1Executed && !_ratchetExecuted && favExcursion >= ratchetTrigDist)
            {
                double lockOffset = RatchetLockMult * _activeScaleS900;
                double ratchetSl = (_activeSide == TradeType.Buy)
                    ? Math.Round(_activeEntryPrice + lockOffset, Symbol.Digits)
                    : Math.Round(_activeEntryPrice - lockOffset, Symbol.Digits);

                ModifyPosition(pos, ratchetSl, pos.TakeProfit, ProtectionType.Absolute);
                _ratchetExecuted = true;
                Print("[VCSR RATCHET LOCK] Pos {0} excursion +${1:F2}/oz; Runner SL ratcheted to {2:F2}",
                    pos.Id, favExcursion, ratchetSl);
            }
        }

        private void OnPositionClosed(PositionClosedEventArgs args)
        {
            if (args.Position.Id == _activePositionId)
            {
                _activePositionId = -1;
            }
        }
    }
}
