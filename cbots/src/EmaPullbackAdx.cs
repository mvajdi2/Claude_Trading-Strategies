// =================================================================================================
// EmaPullbackAdx.cs  -  cTrader Automate cBot (C# / .NET 6)
// Port of strategies/ema_pullback_adx.py with the frozen card strategy_cards/ema_pullback_adx.frozen.json
//   params: adx_min = 30, stop_atr = 1.5, dead_filter = true
//   exit  : sl 2.0 x unit, partial 50% at 0.25 x unit then stop to break-even, final target 3.0 x unit,
//           time exit 20:45 UTC (unit = structural stop distance R)
//
// Rules (closed 15-minute bars, decision at the bar close, entry on the next tick):
//   Long : bar opened 07:00-18:45 UTC, EMA20 > EMA50 (m15), ADX14 > AdxMin, last closed H1 close > EMA50(H1),
//          low <= EMA20 and close > EMA20, ATR14 (simple mean of true range) >= its 1840-bar median.
//   Short: mirror.
//   unit = max(close - (5-bar swing low - 0.5 ATR), StopAtrMult x ATR)   (mirror for shorts)
//   Max 2 signals per UTC day, one position at a time.
// All indicators are hand-rolled to match the pandas definitions exactly (see cbots/docs/EmaPullbackAdx.md).
// =================================================================================================

using System;
using System.Collections.Generic;
using cAlgo.API;
using cAlgo.API.Internals;

namespace cAlgo.Robots
{
    [Robot(AccessRights = AccessRights.None, TimeZone = TimeZones.UTC)]
    public class EmaPullbackAdx : Robot
    {
        public enum RiskModeType { PercentOfEquity, FixedLots, FixedCash }

        // ---------------------------------------------------------------- 1. Identity
        [Parameter("Label", Group = "1. Identity", DefaultValue = "EmaPullbackAdx")]
        public string Label { get; set; }

        [Parameter("Trade Comment", Group = "1. Identity", DefaultValue = "EmaPullbackAdx")]
        public string TradeComment { get; set; }

        // ---------------------------------------------------------------- 2. Risk & sizing
        [Parameter("Risk Mode", Group = "2. Risk & Sizing", DefaultValue = RiskModeType.PercentOfEquity)]
        public RiskModeType RiskMode { get; set; }

        [Parameter("Risk % of Equity", Group = "2. Risk & Sizing", DefaultValue = 0.5, MinValue = 0.1, MaxValue = 3.0, Step = 0.1)]
        public double RiskPercent { get; set; }

        [Parameter("Fixed Lots", Group = "2. Risk & Sizing", DefaultValue = 0.10, MinValue = 0.01, MaxValue = 10.0, Step = 0.01)]
        public double FixedLots { get; set; }

        [Parameter("Fixed Cash Risk", Group = "2. Risk & Sizing", DefaultValue = 500.0, MinValue = 10.0, MaxValue = 10000.0, Step = 10.0)]
        public double FixedCashRisk { get; set; }

        [Parameter("Max Lots", Group = "2. Risk & Sizing", DefaultValue = 5.0, MinValue = 0.01, MaxValue = 50.0, Step = 0.01)]
        public double MaxLots { get; set; }

        // ---------------------------------------------------------------- 3. Account protection
        [Parameter("Max Spread (USD)", Group = "3. Account Protection", DefaultValue = 0.60, MinValue = 0.05, MaxValue = 3.0, Step = 0.05)]
        public double MaxSpreadUsd { get; set; }

        [Parameter("Max Daily Loss % (0 = off)", Group = "3. Account Protection", DefaultValue = 3.0, MinValue = 0.0, MaxValue = 10.0, Step = 0.5)]
        public double MaxDailyLossPercent { get; set; }

        [Parameter("Close All On Daily Loss", Group = "3. Account Protection", DefaultValue = false)]
        public bool CloseAllOnDailyLoss { get; set; }

        [Parameter("Max Trades Per Day (0 = off)", Group = "3. Account Protection", DefaultValue = 2, MinValue = 0, MaxValue = 10, Step = 1)]
        public int MaxTradesPerDay { get; set; }

        [Parameter("Max Open Positions", Group = "3. Account Protection", DefaultValue = 1, MinValue = 1, MaxValue = 5, Step = 1)]
        public int MaxOpenPositions { get; set; }

        [Parameter("Cooldown Minutes After Close", Group = "3. Account Protection", DefaultValue = 0, MinValue = 0, MaxValue = 240, Step = 15)]
        public int CooldownMinutes { get; set; }

