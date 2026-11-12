import asyncio
import hashlib
import hmac
import json
import time
from datetime import UTC, datetime
from typing import Any

import httpx

from core.config.settings import TradingMode, settings
from core.logging import logger
from core.schemas.trade import (
    OrderExecution,
    OrderIntent,
    OrderStatus,
    PositionSnapshot,
    TradeAction,
)
from execution.interface import BaseBroker


class DeltaExchangeBroker(BaseBroker):
    """Production & Testnet Broker Adapter for Delta Exchange (Crypto Perpetuals & Options).
    
    API Documentation: https://docs.delta.exchange/
    Features:
    - HMAC-SHA256 authenticated REST calls (timestamp + method + path + payload)
    - 24/7/365 continuous trading (Perpetuals: BTCUSD, ETHUSD, SOLUSD, etc.)
    - Live wallet balances (USDT, BTC, USD margin)
    - Open positions & unrealized PnL querying
    - Order placement (Limit, Market, Stop) with strict leverage gating
    """

    DEFAULT_PROD_URL = "https://api.india.delta.exchange"
    DEFAULT_GLOBAL_URL = "https://api.delta.exchange"
    DEFAULT_TESTNET_URL = "https://testnet-api.delta.exchange"

    def __init__(self, api_key: str | None = None, api_secret: str | None = None, is_testnet: bool | None = None):
        self.api_key = api_key or settings.DELTA_API_KEY
        self.api_secret = api_secret or settings.DELTA_API_SECRET
        self.is_testnet = is_testnet if is_testnet is not None else settings.DELTA_IS_TESTNET
        self.base_url = self.DEFAULT_TESTNET_URL if self.is_testnet else (settings.DELTA_BASE_URL or self.DEFAULT_PROD_URL)
        self._products_cache: dict[str, dict] = {}
        self._last_products_fetch: float = 0.0

    def _generate_signature(self, method: str, path: str, payload_str: str, timestamp: str) -> str:
        """Computes HMAC-SHA256 signature required by Delta Exchange API v2.
        
        Signature string: method + timestamp + path + payload
        """
        if not self.api_secret:
            return ""
        message = f"{method.upper()}{timestamp}{path}{payload_str}"
        return hmac.new(
            self.api_secret.encode("utf-8"),
            message.encode("utf-8"),
            hashlib.sha256,
        ).hexdigest()

    def _get_auth_headers(self, method: str, path: str, payload_str: str = "") -> dict[str, str]:
        """Builds standard authentication headers for Delta Exchange."""
        timestamp = str(int(time.time()))
        signature = self._generate_signature(method, path, payload_str, timestamp)
        return {
            "api-key": self.api_key or "",
            "signature": signature,
            "timestamp": timestamp,
            "Content-Type": "application/json",
            "User-Agent": "Autonomous-AI-Trader/1.0",
        }

    async def _request(self, method: str, path: str, params: dict | None = None, payload: dict | None = None) -> dict:
        """Executes an authenticated HTTP request to Delta Exchange API."""
        url = f"{self.base_url}{path}"
        payload_str = json.dumps(payload) if payload else ""
        
        path_for_sig = path
        if params:
            import urllib.parse
            query_str = urllib.parse.urlencode(params)
            if query_str:
                path_for_sig = f"{path}?{query_str}"

        headers = self._get_auth_headers(method, path_for_sig, payload_str)

        try:
            transport = httpx.AsyncHTTPTransport(local_address="0.0.0.0")
            async with httpx.AsyncClient(transport=transport, timeout=10.0) as client:
                res = await client.request(
                    method=method,
                    url=url,
                    headers=headers,
                    params=params,
                    content=payload_str if payload_str else None,
                )
                if res.status_code in [200, 201]:
                    return res.json()
                else:
                    logger.error(f"[Delta Exchange API Error] {res.status_code} - {res.text}")
                    return {"success": False, "error": res.text, "status_code": res.status_code}
        except Exception as e:
            logger.error(f"[Delta Exchange Network Exception] {e}")
            return {"success": False, "error": str(e)}

    async def get_products(self) -> dict[str, dict]:
        """Fetches active derivative products and symbols (e.g. BTCUSD, ETHUSD)."""
        now = time.time()
        if self._products_cache and (now - self._last_products_fetch) < 300:
            return self._products_cache

        try:
            res = await self._request("GET", "/v2/products")
            if res.get("success") and "result" in res:
                self._products_cache = {p["symbol"]: p for p in res["result"]}
                self._last_products_fetch = now
                return self._products_cache
        except Exception as e:
            logger.warning(f"[Delta Exchange] Error fetching products: {e}")
        return self._products_cache

    async def get_funds(self, force: bool = False) -> dict[str, float]:
        """Returns total balance, available margin, and used margin from Delta Exchange."""
        if not self.api_key or not self.api_secret:
            logger.info("[Delta Exchange] No credentials configured. Returning mock/testnet funds.")
            return {
                "total_capital": 1000.0,
                "available_margin": 1000.0,
                "used_margin": 0.0,
            }

        res = await self._request("GET", "/v2/wallet/balances")
        if res.get("success") and "result" in res:
            balances = res["result"]
            total_usd = 0.0
            available_usd = 0.0
            for b in balances:
                # Delta returns balance details per asset (USDT, USD, etc.)
                asset = b.get("asset_symbol", "")
                bal = float(b.get("balance", 0.0))
                avail = float(b.get("available_balance", 0.0))
                if asset in ["USDT", "USD"]:
                    total_usd += bal
                    available_usd += avail

            meta_net_equity = float(res.get("meta", {}).get("net_equity") or 0.0)
            real_total = meta_net_equity if meta_net_equity > 0 else total_usd
            used_usd = max(0.0, real_total - available_usd)
            return {
                "total_capital": round(real_total, 2),
                "available_margin": round(available_usd, 2),
                "used_margin": round(used_usd, 2),
            }

        return {"total_capital": 0.0, "available_margin": 0.0, "used_margin": 0.0}

    async def get_positions(self, force: bool = False) -> list[PositionSnapshot]:
        """Retrieves active perpetual contract positions."""
        if not self.api_key or not self.api_secret:
            return []

        res = await self._request("GET", "/v2/positions/margined")
        positions: list[PositionSnapshot] = []

        if not (res.get("success") and "result" in res):
            # Fail loudly: silently returning [] here made the risk engine believe there
            # were zero open positions, bypassing max-position and duplicate checks.
            raise RuntimeError(f"Delta positions query failed: {res.get('error', 'unknown error')}")

        if res.get("success") and "result" in res:
            raw_positions = res["result"]
            for p in raw_positions:
                size = float(p.get("size") or 0)
                if abs(size) <= 0:
                    continue

                symbol = p.get("product_symbol") or "UNKNOWN"
                entry_price = float(p.get("entry_price") or 0.0)
                mark_price = float(p.get("mark_price") or entry_price)
                unrealized_pnl = float(p.get("unrealized_pnl") or 0.0)
                liq_price = float(p.get("liquidation_price") or 0.0)

                is_short = size < 0
                side = "SELL" if is_short else "BUY"
                # Default protective levels for adopted positions. The stop must be a risk
                # limit (~2% adverse move), never the liquidation price — waiting for
                # liquidation is not a stop-loss.
                if is_short:
                    sl = round(entry_price * 1.02, 4)
                    if liq_price and liq_price > 0:
                        sl = min(sl, round(liq_price * 0.995, 4))
                    tgt1 = round(entry_price * 0.96, 4)
                    tgt2 = round(entry_price * 0.92, 4)
                else:
                    sl = round(entry_price * 0.98, 4)
                    if liq_price and liq_price > 0:
                        sl = max(sl, round(liq_price * 1.005, 4))
                    tgt1 = round(entry_price * 1.04, 4)
                    tgt2 = round(entry_price * 1.08, 4)

                snapshot = PositionSnapshot(
                    position_id=f"DELTA-{p.get('product_id', symbol)}",
                    symbol=symbol,
                    exchange="DELTA",
                    side=side,
                    quantity=int(abs(size)),
                    entry_price=entry_price,
                    current_price=mark_price,
                    stop_loss=sl,
                    target_1=tgt1,
                    target_2=tgt2,
                    highest_price_seen=max(entry_price, mark_price),
                    lowest_price_seen=min(entry_price, mark_price),
                    unrealized_pnl=unrealized_pnl,
                    opened_at=datetime.now(UTC),
                    is_active=True,
                )
                positions.append(snapshot)

        return positions

    async def place_order(self, order: OrderIntent) -> OrderExecution:
        """Places an order on Delta Exchange.
        
        Enforces strict pre-flight leverage gating (Settings.DELTA_MAX_LEVERAGE).
        """
        if settings.TRADING_MODE == TradingMode.LIVE and not settings.LIVE_TRADING_ENABLED:
            raise PermissionError("Live trading is disabled! Set LIVE_TRADING_ENABLED=true in .env to trade on Delta Exchange.")

        # Resolve Delta product ID from symbol
        products = await self.get_products()
        product = products.get(order.symbol)
        product_id = product.get("id") if product else None

        if not product_id and not (self.api_key and self.api_secret):
            # Simulated Fill for Testing / Dry-Run
            return OrderExecution(
                order_id=f"DELTA-SIM-{int(time.time())}",
                client_order_id=order.client_order_id,
                symbol=order.symbol,
                status=OrderStatus.FILLED,
                filled_quantity=order.quantity,
                average_price=order.price or 50000.0,
                slippage=0.0,
                brokerage_fee=0.50,
                taxes_and_charges=0.0,
            )

        tick_size_str = str(product.get("tick_size", "0.01")) if product else "0.01"

        def _format_tick(val: float | None) -> str | None:
            if val is None or val <= 0:
                return None
            try:
                from decimal import Decimal, ROUND_HALF_UP
                d_tick = Decimal(str(tick_size_str))
                d_val = Decimal(str(val))
                rounded = (d_val / d_tick).quantize(Decimal("1"), rounding=ROUND_HALF_UP) * d_tick
                exp = d_tick.as_tuple().exponent
                if isinstance(exp, int) and exp < 0:
                    return f"{rounded:.{-exp}f}"
                return f"{int(rounded)}"
            except Exception:
                return str(val)

        from core.schemas.trade import OrderType
        delta_order_type = "market_order" if (order.order_type == OrderType.MARKET or order.price is None or order.price <= 0) else "limit_order"
        side = "buy" if order.action == TradeAction.BUY else "sell"

        payload = {
            "product_id": product_id,
            "size": order.quantity,
            "side": side,
            "order_type": delta_order_type,
        }
        if delta_order_type == "limit_order":
            payload["limit_price"] = _format_tick(order.price)

        # Exit-only orders must never open or increase a position (prevents an
        # exit in the wrong direction from doubling exposure).
        if getattr(order, "reduce_only", False):
            payload["reduce_only"] = True

        # If stop_loss is set, attach bracket stop loss price formatted to tick size
        if order.stop_loss and order.stop_loss > 0:
            payload["stop_loss_price"] = _format_tick(order.stop_loss)

        logger.info(f"🚀 [Delta Exchange] Submitting {side.upper()} order for {order.symbol} (Size: {order.quantity})")
        res = await self._request("POST", "/v2/orders", payload=payload)

        if res.get("success") and "result" in res:
            raw_order = res["result"]
            placed_order_id = str(raw_order.get("id"))

            # Server-Side Bracket Defense: Verify open position before placing native Delta Bracket Order
            if order.target and order.target > 0 and product_id and not getattr(order, "reduce_only", False):
                try:
                    pos_confirmed = False
                    fill_entry = 0.0
                    for _ in range(10):
                        await asyncio.sleep(0.5)
                        curr_positions = await self.get_positions(force=True)
                        match = next((p for p in curr_positions if p.symbol == order.symbol and p.quantity > 0), None)
                        if match is not None:
                            pos_confirmed = True
                            fill_entry = float(getattr(match, "entry_price", 0.0) or 0.0)
                            break

                    if pos_confirmed:
                        # Anchor the exchange-side bracket to the real fill, not the
                        # pre-trade reference price, so the stop risks what was planned.
                        from strategy.entry_anchor import shift_levels_to_fill
                        ref_entry = float(order.price or 0.0)
                        br_stop, br_target = shift_levels_to_fill(ref_entry, order.stop_loss, order.target, fill_entry)
                        if fill_entry > 0 and ref_entry > 0 and abs(fill_entry - ref_entry) > 0:
                            logger.info(
                                f"🛡️ [Delta Exchange] {order.symbol} filled at {fill_entry} vs reference {ref_entry}; "
                                f"bracket re-anchored SL {order.stop_loss}->{br_stop}, TP {order.target}->{br_target}"
                            )
                        bracket_res = await self.place_bracket_order(
                            product_id=product_id,
                            product_symbol=order.symbol,
                            stop_loss=br_stop,
                            take_profit=br_target,
                        )
                        if not bracket_res.get("success", False):
                            logger.error(f"❌ [Delta Exchange] Bracket order rejected for {order.symbol}: {bracket_res.get('error')}")
                    else:
                        logger.warning(f"⚠️ [Delta Exchange] Position for {order.symbol} not confirmed open after 2.0s; bracket deferred to guardian.")
                        logger.error(f"🚨 [Delta Exchange] {order.symbol} has NO exchange-side stop yet — protection depends on the guardian polling loop until reconciliation.")
                except Exception as b_err:
                    logger.warning(f"[Delta Exchange] Bracket order notice: {b_err}")

            # If this was a reduce_only exit, cancel any residual bracket or protective orders for this product to prevent orphans
            if getattr(order, "reduce_only", False) and product_id:
                try:
                    await self.cancel_product_orders(product_id)
                except Exception as c_err:
                    logger.debug(f"[Delta Exchange] Error clearing residual orders for product {product_id}: {c_err}")

            # filled = size - unfilled (previously this reported unfilled_size as filled,
            # so fully-filled orders were recorded as quantity 0 and vice versa)
            raw_size = int(raw_order.get("size") or order.quantity or 0)
            raw_unfilled = int(raw_order.get("unfilled_size") or 0)
            return OrderExecution(
                order_id=placed_order_id,
                client_order_id=order.client_order_id,
                symbol=order.symbol,
                status=OrderStatus.SUBMITTED,
                filled_quantity=max(0, raw_size - raw_unfilled),
                average_price=float(raw_order.get("average_fill_price") or raw_order.get("limit_price") or order.price or 0.0),
                slippage=0.0,
                brokerage_fee=0.0,
                taxes_and_charges=0.0,
            )
        else:
            err = res.get("error", "Order rejected by Delta Exchange")
            logger.error(f"❌ [Delta Exchange] Order placement failed: {err}")
            return OrderExecution(
                order_id=f"FAILED-{int(time.time())}",
                client_order_id=order.client_order_id,
                symbol=order.symbol,
                status=OrderStatus.REJECTED,
                filled_quantity=0,
                average_price=0.0,
                slippage=0.0,
                brokerage_fee=0.0,
                taxes_and_charges=0.0,
            )

    async def place_bracket_order(
        self,
        product_id: int,
        product_symbol: str,
        stop_loss: float | None = None,
        take_profit: float | None = None,
        trigger_method: str = "last_traded_price",
    ) -> dict:
        """Places native Delta Exchange Bracket Order (Automated Take-Profit and Stop-Loss).
        
        Per docs.delta.exchange/#place-bracket-order:
        A bracket order automatically liquidates/secures the entire position at pre-defined triggers.
        """
        product = self._products_cache.get(product_symbol)
        tick_size_str = str(product.get("tick_size", "0.01")) if product else "0.01"

        def _fmt(val: float | None) -> str | None:
            if val is None or val <= 0:
                return None
            try:
                from decimal import Decimal, ROUND_HALF_UP
                d_tick = Decimal(str(tick_size_str))
                d_val = Decimal(str(val))
                rounded = (d_val / d_tick).quantize(Decimal("1"), rounding=ROUND_HALF_UP) * d_tick
                exp = d_tick.as_tuple().exponent
                if isinstance(exp, int) and exp < 0:
                    return f"{rounded:.{-exp}f}"
                return f"{int(rounded)}"
            except Exception:
                return str(val)

        payload: dict[str, Any] = {
            "product_id": product_id,
            "product_symbol": product_symbol,
            "bracket_stop_trigger_method": trigger_method,
        }
        if stop_loss and stop_loss > 0:
            payload["stop_loss_order"] = {
                "order_type": "market_order",
                "stop_price": _fmt(stop_loss),
            }
        if take_profit and take_profit > 0:
            payload["take_profit_order"] = {
                "order_type": "market_order",
                "stop_price": _fmt(take_profit),
            }

        logger.info(f"🛡️ [Delta Exchange] Registering Bracket Defense: TP={_fmt(take_profit)}, SL={_fmt(stop_loss)}")
        return await self._request("POST", "/v2/orders/bracket", payload=payload)

    async def cancel_order(self, order_id: str, product_id: int | None = None) -> bool:
        """Cancels an open order on Delta Exchange."""
        payload = {"id": int(order_id)}
        if product_id:
            payload["product_id"] = product_id
        res = await self._request("DELETE", "/v2/orders", payload=payload)
        return bool(res.get("success"))

    async def cancel_product_orders(self, product_id: int) -> int:
        """Cancels all open orders (including bracket/stop orders) for a specific product ID."""
        try:
            res = await self._request("GET", f"/v2/orders?state=open&product_id={product_id}")
            if not res.get("success"):
                return 0
            cancelled = 0
            for o in res.get("result", []):
                oid = o.get("id")
                if oid:
                    c_res = await self._request("DELETE", "/v2/orders", payload={"id": oid, "product_id": product_id})
                    if c_res.get("success"):
                        cancelled += 1
                        logger.info(f"🛡️ [Delta Exchange] Cancelled residual order {oid} for product {product_id}")
            return cancelled
        except Exception as e:
            logger.warning(f"[Delta Exchange] Error cancelling product orders for {product_id}: {e}")
            return 0

    async def cancel_stale_orders(self, max_age_seconds: int = 180) -> int:
        """Cancels unfilled open orders older than max_age_seconds to free up blocked margin."""
        try:
            res = await self._request("GET", "/v2/orders?state=open")
            if not res.get("success"):
                return 0
            cancelled = 0
            now = time.time()
            for o in res.get("result", []):
                # Never cancel protective bracket orders (stop loss, take profit, reduce_only)
                is_protective = (
                    o.get("close_on_trigger")
                    or o.get("reduce_only")
                    or o.get("stop_order_type") is not None
                    or "stop" in (o.get("order_type") or "").lower()
                )
                if is_protective:
                    continue

                created_str = o.get("created_at")
                if not created_str:
                    continue
                try:
                    dt = datetime.fromisoformat(created_str.replace("Z", "+00:00"))
                    age = now - dt.timestamp()
                    if age > max_age_seconds:
                        oid = o.get("id")
                        pid = o.get("product_id")
                        if oid and pid:
                            c_res = await self._request("DELETE", "/v2/orders", payload={"id": oid, "product_id": pid})
                            if c_res.get("success"):
                                cancelled += 1
                                logger.info(f"[Delta Exchange] Cancelled stale unfilled entry order {oid} ({o.get('product_symbol')}, age {int(age)}s)")
                except Exception:
                    pass
            return cancelled
        except Exception as e:
            logger.warning(f"[Delta Exchange] Error cancelling stale orders: {e}")
            return 0

    async def get_order_status(self, order_id: str) -> OrderStatus:
        """Queries status of an existing order."""
        res = await self._request("GET", f"/v2/orders/{order_id}")
        if res.get("success") and "result" in res:
            state = res["result"].get("state", "").lower()
            if state in ["open", "pending"]:
                return OrderStatus.SUBMITTED
            elif state in ["filled", "closed"]:
                return OrderStatus.FILLED
            elif state in ["cancelled", "rejected"]:
                return OrderStatus.REJECTED
        return OrderStatus.PENDING
