import json
from datetime import UTC, datetime, timedelta

from sqlalchemy import select

from core.schemas.trade import OrderExecution, PositionSnapshot, TradeDecision
from database.models.tables import (
    OrderEntity,
    PositionEntity,
    TradeDecisionEntity,
    TradeJournalEntity,
)
from database.session import AsyncSessionLocal


class TradeRepository:
    """Persistence repository for decisions, orders, positions, and journal reflections."""

    @staticmethod
    async def save_decision(decision: TradeDecision):
        async with AsyncSessionLocal() as session, session.begin():
            entity = TradeDecisionEntity(
                analysis_id=decision.analysis_id,
                symbol=decision.symbol,
                exchange=decision.exchange,
                decision=decision.decision.value,
                confidence=decision.confidence,
                entry_price=decision.entry_price,
                stop_loss=decision.stop_loss,
                target_1=decision.target_1,
                expected_risk_reward=decision.expected_risk_reward,
                thesis_json=json.dumps(decision.thesis),
                supporting_evidence_json=json.dumps(decision.supporting_evidence),
                opposing_evidence_json=json.dumps(decision.opposing_evidence),
                invalidation_conditions_json=json.dumps(decision.invalidation_conditions),
                strategy_version=decision.strategy_version,
                prompt_version=decision.prompt_version,
                model_version=decision.model_version,
            )
            session.add(entity)

    @staticmethod
    async def save_order(exec_report: OrderExecution, action: str, decision_id: str | None = None):
        async with AsyncSessionLocal() as session, session.begin():
            entity = OrderEntity(
                order_id=exec_report.order_id,
                client_order_id=exec_report.client_order_id,
                symbol=exec_report.symbol,
                action=action,
                status=exec_report.status.value,
                quantity=exec_report.filled_quantity,
                average_price=exec_report.average_price,
                slippage=exec_report.slippage,
                brokerage_fee=exec_report.brokerage_fee,
                taxes_and_charges=exec_report.taxes_and_charges,
                decision_id=decision_id,
            )
            session.add(entity)

    @staticmethod
    async def save_journal(
        symbol: str,
        entry_price: float,
        exit_price: float,
        pnl: float,
        exit_reason: str,
        holding_period_seconds: float = 0.0,
        market_regime: str = "UNKNOWN",
        reflection_notes: str = "",
    ):
        """Persists a completed trade to the trade_journal table (win-rate / learning history)."""
        async with AsyncSessionLocal() as session, session.begin():
            session.add(TradeJournalEntity(
                symbol=symbol,
                entry_price=entry_price,
                exit_price=exit_price,
                pnl=pnl,
                exit_reason=exit_reason,
                holding_period_seconds=holding_period_seconds,
                market_regime=market_regime,
                reflection_notes=reflection_notes,
            ))

    @staticmethod
    async def get_recent_journal_for_symbol(symbol: str, hours: int = 24, limit: int = 10) -> list:
        """Returns the symbol's most recent completed trades (newest first) within a window."""
        async with AsyncSessionLocal() as session:
            cutoff = datetime.now(UTC) - timedelta(hours=hours)
            stmt = (
                select(TradeJournalEntity)
                .where(TradeJournalEntity.symbol == symbol, TradeJournalEntity.logged_at >= cutoff)
                .order_by(TradeJournalEntity.logged_at.desc())
                .limit(limit)
            )
            res = await session.execute(stmt)
            return list(res.scalars())

    @staticmethod
    async def get_journal_win_stats(hours: int = 48, limit: int = 20) -> dict:
        """Aggregate recent performance across ALL symbols — the system's live report card."""
        async with AsyncSessionLocal() as session:
            cutoff = datetime.now(UTC) - timedelta(hours=hours)
            stmt = (
                select(TradeJournalEntity)
                .where(TradeJournalEntity.logged_at >= cutoff)
                .order_by(TradeJournalEntity.logged_at.desc())
                .limit(limit)
            )
            res = await session.execute(stmt)
            rows = list(res.scalars())
        wins = sum(1 for r in rows if r.pnl > 0)
        total = len(rows)
        gross_win = sum(r.pnl for r in rows if r.pnl > 0)
        gross_loss = abs(sum(r.pnl for r in rows if r.pnl < 0))
        return {
            "total": total,
            "wins": wins,
            "losses": total - wins,
            "win_rate": (wins / total) if total else 0.0,
            "profit_factor": (gross_win / gross_loss) if gross_loss > 0 else (999.0 if gross_win > 0 else 0.0),
            "net_pnl": round(sum(r.pnl for r in rows), 4),
        }

    @staticmethod
    async def save_position(pos: PositionSnapshot):
        pos_id = getattr(pos, "position_id", getattr(pos, "decision_id", getattr(pos, "guardian_id", None)))
        if not pos_id:
            return
        async with AsyncSessionLocal() as session, session.begin():
            stmt = select(PositionEntity).where(PositionEntity.position_id == pos_id)
            res = await session.execute(stmt)
            entity = res.scalar_one_or_none()
            if entity:
                entity.quantity = getattr(pos, "quantity", entity.quantity)
                entity.current_price = getattr(pos, "current_price", entity.current_price)
                entity.stop_loss = getattr(pos, "stop_loss", entity.stop_loss)
                entity.target_1 = getattr(pos, "target_1", entity.target_1)
                entity.highest_price_seen = getattr(pos, "highest_price_seen", entity.highest_price_seen)
                entity.unrealized_pnl = getattr(pos, "unrealized_pnl", entity.unrealized_pnl)
                entity.realized_pnl = getattr(pos, "realized_pnl", entity.realized_pnl)
                entity.is_active = getattr(pos, "is_active", entity.is_active)
                entity.updated_at = datetime.now(UTC)
            else:
                entity = PositionEntity(
                    position_id=pos_id,
                    symbol=pos.symbol,
                    exchange=getattr(pos, "exchange", "NSE"),
                    quantity=getattr(pos, "quantity", 0),
                    entry_price=getattr(pos, "entry_price", 0.0),
                    current_price=getattr(pos, "current_price", 0.0),
                    stop_loss=getattr(pos, "stop_loss", 0.0),
                    target_1=getattr(pos, "target_1", 0.0),
                    highest_price_seen=getattr(pos, "highest_price_seen", getattr(pos, "current_price", 0.0)),
                    unrealized_pnl=getattr(pos, "unrealized_pnl", 0.0),
                    realized_pnl=getattr(pos, "realized_pnl", 0.0),
                    is_active=getattr(pos, "is_active", True),
                    opened_at=getattr(pos, "opened_at", datetime.now(UTC)),
                    updated_at=datetime.now(UTC),
                )
                session.add(entity)

    @staticmethod
    async def get_active_positions() -> list[PositionEntity]:
        async with AsyncSessionLocal() as session:
            stmt = select(PositionEntity).where(PositionEntity.is_active)
            res = await session.execute(stmt)
            return list(res.scalars().all())

    @staticmethod
    async def get_recent_orders(limit: int = 20) -> list[OrderEntity]:
        async with AsyncSessionLocal() as session:
            stmt = select(OrderEntity).order_by(OrderEntity.executed_at.desc()).limit(limit)
            res = await session.execute(stmt)
            return list(res.scalars().all())


    @staticmethod
    async def get_recent_decisions(limit: int = 20) -> list[TradeDecisionEntity]:
        async with AsyncSessionLocal() as session:
            stmt = select(TradeDecisionEntity).order_by(TradeDecisionEntity.created_at.desc()).limit(limit)
            res = await session.execute(stmt)
            return list(res.scalars().all())

