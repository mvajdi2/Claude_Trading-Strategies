// =================================================================================================
// AvwapLondon.cs  -  cTrader Automate cBot (C#, .NET 6)
// Port of strategies/avwap_london.py, frozen settings from strategy_cards/avwap_london.frozen.json
// (params anchor 23.0, trend_frac 0.7, touch_band 0.0, mode pullback;
//  exit {"sl": 2.0, "trail": 1.0, "tp": 0} in units of the native stop distance d).
//
// Rules (5-minute bars, all times UTC):
//   * Anchored VWAP reset at Anchor (frozen 23:00 UTC = session start). Typical price (H+L+C)/3
//     weighted by Bars.TickVolumes (Python: Dukascopy tick count per bar), with the weighted
//     standard deviation sigma.
//   * frac_up = share of 5m closes since the anchor above the VWAP (current bar included);
//     slope = VWAP - VWAP 12 bars earlier (same session). Uptrend: frac_up >= TrendFrac and
//     slope > 0; downtrend: (1 - frac_up) >= TrendFrac and slope < 0.
//   * Signals only on bars opening 08:00-20:00 UTC with >= 12 bars since the anchor, ATR14 ready and
//     sigma > 0.
//   * Pullback (frozen): in an uptrend a bar low <= VWAP + TouchBand x sigma arms the long; the first
//     bar (same or later) closing above VWAP with close > open triggers. Losing the trend disarms.
//     Shorts mirror. Fade2Sd (alternative mode): a bar opening beyond the previous bar's 2-sigma band
//     and closing back inside fades toward the VWAP.
//   * d (pullback) = max(close - (VWAP - 1.5 sigma), 0.5 x ATR14(5m)) for longs (mirror for shorts).
//   * At most 2 signals per UTC day (Python groupby(day).head(2)); a signal that arrives while a
//     position is open is skipped and still counts.
//   * Exit (UnitMultiples, frozen): stop = SlMult x d, trailing stop TrailingStopMult x d from the
//     entry (stop = best price - 1.0 x d, ratchets only), no fixed target (TpMult 0). Flat 20:55 UTC.
//   * Entry = market order on the first tick after the signal bar closes.
// =================================================================================================
using System;
using System.Collections.Generic;
using System.Linq;
using cAlgo.API;
using cAlgo.API.Internals;

namespace cAlgo.Robots
{
    public enum AvwRiskMode { PercentOfEquity, FixedLots, FixedCash }
    public enum AvwExitStyle { UnitMultiples, Native }
    public enum AvwAnchor { Utc0700, Utc2300, Utc1330 }
    public enum AvwMode { Pullback, Fade2Sd }

    [Robot(AccessRights = AccessRights.None, TimeZone = TimeZones.UTC)]
    public class AvwapLondon : Robot
    {
        // ---------------------------------------------------------------- 1. Identity
        [Parameter("Label", Group = "Identity", DefaultValue = "AVW_XAUUSD")]
        public string Label { get; set; }

        [Parameter("Trade Comment", Group = "Identity", DefaultValue = "AvwapLondon")]
        public string TradeComment { get; set; }

        // ---------------------------------------------------------------- 2. Risk & sizing
        [Parameter("Risk Mode", Group = "Risk & Sizing", DefaultValue = AvwRiskMode.PercentOfEquity)]
        public AvwRiskMode RiskMode { get; set; }

        [Parameter("Risk % of Equity", Group = "Risk & Sizing", DefaultValue = 0.5, MinValue = 0.1, MaxValue = 3.0, Step = 0.1)]
        public double RiskPercent { get; set; }

        [Parameter("Fixed Lots", Group = "Risk & Sizing", DefaultValue = 0.1, MinValue = 0.01, MaxValue = 50.0, Step = 0.01)]
        public double FixedLots { get; set; }

        [Parameter("Fixed Cash Risk", Group = "Risk & Sizing", DefaultValue = 100.0, MinValue = 10.0, MaxValue = 10000.0, Step = 10.0)]
        public double FixedCashRisk { get; set; }

        [Parameter("Max Lots", Group = "Risk & Sizing", DefaultValue = 10.0, MinValue = 0.01, MaxValue = 100.0, Step = 0.01)]
        public double MaxLots { get; set; }

