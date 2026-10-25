// =================================================================================================
// AsianRangeBreakout.cs  -  cTrader Automate cBot (C#, .NET 6)
// Port of strategies/asian_range_breakout.py + strategies/batcha_util.py, frozen settings from
// strategy_cards/asian_range_breakout.frozen.json (exit {"sl": 2.0, "tp": 1.0} in units of W).
//
// Rules (all times UTC):
//   * Range = high/low of 1-minute bars with open time in [RangeStart, RangeEnd). W = high - low.
//     The range needs at least MinRangeBarFrac of the expected 1m bars (Python window_hl min_frac=0.6).
//   * Day filter (RangeFilter): Usd 3..20 USD | Atr 0.2..1.0 x ATR14(daily, previous day) |
//     Pct 0.3..1.6 % of the last range close | None.  Daily bars run 23:00-21:00 UTC and need
//     >= 300 one-minute bars (Python batcha_util.daily).
//   * Vol state (VolState): percentile of the previous day's realised variance (sum of squared
//     5-minute log returns, bars opening 00:00-20:55) inside the trailing 250 days (min 60 days):
//     Top >= 2/3, MidTop >= 1/3, All = off.
//   * At RangeEnd, if mid price is strictly inside (low - buffer, high + buffer), place an OCO pair:
//     buy stop at high + buffer, sell stop at low - buffer, expiring at Cutoff. First fill cancels
//     the other. One trade per day.
//   * Exit (UnitMultiples, frozen): stop = SlMult x W and target = TpMult x W, both measured from the
//     entry fill. Native: stop = buy level - sell level, target = TgtX x W. Close all at StrategyFlat.
// =================================================================================================
using System;
using System.Collections.Generic;
using System.Linq;
using cAlgo.API;
using cAlgo.API.Internals;

namespace cAlgo.Robots
{
    public enum ArbRiskMode { PercentOfEquity, FixedLots, FixedCash }
    public enum ArbExitStyle { UnitMultiples, Native }
    public enum ArbRangeFilter { Usd, Atr, Pct, None }
    public enum ArbVolState { All, MidTop, Top }

    [Robot(AccessRights = AccessRights.None, TimeZone = TimeZones.UTC)]
    public class AsianRangeBreakout : Robot
    {
        // ---------------------------------------------------------------- 1. Identity
        [Parameter("Label", Group = "Identity", DefaultValue = "ARB_XAUUSD")]
        public string Label { get; set; }

        [Parameter("Trade Comment", Group = "Identity", DefaultValue = "AsianRangeBreakout")]
        public string TradeComment { get; set; }

        // ---------------------------------------------------------------- 2. Risk & sizing
        [Parameter("Risk Mode", Group = "Risk & Sizing", DefaultValue = ArbRiskMode.PercentOfEquity)]
        public ArbRiskMode RiskMode { get; set; }

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
        [Parameter("Range Start Hour UTC", Group = "Session & Calendar", DefaultValue = 0, MinValue = 0, MaxValue = 3, Step = 1)]
        public int RangeStartHourUtc { get; set; }

        [Parameter("Range End Hour UTC (orders placed)", Group = "Session & Calendar", DefaultValue = 6, MinValue = 4, MaxValue = 8, Step = 1)]
        public int RangeEndHourUtc { get; set; }

        [Parameter("Order Cutoff Hour UTC (expiry)", Group = "Session & Calendar", DefaultValue = 12, MinValue = 8, MaxValue = 15, Step = 1)]
        public int CutoffHourUtc { get; set; }

        [Parameter("Strategy Flat Hour UTC", Group = "Session & Calendar", DefaultValue = 16, MinValue = 12, MaxValue = 20, Step = 1)]
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
        [Parameter("Breakout Buffer (USD)", Group = "Strategy Signal", DefaultValue = 2.0, MinValue = 0.25, MaxValue = 3.0, Step = 0.25)]
        public double BufferUsd { get; set; }