        // ---------------------------------------------------------------- 4. Session & calendar
        [Parameter("Signal Start Hour UTC (bar open)", Group = "4. Session & Calendar", DefaultValue = 7, MinValue = 0, MaxValue = 23, Step = 1)]
        public int SignalStartHour { get; set; }

        [Parameter("Signal End Hour UTC (bar open, excl.)", Group = "4. Session & Calendar", DefaultValue = 19, MinValue = 1, MaxValue = 24, Step = 1)]
        public int SignalEndHour { get; set; }

        [Parameter("Time Exit Hour UTC", Group = "4. Session & Calendar", DefaultValue = 20, MinValue = 0, MaxValue = 23, Step = 1)]
        public int TimeExitHour { get; set; }

        [Parameter("Time Exit Minute", Group = "4. Session & Calendar", DefaultValue = 45, MinValue = 0, MaxValue = 59, Step = 5)]
        public int TimeExitMinute { get; set; }

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
        [Parameter("EMA Fast Period (m15)", Group = "5. Signal", DefaultValue = 20, MinValue = 10, MaxValue = 50, Step = 5)]
        public int EmaFastPeriod { get; set; }

        [Parameter("EMA Slow Period (m15)", Group = "5. Signal", DefaultValue = 50, MinValue = 30, MaxValue = 100, Step = 10)]
        public int EmaSlowPeriod { get; set; }

        [Parameter("H1 Trend EMA Period", Group = "5. Signal", DefaultValue = 50, MinValue = 20, MaxValue = 100, Step = 10)]
        public int HtfEmaPeriod { get; set; }

        [Parameter("ADX Period", Group = "5. Signal", DefaultValue = 14, MinValue = 7, MaxValue = 28, Step = 1)]
        public int AdxPeriod { get; set; }

        [Parameter("ADX Min (adx_min)", Group = "5. Signal", DefaultValue = 30.0, MinValue = 15.0, MaxValue = 40.0, Step = 5.0)]
        public double AdxMin { get; set; }

        [Parameter("ATR Period (SMA of TR)", Group = "5. Signal", DefaultValue = 14, MinValue = 7, MaxValue = 28, Step = 1)]
        public int AtrPeriod { get; set; }

        [Parameter("Stop ATR Mult (stop_atr)", Group = "5. Signal", DefaultValue = 1.5, MinValue = 0.5, MaxValue = 3.0, Step = 0.25)]
        public double StopAtrMult { get; set; }

        [Parameter("Swing Bars", Group = "5. Signal", DefaultValue = 5, MinValue = 2, MaxValue = 15, Step = 1)]
        public int SwingBars { get; set; }

        [Parameter("Swing ATR Buffer", Group = "5. Signal", DefaultValue = 0.5, MinValue = 0.0, MaxValue = 1.5, Step = 0.25)]
        public double SwingAtrBuffer { get; set; }

        [Parameter("Dead-Market Filter (dead_filter)", Group = "5. Signal", DefaultValue = true)]
        public bool UseDeadFilter { get; set; }

        [Parameter("Dead Filter Lookback Bars", Group = "5. Signal", DefaultValue = 1840, MinValue = 460, MaxValue = 3680, Step = 460)]
        public int DeadFilterLookbackBars { get; set; }

        [Parameter("Dead Filter Min Bars", Group = "5. Signal", DefaultValue = 500, MinValue = 100, MaxValue = 1500, Step = 100)]
        public int DeadFilterMinBars { get; set; }

        [Parameter("Max Signals Per Day (0 = off)", Group = "5. Signal", DefaultValue = 2, MinValue = 0, MaxValue = 6, Step = 1)]
        public int MaxSignalsPerDay { get; set; }

        // ---------------------------------------------------------------- 6. Exit management (multiples of unit)
        [Parameter("Stop Mult (x unit)", Group = "6. Exit Management", DefaultValue = 2.0, MinValue = 0.5, MaxValue = 3.0, Step = 0.5)]
        public double SlMult { get; set; }

        [Parameter("Min Stop (USD)", Group = "6. Exit Management", DefaultValue = 0.15, MinValue = 0.05, MaxValue = 1.0, Step = 0.05)]
        public double MinStopUsd { get; set; }

        [Parameter("Target Mult (x unit, 0 = none)", Group = "6. Exit Management", DefaultValue = 3.0, MinValue = 0.0, MaxValue = 4.0, Step = 0.5)]
        public double TpMult { get; set; }

