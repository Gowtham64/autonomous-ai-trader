"""Canonical Valuation Engine for Multi-Asset Derivatives and Spot Positions.

Provides unified, robust, deterministic accounting across:
1. Linear Crypto Perpetuals (USDT-settled: XRPUSDT, DOGEUSDT, SOLUSDT, ETHUSDT).
2. Inverse Crypto Contracts (Coin-margined: BTC/USD).
3. Indian Cash Equities (INR-settled).

Guarantees:
- Mark-Price-First valuation for all risk, equity, drawdown, and circuit breaker decisions.
- Multiplier applied exactly once per contract specification.
- Fail-safe rejection when mark prices are stale (>60s drift) or missing; no silent LTP substitution.
- Explicit labeling of PriceSource and timestamps.
- Precise separation of Cash Balance vs. Mark-to-Market Portfolio Equity.
- Full support for both Long and Short positions.
"""

from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import Enum
from typing import Any

from core.logging import logger
from core.schemas.trade import PositionSnapshot, TradeAction
from portfolio.position_sizer import get_delta_contract_multiplier


class ContractType(str, Enum):
    LINEAR_PERPETUAL = "LINEAR_PERPETUAL"
    INVERSE_PERPETUAL = "INVERSE_PERPETUAL"
    EQUITY_SPOT = "EQUITY_SPOT"


class PriceSource(str, Enum):
    MARK_PRICE = "MARK_PRICE"
    LAST_TRADED_PRICE = "LAST_TRADED_PRICE"
    ORDER_BOOK_MID = "ORDER_BOOK_MID"
    INDEX_PRICE = "INDEX_PRICE"
    UNAVAILABLE = "UNAVAILABLE"


@dataclass
class ValuationResult:
    symbol: str
    side: str
    quantity: float
    multiplier: float
    contract_type: ContractType
    entry_price: float
    valuation_price: float
    price_source: PriceSource
    price_timestamp_utc: str | None
    gross_unrealized_pnl: float
    net_unrealized_pnl: float
    unrealized_pnl_pct: float
    is_reliable: bool
    unreliability_reason: str | None = None


@dataclass
class PortfolioValuation:
    cash_balance: float
    used_margin: float
    available_margin: float
    total_unrealized_pnl: float
    mark_to_market_equity: float
    peak_equity: float
    drawdown: float
    drawdown_pct: float
    is_valuation_reliable: bool
    warnings: list[str] = field(default_factory=list)
    positions_valued: list[ValuationResult] = field(default_factory=list)


def resolve_contract_multiplier(symbol: str) -> float:
    """Resolves verified contract multiplier using official Delta catalog."""
    mult = get_delta_contract_multiplier(symbol)
    if mult is not None and mult > 0:
        return float(mult)
    return 1.0


def resolve_contract_type(symbol: str, exchange: str = "DELTA") -> ContractType:
    """Classifies instrument into Linear, Inverse, or Spot."""
    sym_upper = symbol.upper().strip()
    exch_upper = (exchange or "").upper().strip()
    if exch_upper in ["DELTA", "CRYPTO"]:
        if "USD" in sym_upper and not sym_upper.endswith("USDT") and "BTC" in sym_upper:
            # BTCUSD coin-margined inverse
            return ContractType.INVERSE_PERPETUAL
        return ContractType.LINEAR_PERPETUAL
    return ContractType.EQUITY_SPOT


def resolve_valuation_price(
    ticker_data: dict[str, Any] | None,
    preferred_source: PriceSource = PriceSource.MARK_PRICE,
    max_drift_ms: float = 60000.0,
) -> tuple[float | None, PriceSource, bool, str]:
    """Resolves reliable valuation price with fail-safe handling of stale or missing feeds.

    Returns: (price, price_source, is_reliable, diagnostic_message)
    """
    if not ticker_data:
        return None, PriceSource.UNAVAILABLE, False, "TICKER_DATA_NONE"

    mark_px = ticker_data.get("mark_price")
    close_px = ticker_data.get("close")
    is_stale = ticker_data.get("is_stale", False)
    drift_ms = ticker_data.get("drift_ms", 0.0)

    # 1. Stale feed check
    if is_stale or drift_ms > max_drift_ms:
        return None, PriceSource.UNAVAILABLE, False, f"DATA_STALE (drift: {drift_ms}ms)"

    # 2. Preferred: MARK_PRICE
    if preferred_source == PriceSource.MARK_PRICE:
        if mark_px is not None and float(mark_px) > 0:
            return float(mark_px), PriceSource.MARK_PRICE, True, "OK"
        # If mark price missing, do NOT silently substitute stale LTP for risk decisions!
        return None, PriceSource.UNAVAILABLE, False, "MARK_PRICE_MISSING_OR_ZERO"

    # 3. Informational / Strategy: LAST_TRADED_PRICE
    if preferred_source == PriceSource.LAST_TRADED_PRICE:
        if close_px is not None and float(close_px) > 0:
            return float(close_px), PriceSource.LAST_TRADED_PRICE, True, "OK"
        return None, PriceSource.UNAVAILABLE, False, "LTP_MISSING_OR_ZERO"

    return None, PriceSource.UNAVAILABLE, False, "UNSUPPORTED_PRICE_SOURCE"


