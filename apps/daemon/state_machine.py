import json
from datetime import UTC, datetime
from pathlib import Path

from agents.facilitator.facilitator import AdversarialDebateDesk
from agents.lifecycle.agent_manager import agent_manager
from agents.research_desk import AIResearchDesk
from agents.trader.fund_manager import FundManagerAgent
from core.config.settings import TradingMode, settings
from core.domain.models import OrderStatus, TradeAction, TradingSessionState
from core.logging import logger
from core.schemas.trade import OrderIntent
from core.treasury.treasury import treasury
from database.repositories.trade_repo import TradeRepository
from execution.interface import BaseBroker
from execution.router import OrderRouter
from guardian.trade_guardian import trade_guardian
from market.premarket_readiness import premarket_readiness_engine
from memory.global_memory import global_ai_memory
from memory.memory_manager_agent import memory_manager_agent
from monitoring.position_monitor import PositionMonitor
from orchestration.batch_engine import MultiStockOrchestrator
from orchestration.event_bus import SystemEventType, realtime_event_bus
from portfolio.position_sizer import PositionSizer
from risk.audit_gate import AuditGate
from risk.engine import DeterministicRiskEngine
from risk.kill_switch import kill_switch
from risk.safety_checker import SafetyChecker
from scanner.quant_scanner import QuantMarketScanner
from strategy.engine import MultiStrategyEngine