        [Parameter("TP1 Mult (x unit, 0 = off)", Group = "6. Exit Management", DefaultValue = 0.25, MinValue = 0.0, MaxValue = 1.0, Step = 0.25)]
        public double Tp1Mult { get; set; }

        [Parameter("TP1 Close %", Group = "6. Exit Management", DefaultValue = 50.0, MinValue = 10.0, MaxValue = 90.0, Step = 10.0)]
        public double Tp1ClosePercent { get; set; }

        [Parameter("Move To Break-Even After TP1", Group = "6. Exit Management", DefaultValue = true)]
        public bool MoveToBreakEven { get; set; }

        [Parameter("Break-Even Offset (USD)", Group = "6. Exit Management", DefaultValue = 0.0, MinValue = 0.0, MaxValue = 1.0, Step = 0.05)]
        public double BreakEvenOffsetUsd { get; set; }

        [Parameter("Trailing Stop Mult (x unit, 0 = off)", Group = "6. Exit Management", DefaultValue = 0.0, MinValue = 0.0, MaxValue = 2.0, Step = 0.5)]
        public double TrailingStopMult { get; set; }

        [Parameter("Max Hold Minutes (0 = off)", Group = "6. Exit Management", DefaultValue = 0, MinValue = 0, MaxValue = 600, Step = 30)]
        public int MaxHoldMinutes { get; set; }

        // ---------------------------------------------------------------- 7. Diagnostics
        [Parameter("Verbose Log", Group = "7. Diagnostics", DefaultValue = false)]
        public bool VerboseLog { get; set; }

        [Parameter("Draw Levels", Group = "7. Diagnostics", DefaultValue = true)]
        public bool DrawLevels { get; set; }

        // ================================================================ state
        private sealed class PosState
        {
            public double Unit;
            public bool Tp1Done;
            public double Best;
            public bool TrailOn;
            public double BeLevel = double.NaN;   // pending break-even stop (retried until applied)
        }

        private Bars _m15, _h1;
        private readonly List<double> _e20 = new List<double>(), _e50 = new List<double>(), _atr = new List<double>(),
            _tr = new List<double>(), _adx = new List<double>(), _trS = new List<double>(), _pdmS = new List<double>(),
            _mdmS = new List<double>();
        private readonly List<double> _hEma = new List<double>();
        private int _lastM15 = -1;          // last m15 index processed into the indicator arrays
        private DateTime _lastM15Open;
        private DateTime _lastEvalOpen = DateTime.MinValue;
        private int _lastH1 = -1;
        private DateTime _lastH1Open;
        private readonly Dictionary<int, PosState> _state = new Dictionary<int, PosState>();
        private readonly HashSet<int> _closing = new HashSet<int>();   // close requested, waiting for Positions.Closed
        private readonly List<double> _medBuf = new List<double>();

        private DateTime _day = DateTime.MinValue;
        private double _dayStartEquity;
        private int _tradesToday, _signalsToday;
        private DateTime _lastCloseTime = DateTime.MinValue;
        private bool _dailyLossHit;

        private bool CanDraw { get { return DrawLevels && RunningMode != RunningMode.Optimization; } }

