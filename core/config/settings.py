from pathlib import Path
import secrets
from enum import Enum

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class TradingMode(str, Enum):
    DRY_RUN = "DRY_RUN"
    PAPER = "PAPER"
    LIVE = "LIVE"


class LLMProviderType(str, Enum):
    GEMINI = "gemini"
    OPENAI = "openai"
    ANTHROPIC = "anthropic"
    OPENROUTER = "openrouter"
    GROQ = "groq"
    OLLAMA = "ollama"
    MOCK = "mock"


_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
_ENV_FILE = _PROJECT_ROOT / ".env"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=(_ENV_FILE, ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    # Operational Mode
    TRADING_MODE: TradingMode = TradingMode.PAPER
    LIVE_TRADING_ENABLED: bool = False

    # LLM Settings
    LLM_PROVIDER: LLMProviderType = LLMProviderType.GEMINI
    GEMINI_API_KEY: str | None = None
    OPENAI_API_KEY: str | None = None
    ANTHROPIC_API_KEY: str | None = None
    OPENROUTER_API_KEY: str | None = None
    GROQ_API_KEY: str | None = None
    OLLAMA_BASE_URL: str = "http://localhost:11434"

    MODEL_FAST: str = "gemini-flash-latest"
    MODEL_REASONING: str = "gemini-flash-latest"

    # Capital & AI Treasury Settings (Bootstrap Model)
    INITIAL_CAPITAL: float = 2000.0               # ₹2,000 bootstrap capital
    MAX_CAPITAL: float = 2000.0                   # Current authorized trading capital
    SURVIVAL_MODE_THRESHOLD_PCT: float = 0.80     # Trigger Survival Mode if capital falls below 80% (₹1,600)
    DAILY_OPERATING_BUDGET: float = 5.0           # ₹5/day simulated infrastructure/API budget
    MAX_ACTIVE_DYNAMIC_AGENTS: int = 4            # Strict limit on dynamic agent spawns

    # Risk Engine Constraints (Strict Deterministic Capital Preservation Limits)
    MAX_RISK_PER_TRADE_PCT: float = 0.005         # 0.5% per trade risk (₹10 on ₹2,000)
    MAX_DAILY_LOSS_PCT: float = 0.01              # 1% max daily loss circuit breaker (₹20 on ₹2,000)
    MAX_PORTFOLIO_DRAWDOWN_PCT: float = 0.03      # 3% max drawdown circuit breaker (₹60 on ₹2,000)
    MAX_OPEN_POSITIONS: int = 3                   # Max concurrent positions on bootstrap capital
    MAX_SECTOR_EXPOSURE_PCT: float = 0.25         # 25% max in any sector
    MAX_SINGLE_STOCK_EXPOSURE_PCT: float = 0.15   # 15% max capital in single stock
    MAX_SLIPPAGE_PCT: float = 0.005               # 0.5% max allowable slippage
    MAX_SPREAD_PCT: float = 0.005                 # 0.5% max allowable bid-ask spread
    MIN_RISK_REWARD_RATIO: float = 2.0            # Strict 1:2.0 minimum R:R required for trades

    # Market / Exchange
    EXCHANGE: str = "NSE"
    TIMEZONE: str = "Asia/Kolkata"

    # Persistence
    DATABASE_URL: str = "sqlite+aiosqlite:///./data/trader.db"
    REDIS_URL: str = "redis://localhost:6379/0"

    # Broker Credentials
    BROKER_NAME: str = "angelone" # "angelone", "zerodha", "fyers", "paper"

    # AngelOne SmartAPI Credentials
    ANGELONE_API_KEY: str | None = None
    ANGELONE_CLIENT_CODE: str | None = None
    ANGELONE_PASSWORD: str | None = None
    ANGELONE_TOTP_KEY: str | None = None
    ANGELONE_AUTH_TOKEN: str | None = None
    ANGELONE_FEED_TOKEN: str | None = None

    # Zerodha Credentials
    ZERODHA_API_KEY: str | None = None
    ZERODHA_API_SECRET: str | None = None
    ZERODHA_ACCESS_TOKEN: str | None = None

    # Fyers Credentials
    FYERS_APP_ID: str | None = None
    FYERS_ACCESS_TOKEN: str | None = None

    # Delta Exchange (Crypto Perpetuals & Options) Credentials
    DELTA_API_KEY: str | None = None
    DELTA_API_SECRET: str | None = None
    DELTA_BASE_URL: str = "https://api.india.delta.exchange"  # or "https://api.delta.exchange"
    DELTA_MAX_LEVERAGE: float = 5.0                     # Max leverage gate for crypto perps (5x with strict 1.5% SL defense)
    DELTA_IS_TESTNET: bool = False

    # AI Foundation Model (Kronos PyTorch - keep False for 512MB RAM cloud tiers)
    ENABLE_KRONOS_MODEL: bool = False

    # Telegram Alerting
    TELEGRAM_BOT_TOKEN: str | None = None
    TELEGRAM_CHAT_ID: str | None = None

    # Web Dashboard & Remote Access Authentication (False by default for paper monitoring)
    AUTH_REQUIRED: bool = False
    ADMIN_USERNAME: str = "admin"
    ADMIN_PASSWORD: str = ""
    JWT_SECRET_KEY: str = Field(default_factory=lambda: secrets.token_urlsafe(32))
    JWT_ALGORITHM: str = "HS256"
    JWT_EXPIRY_HOURS: int = 72
    ALLOWED_ORIGINS: list[str] = [
        "http://localhost:8000",
        "http://127.0.0.1:8000",
        "http://localhost:3000",
        "http://127.0.0.1:3000",
    ]

    # Versioning
    STRATEGY_VERSION: str = "1.0.0"
    PROMPT_VERSION: str = "1.0.0"


settings = Settings()


