import zoneinfo
from datetime import datetime, time

IST_TIMEZONE = zoneinfo.ZoneInfo("Asia/Kolkata")

# Standard NSE / BSE Indian Market Timings per Segment
EQUITY_PRE_OPEN_START = time(9, 0)
EQUITY_PRE_OPEN_END = time(9, 8)
EQUITY_MARKET_OPEN = time(9, 15)
EQUITY_MARKET_CLOSE = time(15, 30)

DERIVATIVES_MARKET_OPEN = time(9, 15)
DERIVATIVES_MARKET_CLOSE = time(15, 40)

CURRENCY_MARKET_OPEN = time(9, 0)
CURRENCY_MARKET_CLOSE = time(17, 0)

COMMODITY_MARKET_OPEN = time(9, 0)
COMMODITY_MARKET_CLOSE = time(23, 30) # 23:55 during US Daylight Saving

POST_MARKET_END = time(16, 0)

# NSE Public Holidays for 2026 (Standard exchange calendar)
NSE_HOLIDAYS_2026 = {
    "2026-01-26",  # Republic Day
    "2026-03-03",  # Holi
    "2026-03-20",  # Id-Ul-Fitr
    "2026-04-03",  # Good Friday
    "2026-04-14",  # Dr. Baba Saheb Ambedkar Jayanti
    "2026-05-01",  # Maharashtra Day
    "2026-08-15",  # Independence Day
    "2026-10-02",  # Mahatma Gandhi Jayanti
    "2026-10-20",  # Dussehra
    "2026-11-09",  # Diwali Laxmi Pujan
    "2026-11-24",  # Gurunanak Jayanti
    "2026-12-25",  # Christmas
}


class IndianMarketCalendar:
    """NSE/BSE Trading Session and Market Hour Validator across all Indian segments."""

    @staticmethod
    def get_holidays() -> set[str]:
        return NSE_HOLIDAYS_2026

    @staticmethod
    def now_ist() -> datetime:
        return datetime.now(IST_TIMEZONE)

    @staticmethod
    def is_trading_day(dt: datetime | None = None) -> bool:
        if dt is None:
            dt = IndianMarketCalendar.now_ist()
        else:
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=IST_TIMEZONE)
            else:
                dt = dt.astimezone(IST_TIMEZONE)

        # Saturday = 5, Sunday = 6
        if dt.weekday() >= 5:
            return False

        date_str = dt.strftime("%Y-%m-%d")
        return date_str not in NSE_HOLIDAYS_2026

    @staticmethod
    def is_market_open(
        dt: datetime | None = None,
        segment: str = "NSE_CASH_EQUITY",
    ) -> bool:
        """Validates if the specific Indian market segment is actively trading."""
        if dt is None:
            dt = IndianMarketCalendar.now_ist()
        else:
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=IST_TIMEZONE)
            else:
                dt = dt.astimezone(IST_TIMEZONE)

        if not IndianMarketCalendar.is_trading_day(dt):
            return False

        current_time = dt.time()

        if "DERIVATIVES" in segment or "FUTURES" in segment or "OPTIONS" in segment:
            if "CURRENCY" in segment:
                return CURRENCY_MARKET_OPEN <= current_time <= CURRENCY_MARKET_CLOSE
            if "COMMODITY" in segment:
                return COMMODITY_MARKET_OPEN <= current_time <= COMMODITY_MARKET_CLOSE
            # Standard Equity Derivatives close at 15:40 IST
            return DERIVATIVES_MARKET_OPEN <= current_time <= DERIVATIVES_MARKET_CLOSE

        # Standard Cash Equity (09:15 - 15:30 IST)
        return EQUITY_MARKET_OPEN <= current_time <= EQUITY_MARKET_CLOSE

    @staticmethod
    def is_pre_market(dt: datetime | None = None) -> bool:
        if dt is None:
            dt = IndianMarketCalendar.now_ist()
        else:
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=IST_TIMEZONE)
            else:
                dt = dt.astimezone(IST_TIMEZONE)

        if not IndianMarketCalendar.is_trading_day(dt):
            return False

        current_time = dt.time()
        return EQUITY_PRE_OPEN_START <= current_time < EQUITY_MARKET_OPEN