        [Parameter("Range Filter", Group = "Strategy Signal", DefaultValue = ArbRangeFilter.Atr)]
        public ArbRangeFilter RangeFilter { get; set; }

        [Parameter("Usd Filter: Min W (USD)", Group = "Strategy Signal", DefaultValue = 3.0, MinValue = 1.0, MaxValue = 10.0, Step = 0.5)]
        public double RngUsdMin { get; set; }

        [Parameter("Usd Filter: Max W (USD)", Group = "Strategy Signal", DefaultValue = 20.0, MinValue = 10.0, MaxValue = 40.0, Step = 1.0)]
        public double RngUsdMax { get; set; }

        [Parameter("Atr Filter: Min W / ATR", Group = "Strategy Signal", DefaultValue = 0.2, MinValue = 0.0, MaxValue = 0.5, Step = 0.05)]
        public double RngAtrMin { get; set; }

        [Parameter("Atr Filter: Max W / ATR", Group = "Strategy Signal", DefaultValue = 1.0, MinValue = 0.5, MaxValue = 2.0, Step = 0.1)]
        public double RngAtrMax { get; set; }

        [Parameter("Pct Filter: Min W %", Group = "Strategy Signal", DefaultValue = 0.3, MinValue = 0.1, MaxValue = 1.0, Step = 0.1)]
        public double RngPctMin { get; set; }

        [Parameter("Pct Filter: Max W %", Group = "Strategy Signal", DefaultValue = 1.6, MinValue = 0.8, MaxValue = 3.0, Step = 0.1)]
        public double RngPctMax { get; set; }

        [Parameter("Daily ATR Period (days)", Group = "Strategy Signal", DefaultValue = 14, MinValue = 5, MaxValue = 30, Step = 1)]
        public int AtrPeriodDays { get; set; }

        [Parameter("Min 1m Bars Per Daily Bar", Group = "Strategy Signal", DefaultValue = 300, MinValue = 100, MaxValue = 1000, Step = 50)]
        public int MinDailyBars { get; set; }

        [Parameter("Min Range Bar Fraction", Group = "Strategy Signal", DefaultValue = 0.6, MinValue = 0.3, MaxValue = 1.0, Step = 0.1)]
        public double MinRangeBarFrac { get; set; }

        [Parameter("Vol State Filter", Group = "Strategy Signal", DefaultValue = ArbVolState.Top)]
        public ArbVolState VolState { get; set; }

        [Parameter("Vol Lookback (days)", Group = "Strategy Signal", DefaultValue = 250, MinValue = 100, MaxValue = 300, Step = 50)]
        public int VolLookbackDays { get; set; }

        [Parameter("Vol Min History (days)", Group = "Strategy Signal", DefaultValue = 60, MinValue = 20, MaxValue = 120, Step = 10)]
        public int VolMinHistoryDays { get; set; }

        [Parameter("History To Load (calendar days)", Group = "Strategy Signal", DefaultValue = 400, MinValue = 30, MaxValue = 800, Step = 10)]
        public int HistoryDays { get; set; }

        // ---------------------------------------------------------------- 6. Exit management
        [Parameter("Exit Style", Group = "Exit Management", DefaultValue = ArbExitStyle.UnitMultiples)]
        public ArbExitStyle ExitStyle { get; set; }

        [Parameter("Stop Mult (x W)", Group = "Exit Management", DefaultValue = 2.0, MinValue = 0.5, MaxValue = 3.0, Step = 0.25)]
        public double SlMult { get; set; }

        [Parameter("Target Mult (x W, 0 = none)", Group = "Exit Management", DefaultValue = 1.0, MinValue = 0.0, MaxValue = 3.0, Step = 0.25)]
        public double TpMult { get; set; }

        [Parameter("Native Target (x W)", Group = "Exit Management", DefaultValue = 1.5, MinValue = 0.5, MaxValue = 3.0, Step = 0.25)]
        public double TgtX { get; set; }

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
        private readonly Dictionary<int, DateTime> _closing = new Dictionary<int, DateTime>();
        private Bars _b1, _b5;
        private DateTime _last1 = DateTime.MinValue, _last5 = DateTime.MinValue;
        private bool _warm;
        private bool _canDraw;

