"""
Laya Non-Autoregressive System 1 Decision Engine Service.

Provides sub-second, typed decision inference for trading candidates, breaking news headlines,
and real-time risk checks using non-autoregressive reinforcement-learned decision heads (RLCD).
"""

import asyncio
from typing import Any

from core.logging import logger


class LayaSystemOneService:
    """Singleton service providing non-autoregressive System 1 decisions over Laya."""

    def __init__(self):
        self._router: Any = None
        self._initialized = False
        self._init_lock = asyncio.Lock()

    def _sync_init(self) -> None:
        import os
        if os.getenv("ENABLE_LAYA_MODEL", "false").lower() != "true":
            self._initialized = True
            self._router = None
            return
        try:
            from laya import Router
            self._router = Router()
            self._initialized = True
            logger.info("⚡ [Laya System 1] Non-autoregressive decision engine initialized successfully.")
        except Exception as e:
            logger.warning(f"⚠️ [Laya System 1] Failed to initialize Laya router: {e}")
            self._router = None

    async def ensure_initialized(self) -> bool:
        if self._initialized:
            return self._router is not None
        async with self._init_lock:
            if not self._initialized:
                loop = asyncio.get_event_loop()
                await loop.run_in_executor(None, self._sync_init)
        return self._router is not None

    async def triage_candidate(
        self,
        symbol: str,
        ltp: float,
        change_24h: float,
        rsi: float,
        trend_summary: str,
    ) -> dict[str, Any]:
        """Rapid non-autoregressive triage of a trading candidate."""
        ready = await self.ensure_initialized()
        if not ready or self._router is None:
            return {"stance": "NEUTRAL", "conviction": 0.50, "is_actionable": False, "source": "FALLBACK"}

        state = (
            f"Asset {symbol} at price ${ltp:.4f}, 24h change {change_24h:+.2f}%, "
            f"RSI 14 at {rsi:.1f}. Technical structure: {trend_summary}."
        )

        questions = {
            "bias": {
                "type": "choice",
                "instructions": "What is the structural price bias for this asset?",
                "criteria": {
                    "BULLISH": "uptrend breakout, support bounce, or accumulation",
                    "BEARISH": "downtrend breakdown, resistance rejection, or dump",
                    "NEUTRAL": "choppy consolidation or lack of clear edge",
                },
            },
            "is_actionable": {
                "type": "noul",
                "instructions": "Does this setup have sufficient momentum and favorable risk/reward to trade right now?",
            },
        }

        def _predict():
            try:
                return self._router.predict(state, questions)
            except Exception as err:
                logger.debug(f"[Laya System 1] Triage error on {symbol}: {err}")
                return None

        loop = asyncio.get_event_loop()
        res = await loop.run_in_executor(None, _predict)

        if not res or "answers" not in res:
            return {"stance": "NEUTRAL", "conviction": 0.50, "is_actionable": False, "source": "FALLBACK"}

        bias_ans = res["answers"].get("bias", {})
        action_ans = res["answers"].get("is_actionable", {})

        stance = bias_ans.get("choice", "NEUTRAL")
        prob_actionable = float(action_ans.get("noul", 0.50))

        return {
            "symbol": symbol,
            "stance": stance,
            "is_actionable": prob_actionable >= 0.65,
            "conviction": round(prob_actionable, 4),
            "source": "LAYA_SYSTEM_1",
        }

    async def triage_headline(self, headline: str) -> dict[str, Any]:
        """Rapid sentiment and urgency scoring for breaking crypto news headlines."""
        ready = await self.ensure_initialized()
        if not ready or self._router is None:
            return {"sentiment": "NEUTRAL", "impact_score": 0.5, "is_breaking": False}

        questions = {
            "sentiment": {
                "type": "choice",
                "instructions": "What is the market sentiment of this news?",
                "criteria": {
                    "BULLISH": "adoption, ETF inflows, rate cuts, protocol upgrades, institutional buying",
                    "BEARISH": "hacks, exploits, lawsuits, SEC bans, liquidations, insolvencies",
                    "NEUTRAL": "general commentary, routine updates, opinion pieces",
                },
            },
            "is_breaking": {
                "type": "noul",
                "instructions": "Is this urgent breaking news that will immediately move cryptocurrency prices?",
            },
        }

        def _predict():
            try:
                return self._router.predict(headline, questions)
            except Exception:
                return None

        loop = asyncio.get_event_loop()
        res = await loop.run_in_executor(None, _predict)

        if not res or "answers" not in res:
            return {"sentiment": "NEUTRAL", "impact_score": 0.5, "is_breaking": False}

        sent_ans = res["answers"].get("sentiment", {})
        break_ans = res["answers"].get("is_breaking", {})

        return {
            "sentiment": sent_ans.get("choice", "NEUTRAL"),
            "impact_score": round(float(break_ans.get("noul", 0.5)), 4),
            "is_breaking": float(break_ans.get("noul", 0.5)) >= 0.70,
            "source": "LAYA_SYSTEM_1",
        }


# Global singleton instance
laya_service = LayaSystemOneService()
