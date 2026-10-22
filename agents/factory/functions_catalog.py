from typing import TypedDict


class FunctionDefinition(TypedDict):
    id: str
    name: str
    category: str
    description: str
    required_permission: str
    is_elevated: bool


FUNCTIONS_CATALOG: list[FunctionDefinition] = [
    # 1. Market Functions
    {
        "id": "get_live_price",
        "name": "Get Live Price",
        "category": "Market Functions",
        "description": "Fetches current LTP for Indian equity symbol on NSE",
        "required_permission": "read_market_data",
        "is_elevated": False,
    },
    {
        "id": "get_ohlc_data",
        "name": "Get OHLCV Candles",
        "category": "Market Functions",
        "description": "Fetches multi-timeframe candle data for technical evaluation",
        "required_permission": "read_historical_data",
        "is_elevated": False,
    },
    {
        "id": "scan_stocks",
        "name": "Scan Equity Universe",
        "category": "Market Functions",
        "description": "Parallel scanner across Nifty 50, Nifty 100 or custom lists",
        "required_permission": "read_market_data",
        "is_elevated": False,
    },
    {
        "id": "compare_stocks",
        "name": "Compare Multi-Stock Setups",
        "category": "Market Functions",
        "description": "Compares relative momentum, volume, and ATR across N stocks",
        "required_permission": "read_market_data",
        "is_elevated": False,
    },

    # 2. Analysis Functions
    {
        "id": "technical_analysis",
        "name": "Technical Indicator Suite",
        "category": "Analysis Functions",
        "description": "Calculates RSI, MACD, EMA 20/50, ATR, VWAP and chart structure",
        "required_permission": "run_technical_analysis",
        "is_elevated": False,
    },
    {
        "id": "fundamental_analysis",
        "name": "Fundamental Valuation",
        "category": "Analysis Functions",
        "description": "Evaluates P/E, EPS, revenue growth, debt-to-equity and balance sheet",
        "required_permission": "run_fundamental_analysis",
        "is_elevated": False,
    },
    {
        "id": "news_analysis",
        "name": "Corporate News & Filings",
        "category": "Analysis Functions",
        "description": "Monitors quarterly earnings, corporate disclosures & regulatory filings",
        "required_permission": "search_news",
        "is_elevated": False,
    },
    {
        "id": "market_regime_detection",
        "name": "Market Regime Detector",
        "category": "Analysis Functions",
        "description": "Detects Bullish Trend, Bearish Trend, Sideways, High Volatility regimes",
        "required_permission": "run_technical_analysis",
        "is_elevated": False,
    },

    # 3. Research Functions
    {
        "id": "backtest_strategy",
        "name": "Historical Backtest Engine",
        "category": "Research Functions",
        "description": "Validates strategies over walk-forward historical OHLCV data",
        "required_permission": "run_backtest",
        "is_elevated": False,
    },
    {
        "id": "generate_reports",
        "name": "Research Brief Generator",
        "category": "Research Functions",
        "description": "Generates structured trade theses and invalidation criteria",
        "required_permission": "generate_signals",
        "is_elevated": False,
    },

    # 4. Portfolio & Risk Functions
    {
        "id": "read_portfolio",
        "name": "Read Open Positions",
        "category": "Portfolio Functions",
        "description": "Reads active holdings, entry prices, stop-losses, and margins",
        "required_permission": "read_market_data",
        "is_elevated": False,
    },
    {
        "id": "calculate_position_size",
        "name": "ATR Position Sizing",
        "category": "Portfolio Functions",
        "description": "Calculates capital-capped and volatility-adjusted share quantities",
        "required_permission": "read_market_data",
        "is_elevated": False,
    },

    # 5. Communication Functions
    {
        "id": "send_dashboard_alert",
        "name": "Dashboard Alert",
        "category": "Communication Functions",
        "description": "Publishes high-conviction signals to the UI and Agent Message Bus",
        "required_permission": "generate_signals",
        "is_elevated": False,
    },

    # 6. Trading Functions (Elevated Privileges)
    {
        "id": "paper_trade_order",
        "name": "Paper Trade Submission",
        "category": "Trading Functions",
        "description": "Submits simulated orders to PaperBroker with zero real risk",
        "required_permission": "paper_trade",
        "is_elevated": False,
    },
    {
        "id": "place_live_orders",
        "name": "Live Broker Execution",
        "category": "Trading Functions",
        "description": "Routes orders to live Zerodha / Fyers account (Strictly Gated)",
        "required_permission": "place_live_orders",
        "is_elevated": True,
    },
]


def get_available_functions() -> list[FunctionDefinition]:
    return FUNCTIONS_CATALOG