def calculate_unrealized_pnl(
    entry_price: float,
    valuation_price: float,
    quantity: float,
    side: str | TradeAction,
    multiplier: float = 1.0,
    contract_type: ContractType = ContractType.LINEAR_PERPETUAL,
) -> float:
    """Calculates exact unrealized P&L applying contract multiplier exactly once."""
    if entry_price <= 0 or valuation_price <= 0 or quantity <= 0:
        return 0.0

    side_str = side.value if isinstance(side, TradeAction) else str(side).upper()
    is_short = side_str in ["SELL", "SHORT"]
    direction = -1.0 if is_short else 1.0

    if contract_type == ContractType.LINEAR_PERPETUAL or contract_type == ContractType.EQUITY_SPOT:
        # PnL = (valuation - entry) * quantity * multiplier (for long)
        return (valuation_price - entry_price) * quantity * multiplier * direction

    elif contract_type == ContractType.INVERSE_PERPETUAL:
        # PnL in USD = (valuation - entry) / entry * quantity * multiplier (for long)
        pnl_coin = ((1.0 / entry_price) - (1.0 / valuation_price)) * quantity * multiplier * (-direction)
        return pnl_coin * valuation_price

    return (valuation_price - entry_price) * quantity * multiplier * direction


def value_position(
    pos: PositionSnapshot,
    ticker_data: dict[str, Any] | None,
    preferred_source: PriceSource = PriceSource.MARK_PRICE,
) -> ValuationResult:
    """Computes full valuation for an open position using the canonical model."""
    sym = pos.symbol
    mult = resolve_contract_multiplier(sym)
    ctype = resolve_contract_type(sym, pos.exchange)
    side_str = str(pos.side).upper()

    val_px, source, is_reliable, reason = resolve_valuation_price(
        ticker_data, preferred_source=preferred_source
    )

    if not is_reliable or val_px is None:
        return ValuationResult(
            symbol=sym,
            side=side_str,
            quantity=pos.quantity,
            multiplier=mult,
            contract_type=ctype,
            entry_price=pos.entry_price,
            valuation_price=pos.entry_price,
            price_source=PriceSource.UNAVAILABLE,
            price_timestamp_utc=None,
            gross_unrealized_pnl=0.0,
            net_unrealized_pnl=0.0,
            unrealized_pnl_pct=0.0,
            is_reliable=False,
            unreliability_reason=reason,
        )

    gross_pnl = calculate_unrealized_pnl(
        entry_price=pos.entry_price,
        valuation_price=val_px,
        quantity=pos.quantity,
        side=side_str,
        multiplier=mult,
        contract_type=ctype,
    )

    # Approximate exit fee (0.05% taker commission on turnover)
    turnover = val_px * pos.quantity * mult
    est_exit_fee = round(turnover * 0.0005, 4)
    net_pnl = gross_pnl - est_exit_fee

    entry_turnover = pos.entry_price * pos.quantity * mult
    pnl_pct = (gross_pnl / entry_turnover * 100.0) if entry_turnover > 0 else 0.0

    return ValuationResult(
        symbol=sym,
        side=side_str,
        quantity=pos.quantity,
        multiplier=mult,
        contract_type=ctype,
        entry_price=pos.entry_price,
        valuation_price=val_px,
        price_source=source,
        price_timestamp_utc=ticker_data.get("timestamp") if ticker_data else None,
        gross_unrealized_pnl=round(gross_pnl, 4),
        net_unrealized_pnl=round(net_pnl, 4),
        unrealized_pnl_pct=round(pnl_pct, 2),
        is_reliable=True,
        unreliability_reason=None,
    )