        // ================================================================ lifecycle
        protected override void OnStart()
        {
            _m15 = MarketData.GetBars(TimeFrame.Minute15);
            _h1 = MarketData.GetBars(TimeFrame.Hour);
            int need = DeadFilterLookbackBars + 4 * Math.Max(EmaSlowPeriod, AdxPeriod) + 50;
            for (int k = 0; k < 50 && _m15.Count < need; k++)
                if (_m15.LoadMoreHistory() <= 0) break;
            for (int k = 0; k < 20 && _h1.Count < 6 * HtfEmaPeriod; k++)
                if (_h1.LoadMoreHistory() <= 0) break;

            Positions.Closed += OnPositionClosed;

            // adopt positions left open by a previous run: unit from the order-comment tag "|u=",
            // falling back to the stop distance / SlMult only when the tag is missing
            foreach (var p in Positions.FindAll(Label, SymbolName))
            {
                int sd = p.TradeType == TradeType.Buy ? 1 : -1;
                bool beDone = p.StopLoss.HasValue && (p.StopLoss.Value - p.EntryPrice) * sd >= 0;   // stop at/after entry: TP1 already taken
                double unit = ParseCommentValue(p.Comment);
                bool fromTag = !double.IsNaN(unit);
                if (!fromTag)
                    unit = p.StopLoss.HasValue && SlMult > 0 && !beDone ? Math.Abs(p.EntryPrice - p.StopLoss.Value) / SlMult : 0.0;
                if (unit > 0)
                {
                    _state[p.Id] = new PosState { Unit = unit, Best = sd == 1 ? Symbol.Bid : Symbol.Ask, Tp1Done = beDone,
                                                  TrailOn = TrailingStopMult > 0 && (beDone || !(Tp1Mult > 0)) };
                    Print("Adopted position {0}: unit={1:F3} ({2}), TP1 {3}.", p.Id, unit, fromTag ? "comment tag" : "stop-distance fallback", beDone ? "done" : "pending");
                }
                else
                    Print("Adopted position {0}: unit unknown (no tag, stop at break-even); broker SL/TP stay in force, time exit still applies.", p.Id);
            }

            CatchUpM15();
            if (_lastM15 >= 0) _lastEvalOpen = _m15.OpenTimes[_lastM15];   // history bars are warm-up only
            Print("EmaPullbackAdx started: {0} m15 bars, {1} H1 bars, PipSize={2}, LotSize={3}.",
                _m15.Count, _h1.Count, Symbol.PipSize, Symbol.LotSize);
        }

        protected override void OnStop()
        {
            Positions.Closed -= OnPositionClosed;
        }

        protected override void OnTick()
        {
            DateTime now = Server.Time;
            RollDay(now);
            CheckDailyLoss();

            // time exit (strategy) and force flat (standard)
            var tod = now.TimeOfDay;
            bool pastTimeExit = tod >= new TimeSpan(TimeExitHour, TimeExitMinute, 0);
            bool pastForceFlat = tod >= new TimeSpan(ForceFlatHourUtc, ForceFlatMinute, 0);
            if (pastTimeExit || pastForceFlat)
                FlattenAll(pastForceFlat ? string.Format("force flat {0:D2}:{1:D2}", ForceFlatHourUtc, ForceFlatMinute)
                                          : string.Format("time exit {0:D2}:{1:D2}", TimeExitHour, TimeExitMinute));

            ManagePositions(now);

            // new closed m15 bar -> decision
            if (_m15.Count - 2 > _lastM15 || IndexShifted())
            {
                CatchUpM15();
                if (_lastM15 >= 0 && _m15.OpenTimes[_lastM15] > _lastEvalOpen)
                {
                    _lastEvalOpen = _m15.OpenTimes[_lastM15];
                    EvaluateSignal(_lastM15, now);
                }
            }
        }

        // ================================================================ indicators (hand-rolled, pandas-exact)
        private bool IndexShifted()
        {
            return _lastM15 >= 0 && (_lastM15 >= _m15.Count || _m15.OpenTimes[_lastM15] != _lastM15Open);
        }

        private void ResetM15()
        {
            _e20.Clear(); _e50.Clear(); _atr.Clear(); _tr.Clear(); _adx.Clear(); _trS.Clear(); _pdmS.Clear(); _mdmS.Clear();
            _lastM15 = -1;
        }

        /// <summary>Process every closed m15 bar (up to Count-2) into the indicator arrays.</summary>
        private void CatchUpM15()
        {
            if (IndexShifted()) ResetM15();
            int last = _m15.Count - 2;
            for (int i = _lastM15 + 1; i <= last; i++)
                ProcessM15(i);
            if (last >= 0 && _lastM15 >= 0) _lastM15Open = _m15.OpenTimes[_lastM15];
        }