        // ---------------------------------------------------------------- 3. Account protection
        [Parameter("Max Spread (USD)", Group = "Account Protection", DefaultValue = 1.0, MinValue = 0.1, MaxValue = 5.0, Step = 0.1)]
        public double MaxSpreadUsd { get; set; }

        [Parameter("Max Daily Loss % (0 = off)", Group = "Account Protection", DefaultValue = 3.0, MinValue = 0.0, MaxValue = 20.0, Step = 0.5)]
        public double MaxDailyLossPercent { get; set; }

        [Parameter("Close All On Daily Loss", Group = "Account Protection", DefaultValue = false)]
        public bool CloseOnDailyLoss { get; set; }

        [Parameter("Max Trades Per Day", Group = "Account Protection", DefaultValue = 2, MinValue = 1, MaxValue = 10, Step = 1)]
        public int MaxTradesPerDay { get; set; }

        [Parameter("Max Open Positions", Group = "Account Protection", DefaultValue = 1, MinValue = 1, MaxValue = 10, Step = 1)]
        public int MaxOpenPositions { get; set; }

        [Parameter("Cooldown Minutes", Group = "Account Protection", DefaultValue = 0, MinValue = 0, MaxValue = 1440, Step = 15)]
        public int CooldownMinutes { get; set; }

        // ---------------------------------------------------------------- 4. Session & calendar
        [Parameter("VWAP Anchor (UTC)", Group = "Session & Calendar", DefaultValue = AvwAnchor.Utc2300)]
        public AvwAnchor Anchor { get; set; }

        [Parameter("Signal Start Hour UTC", Group = "Session & Calendar", DefaultValue = 8, MinValue = 0, MaxValue = 12, Step = 1)]
        public int SignalStartHourUtc { get; set; }

        [Parameter("Signal End Hour UTC", Group = "Session & Calendar", DefaultValue = 20, MinValue = 14, MaxValue = 21, Step = 1)]
        public int SignalEndHourUtc { get; set; }

        [Parameter("Force Flat Hour UTC", Group = "Session & Calendar", DefaultValue = 20, MinValue = 0, MaxValue = 23, Step = 1)]
        public int ForceFlatHourUtc { get; set; }

        [Parameter("Force Flat Minute", Group = "Session & Calendar", DefaultValue = 55, MinValue = 0, MaxValue = 59, Step = 5)]
        public int ForceFlatMinute { get; set; }

        [Parameter("Trade Monday", Group = "Session & Calendar", DefaultValue = true)]
        public bool TradeMonday { get; set; }

        [Parameter("Trade Tuesday", Group = "Session & Calendar", DefaultValue = true)]
        public bool TradeTuesday { get; set; }

        [Parameter("Trade Wednesday", Group = "Session & Calendar", DefaultValue = true)]
        public bool TradeWednesday { get; set; }

        [Parameter("Trade Thursday", Group = "Session & Calendar", DefaultValue = true)]
        public bool TradeThursday { get; set; }

        [Parameter("Trade Friday", Group = "Session & Calendar", DefaultValue = true)]
        public bool TradeFriday { get; set; }

        // ---------------------------------------------------------------- 5. Strategy signal
        [Parameter("Mode", Group = "Strategy Signal", DefaultValue = AvwMode.Pullback)]
        public AvwMode Mode { get; set; }

        [Parameter("Trend Fraction", Group = "Strategy Signal", DefaultValue = 0.7, MinValue = 0.5, MaxValue = 0.9, Step = 0.05)]
        public double TrendFrac { get; set; }

        [Parameter("Touch Band (x sigma)", Group = "Strategy Signal", DefaultValue = 0.0, MinValue = -1.5, MaxValue = 0.5, Step = 0.25)]
        public double TouchBand { get; set; }

        [Parameter("Slope / Min Bars Since Anchor", Group = "Strategy Signal", DefaultValue = 12, MinValue = 6, MaxValue = 24, Step = 3)]
        public int SlopeBars { get; set; }

        [Parameter("Stop Band (x sigma)", Group = "Strategy Signal", DefaultValue = 1.5, MinValue = 0.5, MaxValue = 3.0, Step = 0.25)]
        public double StopSigmaMult { get; set; }

