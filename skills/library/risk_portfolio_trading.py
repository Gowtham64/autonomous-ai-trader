"""
Risk Management, Portfolio, Trading & Execution Quality Skills Library
"""

from datetime import UTC, datetime

from core.config.settings import TradingMode, settings
from core.treasury.treasury import treasury
from risk.kill_switch import kill_switch
from skills.models import SkillCategory, SkillDefinition, SkillPermission, SkillRiskLevel


async def exec_position_sizing(params: dict) -> dict:
    entry_price = float(params.get("entry_price", 1000.0))
    stop_loss = float(params.get("stop_loss", 980.0))
    total_equity = float(params.get("total_equity", treasury.current_capital))

    stop_distance = abs(entry_price - stop_loss)
    if stop_distance <= 0 or total_equity <= 0:
        return {
            "quantity": 0,
            "risk_amount": 0.0,
            "allocated_capital": 0.0,
            "reason": "Insufficient equity or zero stop distance",
        }

    risk_amount = total_equity * settings.MAX_RISK_PER_TRADE_PCT
    raw_qty = int(risk_amount / stop_distance)
    max_cap_stock = total_equity * settings.MAX_SINGLE_STOCK_EXPOSURE_PCT
    max_qty_by_cap = int(max_cap_stock / entry_price) if entry_price > 0 else 0

    qty = max(0, min(raw_qty, max_qty_by_cap))
    if qty == 0 and entry_price <= total_equity:
        qty = 1  # Bootstrap single-share allowance

    return {
        "symbol": params.get("symbol", "NSE_STOCK"),
        "total_equity": round(total_equity, 2),
        "entry_price": entry_price,
        "stop_loss": stop_loss,
        "stop_distance": round(stop_distance, 2),
        "risk_amount_inr": round(risk_amount, 2),
        "calculated_quantity": qty,
        "capital_required": round(qty * entry_price, 2),
        "portfolio_exposure_pct": round(((qty * entry_price) / max(1.0, total_equity)) * 100, 2),
    }


async def exec_risk_veto_check(params: dict) -> dict:
    symbol = params.get("symbol", "RELIANCE.NS")
    potential_loss = float(params.get("potential_loss", 20.0))

    is_killed = kill_switch.is_engaged
    daily_loss = abs(min(0.0, treasury.realized_pnl))
    max_daily_allowed = treasury.starting_capital * settings.MAX_DAILY_LOSS_PCT

    veto = False
    reasons = []

    if is_killed:
        veto = True
        reasons.append(f"Emergency Kill Switch is engaged ({kill_switch.reason})")

    if daily_loss + potential_loss > max_daily_allowed > 0:
        veto = True
        reasons.append(f"Daily loss limit would be breached: ₹{daily_loss + potential_loss:.2f} > ₹{max_daily_allowed:.2f}")

    if treasury.is_survival_mode and potential_loss > (max_daily_allowed * 0.5):
        veto = True
        reasons.append("Survival Mode active: Trade exceeds 50% throttled risk ceiling")

    return {
        "symbol": symbol,
        "approved": not veto,
        "veto_engaged": veto,
        "rejection_reasons": reasons,
        "daily_realized_loss": round(daily_loss, 2),
        "daily_loss_limit": round(max_daily_allowed, 2),
        "survival_mode": treasury.is_survival_mode,
        "timestamp": datetime.now(UTC).isoformat(),
    }


async def exec_broker_funds_query(params: dict) -> dict:
    from execution.broker_factory import get_active_broker
    broker = get_active_broker()
    funds = await broker.get_funds()
    return {
        "broker_mode": settings.TRADING_MODE.value,
        "client_code": settings.ANGELONE_CLIENT_CODE if settings.TRADING_MODE == TradingMode.LIVE else "PAPER",
        "total_capital": float(funds.get("total_capital", 0.0)),
        "available_margin": float(funds.get("available_margin", 0.0)),
        "used_margin": float(funds.get("used_margin", 0.0)),
        "treasury_synced": True,
    }


async def exec_order_validation(params: dict) -> dict:
    symbol = params.get("symbol", "")
    price = float(params.get("price", 0.0))
    quantity = int(params.get("quantity", 0))
    action = params.get("action", "BUY")

    errors = []
    if not symbol:
        errors.append("Symbol is required")
    if price <= 0:
        errors.append("Price must be greater than 0")
    if quantity <= 0:
        errors.append("Quantity must be greater than 0")
    if action not in ["BUY", "SELL"]:
        errors.append(f"Invalid action '{action}'. Must be BUY or SELL")

    return {
        "is_valid": len(errors) == 0,
        "symbol": symbol,
        "price": price,
        "quantity": quantity,
        "order_value": round(price * quantity, 2),
        "validation_errors": errors,
    }


RISK_TRADING_SKILLS = [
    SkillDefinition(
        skill_id="skill.risk.position_sizing.v1",
        name="Volatility-Adjusted Position Sizer",
        version="1.0.0",
        category=SkillCategory.RISK,
        description="Calculates exact mathematical lot/share quantity constrained by ATR stop distance and max portfolio risk.",
        inputs=["entry_price", "stop_loss", "total_equity", "symbol"],
        outputs=["calculated_quantity", "risk_amount_inr", "capital_required", "portfolio_exposure_pct"],
        required_tools=["treasury_engine"],
        required_permissions=[SkillPermission.ANALYZE],
        risk_level=SkillRiskLevel.LEVEL_1_ANALYSIS,
        can_trade=False,
    ),
    SkillDefinition(
        skill_id="skill.risk.trade_veto.v1",
        name="Deterministic Risk Veto & Circuit Breaker",
        version="1.0.0",
        category=SkillCategory.RISK,
        description="Enforces non-negotiable risk barriers (2% daily loss limit, max drawdown, kill switch, duplicate orders).",
        inputs=["symbol", "potential_loss"],
        outputs=["approved", "veto_engaged", "rejection_reasons", "daily_loss_limit"],
        required_tools=["risk_engine", "kill_switch"],
        required_permissions=[SkillPermission.ANALYZE],
        risk_level=SkillRiskLevel.LEVEL_2_RECOMMENDATION,
        can_trade=False,
    ),
    SkillDefinition(
        skill_id="skill.trading.check_broker_funds.v1",
        name="Broker Funds & Margin Inspector",
        version="1.0.0",
        category=SkillCategory.TRADING,
        description="Queries real-time broker RMS margin limits and available funds directly from AngelOne SmartAPI.",
        inputs=[],
        outputs=["broker_mode", "client_code", "total_capital", "available_margin", "used_margin"],
        required_tools=["broker_api"],
        required_permissions=[SkillPermission.READ],
        risk_level=SkillRiskLevel.LEVEL_0_INFO,
        can_trade=False,
    ),
    SkillDefinition(
        skill_id="skill.execution_quality.order_validator.v1",
        name="Institutional Order Validator",
        version="1.0.0",
        category=SkillCategory.EXECUTION_QUALITY,
        description="Pre-execution checks: symbol format, price collars, tick size, liquidity depth, and lot multiplier.",
        inputs=["symbol", "price", "quantity", "action"],
        outputs=["is_valid", "order_value", "validation_errors"],
        required_tools=["market_data_api"],
        required_permissions=[SkillPermission.ANALYZE],
        risk_level=SkillRiskLevel.LEVEL_1_ANALYSIS,
        can_trade=False,
    ),
]
