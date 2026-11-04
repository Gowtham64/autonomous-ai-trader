"""Phase 6: Isolated Paper-Only Valuation Patch Validation.

Runs a side-by-side evaluation of identical historical/live market data snapshots
comparing the Pre-Patch (LTP/Cash-based) vs. Post-Patch (Mark-to-Market) pipelines.

Mandatory Safety Guarantees:
- Strictly executes in PAPER mode; zero network order placement.
- Does not affect or interact with running soak daemon PID 17998.
"""

import json
from datetime import UTC, datetime
from pathlib import Path
from core.config.settings import TradingMode, settings
from core.schemas.trade import PositionSnapshot, TradeAction, TradeDecision
from core.valuation import (
    ContractType,
    PriceSource,
    calculate_unrealized_pnl,
    evaluate_bracket_condition,
    resolve_contract_multiplier,
    value_portfolio,
    value_position,
)
from risk.engine import DeterministicRiskEngine

WORKSPACE_ROOT = Path("/Users/gowthamp/Trading-AI-Agents-Live")


def run_isolated_validation():
    print("================================================================================")
    print("PHASE 6: ISOLATED PAPER-ONLY VALUATION AND RISK-GATE PATCH VALIDATION")
    print("================================================================================")

    # 1. Environment & Safety Verification
    from core.config.settings import settings
    assert settings.LIVE_TRADING_ENABLED is False, "FATAL: Live trading must remain disabled!"
    print(f"Safety Gate: LIVE_TRADING_ENABLED = {settings.LIVE_TRADING_ENABLED}")
    print(f"Trading Mode: {settings.TRADING_MODE.value}")

    # 2. Input Snapshot (Exact state from Phase 4A soak snapshot at 2026-10-22T19:05:43Z)
    cash_capital = 11.7062
    peak_equity = 11.7104

    pos_xrp = PositionSnapshot(
        position_id="POS-XRPUSDT",
        symbol="XRPUSDT",
        exchange="DELTA",
        side="BUY",
        quantity=8,
        entry_price=1.3420,
        current_price=1.3420,
        stop_loss=1.3212,
        target_1=1.3836,
        highest_price_seen=1.3420,
        lowest_price_seen=1.3420,
        unrealized_pnl=0.0,
        opened_at=datetime.now(UTC),
        is_active=True,
    )

    pos_doge = PositionSnapshot(
        position_id="POS-DOGEUSDT",
        symbol="DOGEUSDT",
        exchange="DELTA",
        side="BUY",
        quantity=1,
        entry_price=0.083392,
        current_price=0.083392,
        stop_loss=0.0821,
        target_1=0.0860,
        highest_price_seen=0.083392,
        lowest_price_seen=0.083392,
        unrealized_pnl=0.0,
        opened_at=datetime.now(UTC),
        is_active=True,
    )

    tickers = {
        "XRPUSDT": {
            "symbol": "XRPUSDT",
            "close": 1.3413,  # 24h stale LTP
            "mark_price": 1.30771927,  # Live mark price
            "is_stale": False,
            "drift_ms": 0,
        },
        "DOGEUSDT": {
            "symbol": "DOGEUSDT",
            "close": None,  # Null LTP (zero trades)
            "mark_price": 0.07844058,  # Live mark price
            "is_stale": False,
            "drift_ms": 0,
        },
    }

    # -------------------------------------------------------------------------
    # 3. OLD PIPELINE CALCULATION (Pre-Patch)
    # -------------------------------------------------------------------------
    # XRP P&L: using close, mult=1.0
    old_xrp_pnl = (tickers["XRPUSDT"]["close"] - pos_xrp.entry_price) * pos_xrp.quantity
    # DOGE P&L: close is None -> skipped!
    old_doge_pnl = 0.0
    old_total_unrealized = old_xrp_pnl + old_doge_pnl
    old_reported_equity = cash_capital  # Cash capital used as equity
    old_drawdown = peak_equity - old_reported_equity
    old_drawdown_pct = (old_drawdown / peak_equity * 100.0) if peak_equity > 0 else 0.0

    # Risk Engine under Old Pipeline
    old_engine = DeterministicRiskEngine(total_equity=old_reported_equity, peak_equity=peak_equity)
    candidate_dec = TradeDecision(
        analysis_id="DEC-VAL-01",
        symbol="SOLUSDT",
        exchange="DELTA",
        decision=TradeAction.BUY,
        confidence=0.85,
        entry_price=100.0,
        stop_loss=97.0,
        target_1=107.0,
    )
    old_risk_check = old_engine.evaluate_trade_intent(candidate_dec, [pos_xrp, pos_doge])

    # -------------------------------------------------------------------------
    # 4. NEW PIPELINE CALCULATION (Post-Patch)
    # -------------------------------------------------------------------------
    val_xrp = value_position(pos_xrp, tickers["XRPUSDT"], preferred_source=PriceSource.MARK_PRICE)
    val_doge = value_position(pos_doge, tickers["DOGEUSDT"], preferred_source=PriceSource.MARK_PRICE)

    port_val = value_portfolio(
        cash_balance=cash_capital,
        used_margin=3.8150,
        available_margin=7.8912,
        positions=[pos_xrp, pos_doge],
        ticker_map=tickers,
        peak_equity=peak_equity,
    )

    # Risk Engine under New Pipeline (fed with true MtM equity)
    new_engine = DeterministicRiskEngine(total_equity=port_val.mark_to_market_equity, peak_equity=peak_equity)
    new_risk_check = new_engine.evaluate_trade_intent(candidate_dec, [pos_xrp, pos_doge])

    # Bracket Evaluation under New Pipeline
    # 1. Under "mark_price" trigger method:
    brk_xrp_mark = evaluate_bracket_condition(pos_xrp, tickers["XRPUSDT"], trigger_method="mark_price")
    brk_doge_mark = evaluate_bracket_condition(pos_doge, tickers["DOGEUSDT"], trigger_method="mark_price")

    # 2. Under "last_traded_price" trigger method:
    brk_xrp_ltp = evaluate_bracket_condition(pos_xrp, tickers["XRPUSDT"], trigger_method="last_traded_price")
    brk_doge_ltp = evaluate_bracket_condition(pos_doge, tickers["DOGEUSDT"], trigger_method="last_traded_price")

    # -------------------------------------------------------------------------
    # 5. Output Results Comparison
    # -------------------------------------------------------------------------
    comparison = {
        "xrp_unrealized_pnl": {
            "pre_patch_ltp": round(old_xrp_pnl, 4),
            "post_patch_mtm": val_xrp.gross_unrealized_pnl,
            "discrepancy": round(val_xrp.gross_unrealized_pnl - old_xrp_pnl, 4),
        },
        "doge_unrealized_pnl": {
            "pre_patch_ltp": round(old_doge_pnl, 4),
            "post_patch_mtm": val_doge.gross_unrealized_pnl,
            "discrepancy": round(val_doge.gross_unrealized_pnl - old_doge_pnl, 4),
        },
        "portfolio_unrealized_pnl": {
            "pre_patch_ltp": round(old_total_unrealized, 4),
            "post_patch_mtm": port_val.total_unrealized_pnl,
            "discrepancy": round(port_val.total_unrealized_pnl - old_total_unrealized, 4),
        },
        "reported_equity": {
            "pre_patch_cash": round(old_reported_equity, 4),
            "post_patch_mtm": port_val.mark_to_market_equity,
            "discrepancy": round(port_val.mark_to_market_equity - old_reported_equity, 4),
        },
        "portfolio_drawdown": {
            "pre_patch_pct": round(old_drawdown_pct, 2),
            "post_patch_pct": port_val.drawdown_pct,
            "true_drawdown_difference_pct": round(port_val.drawdown_pct - old_drawdown_pct, 2),
        },
        "bracket_evaluation": {
            "xrp_mark_trigger": brk_xrp_mark,
            "doge_mark_trigger": brk_doge_mark,
            "xrp_ltp_trigger": brk_xrp_ltp,
            "doge_ltp_failsafe_trigger": brk_doge_ltp,
        },
    }

    print("\n--- SIDE-BY-SIDE PIPELINE COMPARISON ---")
    print(f"XRPUSDT PnL     : Old = ${comparison['xrp_unrealized_pnl']['pre_patch_ltp']:+.4f} | New = ${comparison['xrp_unrealized_pnl']['post_patch_mtm']:+.4f}")
    print(f"DOGEUSDT PnL    : Old = ${comparison['doge_unrealized_pnl']['pre_patch_ltp']:+.4f} | New = ${comparison['doge_unrealized_pnl']['post_patch_mtm']:+.4f}")
    print(f"Total Unrealized: Old = ${comparison['portfolio_unrealized_pnl']['pre_patch_ltp']:+.4f} | New = ${comparison['portfolio_unrealized_pnl']['post_patch_mtm']:+.4f}")
    print(f"Portfolio Equity: Old = ${comparison['reported_equity']['pre_patch_cash']:.4f} | New = ${comparison['reported_equity']['post_patch_mtm']:.4f}")
    print(f"Drawdown Pct    : Old = {comparison['portfolio_drawdown']['pre_patch_pct']:.2f}% | New = {comparison['portfolio_drawdown']['post_patch_pct']:.2f}%")
    print("--------------------------------------------------------------------------------")
    print(f"Bracket DOGE Failsafe Trigger: {brk_doge_ltp[0]} (Reason: {brk_doge_ltp[1]} | {brk_doge_ltp[2]})")
    print(f"Bracket XRP Mark Trigger    : {brk_xrp_mark[0]} (Reason: {brk_xrp_mark[1]} | {brk_xrp_mark[2]})")

    results_file = WORKSPACE_ROOT / "data" / "patch_validation_results.json"
    with open(results_file, "w") as f:
        json.dump(comparison, f, indent=2)
    print(f"Validation evidence recorded in {results_file.name}")
    print("================================================================================")
    return comparison


if __name__ == "__main__":
    run_isolated_validation()