        [Parameter("Min Stop (x ATR)", Group = "Strategy Signal", DefaultValue = 0.5, MinValue = 0.0, MaxValue = 1.5, Step = 0.25)]
        public double MinStopAtrMult { get; set; }

        [Parameter("Fade Stop Pad (x ATR)", Group = "Strategy Signal", DefaultValue = 0.25, MinValue = 0.0, MaxValue = 1.0, Step = 0.05)]
        public double FadeStopAtrMult { get; set; }

        [Parameter("ATR Period (5m)", Group = "Strategy Signal", DefaultValue = 14, MinValue = 7, MaxValue = 28, Step = 1)]
        public int AtrPeriod { get; set; }

        [Parameter("Max Signals Per UTC Day", Group = "Strategy Signal", DefaultValue = 2, MinValue = 1, MaxValue = 5, Step = 1)]
        public int MaxSignalsPerDay { get; set; }

        // ---------------------------------------------------------------- 6. Exit management
        [Parameter("Exit Style", Group = "Exit Management", DefaultValue = AvwExitStyle.UnitMultiples)]
        public AvwExitStyle ExitStyle { get; set; }

        [Parameter("Stop Mult (x d)", Group = "Exit Management", DefaultValue = 2.0, MinValue = 0.5, MaxValue = 3.0, Step = 0.25)]
        public double SlMult { get; set; }

        [Parameter("Target Mult (x d, 0 = none)", Group = "Exit Management", DefaultValue = 0.0, MinValue = 0.0, MaxValue = 3.0, Step = 0.25)]
        public double TpMult { get; set; }

        [Parameter("Min Stop (USD)", Group = "Exit Management", DefaultValue = 0.15, MinValue = 0.0, MaxValue = 1.0, Step = 0.05)]
        public double MinStopUsd { get; set; }

        [Parameter("TP1 Mult (x unit, 0 = off)", Group = "Exit Management", DefaultValue = 0.0, MinValue = 0.0, MaxValue = 2.0, Step = 0.25)]
        public double Tp1Mult { get; set; }

        [Parameter("TP1 Close %", Group = "Exit Management", DefaultValue = 50.0, MinValue = 10.0, MaxValue = 90.0, Step = 10.0)]
        public double Tp1ClosePercent { get; set; }

        [Parameter("Move To Break-Even", Group = "Exit Management", DefaultValue = false)]
        public bool MoveToBreakEven { get; set; }

        [Parameter("BE Trigger (x unit, used when TP1 off)", Group = "Exit Management", DefaultValue = 1.0, MinValue = 0.25, MaxValue = 3.0, Step = 0.25)]
        public double BreakEvenTriggerMult { get; set; }

        [Parameter("BE Offset (USD)", Group = "Exit Management", DefaultValue = 0.0, MinValue = 0.0, MaxValue = 2.0, Step = 0.1)]
        public double BreakEvenOffsetUsd { get; set; }

        [Parameter("Trailing Stop Mult (x d, 0 = off)", Group = "Exit Management", DefaultValue = 1.0, MinValue = 0.0, MaxValue = 3.0, Step = 0.25)]
        public double TrailingStopMult { get; set; }

        [Parameter("Trail Min Step (USD)", Group = "Exit Management", DefaultValue = 0.05, MinValue = 0.01, MaxValue = 1.0, Step = 0.01)]
        public double TrailStepUsd { get; set; }

        [Parameter("Max Hold Minutes (0 = off)", Group = "Exit Management", DefaultValue = 0, MinValue = 0, MaxValue = 1440, Step = 15)]
        public int MaxHoldMinutes { get; set; }

        // ---------------------------------------------------------------- 7. Diagnostics
        [Parameter("Verbose Log", Group = "Diagnostics", DefaultValue = false)]
        public bool VerboseLog { get; set; }

        [Parameter("Draw Levels", Group = "Diagnostics", DefaultValue = true)]
        public bool DrawLevels { get; set; }

        // ================================================================ state
        private sealed class PosState
        {
            public double Unit;
            public double Best;
            public bool Tp1Done;
            public bool BeDone;
            public bool TrailOn;
        }