        private void ProcessM15(int i)
        {
            double h = _m15.HighPrices[i], l = _m15.LowPrices[i], c = _m15.ClosePrices[i];
            double aF = 2.0 / (EmaFastPeriod + 1), aS = 2.0 / (EmaSlowPeriod + 1), aW = 1.0 / AdxPeriod;

            // EMA: pandas ewm(span=n, adjust=False), seeded with the first close
            _e20.Add(i == 0 ? c : _e20[i - 1] + aF * (c - _e20[i - 1]));
            _e50.Add(i == 0 ? c : _e50[i - 1] + aS * (c - _e50[i - 1]));

            // true range (NaN on the first bar, as pandas shift(1))
            double tr = double.NaN, pdm = 0.0, mdm = 0.0;
            if (i > 0)
            {
                double pc = _m15.ClosePrices[i - 1];
                tr = Math.Max(h - l, Math.Max(Math.Abs(h - pc), Math.Abs(l - pc)));
                double up = h - _m15.HighPrices[i - 1], dn = _m15.LowPrices[i - 1] - l;
                pdm = (up > dn && up > 0) ? up : 0.0;
                mdm = (dn > up && dn > 0) ? dn : 0.0;
            }
            _tr.Add(tr);

            // ATR = simple rolling mean of TR over AtrPeriod (NaN until AtrPeriod valid TRs)
            double atr = double.NaN;
            if (i >= AtrPeriod)
            {
                double s = 0; for (int k = i - AtrPeriod + 1; k <= i; k++) s += _tr[k];
                atr = s / AtrPeriod;
            }
            _atr.Add(atr);

            // ADX: Wilder smoothing via ewm(alpha=1/n, adjust=False), seeded at the first valid value
            double prevTrS = i > 0 ? _trS[i - 1] : double.NaN;
            double trS = double.IsNaN(tr) ? prevTrS : (double.IsNaN(prevTrS) ? tr : prevTrS + aW * (tr - prevTrS));
            double pS = i == 0 ? pdm : _pdmS[i - 1] + aW * (pdm - _pdmS[i - 1]);
            double mS = i == 0 ? mdm : _mdmS[i - 1] + aW * (mdm - _mdmS[i - 1]);
            _trS.Add(trS); _pdmS.Add(pS); _mdmS.Add(mS);
            double dx = double.NaN;
            if (!double.IsNaN(trS) && trS > 0)
            {
                double pdi = 100.0 * pS / trS, mdi = 100.0 * mS / trS;
                dx = 100.0 * Math.Abs(pdi - mdi) / Math.Max(pdi + mdi, 1e-9);
            }
            double prevAdx = i > 0 ? _adx[i - 1] : double.NaN;
            double adx = double.IsNaN(dx) ? prevAdx : (double.IsNaN(prevAdx) ? dx : prevAdx + aW * (dx - prevAdx));
            _adx.Add(adx);

            _lastM15 = i;
            _lastM15Open = _m15.OpenTimes[i];
        }

        /// <summary>EMA(HtfEmaPeriod) of H1 closes at H1 index j (bar j must be closed).</summary>
        private double H1EmaAt(int j)
        {
            if (_lastH1 >= 0 && (_lastH1 >= _h1.Count || _h1.OpenTimes[_lastH1] != _lastH1Open))
            { _hEma.Clear(); _lastH1 = -1; }
            double a = 2.0 / (HtfEmaPeriod + 1);
            for (int k = _lastH1 + 1; k <= j; k++)
            {
                double c = _h1.ClosePrices[k];
                _hEma.Add(k == 0 ? c : _hEma[k - 1] + a * (c - _hEma[k - 1]));
                _lastH1 = k; _lastH1Open = _h1.OpenTimes[k];
            }
            return j >= 0 && j < _hEma.Count ? _hEma[j] : double.NaN;
        }

        /// <summary>Median of the last DeadFilterLookbackBars finite ATR values before index i (pandas rolling().median().shift(1)).</summary>
        private double AtrMedianBefore(int i)
        {
            _medBuf.Clear();
            for (int k = Math.Max(0, i - DeadFilterLookbackBars); k < i; k++)
                if (!double.IsNaN(_atr[k])) _medBuf.Add(_atr[k]);
            if (_medBuf.Count < DeadFilterMinBars || _medBuf.Count == 0) return double.NaN;
            _medBuf.Sort();
            int n = _medBuf.Count;
            return (n % 2 == 1) ? _medBuf[n / 2] : 0.5 * (_medBuf[n / 2 - 1] + _medBuf[n / 2]);
        }

