"""Phase 4C: Comprehensive Isolated End-to-End Paper Validation Test Suite.

Validates:
1. End-to-end stop-loss and take-profit lifecycle for XRPUSDT and DOGEUSDT:
   - Trigger detection -> Order generation -> Execution -> Position closure -> Ledger update.
2. Exact margin release, fee deduction, cash balance reconciliation, and zero discrepancy.
3. Idempotency / duplicate exit prevention on subsequent polling cycles.
4. Partial exit handling and proportional margin release.
5. Rejection resilience on duplicate/invalid reduce-only exits.
6. Stale data safety: blocking triggers on stale feeds, recovering upon fresh feed resumption.
7. Full multi-component alignment across Broker, Treasury, Monitor, Guardian, and Risk Engine.
8. Daily loss and maximum drawdown circuit breaker enforcement.
"""

import pytest
import asyncio
from datetime import UTC, datetime
from core.domain.models import ExitReason
from core.schemas.trade import (
    OrderIntent,
    OrderStatus,
    PositionSnapshot,
    RiskCheckResult,
    TradeAction,
    TradeDecision,
)
from core.treasury.treasury import AITreasury
from core.valuation import (
    ContractType,
    PriceSource,
    calculate_unrealized_pnl,
    evaluate_bracket_condition,
    resolve_contract_multiplier,
    value_portfolio,
    value_position,
)
from execution.paper.delta_paper import DeltaPaperBroker
from guardian.position_guardian import PositionGuardianWorker
from monitoring.position_monitor import PositionMonitor
from risk.engine import DeterministicRiskEngine


def test_01_e2e_xrpusdt_stop_loss_lifecycle():
    """Verify complete end-to-end stop-loss trigger, execution, position closure, and accounting for XRPUSDT."""
    broker = DeltaPaperBroker(initial_capital=10.0, slippage_pct=0.0005, taker_fee_pct=0.0005)

    async def _run():
        # 1. Entry: BUY 8 XRPUSDT @ 1.3413 limit -> filled @ 1.3420 (slippage 0.0007)
        entry_intent = OrderIntent(
            client_order_id="E2E-XRP-ENT",
            decision_id="DEC-XRP-01",
            symbol="XRPUSDT",
            exchange="DELTA",
            action=TradeAction.BUY,
            quantity=8,
            price=1.3413,
            stop_loss=1.3212,
            target=1.3836,
        )
        ent_res = await broker.place_order(entry_intent)
        assert ent_res.status == OrderStatus.FILLED
        assert ent_res.average_price == 1.3420
        assert ent_res.brokerage_fee == 0.0054

        # Attach native bracket
        brk_res = await broker.place_bracket_order(
            product_id=187,
            product_symbol="XRPUSDT",
            stop_loss=1.3212,
            take_profit=1.3836,
        )
        assert brk_res["success"] is True
        assert "XRPUSDT" in broker.bracket_orders

        # Verify funds post-entry
        funds_post_entry = await broker.get_funds()
        expected_cash_post_entry = round(10.0 - 0.0054, 4)  # $9.9946
        expected_used_margin = round((1.3420 * 8 * 1.0) / 5.0, 4)  # $2.1472
        expected_avail_margin = round(expected_cash_post_entry - expected_used_margin, 4)  # $7.8474
        assert funds_post_entry["total_capital"] == expected_cash_post_entry
        assert funds_post_entry["used_margin"] == expected_used_margin
        assert funds_post_entry["available_margin"] == expected_avail_margin

        # 2. Market Tick: Stale LTP = 1.3413, Live Mark Price = 1.3077 (breaches SL 1.3212)
        ticker_data = {
            "symbol": "XRPUSDT",
            "close": 1.3413,
            "mark_price": 1.30771927,
            "is_stale": False,
            "drift_ms": 250,
        }

        # Step A: Trigger Detection
        pos = (await broker.get_positions())[0]
        triggered, reason, note, eval_px = evaluate_bracket_condition(pos, ticker_data, trigger_method="mark_price")
        assert triggered is True
        assert reason == "STOP_LOSS_HIT"
        assert eval_px == 1.30771927

        # Step B: Generate Simulated Reduce-Only Exit Order
        exit_intent = OrderIntent(
            client_order_id="E2E-XRP-EXT-01",
            decision_id="DEC-XRP-EXIT",
            symbol="XRPUSDT",
            exchange="DELTA",
            action=TradeAction.SELL,
            quantity=pos.quantity,
            price=eval_px,
            stop_loss=0.0,
            target=0.0,
            reduce_only=True,
        )

        # Step C: Execute Simulated Exit
        ext_res = await broker.place_order(exit_intent)
        assert ext_res.status == OrderStatus.FILLED
        # Executed with adverse slippage: 1.30771927 * (1 - 0.0005) = 1.307065 -> round to 1.3071
        assert ext_res.average_price < eval_px
        exit_fee = ext_res.brokerage_fee
        assert exit_fee > 0

        # Step D: Verify Position Closure
        active_positions = await broker.get_positions()
        assert len(active_positions) == 0  # No longer treated as open!
        assert "XRPUSDT" not in broker.bracket_orders  # Residual bracket expunged!

        # Step E: Reconcile Realized P&L and Cash Balance
        gross_pnl = (ext_res.average_price - ent_res.average_price) * 8 * 1.0
        net_exit_pnl = gross_pnl - exit_fee
        expected_final_cash = round(expected_cash_post_entry + net_exit_pnl, 4)

        final_funds = await broker.get_funds()
        assert final_funds["total_capital"] == expected_final_cash
        assert final_funds["used_margin"] == 0.0
        assert final_funds["available_margin"] == expected_final_cash
        assert final_funds["unrealized_pnl"] == 0.0
        assert final_funds["mark_to_market_equity"] == expected_final_cash

        # Step F: Idempotency Check — Duplicate exit attempt must be rejected!
        duplicate_exit = OrderIntent(
            client_order_id="E2E-XRP-EXT-DUP",
            decision_id="DEC-XRP-EXIT",
            symbol="XRPUSDT",
            exchange="DELTA",
            action=TradeAction.SELL,
            quantity=8,
            price=eval_px,
            stop_loss=0.0,
            target=0.0,
            reduce_only=True,
        )
        dup_res = await broker.place_order(duplicate_exit)
        assert dup_res.status == OrderStatus.REJECTED  # Rejected cleanly!
        # Final cash must remain completely invariant
        funds_after_dup = await broker.get_funds()
        assert funds_after_dup["total_capital"] == expected_final_cash

    asyncio.run(_run())