        private static readonly DateTime Epoch = new DateTime(1970, 1, 1, 0, 0, 0, DateTimeKind.Utc);
        private readonly Dictionary<int, PosState> _state = new Dictionary<int, PosState>();
        private readonly Dictionary<int, DateTime> _closing = new Dictionary<int, DateTime>();
        private Bars _b5;
        private DateTime _last5 = DateTime.MinValue;
        private bool _warm;
        private bool _canDraw;

        private DateTime _day = DateTime.MinValue;
        private double _dayStartEquity;
        private double _realizedToday;
        private DateTime _realizedAt = DateTime.MinValue;
        private int _tradesToday;
        private bool _dailyLossHit, _flatDone;
        private DateTime _lastCloseTime = DateTime.MinValue;
        private double _nextUnit = double.NaN;

        // anchored VWAP session state
        private long _grp = long.MinValue;
        private double _cv, _s1, _s2;
        private int _nbar, _nAbove;
        private readonly List<double> _vwHist = new List<double>();
        private bool _tl, _ts;
        private double _prevVw = double.NaN, _prevSd = double.NaN;

        // ATR(5m) simple mean of true range
        private double _prevClose5 = double.NaN;
        private readonly Queue<double> _trQ = new Queue<double>();
        private double _trSum;

        // signals per UTC day (Python head(2))
        private DateTime _sigDay = DateTime.MinValue;
        private int _sigCount;

        // ================================================================ lifecycle
        protected override void OnStart()
        {
            _canDraw = DrawLevels && RunningMode != RunningMode.Optimization && RunningMode != RunningMode.SilentBacktesting;
            _b5 = MarketData.GetBars(TimeFrame.Minute5);
            DateTime need = Server.Time.AddDays(-4);
            int guard = 0;
            try
            {
                while (_b5.Count > 0 && _b5.OpenTimes[0] > need && guard++ < 100)
                {
                    if (_b5.LoadMoreHistory() <= 0) break;
                }
            }
            catch (Exception ex)
            {
                Print("LoadMoreHistory not available (" + ex.Message + "); using the bars already loaded");
            }
            CheckNewDay();
            CatchUp();
            _warm = true;
            _b5.BarOpened += OnBar5Opened;
            Positions.Opened += OnPositionOpened;
            Positions.Closed += OnPositionClosed;
            Log("started: m5 bars " + _b5.Count);
        }

        protected override void OnStop()
        {
            if (_b5 != null) _b5.BarOpened -= OnBar5Opened;
            Positions.Opened -= OnPositionOpened;
            Positions.Closed -= OnPositionClosed;
        }

        private void OnBar5Opened(BarOpenedEventArgs e)
        {
            CheckNewDay();
            CatchUp();
        }

        private void CatchUp()
        {
            int j = _b5.Count - 2;
            if (j < 0) return;
            int s = j;
            while (s >= 0 && _b5.OpenTimes[s] > _last5) s--;
            for (int k = s + 1; k <= j; k++) ProcessM5(k);
            if (_b5.OpenTimes[j] > _last5) _last5 = _b5.OpenTimes[j];
        }

        private double AnchorSeconds()
        {
            switch (Anchor)
            {
                case AvwAnchor.Utc0700: return 7.0 * 3600;
                case AvwAnchor.Utc1330: return 13.5 * 3600;
                default: return 23.0 * 3600;
            }
        }

