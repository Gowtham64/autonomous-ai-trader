"""
Isolated High-Fidelity Paper Trading Broker for Delta Exchange Crypto Perpetuals.

Simulates:
1. Exact contract multipliers per official Delta Exchange specifications.
2. Standard Delta taker commissions (0.05% on entry and exit turnover).
3. Realistic fill slippage (0.05% adverse move on market orders).
4. Delta native bracket order defense with position-presence verification.
5. Long and Short perpetual positions.
6. Reduce-only protective exits and orphaned order cancellation.
7. Total production isolation: Zero network calls to live exchange.
"""

import asyncio
import json
import os
import time
import uuid
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from core.logging import logger
from core.schemas.trade import (
    OrderExecution,
    OrderIntent,
    OrderStatus,
    PositionSnapshot,
    TradeAction,
)
from execution.interface import BaseBroker
from portfolio.position_sizer import get_delta_contract_multiplier


class DeltaPaperBroker(BaseBroker):
    """High-Fidelity Simulated Broker Adapter for Delta Exchange Crypto Perpetuals."""

    def __init__(
        self,
        initial_capital: float = 10.0,
        slippage_pct: float = 0.0005,
        taker_fee_pct: float = 0.0005,
    ):
        self.initial_capital = float(initial_capital)
        self.available_margin = float(initial_capital)
        self.used_margin = 0.0
        self.slippage_pct = slippage_pct
        self.taker_fee_pct = taker_fee_pct
        self.orders: dict[str, OrderExecution] = {}
        self.positions: dict[str, PositionSnapshot] = {}
        self.bracket_orders: dict[str, dict[str, Any]] = {}
        self.open_orders: dict[str, dict[str, Any]] = {}
        self.api_key = "paper_simulated_key"
        self.api_secret = "paper_simulated_secret"
        self._products_cache: dict[str, dict[str, Any]] = {}
        self.total_fees_paid = 0.0
        self.total_volume_usd = 0.0
        self.fill_delay_seconds = 0.05
        self.state_file = Path("data/paper_broker_state.json")
        self._load_state()

        logger.info(
            f"🛡️ [DeltaPaperBroker] Initialized high-fidelity paper broker with ${self.initial_capital:.2f} USD "
            f"(Positions: {len(self.positions)}, Orders: {len(self.orders)}, Slippage: {self.slippage_pct*100:.2f}%, Taker Fee: {self.taker_fee_pct*100:.2f}%)"
        )

    def _save_state(self) -> None:
        try:
            self.state_file.parent.mkdir(parents=True, exist_ok=True)
            data = {
                "available_margin": self.available_margin,
                "used_margin": self.used_margin,
                "total_fees_paid": self.total_fees_paid,
                "total_volume_usd": self.total_volume_usd,
                "positions": {
                    k: p.model_dump(mode="json") if hasattr(p, "model_dump") else p.dict()
                    for k, p in self.positions.items()
                },
                "orders": {
                    k: o.model_dump(mode="json") if hasattr(o, "model_dump") else o.dict()
                    for k, o in self.orders.items()
                },
            }
            with open(self.state_file, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2, default=str)
        except Exception as e:
            logger.debug(f"[DeltaPaperBroker] State save notice: {e}")

    def _load_state(self) -> None:
        if not self.state_file.exists():
            return
        try:
            with open(self.state_file, "r", encoding="utf-8") as f:
                data = json.load(f)
            self.available_margin = float(data.get("available_margin", self.available_margin))
            self.used_margin = float(data.get("used_margin", self.used_margin))
            self.total_fees_paid = float(data.get("total_fees_paid", 0.0))
            self.total_volume_usd = float(data.get("total_volume_usd", 0.0))
            for k, p_raw in data.get("positions", {}).items():
                self.positions[k] = PositionSnapshot.model_validate(p_raw)
            for k, o_raw in data.get("orders", {}).items():
                self.orders[k] = OrderExecution.model_validate(o_raw)
        except Exception as e:
            logger.debug(f"[DeltaPaperBroker] State load notice: {e}")

    def _resolve_multiplier(self, symbol: str) -> float:
        mult = get_delta_contract_multiplier(symbol)
        return mult if mult is not None else 1.0

    def update_mark_prices(self, mark_prices: dict[str, float]) -> None:
        """Updates live mark prices on open positions and recalculates unrealized P&L."""
        for sym, mark_px in mark_prices.items():
            pos_id = f"POS-{sym}"
            if pos_id in self.positions and self.positions[pos_id].is_active:
                pos = self.positions[pos_id]
                mult = self._resolve_multiplier(sym)
                is_short = pos.side.upper() == "SELL"
                pos.current_price = float(mark_px)
                pnl = ((pos.entry_price - mark_px) if is_short else (mark_px - pos.entry_price)) * pos.quantity * mult
                pos.unrealized_pnl = round(pnl, 4)

    def get_unrealized_pnl(self) -> float:
        """Returns aggregate mark-to-market unrealized P&L across all active positions."""
        return round(sum(p.unrealized_pnl for p in self.positions.values() if p.is_active and p.quantity > 0), 4)

    async def get_funds(self) -> dict[str, float]:
        cash_balance = round(self.available_margin + self.used_margin, 4)
        unrealized = self.get_unrealized_pnl()
        mtm_equity = round(cash_balance + unrealized, 4)
        # Margin availability accounts for open adverse mark moves
        adjusted_available = max(0.0, round(self.available_margin + min(0.0, unrealized), 4))
        return {
            "total_capital": cash_balance,
            "cash_balance": cash_balance,
            "available_margin": adjusted_available,
            "used_margin": round(self.used_margin, 4),
            "unrealized_pnl": unrealized,
            "mark_to_market_equity": mtm_equity,
        }

    async def get_positions(self, force: bool = False) -> list[PositionSnapshot]:
        return [p for p in self.positions.values() if p.is_active and p.quantity > 0]

    async def get_products(self) -> dict[str, dict[str, Any]]:
        return self._products_cache

    async def place_bracket_order(
        self,
        product_id: int,
        product_symbol: str,
        stop_loss: float | None = None,
        take_profit: float | None = None,
        trigger_method: str = "last_traded_price",
    ) -> dict[str, Any]:
        """Simulates native Delta bracket placement with open position verification."""
        # Realistic exchange behavior: verify open position exists
        pos_id = f"POS-{product_symbol}"
        if pos_id not in self.positions or not self.positions[pos_id].is_active:
            logger.warning(f"⚠️ [DeltaPaperBroker] Bracket order rejected: no open position for {product_symbol}")
            return {"success": False, "error": {"code": "no_open_position"}}

        bracket_id = f"BRK-{uuid.uuid4().hex[:8].upper()}"
        self.bracket_orders[product_symbol] = {
            "id": bracket_id,
            "product_id": product_id,
            "product_symbol": product_symbol,
            "stop_loss": stop_loss,
            "take_profit": take_profit,
            "created_at": datetime.now(UTC),
        }
        logger.info(
            f"🛡️ [DeltaPaperBroker] Native Bracket Attached: {product_symbol} "
            f"SL=${stop_loss}, TP=${take_profit} (ID: {bracket_id})"
        )
        return {"success": True, "result": {"id": bracket_id}}

    async def cancel_product_orders(self, product_id: int) -> int:
        """Cancels all open orders (including bracket/stop orders) for a specific product ID."""
        cancelled = 0
        sym_to_clear = [s for s, b in self.bracket_orders.items() if b.get("product_id") == product_id]
        for s in sym_to_clear:
            del self.bracket_orders[s]
            cancelled += 1

        to_del = [oid for oid, o in self.open_orders.items() if o.get("product_id") == product_id]
        for oid in to_del:
            del self.open_orders[oid]
            cancelled += 1

        if cancelled > 0:
            logger.info(f"🛡️ [DeltaPaperBroker] Cancelled {cancelled} residual orders for product {product_id}")
        return cancelled

    async def cancel_stale_orders(self, max_age_seconds: int = 180) -> int:
        now = time.time()
        cancelled = 0
        to_del = []
        for oid, o in self.open_orders.items():
            if now - o.get("created_ts", now) > max_age_seconds:
                to_del.append(oid)
        for oid in to_del:
            del self.open_orders[oid]
            cancelled += 1
        return cancelled

    async def place_order(self, order: OrderIntent) -> OrderExecution:
        logger.info(
            f"🚀 [DeltaPaperBroker] Submitting {order.action.value} order for {order.symbol} "
            f"(Qty: {order.quantity}, Limit: ${order.price or 0.0})"
        )
        mult = self._resolve_multiplier(order.symbol)
        base_price = order.price if (order.price and order.price > 0) else (order.stop_loss or 100.0)

        # 1. Simulate Slippage (adverse execution price) with adaptive precision
        decimals = 8 if base_price < 0.01 else (6 if base_price < 1.0 else 4)
        if order.action == TradeAction.BUY:
            executed_price = round(base_price * (1.0 + self.slippage_pct), decimals)
        else:
            executed_price = round(base_price * (1.0 - self.slippage_pct), decimals)

        # 2. Turnover & Commission Calculation
        turnover = executed_price * order.quantity * mult
        brokerage_fee = round(turnover * self.taker_fee_pct, 4)
        slippage_val = round(abs(executed_price - base_price), decimals)

        # Leverage assumption (5x default on Delta)
        leverage = 5.0
        required_margin = round(turnover / leverage, 4)

        is_reduce_only = getattr(order, "reduce_only", False)
        pos_id = f"POS-{order.symbol}"

        # 3. Handle Margin & Position State
        if is_reduce_only:
            if pos_id not in self.positions or not self.positions[pos_id].is_active:
                logger.warning(
                    f"❌ [DeltaPaperBroker] REJECTED: Reduce-only order rejected (no active position to close for {order.symbol})"
                )
                return OrderExecution(
                    order_id=f"REJ-{uuid.uuid4().hex[:6].upper()}",
                    client_order_id=order.client_order_id,
                    symbol=order.symbol,
                    status=OrderStatus.REJECTED,
                    filled_quantity=0,
                    average_price=0.0,
                    slippage=0.0,
                    brokerage_fee=0.0,
                    taxes_and_charges=0.0,
                )
            # Closing / Reducing existing position
            self.total_fees_paid += brokerage_fee
            self.total_volume_usd += turnover

            pos = self.positions[pos_id]
            is_pos_short = pos.side.upper() == "SELL"
            if is_pos_short:
                gross_pnl = (pos.entry_price - executed_price) * order.quantity * mult
            else:
                gross_pnl = (executed_price - pos.entry_price) * order.quantity * mult

            net_pnl = gross_pnl - brokerage_fee
            # Release margin
            pos_turnover = pos.entry_price * order.quantity * mult
            released_margin = pos_turnover / leverage
            self.used_margin = max(0.0, self.used_margin - released_margin)
            self.available_margin += (released_margin + net_pnl)

            pos.quantity -= order.quantity
            if pos.quantity <= 0:
                pos.is_active = False
                pos.quantity = 0

            # Clear residual bracket orders
            if order.symbol in self.bracket_orders:
                del self.bracket_orders[order.symbol]
        else:
            # Check margin
            if (required_margin + brokerage_fee) > self.available_margin:
                logger.warning(
                    f"❌ [DeltaPaperBroker] REJECTED: Insufficient margin (Need ${required_margin + brokerage_fee:.4f}, "
                    f"Avail ${self.available_margin:.4f}) for {order.symbol}"
                )
                return OrderExecution(
                    order_id=f"REJ-{uuid.uuid4().hex[:6].upper()}",
                    client_order_id=order.client_order_id,
                    symbol=order.symbol,
                    status=OrderStatus.REJECTED,
                    filled_quantity=0,
                    average_price=0.0,
                    slippage=0.0,
                    brokerage_fee=0.0,
                    taxes_and_charges=0.0,
                )

            self.available_margin -= (required_margin + brokerage_fee)
            self.used_margin += required_margin
            self.total_fees_paid += brokerage_fee
            self.total_volume_usd += turnover

            # Open Position
            is_short = order.action == TradeAction.SELL
            side_str = "SELL" if is_short else "BUY"

            self.positions[pos_id] = PositionSnapshot(
                position_id=pos_id,
                symbol=order.symbol,
                exchange="DELTA",
                side=side_str,
                quantity=order.quantity,
                entry_price=executed_price,
                current_price=executed_price,
                stop_loss=order.stop_loss,
                target_1=order.target,
                highest_price_seen=executed_price,
                lowest_price_seen=executed_price,
                unrealized_pnl=0.0,
                opened_at=datetime.now(UTC),
                is_active=True,
            )

        order_id = f"PAP-DLT-{uuid.uuid4().hex[:8].upper()}"
        exec_report = OrderExecution(
            order_id=order_id,
            client_order_id=order.client_order_id,
            symbol=order.symbol,
            status=OrderStatus.FILLED,
            filled_quantity=order.quantity,
            average_price=executed_price,
            slippage=slippage_val,
            brokerage_fee=brokerage_fee,
            taxes_and_charges=0.0,
            executed_at=datetime.now(UTC),
        )
        self.orders[order_id] = exec_report
        self._save_state()

        logger.info(
            f"✅ [DeltaPaperBroker] FILLED {order.action.value} {order.quantity}x {order.symbol} @ "
            f"${executed_price:.4f} (Fee: ${brokerage_fee:.4f}, Slippage: ${slippage_val:.4f}, Order ID: {order_id})"
        )
        return exec_report

    async def get_order_book(self) -> list[dict]:
        orders_list = []
        for o in self.orders.values():
            orders_list.append({
                "order_id": o.order_id,
                "client_order_id": o.client_order_id,
                "symbol": o.symbol,
                "order_type": "MARKET",
                "side": "BUY" if "BUY" in str(getattr(o, "action", "BUY")).upper() else "SELL",
                "quantity": o.filled_quantity,
                "price": o.average_price,
                "status": o.status.value if hasattr(o.status, "value") else str(o.status),
                "timestamp": o.executed_at.isoformat() if hasattr(o.executed_at, "isoformat") else str(o.executed_at),
            })
        return orders_list

    async def get_trade_book(self) -> list[dict]:
        trades_list = []
        for o in self.orders.values():
            if o.status == OrderStatus.FILLED:
                trades_list.append({
                    "trade_id": o.order_id,
                    "order_id": o.order_id,
                    "symbol": o.symbol,
                    "side": "BUY" if "BUY" in str(getattr(o, "action", "BUY")).upper() else "SELL",
                    "quantity": o.filled_quantity,
                    "price": o.average_price,
                    "timestamp": o.executed_at.isoformat() if hasattr(o.executed_at, "isoformat") else str(o.executed_at),
                })
        return trades_list

    async def cancel_order(self, order_id: str, product_id: int | None = None) -> bool:
        if order_id in self.orders:
            self.orders[order_id].status = OrderStatus.CANCELLED
            self._save_state()
            return True
        if order_id in self.open_orders:
            del self.open_orders[order_id]
            self._save_state()
            return True
        return False

    async def get_order_status(self, order_id: str) -> OrderStatus:
        if order_id in self.orders:
            return self.orders[order_id].status
        return OrderStatus.REJECTED
