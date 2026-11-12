"""
AI Trade Guardian - Master Supervisor & Safety Control System
Supervises all individual position guardians, enforces multi-layer portfolio limits,
reconciles live broker state against internal state, prevents duplicate orders / martingale loss-chasing,
and executes emergency protective exits.
"""

import asyncio
from datetime import UTC, datetime

from core.logging import logger
from core.schemas.trade import OrderIntent, PositionSnapshot, TradeAction
from core.treasury.treasury import treasury
from execution.interface import BaseBroker
from guardian.models import (
    BrokerReconciliationReport,
    GuardianAction,
    GuardianRiskLevel,
    PostTradeQualityReport,
)
from guardian.position_guardian import PositionGuardianWorker
from guardian.post_trade_analytics import PostTradeAnalyticsEngine
from market.providers.base import BaseMarketDataProvider


class MasterTradeGuardian:
    """Institutional Trade Guardian Supervisor maintaining continuous oversight over all live trades."""

    def __init__(
        self,
        broker: BaseBroker | None = None,
        max_daily_loss_inr: float = 40.0,
        max_drawdown_pct: float = 0.05,
    ):
        self.broker = broker
        self.guardians: dict[str, PositionGuardianWorker] = {}
        self.completed_reports: list[PostTradeQualityReport] = []
        self.max_daily_loss_inr = max_daily_loss_inr
        self.max_drawdown_pct = max_drawdown_pct
        self.last_reconciliation_report = BrokerReconciliationReport()
        self.is_reconciled = True
        self.lock = asyncio.Lock()
        logger.info("🛡️ [Master Trade Guardian] Initialized institutional protection system.")

    def register_position(
        self,
        pos: PositionSnapshot | None = None,
        symbol: str = "",
        quantity: int = 1,
        entry_price: float = 0.0,
        stop_loss: float = 0.0,
        target_1: float = 0.0,
        target_2: float | None = None,
        decision_id: str = "",
        trade_thesis: list[str] | str | None = None,
        invalidating_scenarios: list[str] | None = None,
        atr_14: float = 10.0,
        trailing_atr_multiplier: float = 0.8,
    ) -> PositionGuardianWorker:
        """Assigns a dedicated guardian worker to a newly opened position."""
        if pos is None:
            if isinstance(trade_thesis, str):
                parsed_thesis = [trade_thesis]
            else:
                parsed_thesis = trade_thesis or ["Technical momentum breakout"]
            now = datetime.now(UTC)
            pos = PositionSnapshot(
                position_id=f"POS-{symbol.replace('.', '_')}-{int(now.timestamp())}",
                symbol=symbol,
                quantity=quantity,
                entry_price=entry_price,
                current_price=entry_price,
                stop_loss=stop_loss,
                target_1=target_1,
                target_2=target_2,
                highest_price_seen=entry_price,
                unrealized_pnl=0.0,
                opened_at=now,
                thesis_invalidation_rules=invalidating_scenarios or [],
            )
        else:
            parsed_thesis = [trade_thesis] if isinstance(trade_thesis, str) else (trade_thesis or ["Approved trade thesis"])

        worker = PositionGuardianWorker(
            pos=pos,
            decision_id=decision_id,
            trade_thesis=parsed_thesis,
            invalidating_scenarios=invalidating_scenarios,
            atr_14=atr_14,
            trailing_atr_multiplier=trailing_atr_multiplier,
            max_permitted_loss_inr=self.max_daily_loss_inr * 0.5,
        )
        self.guardians[pos.symbol] = worker
        return worker

    def get_worker(self, symbol: str) -> PositionGuardianWorker | None:
        """Returns the dedicated guardian worker for a symbol."""
        return self.guardians.get(symbol)

    def get_guardian(self, symbol: str) -> PositionGuardianWorker | None:
        """Alias for get_worker."""
        return self.guardians.get(symbol)

    async def reconcile_with_broker(self, broker: BaseBroker | None = None) -> BrokerReconciliationReport:
        """Reconciles internal AI positions with actual broker positions from SmartAPI."""
        target_broker = broker or self.broker
        report = BrokerReconciliationReport()

        if not target_broker:
            report.broker_connected = False
            report.discrepancies.append("Broker instance not configured for reconciliation.")
            self.last_reconciliation_report = report
            return report

        if hasattr(target_broker, "_is_authenticated") and not target_broker._is_authenticated:
            report.broker_connected = False
            report.discrepancies.append("Broker is not authenticated. Skipping reconciliation to preserve positions.")
            self.last_reconciliation_report = report
            return report

        try:
            broker_positions = await target_broker.get_positions()
            broker_active = [p for p in broker_positions if p.is_active and p.quantity > 0]

            # Cache the broker's own mark prices: the primary data provider (yfinance)
            # does not list many Delta perpetuals, and without a price the guardian
            # could never exit those positions automatically.
            self._latest_broker_marks = {
                p.symbol.strip().upper(): p.current_price for p in broker_active if p.current_price and p.current_price > 0
            }

            report.ai_open_positions_count = len([w for w in self.guardians.values() if w.state.is_active])
            report.broker_open_positions_count = len(broker_active)

            def _norm(s: str) -> str:
                return s.strip().upper().replace("-EQ", "").replace(".NS", "").replace(".BO", "")

            broker_norm = {_norm(p.symbol): p for p in broker_active}
            ai_norm = {_norm(sym): (sym, w) for sym, w in self.guardians.items() if w.state.is_active}

            # 1. Check for unmanaged broker positions (Positions on broker without Guardian)
            for b_clean, b_pos in broker_norm.items():
                if b_clean not in ai_norm:
                    report.unmanaged_broker_positions.append(b_pos.symbol)
                    report.discrepancies.append(f"Unmanaged position detected on broker: {b_pos.symbol} ({b_pos.quantity} shares)")
                    # Auto-adopt unmanaged position into Guardian protection
                    self.register_position(b_pos)
                    logger.warning(f"🛡️ [Guardian Auto-Adopt] Adopted unmanaged broker position under protection: {b_pos.symbol}")

            # 2. Check for quantity mismatches & closed positions
            for a_clean, (sym, worker) in ai_norm.items():
                if a_clean in broker_norm:
                    b_pos = broker_norm[a_clean]
                    if worker.state.quantity != b_pos.quantity:
                        report.discrepancies.append(
                            f"Quantity mismatch for {sym}: AI State={worker.state.quantity}, Broker Actual={b_pos.quantity}"
                        )
                        worker.state.quantity = b_pos.quantity
                        worker.state.broker_shares_matched = False
                else:
                    # AI thinks position is open, but broker shows 0
                    report.discrepancies.append(f"Position {sym} closed on broker but active in AI state. Auto-resolving.")
                    worker.state.is_active = False

                    # BUG-05 FIX: Calculate analytics, record in Treasury, and persist completed trade in journal
                    try:
                        exit_price = worker.state.current_price or worker.state.entry_price
                        post_report = PostTradeAnalyticsEngine.analyze_completed_guardian_position(
                            state=worker.state,
                            exit_price=exit_price,
                            exit_reason="BROKER_RECONCILED_CLOSED",
                            brokerage_fee=None,
                            interventions_count=worker.interventions_count,
                        )
                        self.completed_reports.append(post_report)
                        gross_pnl = round(post_report.realized_pnl + post_report.brokerage_and_fees, 2)
                        treasury.record_trade_result(
                            pnl=gross_pnl,
                            broker_fees=post_report.brokerage_and_fees,
                            symbol=sym,
                        )
                        from database.repositories.trade_repo import TradeRepository
                        holding_secs = max(0.0, (datetime.now(UTC) - worker.state.opened_at).total_seconds()) if worker.state.opened_at else 0.0
                        await TradeRepository.save_journal(
                            symbol=sym,
                            entry_price=worker.state.entry_price,
                            exit_price=exit_price,
                            pnl=post_report.realized_pnl,
                            exit_reason="BROKER_RECONCILED_CLOSED",
                            holding_period_seconds=holding_secs,
                            market_regime="Unknown",
                            reflection_notes=f"side={worker.state.side} qty={worker.state.quantity} closed_by_broker=true",
                        )
                    except Exception as rec_err:
                        logger.warning(f"[Trade Guardian] Broker-closed trade record error: {rec_err}")

            report.is_synchronized = len(report.discrepancies) == 0
            self.is_reconciled = report.is_synchronized

            if not report.is_synchronized:
                logger.warning(f"⚠️ [Broker Reconciliation Discrepancy] {len(report.discrepancies)} issues detected: {report.discrepancies}")

        except Exception as e:
            report.broker_connected = False
            report.discrepancies.append(f"Reconciliation query error: {e}")
            logger.error(f"[Broker Reconciliation Error] {e}")

        self.last_reconciliation_report = report
        return report

    def verify_no_duplicate_orders(self, symbol: str, proposed_qty: int) -> tuple[bool, str]:
        """Prevents duplicate submissions, duplicate positions, and unauthorized martingale averaging."""
        if symbol in self.guardians and self.guardians[symbol].state.is_active:
            worker = self.guardians[symbol]
            # Disallow adding to a losing position (Anti-Martingale rule)
            if worker.state.unrealized_pnl < 0:
                reason = f"Anti-Martingale Guard: Prohibited from averaging down on losing position {symbol} (PnL: ₹{worker.state.unrealized_pnl})."
                logger.warning(f"🚫 [Guardian Rule 15] {reason}")
                return False, reason
            else:
                reason = f"Duplicate Position Guard: Active position already exists for {symbol}."
                logger.warning(f"🚫 [Guardian Rule 13] {reason}")
                return False, reason
        return True, "Approved"

    async def evaluate_all_guardians(
        self,
        provider: BaseMarketDataProvider,
        broker: BaseBroker | None = None,
        market_regime: str = "Trending",
    ) -> list[tuple[str, GuardianAction, str]]:
        """Evaluates every single active position and executes protective exits when boundaries are breached."""
        target_broker = broker or self.broker
        actions_taken = []

        async with self.lock:
            # First reconcile with broker
            await self.reconcile_with_broker(target_broker)

            for symbol, worker in list(self.guardians.items()):
                if not worker.state.is_active:
                    continue

                try:
                    try:
                        ltp = await provider.get_ltp(symbol)
                    except Exception:
                        ltp = 0.0
                    mark_px = float(getattr(self, "_latest_broker_marks", {}).get(symbol.strip().upper(), 0.0))
                    if not ltp or ltp <= 0:
                        # Fallback to the broker's mark price so no position is ever left unpriced/unmanaged
                        ltp = mark_px
                    if not ltp or ltp <= 0:
                        logger.warning(f"[Guardian] No live price available for {symbol} (provider + broker mark both empty). Will retry next cycle.")
                        continue

                    # Monitor live 5-minute chart candles for real-time price action & candlestick exhaustion
                    # (long positions only — the chart profit-taker's wick/EMA analysis is long-biased)
                    df_5m = None
                    is_long_worker = getattr(worker.state, "side", "BUY").upper() != "SELL"
                    if provider and is_long_worker and hasattr(provider, "get_historical_ohlcv") and (worker.state.unrealized_pnl > 0 or worker.state.highest_price_seen > worker.state.entry_price):
                        try:
                            df_5m = await provider.get_historical_ohlcv(symbol, interval="5m", period="1d")
                        except Exception as ohlc_err:
                            logger.debug(f"[Guardian Chart Fetch] Could not fetch 5m candles for {symbol}: {ohlc_err}")

                    action, note = await worker.evaluate_tick(
                        current_ltp=ltp,
                        market_regime=market_regime,
                        ohlcv_5m=df_5m,
                        provider=provider,
                        mark_price=mark_px if mark_px > 0 else None,
                    )

                    if action in [
                        GuardianAction.HARD_STOP_EXIT,
                        GuardianAction.TARGET_EXIT,
                        GuardianAction.THESIS_INVALIDATION_EXIT,
                        GuardianAction.EMERGENCY_EXIT,
                        GuardianAction.EOD_SQUAREOFF,
                        GuardianAction.STAGNATION_SCRATCH_EXIT,
                        GuardianAction.MIDDAY_PEAK_HARVEST,
                        GuardianAction.CHART_PROFIT_TAKE,
                    ]:
                        exit_fill_price = ltp
                        if target_broker:
                            from core.domain.models import OrderStatus
                            from core.schemas.trade import OrderType
                            from execution.router import OrderRouter
                            router = OrderRouter(target_broker)
                            is_short = getattr(worker.state, "side", "BUY").upper() == "SELL"
                            exit_action = TradeAction.BUY if is_short else TradeAction.SELL
                            exit_order = OrderIntent(
                                client_order_id=f"GRD-EXT-{symbol}-{int(datetime.now(UTC).timestamp())}",
                                symbol=symbol,
                                exchange=worker.state.exchange,
                                action=exit_action,
                                quantity=worker.state.quantity,
                                # Exits are MARKET orders. `price` is only a reference for paper
                                # brokers' simulated fill; live adapters must not rest it as a limit
                                # (a resting limit stop never fills in a falling market).
                                order_type=OrderType.MARKET,
                                price=ltp if (ltp and ltp > 0) else None,
                                stop_loss=0.0,
                                target=0.0,
                                decision_id=f"GRD-{action.value}",
                                reduce_only=True,  # can only close/shrink the position, never flip or double it
                            )
                            exec_report = await router.route_order(exit_order)
                            try:
                                from database.repositories.trade_repo import TradeRepository
                                await TradeRepository.save_order(exec_report, action=exit_order.action.value, decision_id=exit_order.decision_id)
                            except Exception as db_err:
                                logger.debug(f"[Trade Guardian] Exit order DB persistence notice: {db_err}")

                            # The position is still open if the exit didn't go through. Keep the
                            # guardian active so it retries next cycle, instead of marking the trade
                            # closed and leaving a live position with no one watching it.
                            if exec_report.status == OrderStatus.REJECTED and (exec_report.filled_quantity or 0) <= 0:
                                logger.error(
                                    f"🚨 [Trade Guardian] Exit {action.value} for {symbol} was REJECTED "
                                    f"({exec_report.order_id}). Position remains open; guardian stays active and retries next cycle."
                                )
                                continue
                            if exec_report.average_price and exec_report.average_price > 0:
                                exit_fill_price = float(exec_report.average_price)

                        # Generate Post-Trade Quality Report and deactivate worker
                        post_report = PostTradeAnalyticsEngine.analyze_completed_guardian_position(
                            state=worker.state,
                            exit_price=exit_fill_price,
                            exit_reason=action.value,
                            brokerage_fee=None,
                            interventions_count=worker.interventions_count,
                        )
                        self.completed_reports.append(post_report)
                        worker.state.is_active = False

                        # Record in Treasury (gross PnL passed so treasury deducts broker fees cleanly without double-counting)
                        gross_pnl = round(post_report.realized_pnl + post_report.brokerage_and_fees, 2)
                        treasury.record_trade_result(
                            pnl=gross_pnl,
                            broker_fees=post_report.brokerage_and_fees,
                            symbol=symbol,
                        )

                        # Persist the completed trade to the journal so win-rate, profit factor
                        # and the capital-scaling policy have real history to evaluate.
                        try:
                            from database.repositories.trade_repo import TradeRepository
                            holding_secs = max(0.0, (datetime.now(UTC) - worker.state.opened_at).total_seconds()) if worker.state.opened_at else 0.0
                            await TradeRepository.save_journal(
                                symbol=symbol,
                                entry_price=worker.state.entry_price,
                                exit_price=exit_fill_price,
                                pnl=post_report.realized_pnl,
                                exit_reason=action.value,
                                holding_period_seconds=holding_secs,
                                market_regime=market_regime,
                                reflection_notes=f"side={worker.state.side} qty={worker.state.quantity} planned_rr={post_report.planned_risk_reward} actual_rr={post_report.actual_risk_reward}",
                            )
                        except Exception as jrn_err:
                            logger.debug(f"[Trade Guardian] Journal persistence notice: {jrn_err}")

                        actions_taken.append((symbol, action, note))

                except Exception as eval_err:
                    logger.error(f"[Guardian Error evaluating {symbol}] {eval_err}")

        return actions_taken

    def get_guardian_dashboard_summary(self) -> dict:
        """Returns comprehensive real-time dashboard telemetry for the Trade Guardian HUD."""
        active_workers = [w for w in self.guardians.values() if w.state.is_active]
        at_risk = [w for w in active_workers if w.state.risk_level in [GuardianRiskLevel.HIGH, GuardianRiskLevel.CRITICAL]]
        total_unrealized_pnl = sum(w.state.unrealized_pnl for w in active_workers)

        positions_list = []
        for w in active_workers:
            positions_list.append({
                "symbol": w.state.symbol,
                "entry_price": w.state.entry_price,
                "current_price": w.state.current_price,
                "quantity": w.state.quantity,
                "stop_loss": w.state.stop_loss,
                "current_stop_loss": w.state.stop_loss,
                "original_stop_loss": w.state.original_stop_loss or w.state.stop_loss,
                "target_1": w.state.target_1,
                "target_2": w.state.target_2,
                "unrealized_pnl": w.state.unrealized_pnl,
                "unrealized_pnl_pct": w.state.unrealized_pnl_pct,
                "distance_to_stop_pct": w.state.distance_to_stop_pct,
                "distance_to_target_pct": w.state.distance_to_target_pct,
                "risk_level": w.state.risk_level.value,
                "trade_thesis": w.state.trade_thesis[0] if w.state.trade_thesis else "Technical Breakout",
                "thesis_valid": w.state.thesis_intact,
                "invalidation_reason": w.state.invalidation_reason,
                "current_action": "HOLD",
                "guardian_id": w.guardian_id,
            })

        return {
            "status": "ACTIVE_PROTECTION",
            "active_positions_count": len(active_workers),
            "positions_at_risk_count": len(at_risk),
            "total_unrealized_pnl": round(total_unrealized_pnl, 2),
            "net_trading_profit": round(treasury.net_trading_profit, 2),
            "broker_synchronized": self.is_reconciled,
            "discrepancies": self.last_reconciliation_report.discrepancies,
            "positions": positions_list,
            "completed_trades_count": len(self.completed_reports),
            "closed_positions_audit": [
                {
                    "trade_id": r.trade_id,
                    "symbol": r.symbol,
                    "entry_price": r.entry_price,
                    "exit_price": r.exit_price,
                    "quantity": r.quantity,
                    "realized_pnl": r.realized_pnl,
                    "realized_pnl_pct": r.realized_pnl_pct,
                    "exit_reason": r.exit_reason,
                    "max_favorable_excursion": r.max_favorable_excursion_pct,
                    "max_adverse_excursion": r.max_adverse_excursion_pct,
                    "slippage": r.slippage_cost,
                    "planned_risk_reward": r.planned_risk_reward,
                    "actual_risk_reward": r.actual_risk_reward,
                    "learning_loop_quadrant": r.decision_vs_outcome_quadrant,
                }
                for r in reversed(self.completed_reports[-20:])
            ],
            "last_check_timestamp": datetime.now(UTC).isoformat(),
        }


# Global Master Trade Guardian Singleton
trade_guardian = MasterTradeGuardian()