        private void ProcessM5(int i)
        {
            DateTime t = _b5.OpenTimes[i];
            double o = _b5.OpenPrices[i], h = _b5.HighPrices[i], l = _b5.LowPrices[i], c = _b5.ClosePrices[i];
            double v = _b5.TickVolumes[i];
            if (double.IsNaN(o) || double.IsNaN(h) || double.IsNaN(l) || double.IsNaN(c)) return;
            if (double.IsNaN(v) || v < 0) v = 0;

            // ATR14 including this bar (Python: a[m] of the signal bar)
            if (!double.IsNaN(_prevClose5))
            {
                double tr = Math.Max(h - l, Math.Max(Math.Abs(h - _prevClose5), Math.Abs(l - _prevClose5)));
                _trQ.Enqueue(tr); _trSum += tr;
                while (_trQ.Count > AtrPeriod) _trSum -= _trQ.Dequeue();
            }
            _prevClose5 = c;
            double atr = (AtrPeriod > 0 && _trQ.Count == AtrPeriod) ? _trSum / AtrPeriod : double.NaN;

            // session group = floor((bar start - anchor) / 1 day)
            double sec = (t - Epoch).TotalSeconds;
            long grp = (long)Math.Floor((sec - AnchorSeconds()) / 86400.0);
            if (grp != _grp)
            {
                _grp = grp; _cv = _s1 = _s2 = 0; _nbar = _nAbove = 0; _vwHist.Clear();
                _tl = _ts = false; _prevVw = _prevSd = double.NaN;
            }
            double tp = (h + l + c) / 3.0;
            _cv += v; _s1 += tp * v; _s2 += tp * tp * v;
            double den = Math.Max(_cv, 1.0);
            double vw = _s1 / den, ex2 = _s2 / den;
            if (_cv <= 0) vw = tp;                  // no volume yet: neutral (Python would give 0, never ok since sd = 0)
            double sd = Math.Sqrt(Math.Max(ex2 - vw * vw, 0.0));
            if (_cv <= 0) sd = 0;
            _nbar++;
            if (c > vw) _nAbove++;
            double frac = (double)_nAbove / _nbar;
            _vwHist.Add(vw);
            double slope = _nbar > SlopeBars ? vw - _vwHist[_nbar - 1 - SlopeBars] : double.NaN;
            double hourF = t.Hour + t.Minute / 60.0;
            bool ok = hourF >= SignalStartHourUtc && hourF < SignalEndHourUtc && !double.IsNaN(atr)
                      && !double.IsNaN(slope) && _nbar >= SlopeBars && sd > 0;

            if (_canDraw && _warm) DrawSession(t, vw, sd);

            int side = 0;
            double d = double.NaN, tpNative = 0;
            if (Mode == AvwMode.Pullback)
            {
                if (ok)
                {
                    bool upt = frac >= TrendFrac && slope > 0;
                    bool dnt = (1 - frac) >= TrendFrac && slope < 0;
                    if (upt && l <= vw + TouchBand * sd) _tl = true;
                    if (dnt && h >= vw - TouchBand * sd) _ts = true;
                    if (!upt) _tl = false;
                    if (!dnt) _ts = false;
                    if (_tl && c > vw && c > o) { side = 1; _tl = false; }
                    else if (_ts && c < vw && c < o) { side = -1; _ts = false; }
                }
                if (side != 0)
                {
                    d = side == 1 ? c - (vw - StopSigmaMult * sd) : (vw + StopSigmaMult * sd) - c;
                    d = Math.Max(d, MinStopAtrMult * atr);
                    double tq = side == 1 ? vw + 2 * sd - c : c - (vw - 2 * sd);
                    tpNative = Math.Max(tq, d);
                }
            }
            else
            {
                if (ok && !double.IsNaN(_prevVw))
                {
                    double hp = _prevVw + 2 * _prevSd, lp = _prevVw - 2 * _prevSd;
                    bool sh = o > hp && c < vw + 2 * sd;
                    bool lg = o < lp && c > vw - 2 * sd;
                    if (lg) side = 1; else if (sh) side = -1;
                }
                if (side != 0)
                {
                    d = (side == 1 ? c - l : h - c) + FadeStopAtrMult * atr;
                    tpNative = Math.Abs(c - vw);
                }
            }
            _prevVw = vw; _prevSd = sd;
            if (side == 0) return;

            // max signals per UTC day of the signal (bar close)
            DateTime sday = t.AddMinutes(5).AddSeconds(-1).Date;
            if (sday != _sigDay) { _sigDay = sday; _sigCount = 0; }
            if (_sigCount >= MaxSignalsPerDay) return;
            _sigCount++;

            bool live = _warm && (Server.Time - t.AddMinutes(5)).TotalMinutes < 5;
            Log(string.Format("{0} signal {1} at {2:HH:mm} close {3:F2} vwap {4:F2} sd {5:F2} d {6:F2} ({7}/{8}){9}", Mode,
                side > 0 ? "LONG" : "SHORT", t.AddMinutes(5), c, vw, sd, d, _sigCount, MaxSignalsPerDay, live ? "" : " (history, not traded)"));
            if (!live || double.IsNaN(d) || !(d > 0)) return;

            double slD, tpD;
            if (ExitStyle == AvwExitStyle.UnitMultiples) { slD = SlMult * d; tpD = TpMult * d; }
            else { slD = d; tpD = tpNative; }
            OpenMarket(side > 0 ? TradeType.Buy : TradeType.Sell, slD, tpD, d);
        }

