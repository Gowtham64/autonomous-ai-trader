import re
from datetime import UTC, datetime

from core.logging import logger
from memory.access_control import MemoryAccessControl
from memory.models import (
    MemoryImportance,
    MemoryLevel,
    MemoryRecord,
    MemoryType,
    QualityCategory,
    VerificationStatus,
)


class GlobalAIMemory:
    """Unified Multi-Layer AI Memory & Collective Organizational Brain.
    
    Implements:
    - Level 1: Private Agent Memory (Isolated)
    - Level 2: Shared Organizational Memory (Collective Knowledge)
    - Level 3: Long-Term Knowledge Memory (Survives Restarts & Upgrades)
    """

    def __init__(self):
        self.private_memories: dict[str, list[MemoryRecord]] = {}  # agent_id -> memories
        self.organizational_memories: list[MemoryRecord] = []
        self.long_term_knowledge: list[MemoryRecord] = []
        self.conflicts: list[dict] = []
        self._seed_default_knowledge()

    def _seed_default_knowledge(self) -> None:
        """Seeds permanent institutional knowledge and core operating rules."""
        seed_records = [
            MemoryRecord(
                memory_id="mem_rule_001",
                created_by="system_architect",
                level=MemoryLevel.LONG_TERM,
                memory_type=MemoryType.PROCEDURAL,
                category=QualityCategory.FACT,
                content="Prioritize capital preservation over maximum returns on ₹2,000 bootstrap capital.",
                confidence=1.0,
                source="master_system_instruction",
                importance=MemoryImportance.CRITICAL,
                verification_status=VerificationStatus.VERIFIED,
                evidence=["Master System Instruction Rule #1"],
            ),
            MemoryRecord(
                memory_id="mem_rule_002",
                created_by="risk_officer",
                level=MemoryLevel.LONG_TERM,
                memory_type=MemoryType.STRATEGIC,
                category=QualityCategory.LESSON,
                content="Breakout strategies produce elevated false signals in High Volatility Sideways regimes. Halve position sizing.",
                confidence=0.92,
                source="historical_market_regime_study",
                importance=MemoryImportance.HIGH,
                verification_status=VerificationStatus.VERIFIED,
                evidence=["Post-trade variance analysis over 500 backtested trades"],
            ),
            MemoryRecord(
                memory_id="mem_rule_003",
                created_by="technical_agent",
                level=MemoryLevel.LONG_TERM,
                memory_type=MemoryType.PROCEDURAL,
                category=QualityCategory.FACT,
                content="Always confirm volume >= 1.2x 20-day SMA before executing intraday momentum breakouts on NSE.",
                confidence=0.88,
                source="quant_scanner_validation",
                importance=MemoryImportance.HIGH,
                verification_status=VerificationStatus.VERIFIED,
                evidence=["Quant scanner statistical backtesting"],
            ),
            MemoryRecord(
                memory_id="mem_ebook_doctrine_001",
                created_by="master_intraday_trainer",
                level=MemoryLevel.LONG_TERM,
                memory_type=MemoryType.STRATEGIC,
                category=QualityCategory.FACT,
                content="Intraday Trading Doctrine: Open and close positions within the same day with ZERO overnight risk. Discipline, speed, and tight risk control beat market prediction.",
                confidence=1.0,
                source="ebook_aditya_intraday_strategies_p1",
                importance=MemoryImportance.CRITICAL,
                verification_status=VerificationStatus.VERIFIED,
                evidence=["Intraday Trading Strategies - Page 1"],
            ),
            MemoryRecord(
                memory_id="mem_ebook_strat_breakout",
                created_by="technical_agent",
                level=MemoryLevel.LONG_TERM,
                memory_type=MemoryType.PROCEDURAL,
                category=QualityCategory.FACT,
                content="Strategy 1 (Breakout Trading): Enter when price breaks a clear support or resistance level on rising volume (>1.5x relative volume), riding the momentum.",
                confidence=0.95,
                source="ebook_aditya_intraday_strategies_p1",
                importance=MemoryImportance.HIGH,
                verification_status=VerificationStatus.VERIFIED,
                evidence=["Intraday Trading Strategies - Page 1 'Breakout trading'"],
            ),
            MemoryRecord(
                memory_id="mem_ebook_strat_pullback",
                created_by="technical_agent",
                level=MemoryLevel.LONG_TERM,
                memory_type=MemoryType.PROCEDURAL,
                category=QualityCategory.FACT,
                content="Strategy 2 (Trend Pullback): In a strong trending market, never chase new highs. Buy small dips toward short moving averages (EMA 20 / VWAP) for superior risk-reward.",
                confidence=0.95,
                source="ebook_aditya_intraday_strategies_p1",
                importance=MemoryImportance.HIGH,
                verification_status=VerificationStatus.VERIFIED,
                evidence=["Intraday Trading Strategies - Page 1 'Trend / pullback'"],
            ),
            MemoryRecord(
                memory_id="mem_ebook_strat_range",
                created_by="technical_agent",
                level=MemoryLevel.LONG_TERM,
                memory_type=MemoryType.PROCEDURAL,
                category=QualityCategory.FACT,
                content="Strategy 3 (Range Trading): On quiet, sideways days, buy near confirmed support and sell near resistance, with tight stops placed just beyond the defined range boundary.",
                confidence=0.92,
                source="ebook_aditya_intraday_strategies_p1",
                importance=MemoryImportance.HIGH,
                verification_status=VerificationStatus.VERIFIED,
                evidence=["Intraday Trading Strategies - Page 1 'Range trading'"],
            ),
            MemoryRecord(
                memory_id="mem_ebook_rules_survival",
                created_by="risk_officer",
                level=MemoryLevel.LONG_TERM,
                memory_type=MemoryType.PROCEDURAL,
                category=QualityCategory.FACT,
                content="5 Rules That Keep Intraday Traders Alive: 1) Trade liquid stocks only; 2) Always use a stop-loss; 3) Set a hard daily loss limit; 4) Avoid the first 15 minutes (09:15-09:30 AM IST opening noise); 5) Mandatory square off on time (03:15 PM IST).",
                confidence=1.0,
                source="ebook_aditya_intraday_strategies_p2",
                importance=MemoryImportance.CRITICAL,
                verification_status=VerificationStatus.VERIFIED,
                evidence=["Intraday Trading Strategies - Page 2 'Rules that keep intraday traders alive'"],
            ),
            MemoryRecord(
                memory_id="mem_ebook_indicators_vwap",
                created_by="technical_agent",
                level=MemoryLevel.LONG_TERM,
                memory_type=MemoryType.PROCEDURAL,
                category=QualityCategory.FACT,
                content="Core Intraday Indicators: VWAP acts as an institutional fair-value anchor; Volume confirms real breakout force; Short moving averages indicate intraday trend direction.",
                confidence=0.94,
                source="ebook_aditya_intraday_strategies_p2",
                importance=MemoryImportance.HIGH,
                verification_status=VerificationStatus.VERIFIED,
                evidence=["Intraday Trading Strategies - Page 2 'Indicators intraday traders watch'"],
            ),
            MemoryRecord(
                memory_id="mem_ebook_discipline_beats_pred",
                created_by="fund_manager",
                level=MemoryLevel.LONG_TERM,
                memory_type=MemoryType.STRATEGIC,
                category=QualityCategory.LESSON,
                content="Discipline Beats Prediction: Margin amplifies losses as fast as gains. Risk only a fixed 0.5%-2% of capital per trade with hard daily loss limit. One well-managed losing day is recoverable; one undisciplined day can wipe out weeks of gains.",
                confidence=1.0,
                source="ebook_aditya_intraday_strategies_p2",
                importance=MemoryImportance.CRITICAL,
                verification_status=VerificationStatus.VERIFIED,
                evidence=["Intraday Trading Strategies - Page 2 'Discipline beats prediction'"],
            ),
            MemoryRecord(
                memory_id="mem_atoz_sector_rotation",
                created_by="macro_analyst",
                level=MemoryLevel.LONG_TERM,
                memory_type=MemoryType.STRATEGIC,
                category=QualityCategory.FACT,
                content="Sector Index & Net Change Doctrine: Never evaluate a stock in isolation. Monitor Sectoral Indices (Nifty Bank, Nifty IT, Nifty Auto, Nifty Metal, Nifty Pharma, Nifty FMCG, Nifty Realty) via Net Change in live market. High-probability setups align with top gaining/losing sectors.",
                confidence=0.98,
                source="ebook_atoz_share_market_lesson_2",
                importance=MemoryImportance.HIGH,
                verification_status=VerificationStatus.VERIFIED,
                evidence=["A To Z Share Market - Lesson 2 'Importance of Net Change in Index and Sector Index'"],
            ),
            MemoryRecord(
                memory_id="mem_atoz_tbq_tsq_trap",
                created_by="quant_specialist",
                level=MemoryLevel.LONG_TERM,
                memory_type=MemoryType.PROCEDURAL,
                category=QualityCategory.LESSON,
                content="Order Book TBQ/TSQ Deception Warning: High Total Buy Quantity (TBQ > TSQ) in Level 2 DOM is frequently MISLEADING. Traders place passive unexecuted bids below LTP giving false bullish impressions while price continues falling. Never trade solely on DOM TBQ/TSQ imbalance; rely on real executed volume.",
                confidence=0.99,
                source="ebook_atoz_share_market_lesson_4",
                importance=MemoryImportance.CRITICAL,
                verification_status=VerificationStatus.VERIFIED,
                evidence=["A To Z Share Market - Lesson 4 'Total Buy Quantity and Total Sell Quantity: Mislead'"],
            ),
            MemoryRecord(
                memory_id="mem_atoz_volume_vs_depth",
                created_by="technical_agent",
                level=MemoryLevel.LONG_TERM,
                memory_type=MemoryType.PROCEDURAL,
                category=QualityCategory.FACT,
                content="Traded Volume vs Pending Depth: Traded volume represents real executed trades. TBQ/TSQ represent unexecuted, cancellable limit orders. Breakout models must strictly verify executed volume expansion (>1.2x - 1.5x 20-day SMA).",
                confidence=0.97,
                source="ebook_atoz_share_market_lesson_4",
                importance=MemoryImportance.HIGH,
                verification_status=VerificationStatus.VERIFIED,
                evidence=["A To Z Share Market - Lesson 4 'What is Volume?'"],
            ),
            MemoryRecord(
                memory_id="mem_atoz_liquid_universe",
                created_by="risk_officer",
                level=MemoryLevel.LONG_TERM,
                memory_type=MemoryType.PROCEDURAL,
                category=QualityCategory.LESSON,
                content="High Volume Stock Mandate & Bid-Ask Spread: Always select liquid stocks with tight bid-ask spreads (5-10 paise). Low volume stocks suffer wide spreads, severe slippage, and execution failure during stop-loss triggers.",
                confidence=0.99,
                source="ebook_atoz_share_market_lesson_4",
                importance=MemoryImportance.CRITICAL,
                verification_status=VerificationStatus.VERIFIED,
                evidence=["A To Z Share Market - Lesson 4 'High Volume Stocks vs Low Volume Stocks'"],
            ),
            MemoryRecord(
                memory_id="mem_atoz_market_horizons",
                created_by="fund_manager",
                level=MemoryLevel.LONG_TERM,
                memory_type=MemoryType.STRATEGIC,
                category=QualityCategory.FACT,
                content="Participant Horizon Separation: 1) Investor (1-5 yrs): Low debt, business growth, annual reports; 2) Positional Trader (1w-2m): Sector momentum, earnings dates, multi-day technicals; 3) Intraday Trader (1 day): Intraday charts, signal confirmation, discipline, zero overnight holding.",
                confidence=0.96,
                source="ebook_atoz_share_market_lesson_3",
                importance=MemoryImportance.HIGH,
                verification_status=VerificationStatus.VERIFIED,
                evidence=["A To Z Share Market - Lesson 3 'Investor vs Positional vs Intraday'"],
            ),
            MemoryRecord(
                memory_id="mem_tax_intraday_speculative",
                created_by="portfolio_tax_specialist",
                level=MemoryLevel.LONG_TERM,
                memory_type=MemoryType.STRATEGIC,
                category=QualityCategory.FACT,
                content="Indian Tax Income Head Classification: 1) Delivery Equities: STCG (<=12m) and LTCG (>12m) under Capital Gains; 2) Intraday Trading: Speculative Business Income (PGBP) taxed at slab rates; 3) F&O: Non-Speculative Business Income (PGBP). Active intraday/F&O traders file ITR-3.",
                confidence=1.0,
                source="ebook_capital_gains_tax_aditya",
                importance=MemoryImportance.HIGH,
                verification_status=VerificationStatus.VERIFIED,
                evidence=["Income Tax Act India - Section 43(5) & Business Income classification"],
            ),
            MemoryRecord(
                memory_id="mem_tax_loss_harvesting_carryforward",
                created_by="portfolio_tax_specialist",
                level=MemoryLevel.LONG_TERM,
                memory_type=MemoryType.PROCEDURAL,
                category=QualityCategory.LESSON,
                content="Tax-Loss Harvesting & Carry Forward Rule: Book unrealized losses before March 31st to offset realized capital gains. Unused capital losses carry forward up to 8 assessment years ONLY if ITR is filed on time, even in a loss year.",
                confidence=0.99,
                source="ebook_capital_gains_tax_aditya",
                importance=MemoryImportance.HIGH,
                verification_status=VerificationStatus.VERIFIED,
                evidence=["Income Tax Act Section 70/74 Set-off & Carry Forward of losses"],
            ),
            MemoryRecord(
                memory_id="mem_algo_backtest_biases",
                created_by="quant_specialist",
                level=MemoryLevel.LONG_TERM,
                memory_type=MemoryType.PROCEDURAL,
                category=QualityCategory.LESSON,
                content="Algo Backtesting Rigor & Bias Elimination: Avoid overfitting to historical noise. Always deduct real-world transaction friction (brokerage, STT, exchange fees, bid-ask slippage). Eliminate look-ahead bias and survivorship bias.",
                confidence=0.99,
                source="ebook_algo_trading_basics_aditya",
                importance=MemoryImportance.CRITICAL,
                verification_status=VerificationStatus.VERIFIED,
                evidence=["Institutional quantitative research & validation protocols"],
            ),
            MemoryRecord(
                memory_id="mem_algo_risk_killswitch_doctrine",
                created_by="risk_officer",
                level=MemoryLevel.LONG_TERM,
                memory_type=MemoryType.PROCEDURAL,
                category=QualityCategory.LESSON,
                content="Algo Risk & Kill-Switch Doctrine: 'Automation amplifies whatever you give it.' Mandate hard-coded sizing, automated maximum daily loss halt (Daily Circuit Breaker), data anomaly circuit breakers, and emergency manual kill-switch.",
                confidence=1.0,
                source="ebook_algo_trading_basics_aditya",
                importance=MemoryImportance.CRITICAL,
                verification_status=VerificationStatus.VERIFIED,
                evidence=["SEBI Algorithmic Trading Framework & ATS Risk Mandates"],
            ),
            MemoryRecord(
                memory_id="mem_handbook_pitfalls_averaging_down",
                created_by="risk_officer",
                level=MemoryLevel.LONG_TERM,
                memory_type=MemoryType.PROCEDURAL,
                category=QualityCategory.LESSON,
                content="Averaging Down & Penny Stock Traps: Never average down on a losing position ('throwing good money after bad' / 'catching a falling knife'). Avoid cheap penny stocks: profits depend on capital deployed, not share count. Institutions drive 70% of daily volume and only sponsor institutional-grade leaders.",
                confidence=1.0,
                source="A to Z of Stock Market - Section 1 'Pitfalls to Avoid'",
                importance=MemoryImportance.CRITICAL,
                verification_status=VerificationStatus.VERIFIED,
                evidence=["Institutional volume dominance study and loss-limiting principles"],
            ),
            MemoryRecord(
                memory_id="mem_handbook_distribution_market_tide",
                created_by="macro_analyst",
                level=MemoryLevel.LONG_TERM,
                memory_type=MemoryType.STRATEGIC,
                category=QualityCategory.FACT,
                content="Market Tide & Distribution Days: Three-fourths (75%) of all individual stocks follow the general market trend. Identify institutional distribution when major indices close lower on heavier volume than the previous day. Never buy aggressively against institutional distribution.",
                confidence=0.98,
                source="A to Z of Stock Market - Section 1 'Buying Stocks In A Down Market'",
                importance=MemoryImportance.HIGH,
                verification_status=VerificationStatus.VERIFIED,
                evidence=["IBD & Institutional Market Distribution statistical correlation"],
            ),
            MemoryRecord(
                memory_id="mem_handbook_quant_ratios",
                created_by="quant_specialist",
                level=MemoryLevel.LONG_TERM,
                memory_type=MemoryType.PROCEDURAL,
                category=QualityCategory.FACT,
                content="Portfolio Performance Evaluation Ratios: 1) Sharpe Ratio: (Rs - Rf) / Standard Deviation; 2) Treynor Ratio: (Rs - Rf) / Beta; 3) Information Ratio (IR): (Rp - Ri) / Tracking Error; 4) Maximum Drawdown (MDD): Peak-to-trough equity decline indicating actual drawdown risk.",
                confidence=1.0,
                source="A to Z of Stock Market - Section 3 'Performance Evaluation'",
                importance=MemoryImportance.HIGH,
                verification_status=VerificationStatus.VERIFIED,
                evidence=["Modern Portfolio Theory (MPT) mathematical formulas"],
            ),
            MemoryRecord(
                memory_id="mem_handbook_fibonacci_retracements",
                created_by="technical_agent",
                level=MemoryLevel.LONG_TERM,
                memory_type=MemoryType.PROCEDURAL,
                category=QualityCategory.FACT,
                content="Fibonacci Retracement & Golden Ratio (Phi = 1.618 / 0.618): Key pullback support/resistance levels during trends are 38.2% and 61.8% (with 50.0% as an equilibrium midpoint). Surge in volume at 38.2% or 61.8% Fibonacci levels confirms institutional support and high-probability trend resumption.",
                confidence=0.97,
                source="A to Z of Stock Market - Section 5 'Fibonacci Retracements'",
                importance=MemoryImportance.HIGH,
                verification_status=VerificationStatus.VERIFIED,
                evidence=["Copper and Nifty 50 historical Fibonacci pullback studies"],
            ),
            MemoryRecord(
                memory_id="mem_handbook_futures_pricing_carry",
                created_by="options_specialist",
                level=MemoryLevel.LONG_TERM,
                memory_type=MemoryType.PROCEDURAL,
                category=QualityCategory.FACT,
                content="Futures Cost of Carry Formula: Futures Price = Index Spot + [Index Spot * (Financing Cost - Dividend Yield) * (t/12)]. When futures trade above spot due to high demand, it reflects Contango; when trading below spot due to intense selling/hedging, it reflects Backwardation.",
                confidence=1.0,
                source="A to Z of Stock Market - Section 6 'Determination of Future Prices'",
                importance=MemoryImportance.HIGH,
                verification_status=VerificationStatus.VERIFIED,
                evidence=["NSE Futures Pricing & Fair Value arbitrage models"],
            ),
            MemoryRecord(
                memory_id="mem_handbook_options_strategies_matrix",
                created_by="options_specialist",
                level=MemoryLevel.LONG_TERM,
                memory_type=MemoryType.STRATEGIC,
                category=QualityCategory.FACT,
                content="Defined-Risk Options Playbook: 1) Bull Call Spread (Debit): Moderately bullish; 2) Bull Put Spread (Credit): Moderately bullish/neutral; 3) Bear Put Spread (Debit): Moderately bearish; 4) Bear Call Spread (Credit): Moderately bearish/neutral; 5) Long Straddle/Strangle: High volatility expectation; 6) Short Straddle/Strangle: Low volatility theta harvesting.",
                confidence=1.0,
                source="A to Z of Stock Market - Section 7 'Futures & Options'",
                importance=MemoryImportance.CRITICAL,
                verification_status=VerificationStatus.VERIFIED,
                evidence=["Black-Scholes option pricing and payoff curves"],
            ),
            MemoryRecord(
                memory_id="mem_handbook_fno_margins_span",
                created_by="risk_officer",
                level=MemoryLevel.LONG_TERM,
                memory_type=MemoryType.PROCEDURAL,
                category=QualityCategory.FACT,
                content="NSE/BSE F&O Margin Architecture: 1) SPAN Margin: Calculated via CME SPAN algorithm analyzing 16 distinct price/volatility scenarios, revised 6 times daily; 2) Exposure Margin: 3% on index, 5% on equity F&O; 3) Mark-to-Market (MTM): Daily cash settlement of unrealized variation margins.",
                confidence=1.0,
                source="A to Z of Stock Market - Section 7 'Types of Margins Levied in F&O Trading'",
                importance=MemoryImportance.CRITICAL,
                verification_status=VerificationStatus.VERIFIED,
                evidence=["SEBI / Exchange SPAN & Exposure Margin circulars"],
            ),
            MemoryRecord(
                memory_id="mem_sst_six_rules_system",
                created_by="technical_agent",
                level=MemoryLevel.LONG_TERM,
                memory_type=MemoryType.PROCEDURAL,
                category=QualityCategory.LESSON,
                content="David Graeme-Smith 6 SST Rules: 1) Max 3%-5% risk; 2) 50 SMA trend filter; 3) 8-period DMI +DI/-DI cross/touch; 4) Confirmation above last Significant Day high; 5) Stop 0.5% below last significant low; 6) Trailing stop under each new significant low, tightening to 50% on a Big Move Day (>=5%).",
                confidence=1.0,
                source="Short Swing Trading - David Graeme-Smith",
                importance=MemoryImportance.CRITICAL,
                verification_status=VerificationStatus.VERIFIED,
                evidence=["Complete 6-rule Short Swing Trading system specification"],
            ),
            MemoryRecord(
                memory_id="mem_sst_stock_personality_correlation",
                created_by="quant_specialist",
                level=MemoryLevel.LONG_TERM,
                memory_type=MemoryType.STRATEGIC,
                category=QualityCategory.LESSON,
                content="Stock Personality & Low Correlation Mandate: Trade shares that move in neat orderly steps with small shadows. Avoid erratic whipsaw stocks. Prefer low-correlation stocks (index correlation <= 0.20) with independent trends.",
                confidence=0.98,
                source="Short Swing Trading - David Graeme-Smith (Chapter 11)",
                importance=MemoryImportance.HIGH,
                verification_status=VerificationStatus.VERIFIED,
                evidence=["Bovis vs BT Group comparative performance study"],
            ),
            MemoryRecord(
                memory_id="mem_wyckoff_campaign_stages",
                created_by="fund_manager",
                level=MemoryLevel.LONG_TERM,
                memory_type=MemoryType.STRATEGIC,
                category=QualityCategory.FACT,
                content="Wyckoff Institutional Campaign Lifecycle: 1) Accumulation (absorption of floating supply); 2) Mark-Up (volume expansion out of range); 3) Distribution (high volume at tops transferring shares to public); 4) Mark-Down (withdrawal of support).",
                confidence=1.0,
                source="The Day Trader's Bible - Richard D. Wyckoff (Chapter 5-7)",
                importance=MemoryImportance.CRITICAL,
                verification_status=VerificationStatus.VERIFIED,
                evidence=["Tape Reading volume studies in Union Pacific and Reading Railroad"],
            ),
            MemoryRecord(
                memory_id="mem_wyckoff_tape_reading_commandments",
                created_by="risk_officer",
                level=MemoryLevel.LONG_TERM,
                memory_type=MemoryType.PROCEDURAL,
                category=QualityCategory.LESSON,
                content="Wyckoff 7 Tape Reading Commandments: 1) Do not overtrade; 2) Eliminate anxiety & trade without preconceived P&L bias; 3) Don't trade trendless markets; 4) Fast execution; 5) No broker discretion; 6) Reduce sizing by 50%-75% after a losing streak; 7) Mental & physical alertness.",
                confidence=1.0,
                source="The Day Trader's Bible - Richard D. Wyckoff (Chapter 11)",
                importance=MemoryImportance.CRITICAL,
                verification_status=VerificationStatus.VERIFIED,
                evidence=["Wyckoff 7 Commandments of professional tape reading"],
            ),
            MemoryRecord(
                memory_id="mem_sadowski_nine_strategies",
                created_by="technical_agent",
                level=MemoryLevel.LONG_TERM,
                memory_type=MemoryType.STRATEGIC,
                category=QualityCategory.FACT,
                content="Sadowski Advanced Strategy Suite: Triple EMA (20/60/100), Heikin-Ashi 2-candle reversal with Stochastics (14,7,3), Bollinger Band Squeeze (<0.0100 width) breakout, NR4/NR7 volatility expansion, Role Reversal, and 3/1000 Money Management Rule (max 3% risk).",
                confidence=0.99,
                source="9 Advanced and Profitable Trading Strategies - Roman Sadowski",
                importance=MemoryImportance.HIGH,
                verification_status=VerificationStatus.VERIFIED,
                evidence=["Multi-strategy backtests and money management framework"],
            ),
            MemoryRecord(
                memory_id="mem_galen_woods_price_action_engine",
                created_by="technical_agent",
                level=MemoryLevel.LONG_TERM,
                memory_type=MemoryType.PROCEDURAL,
                category=QualityCategory.FACT,
                content="Galen Woods Price Action Core Engine: Microscopic bar anatomy (Range = Volatility, Body = Strength, Shadow = Rejection), 10 Essential Setups (Pin Bar, Key Reversal, Exhaustion Bar, 2-Bar & 3-Bar Reversal, 3-Bar Pullback into 20 EMA, Inside Bar, Outside Bar, NR7, Hikkake), Context precedes pattern, Ex-Ante trade journal discipline.",
                confidence=1.0,
                source="How to Trade with Price Action - Galen Woods",
                importance=MemoryImportance.CRITICAL,
                verification_status=VerificationStatus.VERIFIED,
                evidence=["Bar-by-bar price action analysis and trading record methodology"],
            ),
            MemoryRecord(
                memory_id="mem_carli_cci_divergence_framework",
                created_by="technical_agent",
                level=MemoryLevel.LONG_TERM,
                memory_type=MemoryType.PROCEDURAL,
                category=QualityCategory.LESSON,
                content="David Carli CCI Divergence & Trendline Strategy: CCI(20) extreme zones (< -150 oversold for bullish divergence without crossing 0; > +150 overbought for bearish divergence without crossing 0), 1.130-1.618 Fibonacci extension of prior swing, Trendline Breakout confirmation trigger, 127.2% and 161.8% profit targets with BE trailing.",
                confidence=1.0,
                source="Trading with the Trendlines: The Power of Divergence - David Carli",
                importance=MemoryImportance.HIGH,
                verification_status=VerificationStatus.VERIFIED,
                evidence=["CCI Extreme Divergence + Fibonacci Extension rules across forex, commodities, and equities"],
            ),
            MemoryRecord(
                memory_id="mem_clbs_dealer_doctrine",
                created_by="chief_risk_officer",
                level=MemoryLevel.LONG_TERM,
                memory_type=MemoryType.STRATEGIC,
                category=QualityCategory.FACT,
                content="CLBS V2 Dealer Doctrine: Markets exist to redistribute risk and manage dealer inventory, not reward prediction. Stop asking 'Where will price go?' Start asking 'Who is uncomfortable here? Who is forced to hedge or trapped?' Price moves because dealers (Citadel, Jane Street, SIG, Optiver) must manage inventory, gamma, and volatility.",
                confidence=1.0,
                source="CLBS V2 Coursebook - Vikas Gahlot (Metaverse Trading Academy)",
                importance=MemoryImportance.CRITICAL,
                verification_status=VerificationStatus.VERIFIED,
                evidence=["Dealer-First Market Intelligence Engine and Market Maker inventory mechanics"],
            ),
            MemoryRecord(
                memory_id="mem_clbs_gamma_vix_regimes",
                created_by="options_specialist",
                level=MemoryLevel.LONG_TERM,
                memory_type=MemoryType.STRATEGIC,
                category=QualityCategory.FACT,
                content="VIX + Gamma Permission Layer: 1) Low VIX + Long Gamma: Dealers buy dips and sell rallies. Price rotates, breakouts fail, VWAP holds, mean-reversion dominates. 2) Rising VIX + Gamma Instability: Dealer comfort decreases, breakouts begin to hold, market prepares to expand. 3) High VIX + Short Gamma: Dealers chase price to hedge delta. Trends accelerate violently, stops cascade, momentum is rewarded.",
                confidence=1.0,
                source="CLBS V2 Coursebook - Module 5 & 6 (Dealer Gamma & Volatility Regimes)",
                importance=MemoryImportance.CRITICAL,
                verification_status=VerificationStatus.VERIFIED,
                evidence=["Dealer Delta-Hedging and Market Maker Gamma positioning dynamics"],
            ),
            MemoryRecord(
                memory_id="mem_clbs_liquidity_sweeps",
                created_by="quant_specialist",
                level=MemoryLevel.LONG_TERM,
                memory_type=MemoryType.PROCEDURAL,
                category=QualityCategory.LESSON,
                content="Liquidity Sweeps & Stop Hunting Mechanics: Stops are stored liquidity. Dealers engineer liquidity sweeps beyond obvious highs/lows (PDH/PDL, swing pivots) to fulfill inventory requirements without price impact. Never place stops at obvious retail pivot levels; anchor stops beyond structural sweep zones.",
                confidence=1.0,
                source="CLBS V2 Coursebook - Module 7 'Liquidity and Sweeps'",
                importance=MemoryImportance.HIGH,
                verification_status=VerificationStatus.VERIFIED,
                evidence=["Order flow imbalance and stop-run liquidity capture"],
            ),
            MemoryRecord(
                memory_id="mem_clbs_structural_levels_vwap",
                created_by="technical_agent",
                level=MemoryLevel.LONG_TERM,
                memory_type=MemoryType.PROCEDURAL,
                category=QualityCategory.FACT,
                content="CLBS V2 Reference Hierarchy: 1) Structural Levels: PDH/PDL (Previous Day High/Low), PWH/PWL (Previous Week), PMH/PML (Previous Month). 2) Multi-Timeframe VWAPs (Daily, Weekly, Monthly) represent institutional inventory cost. Balanced markets gravitate back to VWAP; unbalanced markets break away into short-gamma expansion.",
                confidence=0.99,
                source="CLBS V2 Coursebook - Module 8 'Structural Levels & VWAPs'",
                importance=MemoryImportance.HIGH,
                verification_status=VerificationStatus.VERIFIED,
                evidence=["Volume-Weighted Average Price equilibrium and period high/low rejection"],
            ),
            MemoryRecord(
                memory_id="mem_mta_stop_loss_six_archetypes",
                created_by="risk_officer",
                level=MemoryLevel.LONG_TERM,
                memory_type=MemoryType.PROCEDURAL,
                category=QualityCategory.LESSON,
                content="Metaverse 6 Stop-Loss Archetypes: 1) Percentage-Based (max 2% account risk); 2) Support/Resistance Structural Stop; 3) Trailing Stop; 4) Volatility-Based (ATR-adjusted wider in volatile regimes); 5) Time-Based Stop; 6) Risk-Reward Alignment (ensure stop distance <= 50% target distance for min 1:2 R:R).",
                confidence=1.0,
                source="Stop Loss: A Guide To The Perfect Stop Loss Management - Metaverse Trading Academy",
                importance=MemoryImportance.CRITICAL,
                verification_status=VerificationStatus.VERIFIED,
                evidence=["Risk management & capital preservation doctrine"],
            ),
            MemoryRecord(
                memory_id="mem_mta_candlestick_cheat_sheet",
                created_by="technical_agent",
                level=MemoryLevel.LONG_TERM,
                memory_type=MemoryType.PROCEDURAL,
                category=QualityCategory.FACT,
                content="Metaverse Candlestick Precision Rules: 1) Morning/Evening Star: Third candle close must achieve >60% u-turn retracement of first candle. 2) Tweezer Tops/Bottoms: Long rejection wicks must constitute at least 60% of total candle range. 3) Piercing Line & Dark Cloud Cover: Second candle must close beyond 60% of prior candle body. 4) Protective Buffer Stops: Always place protective stops 10-15 ticks beyond the extreme wicks of the formation.",
                confidence=0.98,
                source="Candlestick Cheat Sheet - Metaverse Trading Academy",
                importance=MemoryImportance.HIGH,
                verification_status=VerificationStatus.VERIFIED,
                evidence=["Candlestick geometry, 60% U-turn rule, and buffer stop placement"],
            ),
            MemoryRecord(
                memory_id="mem_mta_option_buying_rules",
                created_by="options_specialist",
                level=MemoryLevel.LONG_TERM,
                memory_type=MemoryType.PROCEDURAL,
                category=QualityCategory.LESSON,
                content="Option Buying Precision & Theta Headwinds: Option buying provides asymmetric leverage with risk limited to premium, but faces theta time decay acceleration into expiry. Never buy options in dull, low-volatility markets. Only buy options when real-time Order Flow shows aggressive market order imbalance and rising Open Interest in direction of momentum.",
                confidence=1.0,
                source="Option Buying Trading - Metaverse Trading Academy",
                importance=MemoryImportance.HIGH,
                verification_status=VerificationStatus.VERIFIED,
                evidence=["Option Greeks theta decay mechanics and order flow volume confirmation"],
            ),
            MemoryRecord(
                memory_id="mem_mta_oi_order_flow_matrix",
                created_by="quant_specialist",
                level=MemoryLevel.LONG_TERM,
                memory_type=MemoryType.STRATEGIC,
                category=QualityCategory.FACT,
                content="The 4-Quadrant OI & Price Trend Matrix: 1) Price Rising + OI Rising + Vol Rising -> Long Build-Up (Strong Bullish Trend); 2) Price Rising + OI Falling + Vol Falling -> Short Covering (Weak/Exhausting Rally); 3) Price Falling + OI Rising + Vol Rising -> Short Build-Up (Strong Bearish Trend); 4) Price Falling + OI Falling + Vol Falling -> Long Unwinding (Weakening Decline / Potential Bounce).",
                confidence=1.0,
                source="Data Discovery: Open Interest + Order Flow - Metaverse Trading Academy",
                importance=MemoryImportance.CRITICAL,
                verification_status=VerificationStatus.VERIFIED,
                evidence=["NSE/BSE Open Interest and Order Flow institutional positioning matrix"],
            ),
            MemoryRecord(
                memory_id="mem_mta_chart_patterns_targets",
                created_by="technical_agent",
                level=MemoryLevel.LONG_TERM,
                memory_type=MemoryType.PROCEDURAL,
                category=QualityCategory.FACT,
                content="Classical Chart Pattern Target Projections: 1) Head & Shoulders: Distance from Head to Neckline projected from breakout point; 2) Double / Triple Tops & Bottoms: Height of pattern projected from breakout line; 3) Flags & Pennants: Length of flagpole projected from breakout point; 4) Triangles & Rectangles: Widest vertical height projected from breakout point.",
                confidence=0.99,
                source="Identifying Chart Patterns with Technical Analysis - Metaverse Trading Academy",
                importance=MemoryImportance.HIGH,
                verification_status=VerificationStatus.VERIFIED,
                evidence=["Bulkowski and Edwards & Magee geometric price projection formulas"],
            ),
            MemoryRecord(
                memory_id="mem_mta_explosion_gap_pivot",
                created_by="technical_agent",
                level=MemoryLevel.LONG_TERM,
                memory_type=MemoryType.PROCEDURAL,
                category=QualityCategory.LESSON,
                content="Explosion Gap Pivot & False Breakout Execution: 1) Explosion Gap Pivot: On a high-volume breakaway gap, wait for throwback; if it holds above gap low without filling, enter above high of gap bar with stop below pivot low. 2) False Breakout Trap: When price breaches S/R but immediately reverses into range, trigger a Stop-and-Reverse into the trap direction.",
                confidence=0.98,
                source="Identifying Chart Patterns with Technical Analysis - Metaverse Trading Academy",
                importance=MemoryImportance.HIGH,
                verification_status=VerificationStatus.VERIFIED,
                evidence=["Breakaway gap throwback validation and false breakout trap models"],
            ),
            MemoryRecord(
                memory_id="mem_mta_five_beginner_mistakes",
                created_by="risk_officer",
                level=MemoryLevel.LONG_TERM,
                memory_type=MemoryType.STRATEGIC,
                category=QualityCategory.LESSON,
                content="5 Core Trading Pitfalls: 1) Treat trading strictly as a calculated business; 2) Eliminate emotional and gut-based trades; 3) Success is a formula based on wave structure and supply/demand; 4) In trading you win points or experience—individual losses are business expenses; 5) Avoid overconfidence and continuously review trade records.",
                confidence=1.0,
                source="5 Beginner Mistakes Traders Make - Metaverse Trading Academy",
                importance=MemoryImportance.HIGH,
                verification_status=VerificationStatus.VERIFIED,
                evidence=["Behavioral finance and trading discipline doctrine"],
            ),
            MemoryRecord(
                memory_id="mem_kaufman_kama_efficiency_ratio",
                created_by="quant_specialist",
                level=MemoryLevel.LONG_TERM,
                memory_type=MemoryType.PROCEDURAL,
                category=QualityCategory.FACT,
                content="Kaufman Adaptive Moving Average (KAMA) & Efficiency Ratio (ER): ER = |Net Price Change over n periods| / Sum(Individual Bar Volatilities) (0 to 1). Smoothing Constant SC = [ER * (Fast SC - Slow SC) + Slow SC]^2. In noisy/choppy regimes, KAMA flattens to prevent whipsaws; in high-efficiency trends, KAMA accelerates dynamically to track price without lag.",
                confidence=1.0,
                source="Trading Systems and Methods (5th Ed) - Perry J. Kaufman (Chapter 17)",
                importance=MemoryImportance.CRITICAL,
                verification_status=VerificationStatus.VERIFIED,
                evidence=["Kaufman Adaptive Moving Average mathematical formulation and backtest data"],
            ),
            MemoryRecord(
                memory_id="mem_kaufman_market_noise_theory",
                created_by="quant_specialist",
                level=MemoryLevel.LONG_TERM,
                memory_type=MemoryType.STRATEGIC,
                category=QualityCategory.FACT,
                content="Market Noise & Trend Ratio: Price movement consists of trend + noise. Higher intraday noise degrades trend-following strategies. Quantify noise by comparing total path length to net displacement over time. Only deploy breakout capital when noise is below historical thresholds and efficiency ratio expands.",
                confidence=0.99,
                source="Trading Systems and Methods (5th Ed) - Perry J. Kaufman (Chapter 1 & 20)",
                importance=MemoryImportance.HIGH,
                verification_status=VerificationStatus.VERIFIED,
                evidence=["Kaufman market noise statistics across equities and commodities"],
            ),
            MemoryRecord(
                memory_id="mem_kaufman_triple_screen_mtf",
                created_by="technical_agent",
                level=MemoryLevel.LONG_TERM,
                memory_type=MemoryType.PROCEDURAL,
                category=QualityCategory.FACT,
                content="Elder-Kaufman Triple Screen Framework: 1) Screen 1 (Market Tide): Weekly/Daily trend indicator defines allowable trade direction (50 SMA / MACD slope). 2) Screen 2 (Market Wave): Intermediate oscillator (Stochastics / RSI / CCI) identifies counter-trend pullbacks. 3) Screen 3 (Market Ripple): Intraday breakout trigger confirms trend resumption.",
                confidence=1.0,
                source="Trading Systems and Methods (5th Ed) - Perry J. Kaufman (Chapter 19)",
                importance=MemoryImportance.CRITICAL,
                verification_status=VerificationStatus.VERIFIED,
                evidence=["Triple-Screen multiple timeframe quantitative trading rules"],
            ),
            MemoryRecord(
                memory_id="mem_kaufman_system_testing_integrity",
                created_by="quant_specialist",
                level=MemoryLevel.LONG_TERM,
                memory_type=MemoryType.PROCEDURAL,
                category=QualityCategory.LESSON,
                content="System Testing Integrity & Walk-Forward Validation: 1) Out-of-Sample Discipline: Reserve >=30%-40% of historical data strictly for unseen validation; 2) Walk-Forward Testing: Re-optimize on rolling in-sample windows and test on out-of-sample intervals; 3) Degrees of Freedom: Limit parameters to prevent curve-fitting; 4) Full Cost Inclusion: Deduct slippage, commissions, and spread on every fill.",
                confidence=1.0,
                source="Trading Systems and Methods (5th Ed) - Perry J. Kaufman (Chapter 21)",
                importance=MemoryImportance.CRITICAL,
                verification_status=VerificationStatus.VERIFIED,
                evidence=["Institutional system optimization protocols and robustness testing"],
            ),
            MemoryRecord(
                memory_id="mem_kaufman_risk_control_volatility_parity",
                created_by="risk_officer",
                level=MemoryLevel.LONG_TERM,
                memory_type=MemoryType.PROCEDURAL,
                category=QualityCategory.LESSON,
                content="Kaufman Risk Control & Volatility Parity: 1) Position Sizing by Volatility: Size positions inversely proportional to asset ATR to ensure equal dollar risk across assets; 2) Probability of Ruin: Ruin is non-linear; risking over 3% per trade under adverse streaks accelerates ruin exponentially; 3) Volatility-Scaled Stops: Set trailing stops at a multiple of ATR (2.0x-2.5x ATR).",
                confidence=1.0,
                source="Trading Systems and Methods (5th Ed) - Perry J. Kaufman (Chapter 23 & 24)",
                importance=MemoryImportance.CRITICAL,
                verification_status=VerificationStatus.VERIFIED,
                evidence=["Vince Optimal f, Kelly Criterion, and Risk Parity portfolio allocation models"],
            ),
            MemoryRecord(
                memory_id="mem_global_dxy_usdinr_intermarket",
                created_by="macro_analyst",
                level=MemoryLevel.LONG_TERM,
                memory_type=MemoryType.STRATEGIC,
                category=QualityCategory.FACT,
                content="Global Intermarket (DXY & EM Capital Flow): A strengthening US Dollar Index (DXY) creates capital flight from emerging markets (NSE/BSE) as FIIs sell equities to repatriate funds. DXY weakness fuels foreign institutional inflows into Indian blue-chips. Always check DXY and USDINR trajectories before establishing aggressive long equity campaigns.",
                confidence=1.0,
                source="John J. Murphy Intermarket Analysis & Global Macro Standards",
                importance=MemoryImportance.CRITICAL,
                verification_status=VerificationStatus.VERIFIED,
                evidence=["Statistical correlation between DXY rallies and FII equity net outflows on NSE"],
            ),
            MemoryRecord(
                memory_id="mem_global_yield_curve_inversion",
                created_by="macro_analyst",
                level=MemoryLevel.LONG_TERM,
                memory_type=MemoryType.STRATEGIC,
                category=QualityCategory.FACT,
                content="US 10-Year Yields & 2Y-10Y Yield Curve Inversion: An inverted 2Y-10Y yield curve is the premier leading indicator of global recession. Surging US 10-year Treasury yields increase discount rates, compressing high-multiple growth and tech valuations, triggering rotation into defensive value, energy, and high-dividend sectors.",
                confidence=1.0,
                source="Federal Reserve & Global Central Bank Fixed Income Models",
                importance=MemoryImportance.HIGH,
                verification_status=VerificationStatus.VERIFIED,
                evidence=["Historical equity valuation multiple compression during yield curve inversions"],
            ),
            MemoryRecord(
                memory_id="mem_global_brent_crude_india_impact",
                created_by="macro_analyst",
                level=MemoryLevel.LONG_TERM,
                memory_type=MemoryType.STRATEGIC,
                category=QualityCategory.FACT,
                content="Brent Crude Oil & Indian Macro Balance: India imports >80% of its crude oil. A $10/bbl surge in Brent directly widens India's Current Account Deficit (CAD), weakens INR, and elevates inflation. Hurts: Paints, Tires, Aviation, Specialty Chemicals. Benefits: Upstream exploration (ONGC, Oil India).",
                confidence=1.0,
                source="Reserve Bank of India (RBI) Macroeconomic Monograph",
                importance=MemoryImportance.HIGH,
                verification_status=VerificationStatus.VERIFIED,
                evidence=["Crude oil price pass-through elasticity to Indian CPI and sector EBITDA margins"],
            ),
            MemoryRecord(
                memory_id="mem_global_gift_nifty_transmission",
                created_by="quant_specialist",
                level=MemoryLevel.LONG_TERM,
                memory_type=MemoryType.PROCEDURAL,
                category=QualityCategory.FACT,
                content="GIFT Nifty Overnight Transmission & Opening Gap Playbook: GIFT Nifty (GIFT City IFSC) trades across Asian and Western hours, capturing overnight US market closes (S&P 500, Nasdaq). At 09:00 AM IST, GIFT Nifty premium/discount establishes opening auction fair value for NSE.",
                confidence=0.99,
                source="NSE International Exchange (NSE IX) Settlement Protocols",
                importance=MemoryImportance.HIGH,
                verification_status=VerificationStatus.VERIFIED,
                evidence=["Opening price gap variance between GIFT Nifty and NSE cash open"],
            ),
            MemoryRecord(
                memory_id="mem_microstructure_iceberg_almgren_chriss",
                created_by="execution_engineer",
                level=MemoryLevel.LONG_TERM,
                memory_type=MemoryType.PROCEDURAL,
                category=QualityCategory.FACT,
                content="Market Microstructure & Almgren-Chriss Optimal Execution: Large institutional orders are sliced via TWAP/VWAP or Iceberg orders showing only 5%-10% in Level 2 DOM. Do not trust resting limit order depth. Monitor executed Time & Sales prints: repeated block prints at ask/bid reveal institutional stealth accumulation/distribution.",
                confidence=1.0,
                source="Almgren & Chriss Optimal Execution of Portfolio Transactions",
                importance=MemoryImportance.CRITICAL,
                verification_status=VerificationStatus.VERIFIED,
                evidence=["Limit order book depth reconstitution and algorithmic execution models"],
            ),
            MemoryRecord(
                memory_id="mem_volatility_dealer_gamma_gex",
                created_by="options_specialist",
                level=MemoryLevel.LONG_TERM,
                memory_type=MemoryType.STRATEGIC,
                category=QualityCategory.FACT,
                content="Dealer Gamma Exposure (GEX) & Volatility Regimes: 1) Positive Gamma (+GEX): Market Makers are long gamma. As price drops, dealers buy delta; as price rises, dealers sell delta -> Extreme mean reversion, dampened volatility, range-bound pin to VWAP/Max Pain. 2) Negative Gamma (-GEX): Market Makers are short gamma -> Explosive trend velocity, stop cascades, high volatility expansion.",
                confidence=1.0,
                source="SqueezeMetrics & Institutional Options Market Making Models",
                importance=MemoryImportance.CRITICAL,
                verification_status=VerificationStatus.VERIFIED,
                evidence=["Dealer delta-hedging feedback loops in index futures and options"],
            ),
            MemoryRecord(
                memory_id="mem_options_max_pain_expiry_pin",
                created_by="options_specialist",
                level=MemoryLevel.LONG_TERM,
                memory_type=MemoryType.PROCEDURAL,
                category=QualityCategory.FACT,
                content="Max Pain Theory & Expiry Pinning Mechanics: Options market makers write majority of contracts. At weekly/monthly contract expiry, price exhibits strong gravitational pull toward the strike where aggregate call + put open interest value is minimized (Max Pain strike). In low-volatility regimes on expiry day, avoid chasing breakouts away from Max Pain/VWAP equilibrium.",
                confidence=0.97,
                source="Options Clearing Corporation (OCC) & NSE Expiry Studies",
                importance=MemoryImportance.HIGH,
                verification_status=VerificationStatus.VERIFIED,
                evidence=["Historical strike-pinning frequencies on NSE Bank Nifty / Nifty 50 weekly expiries"],
            ),
            MemoryRecord(
                memory_id="mem_quant_kelly_criterion_var",
                created_by="risk_officer",
                level=MemoryLevel.LONG_TERM,
                memory_type=MemoryType.PROCEDURAL,
                category=QualityCategory.LESSON,
                content="Quantitative Risk (Kelly Criterion & Tail-Risk VaR): 1) Half-Kelly Allocation: Full Kelly fraction f* = (bp - q)/b maximizes geometric growth but exhibits catastrophic drawdowns. Institutional desk mandates Half-Kelly (0.5 * f*) to achieve 75% of peak growth with only 50% volatility. 2) Value at Risk (VaR 99%) & Expected Shortfall (CVaR): Model parametric fat-tailed Student-t losses; never assume Gaussian normality.",
                confidence=1.0,
                source="J.L. Kelly Jr. & Philippe Jorion Financial Risk Manager Handbook",
                importance=MemoryImportance.CRITICAL,
                verification_status=VerificationStatus.VERIFIED,
                evidence=["Capital growth optimization and non-normal fat-tail distribution statistics"],
            ),
            MemoryRecord(
                memory_id="mem_quant_risk_parity_allocation",
                created_by="fund_manager",
                level=MemoryLevel.LONG_TERM,
                memory_type=MemoryType.STRATEGIC,
                category=QualityCategory.FACT,
                content="Ray Dalio Risk Parity & Volatility Budgeting: Traditional 60/40 portfolios are dominated by equity risk (equities drive >85% of portfolio variance). Risk Parity allocates capital so that every uncorrelated asset class (Equities, Sovereign Bonds, Gold, Cash) contributes an equal share of portfolio risk, weighted inversely to individual asset volatility.",
                confidence=1.0,
                source="Bridgewater Associates All-Weather & Risk Parity Research",
                importance=MemoryImportance.HIGH,
                verification_status=VerificationStatus.VERIFIED,
                evidence=["All-Weather multi-decade Sharpe ratio outperformance across stagflation and deflation"],
            ),
            MemoryRecord(
                memory_id="mem_auction_market_profile_poc",
                created_by="technical_agent",
                level=MemoryLevel.LONG_TERM,
                memory_type=MemoryType.PROCEDURAL,
                category=QualityCategory.FACT,
                content="Steidlmayer Auction Market Profile & Value Area: 1) Value Area (VA): The price range where 70% of volume occurred in a session (Value Area High VAH to Value Area Low VAL). 2) Point of Control (POC): Price level with highest traded volume. Rule: When price opens within previous Value Area, expect rotational balance; when price opens outside Value Area and is accepted, expect strong directional initiative trend.",
                confidence=1.0,
                source="Peter Steidlmayer & CBOT Market Profile Framework",
                importance=MemoryImportance.CRITICAL,
                verification_status=VerificationStatus.VERIFIED,
                evidence=["CBOT Auction Market Theory and Volume Profile distribution statistics"],
            ),
            MemoryRecord(
                memory_id="mem_wyckoff_spring_upthrust_schematic",
                created_by="technical_agent",
                level=MemoryLevel.LONG_TERM,
                memory_type=MemoryType.PROCEDURAL,
                category=QualityCategory.LESSON,
                content="Wyckoff Structural Phase Traps: 1) Phase C Spring (False Breakdown): Price briefly pierces support on low volume, quickly reclaims the range, cleaning out retail stops and confirming composite operator accumulation. High-probability aggressive long entry. 2) Upthrust After Distribution (UTAD): Price breaches resistance to lure retail breakout buyers, then slams back into range on high volume. High-probability short entry.",
                confidence=1.0,
                source="Richard D. Wyckoff Method of Trading and Investing in Stocks",
                importance=MemoryImportance.CRITICAL,
                verification_status=VerificationStatus.VERIFIED,
                evidence=["Wyckoff Phase C schematic spring and upthrust trade verification"],
            ),
            MemoryRecord(
                memory_id="mem_corrective_action_curfew_001",
                created_by="system_architect",
                level=MemoryLevel.LONG_TERM,
                memory_type=MemoryType.STRATEGIC,
                category=QualityCategory.LESSON,
                content="[Forensic Corrective Rule 1 - Intraday Curfew]: Strictly ZERO fresh intraday momentum entries between 12:00 PM and 01:30 PM IST (Midday Consolidation Lull). Breakouts during this window have >65% false-signal probability and insufficient session duration before 15:15 IST broker squareoff. Prime intraday execution windows are strictly 09:20 - 11:30 AM (Opening Momentum) and 01:45 - 02:30 PM (Institutional Afternoon Trend).",
                confidence=1.0,
                source="live_trade_audit_forensics_2026_09_29",
                importance=MemoryImportance.CRITICAL,
                verification_status=VerificationStatus.VERIFIED,
                evidence=["EOD Auto-squareoff analysis on COALINDIA and BANDHANBNK entries between 13:07 and 13:28 IST"],
            ),
            MemoryRecord(
                memory_id="mem_corrective_action_stagnation_002",
                created_by="trade_guardian",
                level=MemoryLevel.LONG_TERM,
                memory_type=MemoryType.PROCEDURAL,
                category=QualityCategory.LESSON,
                content="[Forensic Corrective Rule 2 - Stagnation Time-Stop]: If an active intraday trade does not generate at least +0.3% directional progress within 45 minutes of entry, Trade Guardian MUST scratch the position at market price or breakeven immediately. Never hold dead capital through midday chop into 15:15 EOD squareoff.",
                confidence=0.98,
                source="live_trade_audit_forensics_2026_09_29",
                importance=MemoryImportance.HIGH,
                verification_status=VerificationStatus.VERIFIED,
                evidence=["Holding COALINDIA and BANDHANBNK for 120+ minutes inside a 0.2% band led to squareoff slippage"],
            ),
            MemoryRecord(
                memory_id="mem_corrective_action_eod_glide_003",
                created_by="risk_officer",
                level=MemoryLevel.LONG_TERM,
                memory_type=MemoryType.PROCEDURAL,
                category=QualityCategory.LESSON,
                content="[Forensic Corrective Rule 3 - Late Session Glide-Path Profit Lock]: At 02:30 PM IST, if an intraday trade is in profit (+0.1% or greater), Trade Guardian must ratchet the Stop Loss to Entry +0.1% to guarantee a green exit and protect against EOD liquidity evaporation.",
                confidence=0.98,
                source="live_trade_audit_forensics_2026_09_29",
                importance=MemoryImportance.HIGH,
                verification_status=VerificationStatus.VERIFIED,
                evidence=["GAIL was in profit (+0.13%) but missed Target 1 due to 15:15 EOD squareoff termination"],
            ),
            MemoryRecord(
                memory_id="mem_corrective_action_asset_routing_004",
                created_by="technical_agent",
                level=MemoryLevel.LONG_TERM,
                memory_type=MemoryType.STRATEGIC,
                category=QualityCategory.LESSON,
                content="[Forensic Corrective Rule 4 - Asset Routing & Beta Alignment]: Low-beta, large-cap equities (e.g. Coal India, GAIL) require multi-day price expansion and must NOT be traded as afternoon intraday momentum scalps. Route slow-moving large-caps to Multi-Day Swing (Delivery/CNC) to allow trends sufficient time to reach 1:2 R:R targets.",
                confidence=0.95,
                source="live_trade_audit_forensics_2026_09_29",
                importance=MemoryImportance.HIGH,
                verification_status=VerificationStatus.VERIFIED,
                evidence=["COALINDIA low ATR velocity made 1:2 target unreachable within 2 hours of trading time"],
            ),
            # =====================================================================
            # 1. Ondřej Buček Thesis: Analyzing Trading Strategies for Cryptocurrencies Charts
            # =====================================================================
            MemoryRecord(
                memory_id="mem_bucek_turtle_systems",
                created_by="specialist_turtle_trainer",
                level=MemoryLevel.LONG_TERM,
                memory_type=MemoryType.STRATEGIC,
                category=QualityCategory.FACT,
                content="[Buček/Dennis Turtle Trading Systems]: System 1 trades 20-day High/Low breakouts with 10-day exits; System 2 trades 55-day High/Low breakouts with 20/55-day exits. Position sizing uses Volatility N (20-day EMA True Range): 1 Unit = (Capital * Risk_Pct) / (2 * N). Initial Stop Loss is fixed at 2N distance. System 2 exhibits superior survivability in backtests by filtering low-timeframe noise and transaction fee drag.",
                confidence=0.99,
                source="bucek_thesis_chapter_4_5",
                importance=MemoryImportance.CRITICAL,
                verification_status=VerificationStatus.VERIFIED,
                evidence=["Buček Bachelor Thesis Chapter 4.5 & Chapter 5.4 Empirical Backtest Results"],
            ),
            MemoryRecord(
                memory_id="mem_bucek_price_action_pinbars",
                created_by="specialist_price_action_trainer",
                level=MemoryLevel.LONG_TERM,
                memory_type=MemoryType.PROCEDURAL,
                category=QualityCategory.FACT,
                content="[Buček Price Action & Pinbar Mathematics]: Valid swing lows (Red followed by Green candle) trigger Long entries when the candle exhibits a Hammer formation: (min(Open, Close) - Low) / (High - Low) >= 0.70. Valid swing highs (Green followed by Red candle) trigger Short entries when exhibiting a Shooting Star formation: (High - max(Open, Close)) / (High - Low) >= 0.70. Stop Loss is set at the extreme wick with minimum 1:1 Risk-Reward.",
                confidence=0.96,
                source="bucek_thesis_chapter_4_4",
                importance=MemoryImportance.HIGH,
                verification_status=VerificationStatus.VERIFIED,
                evidence=["Buček Bachelor Thesis Section 4.4.1 Algorithmic Strategy Description"],
            ),
            MemoryRecord(
                memory_id="mem_bucek_constant_asset_dca_math",
                created_by="quant_specialist",
                level=MemoryLevel.LONG_TERM,
                memory_type=MemoryType.STRATEGIC,
                category=QualityCategory.LESSON,
                content="[Buček Constant Asset Value DCA & Martingale Warning]: Maintaining a constant asset valuation c across geometric price grids k yields wavy consolidation gain = c * k^2 / (1 + k). However, classical Martingale doubling-down after consecutive losses produces exponential capital depletion and severe margin call risk in trending markets. Martingale without bounded stop losses is strictly banned.",
                confidence=1.0,
                source="bucek_thesis_chapter_4_2_4_3",
                importance=MemoryImportance.CRITICAL,
                verification_status=VerificationStatus.VERIFIED,
                evidence=["Buček Thesis Section 4.2 Martingale & Section 4.3 Constant Value Asset at Sell/Buy Levels"],
            ),
            # =====================================================================
            # 2. Christopher M. McCarthy: Options Unlocked
            # =====================================================================
            MemoryRecord(
                memory_id="mem_mccarthy_options_greeks",
                created_by="options_specialist",
                level=MemoryLevel.LONG_TERM,
                memory_type=MemoryType.PROCEDURAL,
                category=QualityCategory.FACT,
                content="[McCarthy Options Greeks Foundation]: 1) Delta (dC/dS): Directional sensitivity and risk-neutral probability of expiring ITM (0.50 Delta = ~50% POP); 2) Gamma (d^2C/dS^2): Acceleration of Delta, peaking at ATM and near expiration; 3) Theta (dC/dt): Time decay rate, accelerating parabolically under 30 DTE; 4) Vega (dC/dIV): Sensitivity to implied volatility changes, peaking ATM; 5) Rho: Interest rate sensitivity.",
                confidence=1.0,
                source="options_unlocked_chapter_2",
                importance=MemoryImportance.CRITICAL,
                verification_status=VerificationStatus.VERIFIED,
                evidence=["Options Unlocked Chapter 2 'Option Greeks'"],
            ),
            MemoryRecord(
                memory_id="mem_mccarthy_pricing_models",
                created_by="quant_specialist",
                level=MemoryLevel.LONG_TERM,
                memory_type=MemoryType.PROCEDURAL,
                category=QualityCategory.FACT,
                content="[McCarthy Option Pricing Models]: Black-Scholes formula provides theoretical fair value assuming lognormal random walk; Cox-Ross-Rubinstein Binomial Tree handles American style early-exercise optionality via backward induction; Monte Carlo simulation projects thousands of asset price paths St = St-1 * exp((r - 0.5*sigma^2)dt + sigma*sqrt(dt)*Z) to value complex exotic payoffs.",
                confidence=0.98,
                source="options_unlocked_chapter_5",
                importance=MemoryImportance.HIGH,
                verification_status=VerificationStatus.VERIFIED,
                evidence=["Options Unlocked Chapter 5 'Option Pricing Models'"],
            ),
            MemoryRecord(
                memory_id="mem_mccarthy_defined_risk_spreads",
                created_by="options_specialist",
                level=MemoryLevel.LONG_TERM,
                memory_type=MemoryType.STRATEGIC,
                category=QualityCategory.FACT,
                content="[McCarthy Defined-Risk Spreads & Zero-Naked-Risk Rule]: Never sell uncovered/naked options due to infinite loss potential. Deploy defined-risk structures: 1) Bull Call Spreads / Bear Put Spreads for directional leverage with capped debit; 2) Iron Condors (OTM Put credit spread + OTM Call credit spread) for high-probability neutral theta harvesting; 3) Jade Lizards (Short OTM Put + Bear Call credit spread) engineered so total credit exceeds call spread width, eliminating upside risk; 4) Straddles/Strangles for explosive post-earnings/macro volatility expansions.",
                confidence=1.0,
                source="options_unlocked_chapter_6_7",
                importance=MemoryImportance.CRITICAL,
                verification_status=VerificationStatus.VERIFIED,
                evidence=["Options Unlocked Chapter 6 'Options Trading Strategies' & Chapter 7 'Risk Management'"],
            ),
            MemoryRecord(
                memory_id="mem_mccarthy_options_liquidity_safeguards",
                created_by="risk_officer",
                level=MemoryLevel.LONG_TERM,
                memory_type=MemoryType.PROCEDURAL,
                category=QualityCategory.LESSON,
                content="[McCarthy Options Execution & Liquidity Protocols]: 1) Always verify substantial Open Interest before entering any options strike; 2) Audit Bid-Ask spread: wide spreads destroy expectancy; 3) Use Limit Orders exclusively; never execute market orders into illiquid options chains; 4) Anticipate IV Crush: post-earnings or post-event implied volatility collapse rapidly drains option premium from long holders.",
                confidence=0.99,
                source="options_unlocked_chapter_7_9",
                importance=MemoryImportance.CRITICAL,
                verification_status=VerificationStatus.VERIFIED,
                evidence=["Options Unlocked Chapter 7 'Types of Risk' & Chapter 9 'Order Execution'"],
            ),
            # =====================================================================
            # 3. Glen Goodman: The Crypto Trader
            # =====================================================================
            MemoryRecord(
                memory_id="mem_goodman_four_golden_rules",
                created_by="fund_manager",
                level=MemoryLevel.LONG_TERM,
                memory_type=MemoryType.STRATEGIC,
                category=QualityCategory.FACT,
                content="[Glen Goodman Four Golden Rules]: 1) TRADE THE TREND: Never fight the primary trend; trade the line of least resistance; 2) GROW YOUR PROFITS: Give winners breathing room; sit tight through normal retracements and exit only after the trend bends; 3) CUT YOUR LOSSES: Cut losing trades fast and automatically like ripping off a plaster; risk only 0.5%-1% of capital per trade; never average down on losers; 4) CONTROL THE VOICES: Master psychological discipline and suppress destructive cognitive biases.",
                confidence=1.0,
                source="crypto_trader_chapters_3_5_14",
                importance=MemoryImportance.CRITICAL,
                verification_status=VerificationStatus.VERIFIED,
                evidence=["The Crypto Trader Chapters 3, 5, 11, 14 Summary Rules"],
            ),
            MemoryRecord(
                memory_id="mem_goodman_never_chase_breakout_5pct",
                created_by="risk_officer",
                level=MemoryLevel.LONG_TERM,
                memory_type=MemoryType.PROCEDURAL,
                category=QualityCategory.LESSON,
                content="[Glen Goodman 5% Breakout Anti-Chase Rule]: NEVER CHASE A BREAKOUT. Buy only within 5% of the confirmed breakout level. If price has already extended more than 5% above the breakout point, FOMO buying marks the local top before vicious short-term corrections. Patiently wait for a retest of the broken level or skip the trade entirely.",
                confidence=1.0,
                source="crypto_trader_chapter_7_10",
                importance=MemoryImportance.CRITICAL,
                verification_status=VerificationStatus.VERIFIED,
                evidence=["The Crypto Trader Chapter 7 'Don't Chase the Breakout!'"],
            ),
            MemoryRecord(
                memory_id="mem_goodman_classical_charting_geometry",
                created_by="technical_agent",
                level=MemoryLevel.LONG_TERM,
                memory_type=MemoryType.PROCEDURAL,
                category=QualityCategory.FACT,
                content="[Goodman Classical Charting & Basing Patterns]: 1) Basing Patterns: Extended sideways accumulation bases produce the most reliable, sustainable breakouts; 2) Horizontal Resistance > Diagonal Lines: Right-angled triangles with flat horizontal ceilings are statistically far more reliable than diagonal/symmetrical triangles; 3) Volume Confirmation: Valid breakouts require heavy volume expansion ('changing of the guard'); low-volume breakouts frequently fail.",
                confidence=0.97,
                source="crypto_trader_chapter_7",
                importance=MemoryImportance.HIGH,
                verification_status=VerificationStatus.VERIFIED,
                evidence=["The Crypto Trader Chapter 7 'Right-angled triangle' & 'Volume'"],
            ),
            MemoryRecord(
                memory_id="mem_goodman_trailing_stops_reversal_candle",
                created_by="technical_agent",
                level=MemoryLevel.LONG_TERM,
                memory_type=MemoryType.PROCEDURAL,
                category=QualityCategory.FACT,
                content="[Goodman Trailing Stops & Reversal Candles]: 1) 200-day SMA trailing stop (exit on daily close below line); 2) 20/50 MA crossover system for swing trends; 3) Chandelier ATR Trailing Stop: Highest Price (30d) - (3.5 * ATR); 4) Reversal Candle Warning: A candle that tests new highs but closes low with a long upper wick signals trend exhaustion. Lock in partial profits (1/3 to 1/2) and trail stop to breakeven.",
                confidence=0.98,
                source="crypto_trader_chapter_10",
                importance=MemoryImportance.HIGH,
                verification_status=VerificationStatus.VERIFIED,
                evidence=["The Crypto Trader Chapter 10 'When to Sell' & 'Chandelier Stop'"],
            ),
            MemoryRecord(
                memory_id="mem_goodman_risk_parity_and_biases",
                created_by="risk_officer",
                level=MemoryLevel.LONG_TERM,
                memory_type=MemoryType.STRATEGIC,
                category=QualityCategory.LESSON,
                content="[Goodman Risk Parity Allocation & Cognitive Biases Defense]: 1) Risk Parity Sizing: Equalize risk by sizing positions inversely proportional to 30-day ATR; invest smaller sums in crazy volatile assets and larger sums in calmer assets; 2) Cognitive Biases to Eliminate: Sunk-Cost Fallacy (holding dying trades because money was spent), Disposition Effect (selling winners too early and holding losers too long), Anchoring Bias (fixating on past highs or buy price), and Herding/Hot Tips (ignore tips; trust only the price chart).",
                confidence=1.0,
                source="crypto_trader_chapters_11_14",
                importance=MemoryImportance.CRITICAL,
                verification_status=VerificationStatus.VERIFIED,
                evidence=["The Crypto Trader Chapter 11 'Risk Parity Allocation' & Chapter 14 'Where's Your Head At?'"],
            ),
        ]
        self.long_term_knowledge.extend(seed_records)

    def write_memory(
        self,
        memory: MemoryRecord,
        agent_role: str = "technical_agent",
    ) -> MemoryRecord:
        """Stores a memory entry after strict security checks and access control validation."""
        MemoryAccessControl.validate_write_security(memory)

        # Route to appropriate memory layer
        if memory.level == MemoryLevel.PRIVATE:
            if memory.created_by not in self.private_memories:
                self.private_memories[memory.created_by] = []
            self.private_memories[memory.created_by].append(memory)
            logger.info(f"[Global Memory] Stored Level 1 Private Memory for '{memory.created_by}': {memory.content[:60]}...")
        elif memory.level == MemoryLevel.ORGANIZATIONAL:
            self.organizational_memories.append(memory)
            logger.info(f"[Global Memory] Stored Level 2 Organizational Memory [{memory.category.value}]: {memory.content[:60]}...")
        elif memory.level == MemoryLevel.LONG_TERM:
            self.long_term_knowledge.append(memory)
            logger.info(f"[Global Memory] Stored Level 3 Long-Term Knowledge [{memory.category.value}]: {memory.content[:60]}...")

        return memory

    def search_memories(
        self,
        query: str,
        agent_role: str = "chief_trading_agent",
        agent_id: str = "chief_001",
        symbol: str | None = None,
        strategy: str | None = None,
        min_confidence: float = 0.5,
        limit: int = 10,
    ) -> list[MemoryRecord]:
        """Queries memory across all authorized layers using keyword matching and relevance scoring."""
        now = datetime.now(UTC)
        query_words = set(re.findall(r'\w+', query.lower()))

        candidate_pool: list[MemoryRecord] = []

        # 1. Gather all authorized memories
        # Add Long-Term Knowledge
        candidate_pool.extend([m for m in self.long_term_knowledge if MemoryAccessControl.can_read_memory(agent_role, agent_id, m)])

        # Add Organizational Memory
        candidate_pool.extend([m for m in self.organizational_memories if MemoryAccessControl.can_read_memory(agent_role, agent_id, m)])

        # Add Agent's own Private Memory
        if agent_id in self.private_memories:
            candidate_pool.extend(self.private_memories[agent_id])

        # 2. Score and filter
        scored_results: list[tuple[float, MemoryRecord]] = []
        for mem in candidate_pool:
            if mem.confidence < min_confidence:
                continue

            # Calculate Memory Decay
            age_days = (now - mem.timestamp).total_seconds() / 86400.0
            decay = max(0.1, 1.0 - (age_days * 0.05)) if mem.level != MemoryLevel.LONG_TERM else 1.0
            mem.decay_score = round(decay, 2)

            score = 0.0
            content_words = set(re.findall(r'\w+', mem.content.lower()))
            overlap = query_words.intersection(content_words)
            score += len(overlap) * 2.0

            if symbol and mem.symbol and mem.symbol.upper() == symbol.upper():
                score += 5.0
            if strategy and mem.strategy and mem.strategy.lower() == strategy.lower():
                score += 3.0

            score *= (mem.confidence * decay)

            if score > 0 or not query_words:
                scored_results.append((score, mem))

        # Sort by score descending
        scored_results.sort(key=lambda x: x[0], reverse=True)
        return [r[1] for r in scored_results[:limit]]

    def query_pre_decision_memory(
        self,
        symbol: str,
        strategy: str,
        current_regime: str,
    ) -> dict:
        """Memory-Aware Pre-Decision Pipeline for Chief AI (Section 58).
        
        Retrieves similar historical situations, strategy performance, risk warnings,
        and lessons learned before granting trade clearance.
        """
        historical_cases = self.search_memories(
            query=f"{symbol} {strategy} {current_regime}",
            symbol=symbol,
            strategy=strategy,
            limit=5,
        )

        risk_warnings = [
            m.content for m in historical_cases
            if m.importance in [MemoryImportance.HIGH, MemoryImportance.CRITICAL] or m.category == QualityCategory.LESSON
        ]

        return {
            "symbol": symbol,
            "strategy": strategy,
            "regime": current_regime,
            "relevant_memories_found": len(historical_cases),
            "historical_lessons": [m.content for m in historical_cases if m.category == QualityCategory.LESSON],
            "risk_warnings": risk_warnings,
            "confidence_consensus": round(sum(m.confidence for m in historical_cases) / max(1, len(historical_cases)), 2),
        }

    def record_agent_conflict(
        self,
        symbol: str,
        conflicting_opinions: list[dict],
        final_resolution: str,
        risk_assessment: str,
    ) -> dict:
        """Preserves dissenting agent views and conflict evidence without overwriting (Section 56)."""
        conflict_record = {
            "conflict_id": f"conf_{len(self.conflicts)+1:04d}",
            "timestamp": str(datetime.now(UTC)),
            "symbol": symbol,
            "opinions": conflicting_opinions,
            "final_resolution": final_resolution,
            "risk_assessment": risk_assessment,
        }
        self.conflicts.append(conflict_record)
        logger.warning(f"[Memory Conflict] Recorded disagreement on {symbol}: Resolution '{final_resolution}'")
        return conflict_record

    def preserve_retired_agent_knowledge(self, agent_id: str, agent_name: str) -> int:
        """Migrates valuable private memories to organizational memory upon agent retirement (Section 59)."""
        if agent_id not in self.private_memories:
            return 0

        migrated_count = 0
        for mem in self.private_memories[agent_id]:
            if mem.importance in [MemoryImportance.HIGH, MemoryImportance.CRITICAL] or mem.category in [QualityCategory.FACT, QualityCategory.LESSON]:
                mem.level = MemoryLevel.ORGANIZATIONAL
                mem.content = f"[{agent_name} Legacy Wisdom]: {mem.content}"
                self.organizational_memories.append(mem)
                migrated_count += 1

        del self.private_memories[agent_id]
        logger.info(f"[Memory Migration] Successfully migrated {migrated_count} legacy memories for retired agent '{agent_name}'.")
        return migrated_count

    def update_memory_version(self, memory_id: str, new_content: str, updated_by: str) -> MemoryRecord | None:
        """Updates a memory entry with an incremented version and audit log (Section 60)."""
        target = None
        for m in self.long_term_knowledge + self.organizational_memories:
            if m.memory_id == memory_id:
                target = m
                break

        if target:
            old_version = target.version
            ver_num = float(target.version.replace("v", ""))
            target.version = f"v{ver_num + 0.1:.1f}"
            target.version_history.append({
                "previous_version": old_version,
                "previous_content": target.content,
                "updated_by": updated_by,
                "timestamp": str(datetime.now(UTC)),
            })
            target.content = new_content
            logger.info(f"[Memory Versioning] Upgraded memory {memory_id} from {old_version} to {target.version}")
        return target


# Global AI Memory Singleton
global_ai_memory = GlobalAIMemory()