        // ================================================================ signal
        private void EvaluateSignal(int i, DateTime now)
        {
            if (i < Math.Max(SwingBars, EmaSlowPeriod)) return;
            DateTime open = _m15.OpenTimes[i];
            DateTime closeT = open.AddMinutes(15);
            if (open.Hour < SignalStartHour || open.Hour >= SignalEndHour) return;

            double a = _atr[i], adx = _adx[i];
            if (double.IsNaN(a) || a <= 0 || double.IsNaN(adx) || !(adx > AdxMin)) return;
            if (UseDeadFilter)
            {
                double med = AtrMedianBefore(i);
                if (double.IsNaN(med) || !(a >= med)) return;
            }

            // last H1 bar fully closed at the m15 close time (pandas merge_asof on close second)
            int j = _h1.Count - 1;
            while (j >= 0 && _h1.OpenTimes[j].AddHours(1) > closeT) j--;
            if (j < 0) return;
            double hEma = H1EmaAt(j);
            if (double.IsNaN(hEma)) return;
            int hup = Math.Sign(_h1.ClosePrices[j] - hEma);

            double H = _m15.HighPrices[i], L = _m15.LowPrices[i], C = _m15.ClosePrices[i];
            double e20 = _e20[i], e50 = _e50[i];
            bool lg = e20 > e50 && hup > 0 && L <= e20 && C > e20;
            bool sh = !lg && e20 < e50 && hup < 0 && H >= e20 && C < e20;
            if (!lg && !sh) return;

            double swl = double.MaxValue, swh = double.MinValue;
            for (int k = i - SwingBars + 1; k <= i; k++)
            {
                swl = Math.Min(swl, _m15.LowPrices[k]);
                swh = Math.Max(swh, _m15.HighPrices[k]);
            }
            double unit = lg ? C - (swl - SwingAtrBuffer * a) : (swh + SwingAtrBuffer * a) - C;
            unit = Math.Max(unit, StopAtrMult * a);
            if (!(unit > 0)) return;

            // Python: groupby(day).head(2) counts signals, whether or not they could be executed
            _signalsToday++;
            if (MaxSignalsPerDay > 0 && _signalsToday > MaxSignalsPerDay)
            {
                Log("signal #{0} today ignored (MaxSignalsPerDay)", _signalsToday);
                return;
            }
            Log("SIGNAL {0} bar {1:yyyy-MM-dd HH:mm} C={2} EMA{3}={4:F2} EMA{5}={6:F2} ADX={7:F1} ATR={8:F2} unit={9:F2}",
                lg ? "LONG" : "SHORT", open, C, EmaFastPeriod, e20, EmaSlowPeriod, e50, adx, a, unit);

            TryEnter(lg ? TradeType.Buy : TradeType.Sell, unit, now);
        }

        private void TryEnter(TradeType side, double unit, DateTime now)
        {
            if (!DayAllowed(now.DayOfWeek)) { Log("skip: weekday disabled"); return; }
            if (now.TimeOfDay >= new TimeSpan(TimeExitHour, TimeExitMinute, 0) ||
                now.TimeOfDay >= new TimeSpan(ForceFlatHourUtc, ForceFlatMinute, 0)) { Log("skip: past time exit"); return; }
            if (_dailyLossHit) { Log("skip: daily loss limit"); return; }
            if (MaxTradesPerDay > 0 && _tradesToday >= MaxTradesPerDay) { Log("skip: MaxTradesPerDay"); return; }
            if (Positions.FindAll(Label, SymbolName).Length >= MaxOpenPositions) { Log("skip: position open"); return; }
            if (CooldownMinutes > 0 && now < _lastCloseTime.AddMinutes(CooldownMinutes)) { Log("skip: cooldown"); return; }
            double spread = Symbol.Ask - Symbol.Bid;
            if (spread > MaxSpreadUsd) { Log("skip: spread {0:F2} > {1:F2}", spread, MaxSpreadUsd); return; }

            double slDist = Math.Max(SlMult * unit, MinStopUsd);
            double minSl = MinStopDistance();
            if (slDist < minSl) slDist = minSl;
            double tpDist = TpMult > 0 ? TpMult * unit : 0.0;
            if (tpDist > 0 && tpDist < MinTpDistance()) tpDist = MinTpDistance();

            double units = ComputeVolume(slDist);
            if (units <= 0) { Log("skip: volume below minimum"); return; }

            double slPips = Math.Round(slDist / Symbol.PipSize, 1);
            double? tpPips = tpDist > 0 ? Math.Round(tpDist / Symbol.PipSize, 1) : (double?)null;
            var res = ExecuteMarketOrder(side, SymbolName, units, Label, slPips, tpPips, BuildComment(unit));
            if (!res.IsSuccessful || res.Position == null)
            {
                Print("ORDER FAILED {0} {1} units: {2}", side, units, res.Error);
                return;
            }
            var p = res.Position;
            _state[p.Id] = new PosState { Unit = unit, Best = p.EntryPrice, TrailOn = TrailingStopMult > 0 && !(Tp1Mult > 0) };
            _tradesToday++;
            Log("ENTRY {0} {1} units @ {2} SL={3} TP={4} unit={5:F2}", side, units, p.EntryPrice, p.StopLoss, p.TakeProfit, unit);

            if (CanDraw)
            {
                string id = "EPA_" + p.Id;
                DateTime end = now.Date.Add(new TimeSpan(TimeExitHour, TimeExitMinute, 0));
                if (end <= now) end = now.AddHours(1);
                Chart.DrawTrendLine(id + "_e", now, p.EntryPrice, end, p.EntryPrice, Color.Gray, 1, LineStyle.Dots);
                if (p.StopLoss.HasValue) Chart.DrawTrendLine(id + "_sl", now, p.StopLoss.Value, end, p.StopLoss.Value, Color.Red, 1, LineStyle.Solid);
                if (p.TakeProfit.HasValue) Chart.DrawTrendLine(id + "_tp", now, p.TakeProfit.Value, end, p.TakeProfit.Value, Color.LimeGreen, 1, LineStyle.Solid);
                if (Tp1Mult > 0)
                {
                    double t1 = p.EntryPrice + (side == TradeType.Buy ? 1 : -1) * Tp1Mult * unit;
                    Chart.DrawTrendLine(id + "_tp1", now, t1, end, t1, Color.Gold, 1, LineStyle.Lines);
                }
            }
        }