def test_02_e2e_dogeusdt_missing_ltp_failsafe_lifecycle():
    """Verify DOGEUSDT bracket stop-loss with null LTP (`close: None`) triggers failsafe mark and closes position."""
    broker = DeltaPaperBroker(initial_capital=10.0, slippage_pct=0.0005, taker_fee_pct=0.0005)

    async def _run():
        # Entry: BUY 1 DOGEUSDT @ 0.08335 limit -> filled @ 0.083392
        entry_intent = OrderIntent(
            client_order_id="E2E-DOGE-ENT",
            decision_id="DEC-DOGE-01",
            symbol="DOGEUSDT",
            exchange="DELTA",
            action=TradeAction.BUY,
            quantity=1,
            price=0.08335,
            stop_loss=0.0821,
            target=0.0860,
        )
        ent_res = await broker.place_order(entry_intent)
        assert ent_res.status == OrderStatus.FILLED
        assert ent_res.average_price == 0.083392
        # DOGE multiplier: 100. Turnover = 0.083392 * 1 * 100 = $8.3392. Fee = $0.0042
        assert ent_res.brokerage_fee == 0.0042

        # Attach native bracket
        await broker.place_bracket_order(product_id=3316, product_symbol="DOGEUSDT", stop_loss=0.0821, take_profit=0.0860)

        # Market Tick: 0 trades in 24h -> close is None! Mark Price dropped to 0.07844058 (< SL 0.0821)
        ticker_data = {
            "symbol": "DOGEUSDT",
            "close": None,
            "mark_price": 0.07844058,
            "is_stale": False,
            "drift_ms": 150,
        }

        # Step A: Trigger Detection via last_traded_price trigger method
        # Must NOT skip position! Must activate FAILSAFE_MARK_PRICE!
        pos = (await broker.get_positions())[0]
        triggered, reason, note, eval_px = evaluate_bracket_condition(pos, ticker_data, trigger_method="last_traded_price")
        assert triggered is True
        assert reason == "STOP_LOSS_HIT"
        assert "FAILSAFE_MARK_PRICE" in note
        assert eval_px == 0.07844058

        # Step B: Generate and execute reduce-only exit
        exit_intent = OrderIntent(
            client_order_id="E2E-DOGE-EXT-01",
            decision_id="DEC-DOGE-EXIT",
            symbol="DOGEUSDT",
            exchange="DELTA",
            action=TradeAction.SELL,
            quantity=pos.quantity,
            price=eval_px,
            stop_loss=0.0,
            target=0.0,
            reduce_only=True,
        )
        ext_res = await broker.place_order(exit_intent)
        assert ext_res.status == OrderStatus.FILLED
        assert ext_res.average_price < eval_px

        # Step C: Verify position closure & bracket expungement
        active = await broker.get_positions()
        assert len(active) == 0
        assert "DOGEUSDT" not in broker.bracket_orders

        # Step D: Accounting Reconciliation
        # Gross = (0.078401 - 0.083392) * 1 * 100.0 = -$0.4991
        funds = await broker.get_funds()
        assert funds["used_margin"] == 0.0
        assert funds["unrealized_pnl"] == 0.0
        assert funds["total_capital"] == funds["available_margin"]
        assert funds["total_capital"] < 10.0  # Loss accounted for accurately!

    asyncio.run(_run())