        // day bookkeeping
        private DateTime _day = DateTime.MinValue;
        private double _dayStartEquity;
        private double _realizedToday;
        private DateTime _realizedAt = DateTime.MinValue;
        private int _tradesToday;
        private bool _dailyLossHit, _flatDone;
        private DateTime _lastCloseTime = DateTime.MinValue;

        // daily 23:00-21:00 bars (for ATR)
        private DateTime _dTd = DateTime.MinValue;
        private double _dH, _dL, _dC;
        private int _dN;
        private readonly List<double> _dHigh = new List<double>(), _dLow = new List<double>(), _dClose = new List<double>();

        // realised variance per UTC date (5m log returns, bars opening before 21:00)
        private double _prev5Close = double.NaN;
        private DateTime _rvDate = DateTime.MinValue;
        private double _rvSum;
        private bool _rvOpen;
        private readonly List<double> _rv = new List<double>();

        // today's range
        private DateTime _rDate = DateTime.MinValue;
        private double _rH, _rL, _rC;
        private int _rN;
        private DateTime _decidedDate = DateTime.MinValue;
        private DateTime _ordersDate = DateTime.MinValue;
        private double _pendSl, _pendTp, _pendUnit = double.NaN;

        // ================================================================ lifecycle
        protected override void OnStart()
        {
            _canDraw = DrawLevels && RunningMode != RunningMode.Optimization && RunningMode != RunningMode.SilentBacktesting;
            _b1 = MarketData.GetBars(TimeFrame.Minute);
            _b5 = MarketData.GetBars(TimeFrame.Minute5);
            LoadHistory(_b1, Math.Max(30, AtrPeriodDays * 2 + 10));
            LoadHistory(_b5, HistoryDays);
            CheckNewDay();
            CatchUp();                    // build state from closed history bars, no trading
            _warm = true;
            _decidedDate = Server.Time.Date.AddHours(RangeEndHourUtc) <= Server.Time ? Server.Time.Date : DateTime.MinValue;

            _b1.BarOpened += OnBar1Opened;
            _b5.BarOpened += OnBar5Opened;
            Positions.Opened += OnPositionOpened;
            Positions.Closed += OnPositionClosed;
            PendingOrders.Filled += OnPendingFilled;
            Print(string.Format("started: earliest m1 bar {0:yyyy-MM-dd HH:mm}, earliest m5 bar {1:yyyy-MM-dd HH:mm}; daily rows {2} (ATR needs {3}), RV days {4} (vol state needs {5})",
                _b1.Count > 0 ? _b1.OpenTimes[0] : Server.Time, _b5.Count > 0 ? _b5.OpenTimes[0] : Server.Time,
                _dHigh.Count, AtrPeriodDays + 1, _rv.Count, VolMinHistoryDays));
        }

        protected override void OnStop()
        {
            if (_b1 != null) _b1.BarOpened -= OnBar1Opened;
            if (_b5 != null) _b5.BarOpened -= OnBar5Opened;
            Positions.Opened -= OnPositionOpened;
            Positions.Closed -= OnPositionClosed;
            PendingOrders.Filled -= OnPendingFilled;
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
            TryDecide();
        }

        private void OnBar5Opened(BarOpenedEventArgs e)
        {
            CheckNewDay();
            CatchUp();
        }

        // process every closed bar (index <= Count - 2) not yet seen, m1 first then m5
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

