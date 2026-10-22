import asyncio
import json
from collections.abc import Callable
from datetime import UTC, datetime

import websockets

from core.config.settings import settings
from core.logging import logger
from orchestration.event_bus import SystemEventType, realtime_event_bus


class AngelOneWebSocketStreamer:
    """Production AngelOne SmartAPI Real-Time WebSocket Ticker (Section 2 & 17).
    
    Streams live market ticks (LTP, Volume, Depth) for Indian stocks on NSE/BSE,
    aggregates live candles in memory, and triggers real-time price movement events.
    """

    WS_URL = "wss://smartapisocket.angelone.in/smart-stream"

    def __init__(self):
        self.api_key = settings.ANGELONE_API_KEY
        self.client_code = settings.ANGELONE_CLIENT_CODE
        self.jwt_token = settings.ANGELONE_AUTH_TOKEN
        self.feed_token = settings.ANGELONE_FEED_TOKEN
        self.is_connected = False
        self.subscribed_tokens: list[str] = ["3045", "1594", "1333", "11536"] # SBIN, INFY, HDFCBANK, TCS
        self.live_quotes: dict[str, dict] = {} # token -> {ltp, volume, timestamp}
        self._running = False

    async def start_streaming(self, on_tick_callback: Callable[[dict], None] | None = None):
        """Starts persistent WebSocket streaming loop with automatic reconnection."""
        self._running = True
        logger.info("[AngelOne WebSocket] Initializing real-time market data stream...")

        while self._running:
            try:
                # Acquire dynamically authenticated broker token if not present in env
                if not self.jwt_token or not self.client_code:
                    try:
                        from execution.broker_factory import get_active_broker
                        b = get_active_broker()
                        if not getattr(b, "jwt_token", None) and hasattr(b, "authenticate_session"):
                            await b.authenticate_session()
                        if getattr(b, "jwt_token", None):
                            self.jwt_token = b.jwt_token
                            self.feed_token = getattr(b, "feed_token", self.feed_token)
                            self.client_code = getattr(b, "client_code", self.client_code)
                            self.api_key = getattr(b, "api_key", self.api_key)
                    except Exception:
                        pass

                # If credentials are still not configured, simulate live high-frequency feed on laptop
                if not self.jwt_token or not self.client_code:
                    logger.info("[AngelOne Streamer] Credentials not set. Running simulated live tick engine for testing.")
                    await self._run_simulated_tick_stream(on_tick_callback)
                    break

                headers = {
                    "Authorization": f"Bearer {self.jwt_token}",
                    "x-api-key": self.api_key,
                    "x-client-code": self.client_code,
                    "x-feed-token": self.feed_token,
                }

                # websockets >= 14 uses additional_headers, older versions use extra_headers
                import inspect
                sig = inspect.signature(websockets.connect)
                connect_kwargs = {
                    "ping_interval": None,  # Prevent sent 1011 keepalive ping timeout with AngelOne servers
                    "ping_timeout": None,
                }
                if "additional_headers" in sig.parameters:
                    connect_kwargs["additional_headers"] = headers
                else:
                    connect_kwargs["extra_headers"] = headers

                async with websockets.connect(self.WS_URL, **connect_kwargs) as ws:
                    self.is_connected = True
                    logger.info("[AngelOne WebSocket] Connected to SmartAPI Live Stream Server! Subscribing tokens...")

                    # Spawn application-level keepalive heartbeat every 25s for SmartAPI
                    async def _send_heartbeat():
                        while self._running:
                            try:
                                await asyncio.sleep(25.0)
                                is_open = getattr(ws, "open", True)
                                if is_open:
                                    await ws.send("ping")
                            except Exception:
                                break

                    heartbeat_task = asyncio.create_task(_send_heartbeat())

                    try:
                        # Subscribe to Mode 1 (LTP + Volume)
                        sub_payload = {
                            "correlationID": "trader_live_01",
                            "action": 1,
                            "params": {
                                "mode": 1,
                                "tokenList": [{"exchangeType": 1, "tokens": self.subscribed_tokens}],
                            },
                        }
                        await ws.send(json.dumps(sub_payload))

                        while self._running:
                            msg = await ws.recv()
                            # Ignore heartbeat text responses
                            if isinstance(msg, str) and msg.strip().lower() in ("pong", "ping"):
                                continue
                            if isinstance(msg, (bytes, bytearray)) and msg.strip().lower() in (b"pong", b"ping"):
                                continue

                            tick = self._parse_tick(msg)
                            if tick:
                                self.live_quotes[tick.get("token", "default")] = tick
                                if on_tick_callback:
                                    on_tick_callback(tick)

                                # Publish event to bus
                                realtime_event_bus.publish_event(
                                    SystemEventType.PRICE_MOVEMENT,
                                    source="AngelOne WebSocket",
                                    symbol=tick.get("symbol", "N/A"),
                                    payload=tick,
                                )
                    finally:
                        heartbeat_task.cancel()
            except Exception as e:
                self.is_connected = False
                logger.warning(f"[AngelOne WebSocket] Stream disconnected: {e}. Reconnecting in 5s...")
                await asyncio.sleep(5.0)

    def _parse_tick(self, data: bytes | str) -> dict | None:
        """Parses binary or JSON tick data from AngelOne smart stream."""
        import struct
        try:
            if isinstance(data, str):
                if data.strip().lower() in ("pong", "ping"):
                    return None
                return json.loads(data)
            if isinstance(data, (bytes, bytearray)):
                if data.strip().lower() in (b"pong", b"ping"):
                    return None
                if len(data) >= 51:
                    subscription_mode = data[0]
                    exchange_type = data[1]
                    token = data[2:27].decode("utf-8", errors="ignore").rstrip("\x00 \t\r\n")
                    sequence = struct.unpack("<q", data[27:35])[0]
                    exchange_timestamp = struct.unpack("<q", data[35:43])[0]
                    ltp_paise = struct.unpack("<q", data[43:51])[0]
                    ltp = ltp_paise / 100.0

                    symbol_map = {
                        "3045": "SBIN.NS",
                        "1594": "INFY.NS",
                        "1333": "HDFCBANK.NS",
                        "11536": "TCS.NS",
                        "526": "COALINDIA.NS",
                        "474": "GAIL.NS",
                        "3506": "UNIONBANK.NS",
                    }
                    symbol = symbol_map.get(token, f"TOKEN_{token}")

                    return {
                        "token": token,
                        "symbol": symbol,
                        "ltp": round(ltp, 2),
                        "volume": 0,
                        "timestamp": str(datetime.now(UTC)),
                    }
            return None
        except Exception:
            return None

    async def _run_simulated_tick_stream(self, callback: Callable[[dict], None] | None):
        """Simulated real-time tick engine for local laptop execution and dry-runs."""
        symbols = ["RELIANCE.NS", "TCS.NS", "INFY.NS", "HDFCBANK.NS", "TATAMOTORS.NS"]
        base_prices = {"RELIANCE.NS": 2850.0, "TCS.NS": 4020.0, "INFY.NS": 1860.0, "HDFCBANK.NS": 1640.0, "TATAMOTORS.NS": 980.0}

        step = 0
        while self._running and step < 10:
            for s in symbols:
                base_prices[s] += (step % 2 * 2 - 1) * 0.50
                tick = {
                    "symbol": s,
                    "ltp": round(base_prices[s], 2),
                    "volume": 50000 + step * 500,
                    "timestamp": str(datetime.now(UTC)),
                }
                self.live_quotes[s] = tick
                if callback:
                    callback(tick)
            step += 1
            await asyncio.sleep(1.0)

    def stop(self):
        self._running = False
        self.is_connected = False


# Global Streamer singleton
angelone_streamer = AngelOneWebSocketStreamer()