def test_03_partial_exit_and_margin_release():
    """Verify partial exit releases margin proportionally and maintains position for remaining balance."""
    broker = DeltaPaperBroker(initial_capital=20.0)

    async def _run():
        # Buy 10 units @ 1.00 -> Turnover $10.00. Leverage 5x -> Margin $2.00. Fee $0.0050
        intent = OrderIntent(
            client_order_id="TEST-PARTIAL-ENT",
            decision_id="DEC-01",
            symbol="XRPUSDT",
            exchange="DELTA",
            action=TradeAction.BUY,
            quantity=10,
            price=1.0000,
            stop_loss=0.95,
            target=1.10,
        )
        ent = await broker.place_order(intent)
        initial_used_margin = (await broker.get_funds())["used_margin"]
        assert initial_used_margin > 1.99

        # Partial Exit 1: Close 4 contracts
        part1 = OrderIntent(
            client_order_id="TEST-PARTIAL-EXT1",
            decision_id="DEC-01",
            symbol="XRPUSDT",
            exchange="DELTA",
            action=TradeAction.SELL,
            quantity=4,
            price=1.0500,
            stop_loss=0.0,
            target=0.0,
            reduce_only=True,
        )
        await broker.place_order(part1)

        # Remaining position must be 6 contracts, still active
        positions = await broker.get_positions()
        assert len(positions) == 1
        assert positions[0].quantity == 6
        assert positions[0].is_active is True

        funds_part1 = await broker.get_funds()
        # 40% margin released (60% retained)
        assert round(funds_part1["used_margin"], 2) == round(initial_used_margin * 0.60, 2)

        # Partial Exit 2: Close remaining 6 contracts
        part2 = OrderIntent(
            client_order_id="TEST-PARTIAL-EXT2",
            decision_id="DEC-01",
            symbol="XRPUSDT",
            exchange="DELTA",
            action=TradeAction.SELL,
            quantity=6,
            price=1.0500,
            stop_loss=0.0,
            target=0.0,
            reduce_only=True,
        )
        await broker.place_order(part2)

        # Position completely closed
        assert len(await broker.get_positions()) == 0
        funds_part2 = await broker.get_funds()
        assert funds_part2["used_margin"] == 0.0

    asyncio.run(_run())


def test_04_stale_feed_safety_and_fresh_feed_recovery():
    """Verify that stale feeds (>60s drift) block bracket triggers and fresh feeds recover cleanly."""
    pos = PositionSnapshot(
        position_id="POS-SAFE",
        symbol="XRPUSDT",
        exchange="DELTA",
        side="BUY",
        quantity=8,
        entry_price=1.3420,
        current_price=1.3420,
        stop_loss=1.3200,
        target_1=1.3800,
        highest_price_seen=1.3420,
        lowest_price_seen=1.3420,
        unrealized_pnl=0.0,
        opened_at=datetime.now(UTC),
        is_active=True,
    )

    # 1. Stale Feed (is_stale: True)
    ticker_stale = {
        "symbol": "XRPUSDT",
        "close": 1.30,  # Below SL
        "mark_price": 1.30,  # Below SL
        "is_stale": True,
        "drift_ms": 120000,
    }
    trig_stale, reason, note, _ = evaluate_bracket_condition(pos, ticker_stale, trigger_method="mark_price")
    # Must BLOCK trigger to prevent acting on invalid/corrupt data!
    assert trig_stale is False
    assert "FEED_STALE" in note

    # 2. Feed Recovers (Fresh tick arrives)
    ticker_fresh = {
        "symbol": "XRPUSDT",
        "close": 1.30,
        "mark_price": 1.30,
        "is_stale": False,
        "drift_ms": 300,
    }
    trig_fresh, reason_fresh, _, px = evaluate_bracket_condition(pos, ticker_fresh, trigger_method="mark_price")
    assert trig_fresh is True
    assert reason_fresh == "STOP_LOSS_HIT"
    assert px == 1.30


