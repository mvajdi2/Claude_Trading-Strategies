// =================================================================================================
// IbFadeNy.cs  -  cTrader Automate cBot (C#, .NET 6)
// Port of strategies/ib_fade_ny.py (+ strategies/batcha_util.py helpers), frozen settings from
// strategy_cards/ib_fade_ny.frozen.json (exit {"sl": 2.0, "tp": 3.0} in units of the native stop d).
//
// Rules:
//   * Initial balance (IB) = high/low of 1-minute bars opening in [IbStart, IbStart + IbMinutes).
//     IbStart: Ny0820 = 08:20 New York (COMEX open, DST-aware, US rule coded below), Ny0930 =
//     09:30 New York, Utc1330 = 13:30 UTC. Needs >= 60% of the expected 1m bars. W = IB width.
//   * Day filter: W > WideMult x median W of the previous 20 valid IBs (min 10 IBs).
//   * After the IB, on each closed 5-minute bar (bars closing by 18:00 UTC): a bar high above the
//     IB high (low below the IB low) marks a probe; track the probe extreme. The first 5m close
//     back inside the IB and not past the midpoint fades toward the midpoint: short after an upper
//     probe (mid < close < IB high), long after a lower probe (IB low < close < mid). The short
//     check runs first, as in Python. One signal per day.
//   * d = |close - (probe extreme +/- ProbeAtrMult x ATR14(5m) of the previous bar)|.
//   * Exit (UnitMultiples, frozen): stop = SlMult x d, target = TpMult x d from the entry fill.
//     Native: stop = d, target = distance from the close to the IB midpoint. Flat at 20:00 UTC.
//   * Entry = market order on the first tick after the signal bar closes.
// =================================================================================================
using System;
using System.Collections.Generic;
using System.Linq;
using cAlgo.API;
using cAlgo.API.Internals;

namespace cAlgo.Robots
{
    public enum IbfRiskMode { PercentOfEquity, FixedLots, FixedCash }
    public enum IbfExitStyle { UnitMultiples, Native }
    public enum IbfIbStart { Utc1330, Ny0820, Ny0930 }

    [Robot(AccessRights = AccessRights.None, TimeZone = TimeZones.UTC)]
    public class IbFadeNy : Robot
    {
        // ---------------------------------------------------------------- 1. Identity
        [Parameter("Label", Group = "Identity", DefaultValue = "IBF_XAUUSD")]
        public string Label { get; set; }

        [Parameter("Trade Comment", Group = "Identity", DefaultValue = "IbFadeNy")]
        public string TradeComment { get; set; }

        // ---------------------------------------------------------------- 2. Risk & sizing
        [Parameter("Risk Mode", Group = "Risk & Sizing", DefaultValue = IbfRiskMode.PercentOfEquity)]
        public IbfRiskMode RiskMode { get; set; }

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

        [Parameter("Max Trades Per Day", Group = "Account Protection", DefaultValue = 1, MinValue = 1, MaxValue = 10, Step = 1)]
        public int MaxTradesPerDay { get; set; }

        [Parameter("Max Open Positions", Group = "Account Protection", DefaultValue = 1, MinValue = 1, MaxValue = 10, Step = 1)]
        public int MaxOpenPositions { get; set; }

        [Parameter("Cooldown Minutes", Group = "Account Protection", DefaultValue = 0, MinValue = 0, MaxValue = 1440, Step = 15)]
        public int CooldownMinutes { get; set; }

        // ---------------------------------------------------------------- 4. Session & calendar
        [Parameter("IB Start", Group = "Session & Calendar", DefaultValue = IbfIbStart.Ny0820)]
        public IbfIbStart IbStart { get; set; }

        [Parameter("IB Minutes", Group = "Session & Calendar", DefaultValue = 30, MinValue = 15, MaxValue = 60, Step = 15)]
        public int IbMinutes { get; set; }

        [Parameter("Signal End Hour UTC (5m bar close)", Group = "Session & Calendar", DefaultValue = 18, MinValue = 14, MaxValue = 20, Step = 1)]
        public int SignalEndHourUtc { get; set; }

        [Parameter("Strategy Flat Hour UTC", Group = "Session & Calendar", DefaultValue = 20, MinValue = 16, MaxValue = 21, Step = 1)]
        public int StrategyFlatHourUtc { get; set; }

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
        [Parameter("Wide Mult (W > x median)", Group = "Strategy Signal", DefaultValue = 1.2, MinValue = 1.0, MaxValue = 1.6, Step = 0.05)]
        public double WideMult { get; set; }