        private void ProcessM1(int i)
        {
            DateTime t = _b1.OpenTimes[i];
            double h = _b1.HighPrices[i], l = _b1.LowPrices[i], c = _b1.ClosePrices[i];
            if (double.IsNaN(h) || double.IsNaN(l) || double.IsNaN(c)) return;

            // daily bar 23:00-21:00 UTC, trading day = date of (t + 1h)
            int hr = t.Hour;
            if (hr < 21 || hr >= 23)
            {
                DateTime td = t.AddHours(1).Date;
                if (td != _dTd)
                {
                    FlushDaily();
                    _dTd = td; _dH = h; _dL = l; _dC = c; _dN = 0;
                }
                _dH = Math.Max(_dH, h); _dL = Math.Min(_dL, l); _dC = c; _dN++;
            }

            // Asian range [RangeStart, RangeEnd) on the calendar date
            DateTime d = t.Date;
            if (t >= d.AddHours(RangeStartHourUtc) && t < d.AddHours(RangeEndHourUtc))
            {
                if (_rDate != d) { _rDate = d; _rH = h; _rL = l; _rN = 0; }
                _rH = Math.Max(_rH, h); _rL = Math.Min(_rL, l); _rC = c; _rN++;
            }
        }

        private void FlushDaily()
        {
            if (_dTd != DateTime.MinValue && _dN >= MinDailyBars)
            {
                _dHigh.Add(_dH); _dLow.Add(_dL); _dClose.Add(_dC);
            }
            _dN = 0;
            _dTd = DateTime.MinValue;
        }

        private void ProcessM5(int i)
        {
            DateTime t = _b5.OpenTimes[i];
            double c = _b5.ClosePrices[i];
            if (double.IsNaN(c) || c <= 0) return;
            double r = (!double.IsNaN(_prev5Close) && _prev5Close > 0) ? Math.Log(c / _prev5Close) : double.NaN;
            _prev5Close = c;
            if (t.Hour < 21)
            {
                DateTime d = t.Date;
                if (!_rvOpen || d != _rvDate)
                {
                    FlushRv();
                    _rvDate = d; _rvSum = 0; _rvOpen = true;
                }
                if (!double.IsNaN(r)) _rvSum += r * r;
            }
        }

        private void FlushRv()
        {
            if (_rvOpen) _rv.Add(_rvSum);
            _rvOpen = false;
        }

        // ATR (simple mean of true range) of the daily rows strictly before `today`
        private double DailyAtrBefore(DateTime today)
        {
            if (_dTd != DateTime.MinValue && _dTd < today) FlushDaily();
            int n = _dHigh.Count, p = AtrPeriodDays;
            if (p <= 0 || n < p + 1) return double.NaN;
            double s = 0;
            for (int k = n - p; k < n; k++)
            {
                double pc = _dClose[k - 1];
                double tr = Math.Max(_dHigh[k] - _dLow[k], Math.Max(Math.Abs(_dHigh[k] - pc), Math.Abs(_dLow[k] - pc)));
                s += tr;
            }
            return s / p;
        }

        // percentile rank (0-1, ties averaged like pandas rank(pct=True)) of the last completed day's RV
        private double VolPctBefore(DateTime today)
        {
            if (_rvOpen && _rvDate < today) FlushRv();
            int n = _rv.Count;
            if (n == 0) return double.NaN;
            int start = Math.Max(0, n - VolLookbackDays);
            int cnt = n - start;
            if (cnt < VolMinHistoryDays || cnt <= 0) return double.NaN;
            double x = _rv[n - 1];
            int less = 0, eq = 0;
            for (int k = start; k < n; k++)
            {
                if (_rv[k] < x) less++;
                else if (_rv[k] == x) eq++;
            }
            return (less + (eq + 1) / 2.0) / cnt;
        }

