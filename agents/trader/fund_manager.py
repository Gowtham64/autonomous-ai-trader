import uuid

from agents.llm_router import router
from core.config.settings import settings
from core.domain.models import MarketRegime, TradeAction
from core.logging import logger
from core.schemas.trade import (
    AnalystReport,
    CandidateSignal,
    DebateTranscript,
    TradeDecision,
)


class FundManagerAgent:
    """Chief Fund Manager synthesizing research and debates into a strict TradeDecision."""

    def __init__(self):
        self.strategy_version = settings.STRATEGY_VERSION
        self.prompt_version = settings.PROMPT_VERSION

    async def decide(
        self,
        signal: CandidateSignal,
        reports: list[AnalystReport],
        debate: DebateTranscript,
        available_capital: float = 0.0,
    ) -> TradeDecision:
        analysis_id = f"ANL-{uuid.uuid4().hex[:8].upper()}"
        logger.info(f"Fund Manager evaluating trade decision for {signal.symbol} [{analysis_id}] (Live Capital: ₹{available_capital:,.2f})")

        # Extract multi-domain specialist observations
        tech_report = next((r for r in reports if "Technical" in r.agent_name), None)
        fund_report = next((r for r in reports if "Fundamental" in r.agent_name), None)
        news_report = next((r for r in reports if "News" in r.agent_name), None)
        sent_report = next((r for r in reports if "Sentiment" in r.agent_name), None)
        kronos_report = next((r for r in reports if "Kronos" in r.agent_name), None)

        system_prompt = (
            "You are the Chief Investment Officer / Fund Manager of an institutional quantitative hedge fund. "
            "You trade both Indian equities (NSE/BSE, Long/Delivery) and Crypto Derivatives (Delta Exchange Perpetuals, Long & Short Bidirectional). "
            "You synthesize 5 critical pillars to determine trade direction (BUY for Long, SELL for Short), entry price, stop-loss, and target gain:\n"
            "1. Company/Asset Fundamentals & Macro/Distribution Structure.\n"
            "2. Trend & Price Action: Moving average alignment (EMA 20/50), momentum score, and ATR volatility.\n"
            "3. News Catalysts & Market Sentiment: Institutional volume and order book skew.\n"
            "4. Candlestick Foundation Model (Kronos AAAI 2026): Zero-shot neural trajectory, predicted future K-line bars, neural stop loss, and probabilistic target reachability.\n"
            "5. Bidirectional Execution Doctrines:\n"
            "   - Bullish Breakout/Pullback: Buy when trend and indicators confirm upward expansion (BUY).\n"
            "   - Bearish Breakdown/Distribution: For Crypto Perpetuals, actively SHORT (SELL) when technical breakdown, distribution volume, or Kronos neural forecast projects downward expansion.\n"
            "   - Strict Risk: Max 0.5%–2% risk per trade. Always define strict stop-loss and mandate minimum 1:2.0 Risk-to-Reward ratio.\n\n"
            "If evidence is weak, uncertain, or conflicting, return NO_TRADE."
        )

        user_prompt = (
            f"Asset: {signal.symbol} (LTP: ₹{signal.ltp}, Sector: {signal.sector})\n"
            f"Deployable Capital: ₹{available_capital:,.2f}\n\n"
            f"1. Company Fundamentals & Growth History:\n"
            f"   - Stance: {fund_report.stance if fund_report else 'NEUTRAL'}\n"
            f"   - Insights: {', '.join(fund_report.key_observations) if fund_report else 'N/A'}\n\n"
            f"2. Stock Trend & Technical Momentum:\n"
            f"   - Stance: {tech_report.stance if tech_report else 'NEUTRAL'}\n"
            f"   - Insights: {', '.join(tech_report.key_observations) if tech_report else 'N/A'}\n\n"
            f"3. News, Catalysts & Market Sentiment:\n"
            f"   - News Stance: {news_report.stance if news_report else 'NEUTRAL'}\n"
            f"   - News Insights: {', '.join(news_report.key_observations) if news_report else 'N/A'}\n"
            f"   - Sentiment Stance: {sent_report.stance if sent_report else 'NEUTRAL'}\n\n"
            f"4. Kronos Candlestick Foundation Model Forecast:\n"
            f"   - Model Stance: {kronos_report.stance if kronos_report else 'N/A'}\n"
            f"   - Predicted Trajectory: {', '.join(kronos_report.key_observations) if kronos_report else 'N/A'}\n"
            f"   - Suggested Stop: ₹{kronos_report.suggested_stop if kronos_report else 'N/A'} | Target: ₹{kronos_report.suggested_target if kronos_report else 'N/A'}\n\n"
            f"5. Adversarial Debate Consensus:\n"
            f"   - Score: {debate.consensus_score:+.2f}\n"
            f"   - Bull Thesis: {debate.bull_thesis}\n"
            f"   - Bear Thesis: {debate.bear_thesis}\n"
            f"   - Facilitator Verdict: {debate.facilitator_summary}\n"
        )

        def fallback() -> TradeDecision:
            # Deterministic quantitative synthesis fallback based on fundamentals, trend, and news
            is_crypto = ("USD" in signal.symbol.upper()) or (signal.exchange and signal.exchange.upper() in ["DELTA", "CRYPTO"])
            cs = "$" if is_crypto else "₹"
            px_nd = 4 if is_crypto else 2
            entry = signal.ltp
            atr = max(signal.atr_14, signal.ltp * 0.01)
            stop_dist = min(atr * 0.8, entry * 0.015)

            logger.info(
                f"[FundManager] Synthesizing multi-factor decision for {signal.symbol} "
                f"from debate consensus ({debate.consensus_score:+.2f})."
            )
            is_fund_bullish = fund_report and fund_report.stance == "BULLISH"
            is_fund_bearish = fund_report and fund_report.stance == "BEARISH"
            is_news_bullish = news_report and news_report.stance == "BULLISH"
            is_news_bearish = news_report and news_report.stance == "BEARISH"
            is_tech_bullish = tech_report and tech_report.stance == "BULLISH"
            is_tech_bearish = tech_report and tech_report.stance == "BEARISH"
            is_kronos_bearish = kronos_report and kronos_report.stance == "BEARISH" and kronos_report.confidence >= 0.60
            is_kronos_bullish = kronos_report and kronos_report.stance == "BULLISH" and kronos_report.confidence >= 0.60

            # -------------------------------------------------------------
            # A) BEARISH / SHORT DIRECTION (Crypto Perpetuals on Delta)
            # -------------------------------------------------------------
            is_bear_setup = (
                is_crypto and (
                    # 1. Multi-agent bearish consensus
                    (debate.consensus_score <= -0.25 and (is_tech_bearish or is_kronos_bearish or getattr(signal, "setup_direction", "") == "SHORT"))
                    # 2. Or Kronos neural model breakdown with technical/distribution confirmation
                    or (is_kronos_bearish and (is_tech_bearish or debate.consensus_score <= -0.15 or getattr(signal, "setup_direction", "") == "SHORT"))
                    # 3. Or Strong technical breakdown in Bearish Trend
                    or (is_tech_bearish and signal.regime == MarketRegime.BEARISH_TREND and debate.consensus_score <= -0.20)
                )
            )

            if is_bear_setup:
                # Short geometry: SL ABOVE entry, Target BELOW entry
                sl = round(entry + stop_dist, px_nd)
                if kronos_report and kronos_report.suggested_stop and kronos_report.suggested_stop > entry:
                    sl = min(sl, round(kronos_report.suggested_stop, px_nd))
                    stop_dist = max(entry * 0.001, sl - entry)

                target_mult = 2.5 if (is_news_bearish or (kronos_report and kronos_report.confidence >= 0.75)) else 2.1
                tgt_1 = round(entry - (stop_dist * target_mult), px_nd)
                tgt_2 = round(entry - (stop_dist * (target_mult + 1.5)), px_nd)

                if kronos_report and kronos_report.suggested_target and 0 < kronos_report.suggested_target < tgt_1:
                    tgt_1 = round(kronos_report.suggested_target, px_nd)
                    target_mult = round((entry - tgt_1) / stop_dist, 1)

                conf = max(0.72, min(0.92, (-debate.consensus_score + 1.0) / 2.0))
                theses = [
                    f"Bearish Short Momentum: Breakdown verified by Technical ({'Bearish' if is_tech_bearish else 'Neutral'}) & Debate consensus ({debate.consensus_score:+.2f}).",
                    debate.bear_thesis or "Distribution volume and technical breakdown confirm downward line of least resistance.",
                ]
                if kronos_report and kronos_report.key_observations:
                    theses.append(f"Kronos Foundation Model: {kronos_report.key_observations[1] if len(kronos_report.key_observations) > 1 else kronos_report.key_observations[0]}")

                logger.info(
                    f"⚡ [FundManager] Capitalizing on Bearish Breakdown with SHORT entry on {signal.symbol} "
                    f"(Entry: {cs}{entry}, SL: {cs}{sl}, TGT: {cs}{tgt_1}, R:R: {target_mult}:1)"
                )
                return TradeDecision(
                    analysis_id=analysis_id,
                    symbol=signal.symbol,
                    exchange="DELTA",
                    decision=TradeAction.SELL,
                    confidence=conf,
                    entry_price=entry,
                    stop_loss=sl,
                    target_1=tgt_1,
                    target_2=tgt_2,
                    expected_risk_reward=round(target_mult, 1),
                    thesis=theses,
                    supporting_evidence=[obs for r in reports for obs in r.key_observations][:4] or ["Downside distribution & breakdown trajectory intact"],
                    opposing_evidence=[warn for r in reports for warn in r.risk_warnings][:2] or ["Potential short covering rally"],
                    risk_factors=["Crypto intraday volatility spike"],
                    invalidation_conditions=debate.invalidating_scenarios or [f"Reclaim above stop loss {cs}{sl}"],
                    strategy_version=self.strategy_version,
                    prompt_version=self.prompt_version,
                )

            # -------------------------------------------------------------
            # B) BULLISH / LONG DIRECTION
            # -------------------------------------------------------------
            # If Kronos predicts breakdown on long candidates, stand aside from long
            if is_kronos_bearish and not is_crypto:
                logger.warning(f"🛡️ [FundManager] Kronos Foundation Model predicts breakdown on {signal.symbol}. Standing aside.")
                return TradeDecision(
                    analysis_id=analysis_id,
                    symbol=signal.symbol,
                    exchange="NSE",
                    decision=TradeAction.NO_TRADE,
                    confidence=0.35,
                    entry_price=signal.ltp,
                    stop_loss=0.0,
                    target_1=0.0,
                    expected_risk_reward=0.0,
                    thesis=[f"Kronos Foundation Model projected price breakdown (Confidence: {kronos_report.confidence*100:.0f}%). Long entry vetoed."],
                    supporting_evidence=[],
                    opposing_evidence=kronos_report.risk_warnings or ["Kronos neural trajectory projects downward breakdown."],
                    risk_factors=["Severe predictive breakdown risk"],
                    invalidation_conditions=["Kronos forecast invalidation"],
                    strategy_version=self.strategy_version,
                    prompt_version=self.prompt_version,
                )

            is_strong_bull_consensus = debate.consensus_score >= 0.30 and (is_tech_bullish or is_fund_bullish or is_news_bullish)
            is_overwhelming_bull_consensus = debate.consensus_score >= 0.50

            if (is_strong_bull_consensus or is_overwhelming_bull_consensus) and not is_kronos_bearish:
                sl = round(entry - stop_dist, px_nd)
                if kronos_report and kronos_report.suggested_stop and 0 < kronos_report.suggested_stop < entry:
                    sl = max(sl, round(kronos_report.suggested_stop, px_nd))
                    stop_dist = max(entry * 0.001, entry - sl)

                target_mult = 2.5 if (is_fund_bullish and is_news_bullish) else 2.1
                tgt_1 = round(entry + (stop_dist * target_mult), px_nd)
                tgt_2 = round(entry + (stop_dist * (target_mult + 1.5)), px_nd)

                if kronos_report and kronos_report.suggested_target and kronos_report.suggested_target > tgt_1:
                    tgt_1 = round(kronos_report.suggested_target, px_nd)
                    target_mult = round((tgt_1 - entry) / stop_dist, 1)

                conf = max(0.72, min(0.92, (debate.consensus_score + 1.0) / 2.0))
                theses = [
                    f"Multi-Factor Alignment: Trend ({'Bullish' if is_tech_bullish else 'Neutral'}), Growth ({'Strong' if is_fund_bullish else 'Stable'}), News ({'Positive' if is_news_bullish else 'Neutral'}).",
                    debate.bull_thesis or "Technical momentum and company valuation support upside expansion.",
                ]
                if kronos_report and kronos_report.key_observations:
                    theses.append(f"Kronos Foundation Model: {kronos_report.key_observations[1] if len(kronos_report.key_observations) > 1 else kronos_report.key_observations[0]}")

                return TradeDecision(
                    analysis_id=analysis_id,
                    symbol=signal.symbol,
                    exchange="DELTA" if is_crypto else "NSE",
                    decision=TradeAction.BUY,
                    confidence=conf,
                    entry_price=entry,
                    stop_loss=sl,
                    target_1=tgt_1,
                    target_2=tgt_2,
                    expected_risk_reward=round(target_mult, 1),
                    thesis=theses,
                    supporting_evidence=[obs for r in reports for obs in r.key_observations][:4] or ["Company growth & trend structure intact"],
                    opposing_evidence=[warn for r in reports for warn in r.risk_warnings][:2] or ["Intraday volatility"],
                    risk_factors=["Normal market execution variance"],
                    invalidation_conditions=debate.invalidating_scenarios or [f"Break below tight stop loss {cs}{sl}"],
                    strategy_version=self.strategy_version,
                    prompt_version=self.prompt_version,
                )
            else:
                return TradeDecision(
                    analysis_id=analysis_id,
                    symbol=signal.symbol,
                    exchange="DELTA" if is_crypto else "NSE",
                    decision=TradeAction.NO_TRADE,
                    confidence=0.40,
                    entry_price=signal.ltp,
                    stop_loss=0.0,
                    target_1=0.0,
                    expected_risk_reward=0.0,
                    thesis=[f"Directional consensus ({debate.consensus_score:+.2f}) insufficient for capital deployment."],
                    supporting_evidence=[],
                    opposing_evidence=[debate.bear_thesis if debate.consensus_score >= 0 else debate.bull_thesis],
                    risk_factors=["Uncertain market edge or conflicting signals"],
                    invalidation_conditions=["Consensus reversal"],
                    strategy_version=self.strategy_version,
                    prompt_version=self.prompt_version,
                )

        return await router.generate_structured(
            schema=TradeDecision,
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            model_name=settings.MODEL_REASONING,
            fallback_factory=fallback,
        )
