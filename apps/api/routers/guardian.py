"""
AI Trade Guardian - API Router
Exposes dedicated endpoints for Guardian telemetry, broker state reconciliation,
emergency exits, and post-trade execution quality reports.
"""

from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException

from core.auth.security import get_current_user
from core.config.settings import TradingMode, settings
from core.schemas.trade import OrderIntent, TradeAction
from execution.brokers.angelone import AngelOneBroker
from execution.broker_factory import get_active_broker
from execution.router import OrderRouter
from guardian.post_trade_analytics import PostTradeAnalyticsEngine
from guardian.trade_guardian import trade_guardian
from market.providers.yfinance_provider import YFinanceMarketDataProvider

router = APIRouter(prefix="/api/guardian", tags=["Trade Guardian"], dependencies=[Depends(get_current_user)])


async def _get_broker():
    broker = get_active_broker()
    if hasattr(broker, "_is_authenticated") and not broker._is_authenticated:
        await broker.authenticate_session()
    return broker


def _get_router(broker=None):
    b = broker or get_active_broker()
    return OrderRouter(b)



@router.get("/status")
async def get_guardian_status():
    """Returns real-time operational status, positions at risk, and broker sync telemetry."""
    broker = await _get_broker()
    await trade_guardian.reconcile_with_broker(broker)
    return trade_guardian.get_guardian_dashboard_summary()


@router.post("/reconcile")
async def trigger_reconciliation():
    """Forces an immediate synchronization audit between AI internal state and Broker SmartAPI."""
    broker = await _get_broker()
    report = await trade_guardian.reconcile_with_broker(broker)
    return {
        "status": "SUCCESS",
        "report": report.model_dump(),
    }


@router.post("/emergency-exit/{symbol}")
async def emergency_exit_position(symbol: str):
    """Emergency closes a position via Trade Guardian protective exit authority."""
    clean_sym = symbol.upper()
    if clean_sym not in trade_guardian.guardians:
        raise HTTPException(status_code=404, detail=f"No active guardian found for symbol {clean_sym}")

    worker = trade_guardian.guardians[clean_sym]
    if not worker.state.is_active:
        return {"status": "ALREADY_CLOSED", "symbol": clean_sym}

    provider = YFinanceMarketDataProvider()
    ltp = await provider.get_ltp(clean_sym)

    is_short = str(worker.state.side).upper() in ["SELL", "SHORT"]
    exit_action = TradeAction.BUY if is_short else TradeAction.SELL

    exit_order = OrderIntent(
        client_order_id=f"GRD-EMG-{clean_sym}-{int(datetime.now(UTC).timestamp())}",
        symbol=clean_sym,
        exchange=worker.state.exchange,
        action=exit_action,
        quantity=worker.state.quantity,
        price=ltp,
        stop_loss=0.0,
        target=0.0,
        decision_id="GUARDIAN-MANUAL-EMERGENCY",
        reduce_only=True,
    )
    router_gateway = _get_router()
    res = await router_gateway.route_order(exit_order)



    post_report = PostTradeAnalyticsEngine.analyze_completed_guardian_position(
        state=worker.state,
        exit_price=ltp,
        exit_reason="MANUAL_GUARDIAN_EMERGENCY",
        brokerage_fee=None,
        interventions_count=worker.interventions_count + 1,
    )
    trade_guardian.completed_reports.append(post_report)
    worker.state.is_active = False

    return {
        "status": "EMERGENCY_EXIT_EXECUTED",
        "symbol": clean_sym,
        "fill_price": ltp,
        "pnl": post_report.realized_pnl,
        "broker_order_id": res.order_id,
    }


@router.get("/reports")
async def get_post_trade_reports():
    """Returns post-trade excursion analytics (MFE, MAE, slippage, planned vs actual RR)."""
    return {
        "completed_count": len(trade_guardian.completed_reports),
        "reports": [r.model_dump() for r in trade_guardian.completed_reports],
    }