class AutonomousTradingDaemon:
    """End-to-End Autonomous Trading Daemon executing the full institutional pipeline across N stocks."""

    def __init__(
        self,
        scanner: QuantMarketScanner,
        broker: BaseBroker,
        total_capital: float = settings.INITIAL_CAPITAL,
        top_n_candidates: int = 10,
    ):
        self.scanner = scanner
        self.broker = broker
        self.top_n_candidates = top_n_candidates
        self.total_capital = total_capital
        self.research_desk = AIResearchDesk()
        self.debate_desk = AdversarialDebateDesk()
        self.fund_manager = FundManagerAgent()
        self.orchestrator = MultiStockOrchestrator(
            research_desk=self.research_desk,
            debate_desk=self.debate_desk,
            fund_manager=self.fund_manager,
            include_kronos=True,
        )
        self.risk_engine = DeterministicRiskEngine(total_equity=total_capital, peak_equity=total_capital)
        self.position_sizer = PositionSizer(total_equity=total_capital)
        self.router = OrderRouter(broker)
        self.position_monitor = PositionMonitor(broker)

        self.current_state = TradingSessionState.PRE_MARKET
        self.is_running = False

    async def run_single_cycle(self, top_n: int | None = None) -> dict:
        """Executes a complete scanning, multi-stock research, debate, ranking, 14-point audit, risk, sizing, execution & monitoring cycle."""
        phase, time_left, countdown_str = premarket_readiness_engine.get_market_phase()
        logger.info(f"=== STARTING MULTI-STOCK TRADING CYCLE | PHASE: {phase} ({countdown_str}) ===")


        # 0. Live/Paper Broker Funds & Margin Verification (Pre-Market / Active Hours)
        available_margin = self.total_capital
        if settings.TRADING_MODE in [TradingMode.LIVE, TradingMode.PAPER]:
            try:
                funds = await self.broker.get_funds()
                real_cap = float(funds.get("total_capital", 0.0))
                avail_margin = float(funds.get("available_margin", 0.0))
                if real_cap > 0 or avail_margin > 0:
                    treasury.current_capital = real_cap
                    treasury.starting_capital = real_cap
                    treasury.buckets.trading_capital = avail_margin
                    self.total_capital = real_cap
                    self.risk_engine.total_equity = real_cap
                    today_utc = datetime.now(UTC).date()
                    risk_state_file = Path("data/daily_risk_state.json")

                    # Autonomous kill-switch recovery: accept the realized loss and restart
                    # risk baselines from current equity so trading can resume unattended.
                    if kill_switch.rebase_required:
                        kill_switch.rebase_required = False
                        self.risk_engine.peak_equity = real_cap
                        self._equity_day = today_utc
                        self._day_start_equity = real_cap
                        self.risk_engine.daily_realized_loss = 0.0
                        logger.warning(f"🔄 [Risk Rebase] Equity baselines reset to current broker equity ({real_cap:.2f}) after auto-recovery.")
                        try:
                            risk_state_file.parent.mkdir(parents=True, exist_ok=True)
                            with open(risk_state_file, "w") as f:
                                json.dump({
                                    "date": today_utc.isoformat(),
                                    "day_start_equity": real_cap,
                                    "last_updated": datetime.now(UTC).isoformat(),
                                }, f, indent=2)
                        except Exception:
                            pass

                    # Track day-start equity so the daily-loss circuit breaker measures
                    # real broker equity decline (realized + unrealized), persisting across process restarts
                    persisted_day_start = None
                    if risk_state_file.exists():
                        try:
                            with open(risk_state_file, "r") as f:
                                saved_data = json.load(f)
                                if saved_data.get("date") == today_utc.isoformat():
                                    persisted_day_start = float(saved_data.get("day_start_equity", 0.0))
                        except Exception as e:
                            logger.debug(f"[Risk State] Could not load persisted risk state: {e}")

                    if getattr(self, "_equity_day", None) != today_utc:
                        self._equity_day = today_utc
                        self._day_start_equity = persisted_day_start if (persisted_day_start and persisted_day_start > 0) else real_cap
                        try:
                            risk_state_file.parent.mkdir(parents=True, exist_ok=True)
                            with open(risk_state_file, "w") as f:
                                json.dump({
                                    "date": today_utc.isoformat(),
                                    "day_start_equity": self._day_start_equity,
                                    "last_updated": datetime.now(UTC).isoformat(),
                                }, f, indent=2)
                        except Exception as e:
                            logger.debug(f"[Risk State] Could not persist risk state: {e}")

                    self.risk_engine.daily_realized_loss = max(0.0, self._day_start_equity - real_cap)
                    # Peak equity only ratchets upward within a session; lowering it would
                    # silently disable the max-drawdown kill switch.
                    self.risk_engine.peak_equity = max(self.risk_engine.peak_equity, real_cap)
                    self.position_sizer.total_equity = real_cap
                    self.position_sizer.available_margin = avail_margin
                    available_margin = avail_margin
                else:
                    available_margin = self.total_capital
            except Exception as e:
                logger.warning(f"[Broker Funds Check] Failed to query live RMS margin: {e}")

        is_crypto = getattr(self.broker, "DEFAULT_PROD_URL", None) is not None or "DELTA" in type(self.broker).__name__.upper()
        curr_sym = "$" if is_crypto else "₹"
        broker_name = "Delta Exchange" if is_crypto else "AngelOne"

        if available_margin > 0:
            logger.info(f"💰 [Capital Detected] {broker_name} Available Margin: {curr_sym}{available_margin:,.2f} (Total Equity: {curr_sym}{self.total_capital:,.2f}). Full autonomous trading pipeline ACTIVE.")
        else:
            logger.info(f"⏳ [Capital Standby] {broker_name} Available Margin: {curr_sym}0.00. Running scans & multi-agent research in standby mode until funds are deposited.")

        # 0. Emergency Kill Switch & 3-Strike Observation Cooldown Verification
        in_cooldown, cooldown_reason = kill_switch.is_in_cooldown
        if in_cooldown:
            logger.warning(f"⏳ [Risk Gate Cooldown] {cooldown_reason}. Skipping candidate execution for this cycle.")
            return {"status": "cooldown", "reason": cooldown_reason}

        drawdown_pct = (self.risk_engine.peak_equity - self.risk_engine.total_equity) / self.risk_engine.peak_equity if self.risk_engine.peak_equity > 0 else 0.0
        daily_loss = self.risk_engine.daily_realized_loss
        ks_ok, ks_reason = kill_switch.verify_system_integrity(
            daily_loss=daily_loss,
            current_drawdown_pct=drawdown_pct,
            max_capital=self.total_capital,
            broker_connected=True,
            data_feed_healthy=True,
        )
        if not ks_ok:
            logger.critical(f"Aborting cycle: Emergency Kill Switch is ACTIVE ({ks_reason or kill_switch.reason})")
            # New entries are halted, but existing open positions must still be protected:
            # keep evaluating guardians so stops/targets continue to fire.
            try:
                await trade_guardian.evaluate_all_guardians(provider=self.scanner.provider, broker=self.broker)
            except Exception as grd_err:
                logger.error(f"[Kill Switch Monitoring] Guardian evaluation error: {grd_err}")
            return {"error": "Kill switch engaged", "reason": ks_reason or kill_switch.reason}

        # Automatically reconcile Trade Guardian with actual live broker state
        try:
            await trade_guardian.reconcile_with_broker(self.broker)
        except Exception as rec_err:
            logger.debug(f"[Trade Guardian] Note during cycle reconciliation: {rec_err}")

        # 0. Economic Model & Survival Mode Check
        is_survival = treasury.is_survival_mode
        if is_survival:
            logger.warning("⚠️ [TREASURY] Survival Mode is ACTIVE. Throttling risk and enforcing conservative capital preservation.")
            agent_manager.enforce_survival_mode_constraints()
            realtime_event_bus.publish_event(
                SystemEventType.TREASURY_WARNING,
                source="AI Treasury",
                payload={"survival_mode": True, "capital": treasury.current_capital},
            )

        # Deduct micro-operating cost for the cycle (Compute + Data + LLM tokens)
        cycle_compute_cost = (0.005 if is_crypto else 0.50) if not is_survival else (0.001 if is_crypto else 0.15)
        treasury.record_operating_cost(cycle_compute_cost, "AI Cycle Compute & Market Data Feed")

        n_candidates = top_n or self.top_n_candidates
        cycle_summary = {
            "candidates_scanned": 0,
            "debates_conducted": 0,
            "decisions_made": 0,
            "audits_passed": 0,
            "orders_executed": 0,
            "executed_symbols": [],
            "survival_mode_active": is_survival,
            "treasury_capital": round(treasury.current_capital, 2),
            "available_margin": round(available_margin, 2),
            "net_profit": round(treasury.net_trading_profit, 2),
            "realized_pnl": round(treasury.realized_pnl, 2),
        }

        # 1. State: SCANNING Universe of N Stocks
        self.current_state = TradingSessionState.SCANNING
        candidates = await self.scanner.get_top_candidates(top_n=n_candidates)
        # If running on bootstrap margin, ensure we also include actionable stocks whose LTP is within margin
        if not is_crypto and available_margin > 0 and available_margin < 2000 and not any(c.ltp <= available_margin for c in candidates):
            affordable_candidates = await self.scanner.get_top_candidates(top_n=3, max_price=available_margin)
            if affordable_candidates:
                candidates = affordable_candidates + [c for c in candidates if c.symbol not in {a.symbol for a in affordable_candidates}]
                candidates = candidates[:n_candidates]

        cycle_summary["candidates_scanned"] = len(candidates)
        logger.info(f"Scanner qualified {len(candidates)} candidates from universe: {[c.symbol for c in candidates]}")

        if not candidates:
            logger.info("No candidates qualified quantitative momentum thresholds in current market cycle.")
            return cycle_summary

        # 1.5. Autonomous Agent Procreation (AI Self-Spawning Support Workers)
        from agents.factory.auto_procreation import auto_procreation_engine
        try:
            spawned_support = await auto_procreation_engine.evaluate_and_auto_spawn(
                scanned_candidates=candidates,
                market_regime=candidates[0].regime.value if hasattr(candidates[0].regime, "value") else str(candidates[0].regime)
            )
            if spawned_support:
                cycle_summary["auto_spawned_agents"] = [a.name for a in spawned_support]
        except Exception as e:
            logger.debug(f"[AutoProcreation] Evaluation note: {e}")

        # 2 & 3 & 4. State: ANALYZING, DEBATING & DECIDING across all N candidates concurrently
        self.current_state = TradingSessionState.ANALYZING
        batch_results = await self.orchestrator.run_batch_debate_and_allocation(
            candidates=candidates,
            max_allocations=n_candidates,
            available_capital=available_margin,
        )

        cycle_summary["debates_conducted"] = batch_results["total_evaluated"]
        cycle_summary["decisions_made"] = len(batch_results["ranked_candidates"])

        # 5. Risk-Gating & 14-Point Pre-Trade Audit on Ranked High-Conviction Candidates
        self.current_state = TradingSessionState.RISK_GATING
        open_positions = await self.broker.get_positions()

        for item in batch_results["approved_trades"]:
            candidate = item["signal"]
            decision = item["decision"]
            debate = item["debate"]
            reports = item["analyst_reports"]

            logger.info(
                f"Evaluating candidate {candidate.symbol} (Conviction Rank: {item['conviction_rank']}, "
                f"Debate Consensus: {debate.consensus_score})"
            )

            # Strategy Selection
            strategy_res = MultiStrategyEngine.evaluate_strategies(candidate, is_survival_mode=is_survival)
            if not strategy_res.suitable:
                logger.info(f"Strategy filter rejected {candidate.symbol}: {strategy_res.rationale}")
                continue

            # Memory-Aware Pre-Decision Pipeline (Section 58)
            pre_memory = global_ai_memory.query_pre_decision_memory(
                symbol=candidate.symbol,
                strategy=strategy_res.strategy_name,
                current_regime=candidate.regime if hasattr(candidate, "regime") else "High Volatility Sideways",
            )
            if pre_memory["risk_warnings"]:
                logger.info(f"[Memory Awareness] Retrieved {len(pre_memory['risk_warnings'])} memory warnings for {candidate.symbol}.")

            # Deterministic Risk Evaluation
            risk_res = self.risk_engine.evaluate_trade_intent(decision, open_positions)

            if risk_res.approved:
                # 5.4. LEARNING FROM TRADE HISTORY — every completed trade reshapes the
                # next decision. Per-symbol: recent wins raise the win-probability
                # estimate slightly (+0.02 each), recent losses lower it harder (-0.04
                # each — losses teach more than wins). Globally: if the last 20 trades
                # show a cold streak (<45% win rate), the required confluence bar rises
                # from 0.55 to 0.60 until performance recovers.
                history_adj = 0.0
                required_p_override = None
                try:
                    sym_history = await TradeRepository.get_recent_journal_for_symbol(candidate.symbol, hours=72, limit=5)
                    for past_trade in sym_history:
                        history_adj += 0.02 if past_trade.pnl > 0 else -0.04
                    history_adj = max(-0.10, min(0.06, history_adj))

                    global_stats = await TradeRepository.get_journal_win_stats(hours=48, limit=20)
                    if global_stats["total"] >= 6 and global_stats["win_rate"] < 0.45:
                        required_p_override = 0.60
                        logger.info(
                            f"🎓 [Learning Loop] Cold streak detected (win rate {global_stats['win_rate']*100:.0f}% "
                            f"over last {global_stats['total']} trades). Raising required confluence to 0.60."
                        )
                    if history_adj != 0.0:
                        logger.info(
                            f"🎓 [Learning Loop] {candidate.symbol}: history of last {len(sym_history)} trades "
                            f"adjusts win-probability estimate by {history_adj:+.3f}."
                        )
                except Exception as learn_err:
                    logger.debug(f"[Learning Loop] History lookup note: {learn_err}")

                # 5.5. FINAL PROFIT EXPECTANCY GATE — the trade must be mathematically
                # expected to profit AFTER fees (positive EV with buffer), or it is
                # skipped and the scanner keeps evaluating the next candidate.
                from risk.expectancy_gate import ExpectancyGate
                exp_ok, exp_reason, exp_metrics = ExpectancyGate.evaluate(
                    decision=decision,
                    signal=candidate,
                    debate=debate,
                    reports=reports,
                    is_crypto=is_crypto,
                    history_adjustment=history_adj,
                    required_p_override=required_p_override,
                )
                if not exp_ok:
                    logger.info(f"Expectancy Gate skipped {candidate.symbol}: {exp_reason}")
                    continue

                # 5.6. RECENT-LOSER COOLDOWN — if this symbol produced 2+ consecutive
                # losses in the last 24h, stand aside on it; the edge is not working.
                try:
                    recent_trades = await TradeRepository.get_recent_journal_for_symbol(candidate.symbol, hours=24)
                    consecutive_losses = 0
                    for t in recent_trades:
                        if t.pnl < 0:
                            consecutive_losses += 1
                        else:
                            break
                    if consecutive_losses >= 2:
                        logger.info(
                            f"⛔ [Loser Cooldown] {candidate.symbol} lost {consecutive_losses} consecutive trades "
                            f"in the last 24h. Skipping and continuing with other candidates."
                        )
                        continue
                except Exception as cd_err:
                    logger.debug(f"[Loser Cooldown] Journal lookup note: {cd_err}")

                # 6. Position Sizing
                qty = self.position_sizer.calculate_quantity(decision, risk_res)
                if qty > 0:
                    # 7. 14-Point Mandatory Pre-Trade Audit Gate
                    audit_passed, audit_record = AuditGate.audit_trade_intent(
                        signal=candidate,
                        decision=decision,
                        debate=debate,
                        reports=reports,
                        quantity=qty,
                        strategy_name=strategy_res.strategy_name,
                    )

                    if audit_passed:
                        # 7.1. Laya System 1 Sub-35ms Non-Autoregressive Fast Triage
                        if is_crypto:
                            try:
                                from intelligence.laya_service import laya_service
                                laya_res = await laya_service.triage_candidate(
                                    symbol=candidate.symbol,
                                    ltp=candidate.ltp or 0.0,
                                    change_24h=float(getattr(candidate, "change_24h", 0.0) or 0.0),
                                    rsi=float(getattr(candidate, "rsi_14", 50.0) or 50.0),
                                    trend_summary=f"{strategy_res.strategy_name} consensus {debate.consensus_score:+.2f}",
                                )
                                if laya_res.get("source") == "LAYA_SYSTEM_1":
                                    l_stance = laya_res.get("stance", "NEUTRAL")
                                    l_conv = laya_res.get("conviction", 0.0)
                                    if (decision.decision == TradeAction.BUY and l_stance == "BEARISH" and l_conv > 0.82):
                                        logger.warning(f"⚡ [Laya System 1 Fast Veto] {candidate.symbol}: High-conviction Bearish ({l_conv:.2f}) contradicts Long intent. Skipping.")
                                        continue
                                    elif (decision.decision == TradeAction.SELL and l_stance == "BULLISH" and l_conv > 0.82):
                                        logger.warning(f"⚡ [Laya System 1 Fast Veto] {candidate.symbol}: High-conviction Bullish ({l_conv:.2f}) contradicts Short intent. Skipping.")
                                        continue
                            except Exception as laya_err:
                                logger.debug(f"[Laya System 1] Triage notice: {laya_err}")

                        cycle_summary["audits_passed"] += 1
                        is_swing = strategy_res.strategy_name in ["MULTI_DAY_SWING", "Multi-Day Swing"]
                        prod_type = "DELIVERY" if is_swing else "INTRADAY"
                        is_sell = decision.decision == TradeAction.SELL
                        order = OrderIntent(
                            client_order_id=f"AUT-{candidate.symbol}-{int(datetime.now(UTC).timestamp())}",
                            symbol=candidate.symbol,
                            exchange=candidate.exchange,
                            action=decision.decision,
                            quantity=qty,
                            price=decision.entry_price,
                            stop_loss=decision.stop_loss or (candidate.ltp + 0.8 * candidate.atr_14 if is_sell else candidate.ltp - 0.8 * candidate.atr_14),
                            target=decision.target_1 or (candidate.ltp - 2.0 * candidate.atr_14 if is_sell else candidate.ltp + 2.0 * candidate.atr_14),
                            decision_id=decision.analysis_id,
                            product_type=prod_type,
                        )

                        # 8. Immutable Safety Check, Anti-Martingale Guardian & Routing
                        is_dup_allowed, dup_reason = trade_guardian.verify_no_duplicate_orders(order.symbol, order.quantity)
                        if not is_dup_allowed:
                            logger.warning(f"🛡️ [Trade Guardian Pre-Execution Block] {dup_reason}")
                            continue

                        # 8. Refresh real-time tick to prevent post-debate latency staleness
                        try:
                            fresh_ltp = await self.scanner.provider.get_ltp(candidate.symbol)
                            fresh_timestamp = datetime.now(UTC)
                        except Exception:
                            fresh_ltp = candidate.ltp
                            fresh_timestamp = datetime.now(UTC)

                        bid = getattr(candidate, "bid", None) or (fresh_ltp * 0.999)
                        ask = getattr(candidate, "ask", None) or (fresh_ltp * 1.001)
                        bid_vol = getattr(candidate, "bid_volume", None) or getattr(candidate, "total_buy_qty", None)
                        ask_vol = getattr(candidate, "ask_volume", None) or getattr(candidate, "total_sell_qty", None)
                        passed, reason = SafetyChecker.verify_order(
                            order,
                            current_ltp=fresh_ltp,
                            bid_price=bid,
                            ask_price=ask,
                            bid_volume=bid_vol,
                            ask_volume=ask_vol,
                            data_timestamp=fresh_timestamp,
                        )
                        if passed:
                            self.current_state = TradingSessionState.EXECUTING
                            exec_report = await self.router.route_order(order)
                            if exec_report.status in [OrderStatus.FILLED, OrderStatus.SUBMITTED] or exec_report.filled_quantity > 0:
                                cycle_summary["orders_executed"] += 1
                                cycle_summary["executed_symbols"].append(order.symbol)
                                kill_switch.record_trade_approval(order.symbol)
                                logger.info(f"✅ Order Dispatched/Filled successfully: {exec_report.order_id} for {order.symbol} (Qty: {exec_report.filled_quantity or qty})")

                                # Assign Dedicated AI Trade Guardian Worker — only once contracts
                                # actually filled. Registering a guardian for a resting unfilled limit
                                # order creates a phantom position; filled-later orders are adopted
                                # automatically by broker reconciliation on the next cycle.
                                if exec_report.filled_quantity <= 0:
                                    logger.info(f"⏳ [State Machine] {order.symbol} order submitted but not yet filled; guardian will adopt it from broker reconciliation once filled.")
                                else:
                                    try:
                                        from core.schemas.trade import PositionSnapshot
                                        ep = exec_report.average_price or order.price or candidate.ltp
                                        side_val = order.action.value.upper()
                                        ref_entry = order.price or candidate.ltp or ep

                                        # Re-anchor stop loss & target to actual fill price
                                        stop_dist = abs(ref_entry - order.stop_loss) if (order.stop_loss and order.stop_loss > 0) else (ep * 0.015)
                                        tgt_dist = abs(order.target - ref_entry) if (order.target and order.target > 0) else (stop_dist * 2.0)

                                        if side_val == "BUY":
                                            adj_sl = ep - stop_dist
                                            if adj_sl >= ep:
                                                adj_sl = ep * 0.985
                                            adj_tgt = ep + tgt_dist
                                        else:
                                            adj_sl = ep + stop_dist
                                            if adj_sl <= ep:
                                                adj_sl = ep * 1.015
                                            adj_tgt = ep - tgt_dist

                                        trade_guardian.register_position(
                                            pos=PositionSnapshot(
                                                position_id=f"POS-{order.symbol}-{int(datetime.now(UTC).timestamp())}",
                                                symbol=order.symbol,
                                                exchange=order.exchange,
                                                # CRITICAL: record the position direction. Without this,
                                                # SELL (short) entries defaulted to side="BUY", the guardian
                                                # computed P&L backwards, saw the stop as instantly breached,
                                                # and its "exit" SELL doubled the short instead of closing it.
                                                side=order.action.value,
                                                quantity=exec_report.filled_quantity,
                                                entry_price=ep,
                                                current_price=ep,
                                                stop_loss=round(adj_sl, 4),
                                                target_1=round(adj_tgt, 4),
                                                highest_price_seen=ep,
                                                lowest_price_seen=ep,
                                                unrealized_pnl=0.0,
                                                opened_at=datetime.now(UTC),
                                                is_active=True,
                                            ),
                                            decision_id=decision.analysis_id,
                                            trade_thesis=decision.thesis,
                                            invalidating_scenarios=decision.invalidation_conditions,
                                            atr_14=candidate.atr_14,
                                        )
                                    except Exception as grd_err:
                                        logger.error(f"[State Machine] Guardian assignment error: {grd_err}")

                                # 1. Persist Decision & Order in Institutional Database
                                try:
                                    await TradeRepository.save_decision(decision)
                                    await TradeRepository.save_order(exec_report, action=order.action.value, decision_id=decision.analysis_id)
                                except Exception as db_err:
                                    logger.debug(f"[State Machine] DB persistence notice: {db_err}")
                            elif exec_report.status == OrderStatus.SUBMITTED:
                                logger.info(f"⏳ Order Submitted to Broker: {exec_report.order_id} for {order.symbol}. Awaiting confirmation fill before registering position.")
                                try:
                                    await TradeRepository.save_decision(decision)
                                    await TradeRepository.save_order(exec_report, action=order.action.value, decision_id=decision.analysis_id)
                                except Exception as db_err:
                                    logger.debug(f"[State Machine] DB persistence notice: {db_err}")
                            else:
                                logger.warning(f"❌ Order Rejected by Execution Gateway for {order.symbol}: {exec_report.order_id}")

                            # Refresh open positions for subsequent risk checks
                            open_positions = await self.broker.get_positions()

                        else:
                            kill_switch.record_trade_rejection(candidate.symbol, f"Safety Gate: {reason}")
                            logger.warning(f"Safety Gate rejected order for {candidate.symbol}: {reason}")
                    else:
                        failed = [k for k, v in audit_record.audit_checklist.items() if not v]
                        kill_switch.record_trade_rejection(candidate.symbol, f"15-Point Audit Gate: Failed {failed}")
                        logger.info(f"15-Point Audit Gate rejected candidate {candidate.symbol} ({audit_record.audit_questions_passed}/15 checks passed, Failed: {failed})")
                else:
                    logger.info(
                        f"⏳ [Awaiting Funds] Candidate {candidate.symbol} fully approved by AI Debate & Fund Manager! "
                        f"Position size is currently 0 ({broker_name} Margin: {curr_sym}{available_margin:.2f}). "
                        f"The moment free margin is available, the next cycle will automatically size and execute this trade."
                    )
            else:
                kill_switch.record_trade_rejection(candidate.symbol, f"Risk Engine: {risk_res.rejection_reasons}")
                logger.info(f"Risk Engine rejected candidate {candidate.symbol}: {risk_res.rejection_reasons}")

        # 9. State: AI TRADE GUARDIAN CONTINUOUS MONITORING & PROTECTIVE EXITS
        self.current_state = TradingSessionState.MONITORING
        guardian_actions = await trade_guardian.evaluate_all_guardians(
            provider=self.scanner.provider,
            broker=self.broker,
        )
        if guardian_actions:
            cycle_summary["guardian_actions"] = [
                {"symbol": a[0], "action": a[1].value, "reason": a[2]}
                for a in guardian_actions
            ]

        # 10. End-of-Session Memory Consolidation & Daily EOD Reporting (Only triggered post-market)
        if phase == "POST_MARKET_CONSOLIDATION":
            memory_manager_agent.run_daily_consolidation(
                market_regime="High Volatility Sideways",
                completed_trades=trade_guardian.completed_reports,
            )

            # Generate Comprehensive Daily Closing Report
            try:
                from reporting.daily_eod_reporter import daily_eod_reporter
                await daily_eod_reporter.generate_daily_report(
                    broker=self.broker,
                    market_data_provider=self.scanner.provider,
                )
            except Exception as eod_err:
                logger.debug(f"[State Machine] EOD reporting notice: {eod_err}")

        self.current_state = TradingSessionState.REPORTING
        logger.info(f"=== COMPLETED MULTI-STOCK CYCLE: {cycle_summary} ===")
        return cycle_summary