        // ================================================================ exit management
        private void ManagePositions(DateTime now)
        {
            foreach (var p in Positions.FindAll(Label, SymbolName))
            {
                PosState st;
                if (_closing.Contains(p.Id) || !_state.TryGetValue(p.Id, out st)) continue;
                int sd = p.TradeType == TradeType.Buy ? 1 : -1;
                double exitPx = sd == 1 ? Symbol.Bid : Symbol.Ask;   // price the position would close at

                if (MaxHoldMinutes > 0 && now >= p.EntryTime.AddMinutes(MaxHoldMinutes))
                {
                    CloseChecked(p, "max hold");
                    continue;
                }

                // partial target
                if (!st.Tp1Done && Tp1Mult > 0 && (exitPx - (p.EntryPrice + sd * Tp1Mult * st.Unit)) * sd >= 0)
                {
                    st.Tp1Done = true;
                    double closeUnits = Symbol.NormalizeVolumeInUnits(p.VolumeInUnits * Tp1ClosePercent / 100.0, RoundingMode.Down);
                    if (closeUnits >= Symbol.VolumeInUnitsMin && p.VolumeInUnits - closeUnits >= Symbol.VolumeInUnitsMin)
                    {
                        var r = ClosePosition(p, closeUnits);
                        if (!r.IsSuccessful) Print("TP1 partial close failed on {0}: {1}", p.Id, r.Error);
                        else Log("TP1 closed {0} units of {1}", closeUnits, p.Id);
                    }
                    else Log("TP1 partial skipped on {0}: remainder below minimum volume", p.Id);

                    if (MoveToBreakEven) st.BeLevel = p.EntryPrice + sd * BreakEvenOffsetUsd;
                    if (TrailingStopMult > 0) { st.TrailOn = true; st.Best = exitPx; }
                }

                // break-even (re-applied each tick until the stop is at or beyond the level)
                if (!double.IsNaN(st.BeLevel))
                    TightenStop(p, st.BeLevel, exitPx, "break-even");

                // own trailing stop (distance follows the unit)
                if (st.TrailOn && TrailingStopMult > 0)
                {
                    if ((exitPx - st.Best) * sd > 0) st.Best = exitPx;
                    TightenStop(p, st.Best - sd * TrailingStopMult * st.Unit, exitPx, null);
                }
            }
        }

        /// <summary>Move the stop only in the favourable direction; if the new stop is already crossed, close at market.</summary>
        private void TightenStop(Position p, double newSl, double exitPx, string why)
        {
            if (_closing.Contains(p.Id)) return;
            int sd = p.TradeType == TradeType.Buy ? 1 : -1;
            newSl = Math.Round(newSl, Symbol.Digits);
            if (p.StopLoss.HasValue && (newSl - p.StopLoss.Value) * sd <= 0) return;
            if ((exitPx - newSl) * sd <= MinStopDistance())
            {
                // stop level already reached (or inside broker minimum): behave as the stop being hit
                if ((exitPx - newSl) * sd <= 0) CloseChecked(p, (why ?? "trail") + " level crossed");
                return;
            }
            var r = ModifyPosition(p, newSl, p.TakeProfit, ProtectionType.Absolute);
            if (!r.IsSuccessful) Print("ModifyPosition failed on {0}: {1}", p.Id, r.Error);
            else if (why != null) Log("{0}: stop of {1} -> {2}", why, p.Id, newSl);
        }