        // ================================================================ decision at range end
        private void TryDecide()
        {
            if (!_warm) return;
            DateTime now = Server.Time, today = now.Date;
            if (_decidedDate == today) return;
            DateTime tEnd = today.AddHours(RangeEndHourUtc), tCut = today.AddHours(CutoffHourUtc);
            if (now < tEnd) return;
            _decidedDate = today;
            if (now >= tCut) return;

            int need = Math.Max(1, (int)(MinRangeBarFrac * (RangeEndHourUtc - RangeStartHourUtc) * 60));
            if (_rDate != today || _rN < need) { Log("no valid range today (bars " + (_rDate == today ? _rN : 0) + ")"); return; }
            double w = _rH - _rL;
            if (!(w > 0)) return;

            double atr = DailyAtrBefore(today);
            bool ok;
            switch (RangeFilter)
            {
                case ArbRangeFilter.Usd: ok = w >= RngUsdMin && w <= RngUsdMax; break;
                case ArbRangeFilter.Atr: ok = !double.IsNaN(atr) && w >= RngAtrMin * atr && w <= RngAtrMax * atr; break;
                case ArbRangeFilter.Pct:
                    double p = _rC > 0 ? w / _rC * 100.0 : double.NaN;
                    ok = !double.IsNaN(p) && p >= RngPctMin && p <= RngPctMax; break;
                default: ok = true; break;
            }
            double vp = double.NaN;
            if (ok && VolState != ArbVolState.All)
            {
                vp = VolPctBefore(today);
                double th = VolState == ArbVolState.Top ? 2.0 / 3.0 : 1.0 / 3.0;
                ok = !double.IsNaN(vp) && vp >= th;
            }
            Log(string.Format("range {0:F2}-{1:F2} W={2:F2} ATR={3:F2} volPct={4:F3} -> {5}", _rL, _rH, w, atr, vp, ok ? "trade" : "skip"));
            if (!ok) return;

            double up = _rH + BufferUsd, dn = _rL - BufferUsd;
            double mid = 0.5 * (Symbol.Bid + Symbol.Ask);
            if (_canDraw)
            {
                Chart.DrawRectangle("arb_rng_" + today.ToString("yyyyMMdd"), today.AddHours(RangeStartHourUtc), _rH, tEnd, _rL, Color.SteelBlue);
                Chart.DrawTrendLine("arb_up_" + today.ToString("yyyyMMdd"), tEnd, up, tCut, up, Color.LimeGreen);
                Chart.DrawTrendLine("arb_dn_" + today.ToString("yyyyMMdd"), tEnd, dn, tCut, dn, Color.OrangeRed);
            }
            if (!(mid < up && mid > dn)) { Log("price already outside the levels, no orders"); return; }

            string why;
            if (!CanOpen(now, out why)) { Log("entry blocked: " + why); return; }

            double sl, tp;
            if (ExitStyle == ArbExitStyle.UnitMultiples) { sl = SlMult * w; tp = TpMult * w; }
            else { sl = up - dn; tp = TgtX * w; }
            sl = Math.Max(Math.Max(sl, MinStopUsd), MinSlDistance());
            if (tp > 0) tp = Math.Max(tp, MinTpDistance());
            double units = CalcVolume(sl);
            if (units <= 0) { Log("volume below minimum, skip"); return; }
            if (Symbol.PipSize <= 0) return;

            _pendSl = sl; _pendTp = tp; _pendUnit = w;
            double? slPips = Math.Round(sl / Symbol.PipSize, 1);
            double? tpPips = tp > 0 ? Math.Round(tp / Symbol.PipSize, 1) : (double?)null;
            double minEntry = MinSlDistance();
            int placed = 0;
            if (up - Symbol.Ask > minEntry)
            {
                var r = PlaceStopOrder(TradeType.Buy, SymbolName, units, Math.Round(up, Symbol.Digits), Label, slPips, tpPips, ProtectionType.Relative, tCut, TradeComment);
                if (r.IsSuccessful) placed++; else Print("buy stop failed: " + r.Error);
            }
            else Log("buy level too close to market, side skipped");
            if (Symbol.Bid - dn > minEntry)
            {
                var r = PlaceStopOrder(TradeType.Sell, SymbolName, units, Math.Round(dn, Symbol.Digits), Label, slPips, tpPips, ProtectionType.Relative, tCut, TradeComment);
                if (r.IsSuccessful) placed++; else Print("sell stop failed: " + r.Error);
            }
            else Log("sell level too close to market, side skipped");
            if (placed > 0) _ordersDate = today;
            Log(string.Format("OCO placed ({0}): buy {1:F2} / sell {2:F2}, units {3}, sl {4:F2}, tp {5:F2}, expiry {6:HH:mm}", placed, up, dn, units, sl, tp, tCut));
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
            // strategy: cancel unfilled orders at cutoff, close at the strategy flat time
            if (_ordersDate == now.Date && now >= now.Date.AddHours(CutoffHourUtc)) { CancelMyPending("cutoff"); _ordersDate = DateTime.MinValue; }
            if (mine.Length > 0 && now >= now.Date.AddHours(StrategyFlatHourUtc))
            {
                foreach (var p in mine) ClosePos(p, "strategy flat");
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
                    CancelMyPending("daily loss");
                    if (CloseOnDailyLoss) { foreach (var p in mine) ClosePos(p, "daily loss"); return; }
                }
            }
            ManagePositions(mine, now);
        }