        [Parameter("IB Median Lookback (IBs)", Group = "Strategy Signal", DefaultValue = 20, MinValue = 10, MaxValue = 40, Step = 5)]
        public int IbMedianLookback { get; set; }

        [Parameter("IB Median Min IBs", Group = "Strategy Signal", DefaultValue = 10, MinValue = 5, MaxValue = 20, Step = 5)]
        public int IbMedianMinPeriods { get; set; }

        [Parameter("Min IB Bar Fraction", Group = "Strategy Signal", DefaultValue = 0.6, MinValue = 0.3, MaxValue = 1.0, Step = 0.1)]
        public double MinIbBarFrac { get; set; }

        [Parameter("Probe ATR Mult", Group = "Strategy Signal", DefaultValue = 0.1, MinValue = 0.0, MaxValue = 0.5, Step = 0.05)]
        public double ProbeAtrMult { get; set; }

        [Parameter("ATR Period (5m)", Group = "Strategy Signal", DefaultValue = 14, MinValue = 7, MaxValue = 28, Step = 1)]
        public int AtrPeriod { get; set; }

        // ---------------------------------------------------------------- 6. Exit management
        [Parameter("Exit Style", Group = "Exit Management", DefaultValue = IbfExitStyle.UnitMultiples)]
        public IbfExitStyle ExitStyle { get; set; }

        [Parameter("Stop Mult (x d)", Group = "Exit Management", DefaultValue = 2.0, MinValue = 0.5, MaxValue = 3.0, Step = 0.25)]
        public double SlMult { get; set; }

        [Parameter("Target Mult (x d, 0 = none)", Group = "Exit Management", DefaultValue = 3.0, MinValue = 0.0, MaxValue = 4.0, Step = 0.25)]
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

        [Parameter("Trailing Stop Mult (x unit, 0 = off)", Group = "Exit Management", DefaultValue = 0.0, MinValue = 0.0, MaxValue = 3.0, Step = 0.25)]
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

        private readonly Dictionary<int, PosState> _state = new Dictionary<int, PosState>();
        private Bars _b1, _b5;
        private DateTime _last1 = DateTime.MinValue, _last5 = DateTime.MinValue;
        private bool _warm;
        private bool _canDraw;

        private DateTime _day = DateTime.MinValue;
        private double _dayStartEquity;
        private double _realizedToday;
        private int _tradesToday;
        private bool _dailyLossHit, _flatDone;
        private DateTime _lastCloseTime = DateTime.MinValue;
        private double _nextUnit = double.NaN;

        // IB accumulation
        private DateTime _ibDate = DateTime.MinValue, _ibT0, _ibT1;
        private double _ibH, _ibL;
        private int _ibN;
        private bool _ibFinal;
        private readonly List<double> _ibWidths = new List<double>();

        // active fade setup for today
        private bool _active;
        private DateTime _actDate = DateTime.MinValue;
        private double _actH, _actL, _actMid;
        private bool _probeHi, _probeLo;
        private double _extHi, _extLo;

        // ATR(5m) simple mean of true range
        private double _prevClose5 = double.NaN;
        private readonly Queue<double> _trQ = new Queue<double>();
        private double _trSum;

        // ================================================================ lifecycle
        protected override void OnStart()
        {
            _canDraw = DrawLevels && RunningMode != RunningMode.Optimization && RunningMode != RunningMode.SilentBacktesting;
            _b1 = MarketData.GetBars(TimeFrame.Minute);
            _b5 = MarketData.GetBars(TimeFrame.Minute5);
            LoadHistory(_b1, 45);         // >= 20 prior IBs for the median
            LoadHistory(_b5, 45);
            CheckNewDay();
            CatchUp();
            _warm = true;

            _b1.BarOpened += OnBar1Opened;
            _b5.BarOpened += OnBar5Opened;
            Positions.Opened += OnPositionOpened;
            Positions.Closed += OnPositionClosed;
            Log("started: prior IBs " + _ibWidths.Count);
        }

        protected override void OnStop()
        {
            if (_b1 != null) _b1.BarOpened -= OnBar1Opened;
            if (_b5 != null) _b5.BarOpened -= OnBar5Opened;
            Positions.Opened -= OnPositionOpened;
            Positions.Closed -= OnPositionClosed;
        }