        // DrawLevels: only the current session is drawn (3 segments per bar); when a new session starts,
        // the previous session's objects are removed, so at most ~3 x 288 objects exist at any time.
        private readonly List<string> _drawn = new List<string>();
        private long _drawGrp = long.MinValue;

        private void DrawSession(DateTime t, double vw, double sd)
        {
            if (_drawGrp != _grp)
            {
                foreach (var n in _drawn) Chart.RemoveObject(n);
                _drawn.Clear();
                _drawGrp = _grp;
            }
            string k = t.ToString("yyyyMMddHHmm");
            DateTime t2 = t.AddMinutes(5);
            Chart.DrawTrendLine("avw_vw_" + k, t, vw, t2, vw, Color.Gold);
            Chart.DrawTrendLine("avw_up_" + k, t, vw + StopSigmaMult * sd, t2, vw + StopSigmaMult * sd, Color.Gray);
            Chart.DrawTrendLine("avw_dn_" + k, t, vw - StopSigmaMult * sd, t2, vw - StopSigmaMult * sd, Color.Gray);
            _drawn.Add("avw_vw_" + k); _drawn.Add("avw_up_" + k); _drawn.Add("avw_dn_" + k);
        }

        private void OpenMarket(TradeType tt, double sl, double tp, double unit)
        {
            string why;
            if (!CanOpen(Server.Time, out why)) { Log("entry blocked: " + why); return; }
            if (Symbol.PipSize <= 0) return;
            sl = Math.Max(Math.Max(sl, MinStopUsd), MinSlDistance());
            if (tp > 0) tp = Math.Max(tp, MinTpDistance());
            double units = CalcVolume(sl);
            if (units <= 0) { Log("volume below minimum, skip"); return; }
            double? slPips = Math.Round(sl / Symbol.PipSize, 1);
            double? tpPips = tp > 0 ? Math.Round(tp / Symbol.PipSize, 1) : (double?)null;
            _nextUnit = unit;
            var r = ExecuteMarketOrder(tt, SymbolName, units, Label, slPips, tpPips, TradeComment);
            if (!r.IsSuccessful) { Print("market order failed: " + r.Error); _nextUnit = double.NaN; return; }
            if (r.Position != null) Register(r.Position, unit);
            Log(string.Format("{0} {1} units, sl {2:F2}, tp {3:F2}, unit {4:F2}", tt, units, sl, tp, unit));
        }

        // ================================================================ ticks
        protected override void OnTick()
        {
            CheckNewDay();
            DateTime now = Server.Time;
            var mine = Positions.FindAll(Label, SymbolName);

            if (!_flatDone && now >= now.Date.AddHours(ForceFlatHourUtc).AddMinutes(ForceFlatMinute))
            {
                _flatDone = true;
                FlatAll("force flat");
                return;
            }
            if (!_dailyLossHit && MaxDailyLossPercent > 0 && _dayStartEquity > 0)
            {
                if (now >= _realizedAt.AddMinutes(1)) RecomputeRealized();
                double pnl = _realizedToday;
                foreach (var p in mine) pnl += p.NetProfit;
                if (pnl <= -MaxDailyLossPercent / 100.0 * _dayStartEquity)
                {
                    _dailyLossHit = true;
                    Print(string.Format("daily loss limit hit ({0:F2}), new entries blocked for today", pnl));
                    if (CloseOnDailyLoss) { foreach (var p in mine) ClosePos(p, "daily loss"); return; }
                }
            }
            ManagePositions(mine, now);
        }

        // ================================================================ events
        private void OnPositionOpened(PositionOpenedEventArgs e)
        {
            var p = e.Position;
            if (p == null || p.Label != Label || p.SymbolName != SymbolName) return;
            if (_state.ContainsKey(p.Id) || double.IsNaN(_nextUnit)) return;
            Register(p, _nextUnit);
        }