        private void FlattenAll(string why)
        {
            foreach (var p in Positions.FindAll(Label, SymbolName))
                CloseChecked(p, why);
            foreach (var o in PendingOrders)
                if (o.Label == Label && o.SymbolName == SymbolName)
                {
                    var r = CancelPendingOrder(o);
                    if (!r.IsSuccessful) Print("Cancel failed: {0}", r.Error);
                }
        }

        private void CloseChecked(Position p, string why)
        {
            if (_closing.Contains(p.Id)) return;
            var r = ClosePosition(p);
            if (!r.IsSuccessful) Print("Close {0} ({1}) failed: {2}", p.Id, why, r.Error);
            else { _closing.Add(p.Id); Log("CLOSE {0}: {1}", p.Id, why); }
        }

        // ================================================================ events
        private void OnPositionClosed(PositionClosedEventArgs args)
        {
            var p = args.Position;
            if (p.Label != Label || p.SymbolName != SymbolName) return;
            _state.Remove(p.Id);
            _closing.Remove(p.Id);
            _lastCloseTime = Server.Time;
            if (CanDraw)
                foreach (var s in new[] { "_e", "_sl", "_tp", "_tp1" }) Chart.RemoveObject("EPA_" + p.Id + s);
        }

        // ================================================================ risk & guards
        private double ComputeVolume(double stopDist)
        {
            if (!(stopDist > 0) || Symbol.PipSize <= 0) return 0;
            // account-currency value of a 1 USD price move for one unit of volume (= 1 for a USD account)
            double perUnit = Symbol.PipValue > 0 ? Symbol.PipValue / Symbol.PipSize : 1.0;
            double units;
            switch (RiskMode)
            {
                case RiskModeType.FixedLots: units = Symbol.QuantityToVolumeInUnits(FixedLots); break;
                case RiskModeType.FixedCash: units = FixedCashRisk / (stopDist * perUnit); break;
                default: units = Account.Equity * RiskPercent / 100.0 / (stopDist * perUnit); break;
            }
            // lots = units / Symbol.LotSize  (USD account: lots = cash / (stop distance x LotSize))
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
            _tradesToday = 0; _signalsToday = 0; _dailyLossHit = false;
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
                Print("Daily loss limit hit ({0:F2} > {1}% of {2:F2}); no new entries today.", loss, MaxDailyLossPercent, _dayStartEquity);
                if (CloseAllOnDailyLoss) FlattenAll("daily loss limit");
            }
        }

        /// <summary>Realised net P&amp;L of this label+symbol since the UTC day start, from History
        /// (includes partial closes such as TP1, which do not raise Positions.Closed).</summary>
        private double RealisedToday()
        {
            double sum = 0;
            int older = 0;   // stop after a run of older deals; tolerant of History not being strictly time-ordered
            for (int i = History.Count - 1; i >= 0; i--)
            {
                var t = History[i];
                if (t.ClosingTime < _day) { if (++older >= 50) break; continue; }
                older = 0;
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

        // ---- unit persistence in the order comment: "<TradeComment>|u=<value>" (label/symbol untouched)
        private const int MaxCommentLength = 100;          // conservative cTrader/broker comment limit
        private const string UnitTag = "|u=";

        private string BuildComment(double value)
        {
            string tag = UnitTag + value.ToString("F3", System.Globalization.CultureInfo.InvariantCulture);
            string baseText = TradeComment ?? "";
            if (baseText.Length + tag.Length > MaxCommentLength) baseText = baseText.Substring(0, Math.Max(0, MaxCommentLength - tag.Length));
            return baseText + tag;
        }

        /// <summary>Value stored by BuildComment, or NaN when the tag is missing or unreadable.</summary>
        private static double ParseCommentValue(string comment)
        {
            if (string.IsNullOrEmpty(comment)) return double.NaN;
            int k = comment.LastIndexOf(UnitTag, StringComparison.Ordinal);
            if (k < 0) return double.NaN;
            string v = comment.Substring(k + UnitTag.Length);
            double x;
            return double.TryParse(v, System.Globalization.NumberStyles.Float, System.Globalization.CultureInfo.InvariantCulture, out x) && x > 0 && !double.IsInfinity(x) ? x : double.NaN;
        }

        private void Log(string fmt, params object[] args)
        {
            if (VerboseLog) Print(fmt, args);
        }
    }
}