        // ================================================================ events
        private void OnPendingFilled(PendingOrderFilledEventArgs e)
        {
            if (e.PendingOrder == null || e.PendingOrder.Label != Label || e.PendingOrder.SymbolName != SymbolName) return;
            CancelMyPending("OCO sibling");
        }

        private void OnPositionOpened(PositionOpenedEventArgs e)
        {
            var p = e.Position;
            if (p == null || p.Label != Label || p.SymbolName != SymbolName) return;
            if (_state.ContainsKey(p.Id)) return;
            CancelMyPending("OCO sibling");
            // OCO double fill: the sibling filled before the cancel reached the server. Python never holds
            // two positions (one trade per day), so the second leg is closed at once and not registered.
            bool otherOpen = Positions.FindAll(Label, SymbolName).Any(q => q.Id != p.Id);
            if (otherOpen || _tradesToday >= MaxTradesPerDay)
            {
                var rc = ClosePosition(p);
                Print("OCO double fill: closed second position " + p.Id + (rc.IsSuccessful ? "" : " - close failed: " + rc.Error));
                CancelMyPending("OCO double fill");
                return;
            }
            double unit = _pendUnit;
            if (double.IsNaN(unit) || unit <= 0) unit = p.StopLoss.HasValue ? Math.Abs(p.EntryPrice - p.StopLoss.Value) : 1.0;
            Register(p, unit);
            // stop and target measured from the actual fill (Python: distances from the entry fill)
            if (!double.IsNaN(_pendUnit))
            {
                int side = p.TradeType == TradeType.Buy ? 1 : -1;
                double sl = Math.Round(p.EntryPrice - side * _pendSl, Symbol.Digits);
                double? tp = _pendTp > 0 ? Math.Round(p.EntryPrice + side * _pendTp, Symbol.Digits) : (double?)null;
                bool slOff = !p.StopLoss.HasValue || Math.Abs(p.StopLoss.Value - sl) > Symbol.TickSize * 0.5;
                bool tpOff = tp.HasValue && (!p.TakeProfit.HasValue || Math.Abs(p.TakeProfit.Value - tp.Value) > Symbol.TickSize * 0.5);
                if (slOff || tpOff)
                {
                    var r = ModifyPosition(p, sl, tp, ProtectionType.Absolute);
                    if (!r.IsSuccessful) Print("re-base SL/TP failed: " + r.Error);
                }
                _pendUnit = double.NaN;
            }
            Log(string.Format("opened {0} {1} @ {2:F2} SL {3} TP {4}", p.TradeType, p.VolumeInUnits, p.EntryPrice, p.StopLoss, p.TakeProfit));
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
            if (RiskMode == ArbRiskMode.FixedLots)
                units = Symbol.QuantityToVolumeInUnits(FixedLots);
            else
            {
                double cash = RiskMode == ArbRiskMode.PercentOfEquity ? Account.Equity * RiskPercent / 100.0 : FixedCashRisk;
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