        private void LoadHistory(Bars b, int days)
        {
            DateTime need = Server.Time.AddDays(-days);
            int guard = 0;
            try
            {
                while (b.Count > 0 && b.OpenTimes[0] > need && guard++ < 500)
                {
                    int n = b.LoadMoreHistory();
                    if (n <= 0) break;
                }
            }
            catch (Exception ex)
            {
                Print("LoadMoreHistory not available (" + ex.Message + "); using the bars already loaded");
            }
        }

        private void OnBar1Opened(BarOpenedEventArgs e)
        {
            CheckNewDay();
            CatchUp();
        }

        private void OnBar5Opened(BarOpenedEventArgs e)
        {
            CheckNewDay();
            CatchUp();
        }

        private void CatchUp()
        {
            int i = _b1.Count - 2;
            if (i >= 0)
            {
                int s = i;
                while (s >= 0 && _b1.OpenTimes[s] > _last1) s--;
                for (int k = s + 1; k <= i; k++) ProcessM1(k);
                if (_b1.OpenTimes[i] > _last1) _last1 = _b1.OpenTimes[i];
            }
            int j = _b5.Count - 2;
            if (j >= 0)
            {
                int s = j;
                while (s >= 0 && _b5.OpenTimes[s] > _last5) s--;
                for (int k = s + 1; k <= j; k++) ProcessM5(k);
                if (_b5.OpenTimes[j] > _last5) _last5 = _b5.OpenTimes[j];
            }
        }

        // ---------------------------------------------------------------- DST (US rule, coded)
        private static DateTime NthSunday(int year, int month, int n)
        {
            var d = new DateTime(year, month, 1);
            int add = ((int)DayOfWeek.Sunday - (int)d.DayOfWeek + 7) % 7;
            return d.AddDays(add + 7 * (n - 1));
        }

        // US DST: 2nd Sunday of March 02:00 local to 1st Sunday of November 02:00 local.
        // The IB starts at 08:20 / 09:30 local, after the 02:00 switch, so the date decides.
        private static bool IsUsDst(DateTime date)
        {
            DateTime s = NthSunday(date.Year, 3, 2), e = NthSunday(date.Year, 11, 1);
            return date.Date >= s && date.Date < e;
        }

        private DateTime IbStartUtc(DateTime date)
        {
            int offset = IsUsDst(date) ? 4 : 5;     // New York = UTC-4 (EDT) / UTC-5 (EST)
            switch (IbStart)
            {
                case IbfIbStart.Ny0820: return date.Date.AddHours(8 + offset).AddMinutes(20);
                case IbfIbStart.Ny0930: return date.Date.AddHours(9 + offset).AddMinutes(30);
                default: return date.Date.AddHours(13).AddMinutes(30);
            }
        }

        // ---------------------------------------------------------------- bar processing
        private void ProcessM1(int i)
        {
            DateTime t = _b1.OpenTimes[i];
            double h = _b1.HighPrices[i], l = _b1.LowPrices[i];
            if (double.IsNaN(h) || double.IsNaN(l)) return;
            DateTime d = t.Date;
            if (_ibDate != d)
            {
                FinalizeIb();                      // previous day, if not finalized yet
                _ibDate = d; _ibT0 = IbStartUtc(d); _ibT1 = _ibT0.AddMinutes(IbMinutes);
                _ibN = 0; _ibH = double.MinValue; _ibL = double.MaxValue; _ibFinal = false;
            }
            if (t >= _ibT0 && t < _ibT1)
            {
                _ibH = Math.Max(_ibH, h); _ibL = Math.Min(_ibL, l); _ibN++;
            }
            else if (t >= _ibT1) FinalizeIb();
        }

        private void FinalizeIb()
        {
            if (_ibFinal || _ibDate == DateTime.MinValue) return;
            _ibFinal = true;
            int need = Math.Max(1, (int)(MinIbBarFrac * IbMinutes));
            if (_ibN < need) return;
            double w = _ibH - _ibL;
            double med = double.NaN;
            int n = _ibWidths.Count;
            int cnt = Math.Min(IbMedianLookback, n);
            if (cnt >= IbMedianMinPeriods && cnt > 0)
            {
                var win = _ibWidths.GetRange(n - cnt, cnt);
                win.Sort();
                med = cnt % 2 == 1 ? win[cnt / 2] : 0.5 * (win[cnt / 2 - 1] + win[cnt / 2]);
            }
            _ibWidths.Add(w);
            bool wide = !double.IsNaN(med) && w > WideMult * med;
            if (_warm) Log(string.Format("IB {0:yyyy-MM-dd} {1:HH:mm}-{2:HH:mm} UTC: {3:F2}-{4:F2} W={5:F2} med={6:F2} -> {7}",
                _ibDate, _ibT0, _ibT1, _ibL, _ibH, w, med, wide ? "WIDE, watch fade" : "skip"));
            if (!wide) return;
            _active = true; _actDate = _ibDate;
            _actH = _ibH; _actL = _ibL; _actMid = 0.5 * (_ibH + _ibL);
            _probeHi = _probeLo = false; _extHi = double.MinValue; _extLo = double.MaxValue;
            if (_canDraw && _warm)
            {
                string k = _ibDate.ToString("yyyyMMdd");
                Chart.DrawRectangle("ibf_ib_" + k, _ibT0, _ibH, _ibT1, _ibL, Color.SteelBlue);
                Chart.DrawTrendLine("ibf_mid_" + k, _ibT1, _actMid, _ibDate.AddHours(SignalEndHourUtc), _actMid, Color.Gold);
            }
        }

