from agents.llm_router import router
from core.config.settings import settings
from core.domain.models import MarketRegime
from core.schemas.trade import AnalystReport, CandidateSignal


class TechnicalAnalystAgent:
    """Specialist Technical Analyst evaluating price action, momentum, and key support/resistance."""

    def __init__(self):
        self.agent_name = "Technical Analyst"

    async def analyze(self, signal: CandidateSignal, ohlcv_summary: str = "") -> AnalystReport:
        from skills.models import SkillExecutionRequest
        from skills.registry import skill_registry

        # Execute registered technical skills
        rsi_res = await skill_registry.execute_skill(
            SkillExecutionRequest(skill_id="skill.analysis.rsi.v1", agent_id="technical_analyst", parameters={"symbol": signal.symbol, "period": 14})
        )
        ema_res = await skill_registry.execute_skill(
            SkillExecutionRequest(skill_id="skill.analysis.moving_averages.v1", agent_id="technical_analyst", parameters={"symbol": signal.symbol})
        )
        atr_res = await skill_registry.execute_skill(
            SkillExecutionRequest(skill_id="skill.analysis.atr_volatility.v1", agent_id="technical_analyst", parameters={"symbol": signal.symbol})
        )
        pa_res = await skill_registry.execute_skill(
            SkillExecutionRequest(skill_id="skill.analysis.price_action_candles.v1", agent_id="technical_analyst", parameters={"symbol": signal.symbol})
        )
        goodman_res = await skill_registry.execute_skill(
            SkillExecutionRequest(skill_id="skill.strategy.goodman_trend_breakout.v1", agent_id="technical_analyst", parameters={"symbol": signal.symbol})
        )
        pattern_res = await skill_registry.execute_skill(
            SkillExecutionRequest(skill_id="skill.analysis.crypto_chart_patterns.v1", agent_id="technical_analyst", parameters={"symbol": signal.symbol})
        )

        rsi_val = rsi_res.data.get("value", 50.0) if rsi_res.status == "SUCCESS" and rsi_res.data else 50.0
        rsi_interp = rsi_res.data.get("interpretation", "neutral") if rsi_res.status == "SUCCESS" and rsi_res.data else "neutral"
        ema_trend = ema_res.data.get("trend_alignment", "MIXED") if ema_res.status == "SUCCESS" and ema_res.data else "MIXED"
        atr_val = atr_res.data.get("atr_14", signal.atr_14) if atr_res.status == "SUCCESS" and atr_res.data else signal.atr_14
        rec_stop = atr_res.data.get("recommended_stop_distance", atr_val * 1.5) if atr_res.status == "SUCCESS" and atr_res.data else atr_val * 1.5

        pa_sig = pa_res.data.get("signal_type", "NEUTRAL") if pa_res.status == "SUCCESS" and pa_res.data else "NEUTRAL"
        is_chasing = goodman_res.data.get("is_chasing_breakout", False) if goodman_res.status == "SUCCESS" and goodman_res.data else False
        chandelier_stop = goodman_res.data.get("chandelier_trailing_stop", signal.ltp * 0.95) if goodman_res.status == "SUCCESS" and goodman_res.data else signal.ltp * 0.95

        # Crypto Chart Patterns (GoodCrypto Guide: Reversals & Continuations)
        detected_patterns = pattern_res.data.get("detected_patterns", []) if pattern_res.status == "SUCCESS" and pattern_res.data else []
        primary_pattern = pattern_res.data.get("primary_pattern", "NONE") if pattern_res.status == "SUCCESS" and pattern_res.data else "NONE"
        pattern_type = pattern_res.data.get("pattern_type", "NEUTRAL") if pattern_res.status == "SUCCESS" and pattern_res.data else "NEUTRAL"
        pattern_target = pattern_res.data.get("target_price") if pattern_res.status == "SUCCESS" and pattern_res.data else None
        pattern_stop = pattern_res.data.get("invalidation_level") if pattern_res.status == "SUCCESS" and pattern_res.data else None
        pattern_vol_conf = pattern_res.data.get("has_volume_confirmation", False) if pattern_res.status == "SUCCESS" and pattern_res.data else False

        is_crypto = "USD" in signal.symbol.upper()
        curr_sym = "$" if is_crypto else "₹"
        prec = 6 if signal.ltp < 0.10 else (4 if signal.ltp < 10.0 else 2)

        system_prompt = (
            "You are a Senior Technical Analyst specializing in quantitative and classical price action (NSE/BSE & Crypto).\n"
            "Evaluate price action using institutional principles from GoodCrypto, Glen Goodman and Ondřej Buček:\n"
            "1. Crypto Chart Patterns: Detect Reversals (Double/Triple Bottoms, Cup & Handle, Falling Wedges) and Continuations (Ascending Triangles, Rectangles) with measured-move target projection.\n"
            "2. Breakouts: Validate with high relative volume (>1.25x) and verify price is within 5% of the base (Never Chase Rule).\n"
            "3. Trend & Pullbacks: In uptrends (Price > EMA 20 > EMA 50), trade along the line of least resistance. Trail with Chandelier stop.\n"
            "4. Candlestick Pinbars: Detect Buček Hammer / Shooting Star pinbars (shadow ratio >= 0.70) at key swing extremes.\n"
            "5. Risk/Reward: Target minimum 1:1.5 - 1:2.5 R:R with invalidation stop anchored to pattern support/invalidation level."
        )
        user_prompt = (
            f"Candidate: {signal.symbol}\n"
            f"LTP: {curr_sym}{signal.ltp:.{prec}f}\n"
            f"Volume: {signal.volume} (Rel Vol: {signal.relative_volume}x)\n"
            f"Skills Verified Output:\n"
            f"• Crypto Chart Pattern: {primary_pattern} ({pattern_type}) | Target: {curr_sym}{pattern_target if pattern_target else 'N/A'} | Invalidation: {curr_sym}{pattern_stop if pattern_stop else 'N/A'}\n"
            f"• RSI 14: {rsi_val} ({rsi_interp})\n"
            f"• EMA 20/50 Alignment: {ema_trend}\n"
            f"• ATR 14 Volatility: {curr_sym}{atr_val:.{prec}f} (Stop Distance: {curr_sym}{rec_stop:.{prec}f})\n"
            f"• Buček Pinbar Pattern: {pa_sig}\n"
            f"• Goodman Breakout Anti-Chase: {'VIOLATION (>5% chase)' if is_chasing else 'CLEAN (<=5% of base)'}\n"
            f"• Chandelier Trailing Stop: {curr_sym}{chandelier_stop:.{prec}f}\n"
            f"Momentum Score: {signal.momentum_score}/100\n"
            f"Market Regime: {signal.regime.value}\n"
            f"OHLCV Context: {ohlcv_summary}\n"
        )

        def fallback() -> AnalystReport:
            is_bull_pattern = pattern_type in ["BULLISH_REVERSAL", "BULLISH_CONTINUATION"]
            is_bear_pattern = pattern_type in ["BEARISH_REVERSAL", "BEARISH_CONTINUATION"]
            is_short_setup = (getattr(signal, "setup_direction", "LONG") == "SHORT") or is_bear_pattern or (signal.regime == MarketRegime.BEARISH_TREND)
            
            entry = signal.ltp
            if is_short_setup:
                stance = "BEARISH"
                stop = round(pattern_stop if (is_bear_pattern and pattern_stop and pattern_stop > entry) else (signal.ltp + rec_stop), prec)
                target = round(pattern_target if (is_bear_pattern and pattern_target and pattern_target < entry) else (signal.ltp - (rec_stop * 2.1)), prec)
                conf = 0.88 if (is_bear_pattern and pattern_vol_conf) else min(0.92, max(0.55, signal.momentum_score / 100.0))
            else:
                stance = "BULLISH" if (is_bull_pattern or signal.momentum_score > 35 or rsi_val > 52) else ("BEARISH" if signal.momentum_score < -20 else "NEUTRAL")
                stop = round(pattern_stop if (is_bull_pattern and pattern_stop and pattern_stop < entry) else (signal.ltp - rec_stop), prec)
                target = round(pattern_target if (is_bull_pattern and pattern_target and pattern_target > entry) else (signal.ltp + (rec_stop * 2.0)), prec)
                conf = 0.88 if (is_bull_pattern and pattern_vol_conf) else min(0.92, max(0.45, signal.momentum_score / 100.0))

            return AnalystReport(
                agent_name=self.agent_name,
                symbol=signal.symbol,
                stance=stance,
                confidence=conf,
                key_observations=[
                    f"Chart Pattern: {primary_pattern} ({pattern_type}) with target {curr_sym}{target}",
                    f"RSI Skill verified at {rsi_val} ({rsi_interp})",
                    f"EMA Trend Skill confirmed '{ema_trend}' momentum alignment",
                    f"Volatility Invalidation Stop set at {curr_sym}{stop}",
                ],
                risk_warnings=["Sudden high-volatility liquidity sweep at swing extremes"],
                suggested_entry=entry,
                suggested_stop=stop,
                suggested_target=target,
            )

        report = await router.generate_structured(
            schema=AnalystReport,
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            model_name=settings.MODEL_FAST,
            fallback_factory=fallback,
        )
        report.agent_name = self.agent_name
        report.symbol = signal.symbol
        return report