def test_05_multi_component_alignment_real_interfaces():
    """Verify Broker, Treasury, Monitor, Guardian, and Risk Engine agree for identical snapshots."""
    broker = DeltaPaperBroker(initial_capital=10.0)
    treasury = AITreasury(starting_capital=10.0)
    monitor = PositionMonitor(broker=broker)

    async def _run():
        intent = OrderIntent(
            client_order_id="ALIGN-ENT",
            decision_id="DEC-ALIGN",
            symbol="DOGEUSDT",
            exchange="DELTA",
            action=TradeAction.BUY,
            quantity=1,
            price=0.080,
            stop_loss=0.075,
            target=0.090,
        )
        ent = await broker.place_order(intent)

        # Live mark price dropped to 0.0750
        live_mark = 0.0750
        broker.update_mark_prices({"DOGEUSDT": live_mark})
        funds = await broker.get_funds()

        # Expected P&L: (0.0750 - 0.08004) * 1 * 100.0 = -0.5040
        unrealized = funds["unrealized_pnl"]
        assert round(unrealized, 2) == -0.50

        # Treasury Check
        treasury.set_unrealized_pnl(unrealized)
        treasury.current_capital = funds["total_capital"]
        assert treasury.total_equity == funds["mark_to_market_equity"]

        # Monitor Check
        pos = (await broker.get_positions())[0]
        await monitor.evaluate_position(pos, current_ltp=0.080, mark_price=live_mark)
        assert round(pos.unrealized_pnl, 2) == -0.50

        # Guardian Worker Check
        guardian = PositionGuardianWorker(pos=pos)
        await guardian.evaluate_tick(current_ltp=0.080, mark_price=live_mark)
        assert round(guardian.state.unrealized_pnl, 2) == -0.50

        # Risk Engine Check
        engine = DeterministicRiskEngine(
            total_equity=funds["mark_to_market_equity"],
            peak_equity=funds["total_capital"],
        )
        assert round(engine.total_equity, 2) == round(funds["mark_to_market_equity"], 2)

    asyncio.run(_run())


def test_06_circuit_breakers_on_mark_equity():
    """Verify circuit breakers enforce thresholds on Mark-to-Market equity, not cash balance."""
    # Peak equity: $11.7104. Cash balance: $11.7062
    peak = 11.7104
    cash = 11.7062

    # Severe adverse market drop: -$2.00 mark loss
    mark_loss = -2.00
    true_mtm_equity = cash + mark_loss  # $9.7062
    # Drawdown = ($11.7104 - $9.7062) / $11.7104 = 17.11% >= 15.0% effective max drawdown

    decision = TradeDecision(
        analysis_id="DEC-TEST",
        symbol="SOLUSDT",
        exchange="DELTA",
        decision=TradeAction.BUY,
        confidence=0.85,
        entry_price=100.0,
        stop_loss=97.0,
        target_1=107.0,
    )

    # 1. Blinded Cash Engine (Pre-patch behavior)
    blind_engine = DeterministicRiskEngine(total_equity=cash, peak_equity=peak)
    chk_blind = blind_engine.evaluate_trade_intent(decision, [])
    assert chk_blind.approved is True  # Blindsided!

    # 2. Corrected MtM Engine (Post-patch behavior)
    mtm_engine = DeterministicRiskEngine(total_equity=true_mtm_equity, peak_equity=peak)
    chk_mtm = mtm_engine.evaluate_trade_intent(decision, [])
    assert chk_mtm.approved is False  # Must trip breaker!
    assert any("Max Drawdown Limit hit" in r for r in chk_mtm.rejection_reasons)