        private void ProcessM5(int i)
        {
            DateTime t = _b5.OpenTimes[i];
            double h = _b5.HighPrices[i], l = _b5.LowPrices[i], c = _b5.ClosePrices[i];
            if (double.IsNaN(h) || double.IsNaN(l) || double.IsNaN(c)) return;

            // ATR of the previous bar (Python: A[j - 1]), then add this bar's true range
            double atrPrev = (AtrPeriod > 0 && _trQ.Count == AtrPeriod) ? _trSum / AtrPeriod : double.NaN;
            if (!double.IsNaN(_prevClose5))
            {
                double tr = Math.Max(h - l, Math.Max(Math.Abs(h - _prevClose5), Math.Abs(l - _prevClose5)));
                _trQ.Enqueue(tr); _trSum += tr;
                while (_trQ.Count > AtrPeriod) _trSum -= _trQ.Dequeue();
            }
            _prevClose5 = c;

            // make sure today's IB is finalized once a 5m bar at/after its end has closed
            if (_ibDate == t.Date && t >= _ibT1) FinalizeIb();
            if (!_active || _actDate != t.Date || t < _ibT1) return;
            if (t > t.Date.AddHours(SignalEndHourUtc).AddMinutes(-5)) { _active = false; return; }

            if (h > _actH) { _probeHi = true; _extHi = Math.Max(_extHi, h); }
            if (l < _actL) { _probeLo = true; _extLo = Math.Min(_extLo, l); }

            int side = 0; double d = double.NaN, tpNative = double.NaN;
            if (_probeHi && c > _actMid && c < _actH)
            {
                side = -1; d = _extHi + ProbeAtrMult * atrPrev - c; tpNative = c - _actMid;
            }
            else if (_probeLo && c > _actL && c < _actMid)
            {
                side = 1; d = c - (_extLo - ProbeAtrMult * atrPrev); tpNative = _actMid - c;
            }
            if (side == 0) return;
            _active = false;                       // one signal per day (Python: break)

            bool live = _warm && (Server.Time - t.AddMinutes(5)).TotalMinutes < 5;
            Log(string.Format("fade signal {0} at {1:HH:mm} close {2:F2}, d={3:F2}, ATR={4:F2}{5}", side > 0 ? "LONG" : "SHORT",
                t.AddMinutes(5), c, d, atrPrev, live ? "" : " (history, not traded)"));
            if (!live || double.IsNaN(d) || !(d > 0) || !(tpNative > 0)) return;

            double sl, tp;
            if (ExitStyle == IbfExitStyle.UnitMultiples) { sl = SlMult * d; tp = TpMult * d; }
            else { sl = d; tp = tpNative; }
            OpenMarket(side > 0 ? TradeType.Buy : TradeType.Sell, sl, tp, d);
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
            if (mine.Length > 0 && now >= now.Date.AddHours(StrategyFlatHourUtc))
            {
                foreach (var p in mine) ClosePos(p, "strategy flat");
                return;
            }
            if (!_dailyLossHit && MaxDailyLossPercent > 0 && _dayStartEquity > 0)
            {
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

        private void RecomputeRealized()
        {
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
            if (RiskMode == IbfRiskMode.FixedLots)
                units = Symbol.QuantityToVolumeInUnits(FixedLots);
            else
            {
                double cash = RiskMode == IbfRiskMode.PercentOfEquity ? Account.Equity * RiskPercent / 100.0 : FixedCashRisk;
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

        private void ClosePos(Position p, string why)
        {
            var r = ClosePosition(p);
            if (!r.IsSuccessful) Print("close failed (" + why + "): " + r.Error);
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