        private void OnPositionClosed(PositionClosedEventArgs e)
        {
            var p = e.Position;
            if (p == null || p.Label != Label || p.SymbolName != SymbolName) return;
            _state.Remove(p.Id);
            _closing.Remove(p.Id);
            _lastCloseTime = Server.Time;
            RecomputeRealized();
            Log(string.Format("closed {0} net {1:F2} ({2})", p.Id, p.NetProfit, e.Reason));
        }

        // ================================================================ shared framework
        private void Log(string s)
        {
            if (VerboseLog) Print(s);
        }

        private void CheckNewDay()
        {
            DateTime d = Server.Time.Date;
            if (d == _day) return;
            _day = d;
            _dayStartEquity = Account.Equity;
            _realizedToday = 0;
            _tradesToday = 0;
            _dailyLossHit = false;
            _flatDone = false;
        }

        // today's realised P&L of this label + symbol from History; partial closes appear there as
        // separate deals (Positions.Closed does not fire for them)
        private void RecomputeRealized()
        {
            _realizedAt = Server.Time;
            double s = 0;
            foreach (var h in History.FindAll(Label, SymbolName))
                if (h.ClosingTime >= _day) s += h.NetProfit;
            _realizedToday = s;
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

        private bool CanOpen(DateTime now, out string why)
        {
            why = null;
            if (!DayAllowed(now.DayOfWeek)) why = "weekday off";
            else if (_flatDone) why = "after force-flat time";
            else if (_dailyLossHit) why = "daily loss limit";
            else if (_tradesToday >= MaxTradesPerDay) why = "max trades per day";
            else if (Positions.FindAll(Label, SymbolName).Length >= MaxOpenPositions) why = "max open positions";
            else if (CooldownMinutes > 0 && now < _lastCloseTime.AddMinutes(CooldownMinutes)) why = "cooldown";
            else if (Symbol.Ask - Symbol.Bid > MaxSpreadUsd) why = string.Format("spread {0:F2} > {1:F2}", Symbol.Ask - Symbol.Bid, MaxSpreadUsd);
            return why == null;
        }

        private double MinSlDistance()
        {
            double v = Symbol.MinStopLossDistance;
            if (double.IsNaN(v) || v <= 0) return 0;
            return Symbol.MinDistanceType == SymbolMinDistanceType.Pips ? v * Symbol.PipSize : v / 100.0 * Symbol.Bid;
        }

        private double MinTpDistance()
        {
            double v = Symbol.MinTakeProfitDistance;
            if (double.IsNaN(v) || v <= 0) return 0;
            return Symbol.MinDistanceType == SymbolMinDistanceType.Pips ? v * Symbol.PipSize : v / 100.0 * Symbol.Bid;
        }

        // risk cash / (stop distance x LotSize x account value per unit per 1.0 price) = lots
        private double CalcVolume(double slDist)
        {
            double units;
            if (RiskMode == AvwRiskMode.FixedLots)
                units = Symbol.QuantityToVolumeInUnits(FixedLots);
            else
            {
                double cash = RiskMode == AvwRiskMode.PercentOfEquity ? Account.Equity * RiskPercent / 100.0 : FixedCashRisk;
                double valuePerPrice = Symbol.TickSize > 0 ? Symbol.TickValue / Symbol.TickSize : 0;
                if (!(slDist > 0) || !(valuePerPrice > 0) || !(Symbol.LotSize > 0) || !(cash > 0)) return 0;
                double lots = cash / (slDist * Symbol.LotSize * valuePerPrice);
                units = lots * Symbol.LotSize;
            }
            if (double.IsNaN(units) || double.IsInfinity(units)) return 0;
            if (units < Symbol.VolumeInUnitsMin) return 0;
            double maxU = Math.Min(Symbol.VolumeInUnitsMax, Symbol.QuantityToVolumeInUnits(MaxLots));
            units = Math.Min(units, maxU);
            units = Symbol.NormalizeVolumeInUnits(units, RoundingMode.Down);
            return units >= Symbol.VolumeInUnitsMin ? units : 0;
        }

        private void Register(Position p, double unit)
        {
            if (_state.ContainsKey(p.Id)) return;
            _state[p.Id] = new PosState { Unit = unit, Best = p.EntryPrice, TrailOn = TrailingStopMult > 0 && !(Tp1Mult > 0) };
            _tradesToday++;
            _nextUnit = double.NaN;
        }

        private void ManagePositions(Position[] mine, DateTime now)
        {
            foreach (var p in mine)
            {
                PosState st;
                if (!_state.TryGetValue(p.Id, out st)) continue;
                int side = p.TradeType == TradeType.Buy ? 1 : -1;
                double px = side == 1 ? Symbol.Bid : Symbol.Ask;
                double fav = (px - p.EntryPrice) * side;
                double unit = st.Unit;

                if (MaxHoldMinutes > 0 && (now - p.EntryTime).TotalMinutes >= MaxHoldMinutes) { ClosePos(p, "max hold"); continue; }

                if (Tp1Mult > 0 && !st.Tp1Done && fav >= Tp1Mult * unit)
                {
                    st.Tp1Done = true;
                    double cu = Symbol.NormalizeVolumeInUnits(p.VolumeInUnits * Tp1ClosePercent / 100.0, RoundingMode.Down);
                    if (cu >= Symbol.VolumeInUnitsMin && p.VolumeInUnits - cu >= Symbol.VolumeInUnitsMin)
                    {
                        var r = ClosePosition(p, cu);
                        if (!r.IsSuccessful) Print("TP1 partial close failed: " + r.Error);
                        else { Log("TP1 partial close " + cu); RecomputeRealized(); }
                    }
                    else Log("TP1 partial skipped (volume would fall below minimum)");
                    if (MoveToBreakEven) { MoveStop(p, p.EntryPrice + side * BreakEvenOffsetUsd, side); st.BeDone = true; }
                    if (TrailingStopMult > 0) { st.TrailOn = true; st.Best = px; }
                }
                else if (!(Tp1Mult > 0) && MoveToBreakEven && !st.BeDone && fav >= BreakEvenTriggerMult * unit)
                {
                    st.BeDone = true;
                    MoveStop(p, p.EntryPrice + side * BreakEvenOffsetUsd, side);
                }

                if (st.TrailOn && TrailingStopMult > 0)
                {
                    if ((px - st.Best) * side > 0) st.Best = px;
                    double ns = st.Best - side * TrailingStopMult * unit;
                    if (!p.StopLoss.HasValue || (ns - p.StopLoss.Value) * side >= TrailStepUsd) MoveStop(p, ns, side);
                }
            }
        }

        // move the stop only in the favourable direction; if it would cross the price, exit at market
        private void MoveStop(Position p, double price, int side)
        {
            price = Math.Round(price, Symbol.Digits);
            if (p.StopLoss.HasValue && (price - p.StopLoss.Value) * side <= 0) return;
            double px = side == 1 ? Symbol.Bid : Symbol.Ask;
            if ((px - price) * side <= 0) { ClosePos(p, "stop level crossed"); return; }
            double md = MinSlDistance();
            if ((px - price) * side < md)
            {
                price = Math.Round(px - side * md, Symbol.Digits);
                if (p.StopLoss.HasValue && (price - p.StopLoss.Value) * side <= 0) return;
            }
            var r = ModifyPosition(p, price, p.TakeProfit, ProtectionType.Absolute);
            if (!r.IsSuccessful) Print("modify SL failed: " + r.Error);
        }

        // "closing" guard: one close attempt per position per minute, so a rejected close cannot spam every tick
        private void ClosePos(Position p, string why)
        {
            DateTime last;
            if (_closing.TryGetValue(p.Id, out last) && Server.Time < last.AddMinutes(1)) return;
            _closing[p.Id] = Server.Time;
            var r = ClosePosition(p);
            if (!r.IsSuccessful) Print("close failed (" + why + "): " + r.Error + " - retry in 1 min");
            else Log("closed position " + p.Id + ": " + why);
        }

        private void CancelMyPending(string why)
        {
            foreach (var o in PendingOrders.ToArray())
            {
                if (o.Label != Label || o.SymbolName != SymbolName) continue;
                var r = CancelPendingOrder(o);
                if (!r.IsSuccessful) Print("cancel failed: " + r.Error);
                else Log("cancelled pending " + o.Id + ": " + why);
            }
        }

        private void FlatAll(string why)
        {
            CancelMyPending(why);
            foreach (var p in Positions.FindAll(Label, SymbolName)) ClosePos(p, why);
        }
    }
}