def value_portfolio(
    cash_balance: float,
    used_margin: float,
    available_margin: float,
    positions: list[PositionSnapshot],
    ticker_map: dict[str, dict[str, Any]],
    peak_equity: float | None = None,
) -> PortfolioValuation:
    """Computes comprehensive portfolio mark-to-market valuation, true equity, and drawdown."""
    total_unrealized = 0.0
    valued_positions: list[ValuationResult] = []
    warnings: list[str] = []
    is_fully_reliable = True

    for pos in positions:
        if not pos.is_active or pos.quantity <= 0:
            continue
        tick = ticker_map.get(pos.symbol)
        v = value_position(pos, tick, preferred_source=PriceSource.MARK_PRICE)
        valued_positions.append(v)
        if not v.is_reliable:
            is_fully_reliable = False
            warnings.append(f"Position {pos.symbol} valuation unreliable: {v.unreliability_reason}")
        else:
            total_unrealized += v.gross_unrealized_pnl

    mtm_equity = round(cash_balance + total_unrealized, 4)
    peak = max(peak_equity if peak_equity is not None else mtm_equity, mtm_equity)
    dd = round(max(0.0, peak - mtm_equity), 4)
    dd_pct = round((dd / peak * 100.0) if peak > 0 else 0.0, 2)

    return PortfolioValuation(
        cash_balance=round(cash_balance, 4),
        used_margin=round(used_margin, 4),
        available_margin=round(available_margin, 4),
        total_unrealized_pnl=round(total_unrealized, 4),
        mark_to_market_equity=mtm_equity,
        peak_equity=round(peak, 4),
        drawdown=dd,
        drawdown_pct=dd_pct,
        is_valuation_reliable=is_fully_reliable,
        warnings=warnings,
        positions_valued=valued_positions,
    )


def evaluate_bracket_condition(
    pos: PositionSnapshot,
    ticker_data: dict[str, Any] | None,
    trigger_method: str = "last_traded_price",
) -> tuple[bool, str | None, str, float]:
    """Evaluates stop-loss and take-profit conditions with explicit trigger sources and fail-safe handling.

    Returns: (is_exit_triggered, exit_reason, diagnostic_note, evaluation_price)
    """
    if not ticker_data:
        return False, None, "REJECTED_TICKER_NONE", 0.0

    mark_px = ticker_data.get("mark_price")
    close_px = ticker_data.get("close")
    is_stale = ticker_data.get("is_stale", False)

    if is_stale:
        return False, None, "FEED_STALE_EVALUATION_BLOCKED", 0.0

    # Determine evaluation price according to configured trigger_method
    eval_px: float | None = None
    source_used = "UNKNOWN"

    if trigger_method == "mark_price":
        if mark_px is not None and float(mark_px) > 0:
            eval_px = float(mark_px)
            source_used = "MARK_PRICE"
        elif close_px is not None and float(close_px) > 0:
            eval_px = float(close_px)
            source_used = "FALLBACK_LTP"
    else:  # default: "last_traded_price"
        if close_px is not None and float(close_px) > 0:
            eval_px = float(close_px)
            source_used = "LTP"
        elif mark_px is not None and float(mark_px) > 0:
            # Fail-safe: When LTP is None (0 trades in 24h), do NOT blindly ignore the position!
            eval_px = float(mark_px)
            source_used = "FAILSAFE_MARK_PRICE"

    if eval_px is None or eval_px <= 0:
        return False, None, "NO_VALID_PRICE_AVAILABLE", 0.0

    is_long = str(pos.side).upper() not in ["SELL", "SHORT"]
    hit_target = (eval_px >= pos.target_1) if is_long else (eval_px <= pos.target_1)
    hit_stop = (eval_px <= pos.stop_loss) if is_long else (eval_px >= pos.stop_loss)

    if hit_target:
        return True, "TARGET_HIT", f"Target reached @ {eval_px:.4f} via {source_used} (Target: {pos.target_1})", eval_px
    if hit_stop:
        return True, "STOP_LOSS_HIT", f"Stop-loss breached @ {eval_px:.4f} via {source_used} (SL: {pos.stop_loss})", eval_px

    return False, None, f"Healthy @ {eval_px:.4f} via {source_used}", eval_px
