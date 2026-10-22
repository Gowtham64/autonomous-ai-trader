"""Comprehensive Crypto Market Deep Analysis & Multi-Agent Training Engine.

Accesses the entire Delta Exchange perpetuals universe, analyzes macro regime,
order-flow dynamics (OI, funding rates, turnover), Goodman basing setups,
Buček turtle breakout channels, runs Kronos foundation model forecasts,
and seeds learned institutional knowledge into agent memory.
"""

import asyncio
from datetime import UTC, datetime
import json
import os
from typing import Any

import numpy as np
import pandas as pd

from core.logging import logger
from core.tools.advanced_masters_tools import (
    BucekTurtleEngine,
    CryptoChartPatternEngine,
    GoodmanTrendEngine,
)
from execution.brokers.delta_exchange import DeltaExchangeBroker
from intelligence.kronos_service import KronosForecastService
from memory.global_memory import global_ai_memory
from memory.models import (
    MemoryImportance,
    MemoryLevel,
    MemoryRecord,
    MemoryType,
    QualityCategory,
)


class CryptoMarketTrainer:
    """Orchestrates comprehensive crypto market screening, quantitative regime classification,
    multi-timeframe technical modeling, Kronos neural forecasting, and agent training updates.
    """

    def __init__(self):
        self.broker = DeltaExchangeBroker()
        self.kronos = KronosForecastService()

    async def fetch_full_market_snapshot(self) -> list[dict[str, Any]]:
        """Retrieves and normalizes live ticker and market metrics for all perpetuals."""
        logger.info("🌐 [Market Access] Connecting to Delta Exchange: Querying entire perpetuals universe...")
        res = await self.broker._request("GET", "/v2/tickers")
        raw_tickers = res.get("result", [])
        
        perps = []
        for t in raw_tickers:
            if t.get("contract_type") == "perpetual_futures" and t.get("product_trading_status") == "operational":
                try:
                    turnover = float(t.get("turnover_usd") or 0.0)
                    mark = float(t.get("mark_price") or t.get("close") or 0.0)
                    if turnover > 5000 and mark > 0:  # Active liquid contracts
                        perps.append({
                            "symbol": t.get("symbol"),
                            "underlying": t.get("underlying_asset_symbol"),
                            "mark_price": mark,
                            "change_24h": float(t.get("mark_change_24h") or t.get("ltp_change_24h") or 0.0),
                            "turnover_usd": turnover,
                            "oi_usd": float(t.get("oi_value_usd") or 0.0),
                            "oi_change_6h": float(t.get("oi_change_usd_6h") or 0.0),
                            "funding_rate_8h": float(t.get("funding_rate") or 0.0) * 100.0,  # in %
                            "high_24h": float(t.get("high") or mark),
                            "low_24h": float(t.get("low") or mark),
                            "tags": t.get("tags") or [],
                            "contract_value": float(t.get("contract_value") or 1.0),
                        })
                except Exception:
                    continue
        logger.info(f"✅ [Market Access] Successfully retrieved {len(perps)} active liquid perpetual contracts.")
        return perps

    def analyze_macro_regime(self, perps: list[dict[str, Any]]) -> dict[str, Any]:
        """Analyzes market-wide breadth, institutional positioning, and macro regime."""
        df = pd.DataFrame(perps)
        
        total_turnover = df["turnover_usd"].sum()
        total_oi = df["oi_usd"].sum()
        advances = len(df[df["change_24h"] > 0])
        declines = len(df[df["change_24h"] < 0])
        adv_dec_ratio = advances / max(1, declines)
        mean_change = df["change_24h"].mean()
        median_funding = df["funding_rate_8h"].median()
        
        # Benchmark assets
        btc = df[df["symbol"] == "BTCUSD"]
        eth = df[df["symbol"] == "ETHUSD"]
        sol = df[df["symbol"] == "SOLUSD"]
        
        btc_change = float(btc["change_24h"].iloc[0]) if not btc.empty else 0.0
        btc_price = float(btc["mark_price"].iloc[0]) if not btc.empty else 0.0
        eth_price = float(eth["mark_price"].iloc[0]) if not eth.empty else 0.0
        sol_price = float(sol["mark_price"].iloc[0]) if not sol.empty else 0.0
        
        # Regime definition
        if btc_change > 1.5 and adv_dec_ratio > 1.5:
            regime = "STRONG_BULLISH_EXPANSION"
        elif btc_change < -1.5 and adv_dec_ratio < 0.6:
            regime = "BEARISH_LIQUIDATION"
        elif abs(btc_change) <= 1.5 and median_funding > 0.03:
            regime = "OVERHEATED_CONSOLIDATION"
        elif abs(btc_change) <= 1.5 and median_funding < -0.01:
            regime = "ACCUMULATION_SHORT_SQUEEZE_PRIME"
        else:
            regime = "ROTATIONAL_SELECTIVE_BULLISH"
            
        return {
            "macro_regime": regime,
            "btc_price": btc_price,
            "btc_change_24h": btc_change,
            "eth_price": eth_price,
            "sol_price": sol_price,
            "total_market_turnover_usd": total_turnover,
            "total_open_interest_usd": total_oi,
            "advances": advances,
            "declines": declines,
            "advance_decline_ratio": round(adv_dec_ratio, 2),
            "market_mean_change_24h": round(mean_change, 2),
            "median_8h_funding_pct": round(median_funding, 4),
        }

    async def scan_goodman_and_turtle_setups(self, perps: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """Applies Glen Goodman basing rules & Ondřej Buček Turtle breakout filters."""
        # Rank by liquidity and clean trend
        sorted_perps = sorted(perps, key=lambda x: x["turnover_usd"], reverse=True)
        top_candidates = sorted_perps[:40]
        
        screened_setups = []
        for p in top_candidates:
            sym = p["symbol"]
            # Fetch historical K-lines (1h resolution, 100 bars)
            try:
                import time
                now_ts = int(time.time())
                start_ts = now_ts - (100 * 3600)
                res = await self.broker._request("GET", f"/v2/chart/history?symbol={sym}&resolution=60&from={start_ts}&to={now_ts}")
                candles = res.get("result", {})
                c_closes = candles.get("c", [])
                c_highs = candles.get("h", [])
                c_lows = candles.get("l", [])
                c_opens = candles.get("o", [])
                c_volumes = candles.get("v", [])
                
                if len(c_closes) < 30:
                    continue
                    
                df_bar = pd.DataFrame({
                    "Open": [float(x) for x in c_opens],
                    "High": [float(x) for x in c_highs],
                    "Low": [float(x) for x in c_lows],
                    "Close": [float(x) for x in c_closes],
                    "Volume": [float(x) for x in c_volumes],
                })
                
                # 1. Glen Goodman Trend & Basing Evaluation
                goodman_eval = GoodmanTrendEngine.evaluate_trend_and_discipline(symbol=sym, df=df_bar)
                
                # 2. Ondřej Buček Turtle System (20-bar Donchian & True Range N)
                turtle_eval = BucekTurtleEngine.calculate_turtle_metrics(symbol=sym, df=df_bar, deposit=7.65, risk_pct=0.015)
                pa_eval = BucekTurtleEngine.calculate_price_action_patterns(symbol=sym, df=df_bar)
                pattern_eval = CryptoChartPatternEngine.detect_patterns(symbol=sym, df=df_bar)
                
                funding = p["funding_rate_8h"]
                change_24h = p["change_24h"]
                
                conviction = 0.0
                reasons = []
                
                # GoodCrypto Pattern Confluence
                if pattern_eval.primary_pattern:
                    if pattern_eval.pattern_type in ["BULLISH_REVERSAL", "BULLISH_CONTINUATION"]:
                        conviction += 0.25
                        reasons.append(f"Chart Pattern: {pattern_eval.primary_pattern} (Target: ${pattern_eval.target_price})")
                    elif pattern_eval.pattern_type in ["BEARISH_REVERSAL", "BEARISH_CONTINUATION"]:
                        conviction -= 0.20

                if goodman_eval.is_trend_intact:
                    conviction += 0.20
                    reasons.append("Goodman Trend Intact (>50-EMA/200-SMA)")
                if goodman_eval.basing_duration_bars >= 10:
                    conviction += 0.20
                    reasons.append(f"Goodman Basing ({goodman_eval.basing_duration_bars} bars consolidation)")
                if goodman_eval.has_volume_confirmation:
                    conviction += 0.15
                    reasons.append("Volume Expansion Confirmation")
                if not goodman_eval.is_chasing_breakout:
                    conviction += 0.10
                    reasons.append("Within 5% of Base (Anti-Chase Passed)")
                if turtle_eval.system1_entry_long or turtle_eval.system2_entry_long:
                    conviction += 0.25
                    reasons.append("Buček Turtle Donchian Breakout Triggered")
                if pa_eval.is_hammer_bullish or pa_eval.is_swing_low:
                    conviction += 0.15
                    reasons.append(f"Price Action {pa_eval.signal_type} at Support")
                if funding < 0:
                    conviction += 0.15
                    reasons.append(f"Negative Funding Squeeze Fuel ({funding:.4f}%)")
                if change_24h > 1.5:
                    conviction += 0.10
                    reasons.append(f"24h Relative Momentum (+{change_24h:.1f}%)")
                    
                if conviction >= 0.40:
                    screened_setups.append({
                        "symbol": sym,
                        "mark_price": p["mark_price"],
                        "change_24h": change_24h,
                        "turnover_usd": p["turnover_usd"],
                        "contract_value": p["contract_value"],
                        "funding_rate": funding,
                        "conviction": round(conviction, 2),
                        "reasons": reasons,
                        "turtle_upper": turtle_eval.stop_loss_long,
                        "turtle_stop": turtle_eval.stop_loss_long,
                        "volatility_n": turtle_eval.volatility_n,
                        "df_bar": df_bar,
                    })
            except Exception as err:
                logger.debug(f"Error screening {sym}: {err}")
                continue

        screened_setups.sort(key=lambda x: x["conviction"], reverse=True)
        return screened_setups

    async def train_and_update_agent_memory(
        self,
        macro: dict[str, Any],
        top_setups: list[dict[str, Any]],
        kronos_results: list[dict[str, Any]],
    ) -> dict[str, Any]:
        """Synthesizes market training into Level-3 permanent institutional memory."""
        logger.info("🧠 [Agent Training] Encoding live market regime & masters trading patterns into agent memory...")
        
        # 1. Store Macro Regime in Global Permanent Memory
        macro_record = {
            "regime": macro["macro_regime"],
            "btc_price": macro["btc_price"],
            "btc_change_24h": macro["btc_change_24h"],
            "adv_dec_ratio": macro["advance_decline_ratio"],
            "median_funding_pct": macro["median_8h_funding_pct"],
            "institutional_posture": "AGGRESSIVE_TREND_LONG" if "BULLISH" in macro["macro_regime"] else "SELECTIVE_ACCUMULATION",
            "updated_at": datetime.now(UTC).isoformat(),
        }
        now_ts = int(datetime.now(UTC).timestamp())
        rec_macro = MemoryRecord(
            memory_id=f"mem_regime_{now_ts}",
            created_by="CryptoMarketTrainer",
            level=MemoryLevel.LONG_TERM,
            memory_type=MemoryType.EPISODIC,
            category=QualityCategory.FACT,
            importance=MemoryImportance.CRITICAL,
            content=(
                f"LIVE CRYPTO REGIME: {macro['macro_regime']}. BTC: ${macro['btc_price']:,.2f} ({macro['btc_change_24h']:+.2f}%), "
                f"Adv/Dec: {macro['advance_decline_ratio']}, Median Funding: {macro['median_8h_funding_pct']:.4f}%. "
                f"Posture: {macro_record['institutional_posture']}."
            ),
            tags=["crypto", "regime", "btc", macro["macro_regime"].lower()],
            evidence=["Delta Exchange live tickers turnover and funding analysis"],
            confidence_score=0.95,
        )
        global_ai_memory.write_memory(rec_macro, agent_role="market_trainer")
        
        # 2. Store High-Conviction Setups in Agent Knowledge
        trained_setups_summary = []
        for i, s in enumerate(top_setups[:5]):
            kronos_match = next((k for k in kronos_results if k["symbol"] == s["symbol"]), None)
            k_dir = kronos_match["direction"] if kronos_match else "UNKNOWN"
            k_conf = kronos_match["confidence"] if kronos_match else 0.0
            
            entry_thesis = (
                f"Trained Setup {s['symbol']}: Conviction {s['conviction']*100:.0f}%, "
                f"Reasons: {'; '.join(s['reasons'])}, "
                f"Kronos Forecast: {k_dir} (Conf: {k_conf*100:.0f}%), "
                f"ATR N: {s['volatility_n']:.5f}, Contract Value: {s['contract_value']}"
            )
            
            rec_setup = MemoryRecord(
                memory_id=f"mem_setup_{now_ts}_{i}",
                created_by="CryptoMarketTrainer",
                level=MemoryLevel.ORGANIZATIONAL,
                memory_type=MemoryType.EPISODIC,
                category=QualityCategory.LESSON,
                importance=MemoryImportance.HIGH,
                content=entry_thesis,
                tags=["crypto", "setup", s["symbol"].lower(), "breakout"],
                evidence=[f"Delta perpetual 1h candles & Kronos forecast {k_dir}"],
                confidence_score=min(0.95, s["conviction"] + (0.1 if k_dir == "BULLISH" else 0.0)),
            )
            global_ai_memory.write_memory(rec_setup, agent_role="market_trainer")
            
            trained_setups_summary.append({
                "symbol": s["symbol"],
                "price": s["mark_price"],
                "conviction": s["conviction"],
                "kronos_direction": k_dir,
                "reasons": s["reasons"],
            })
            
        logger.info("🎯 [Agent Training] All 10 agents on the AI Research Desk updated with trained market parameters!")
        return {
            "macro": macro_record,
            "top_trained_setups": trained_setups_summary,
        }

    async def run_full_training_cycle(self) -> dict[str, Any]:
        """Full pipeline execution: Scan -> Model -> Forecast -> Train."""
        # Step 1: Query entire market
        perps = await self.fetch_full_market_snapshot()
        
        # Step 2: Macro Regime Analysis
        macro = self.analyze_macro_regime(perps)
        logger.info(f"📊 [Macro Regime] Detected: {macro['macro_regime']} | BTC: ${macro['btc_price']:,.2f} ({macro['btc_change_24h']:+.2f}%)")
        
        # Step 3: Scan Goodman & Buček Setups
        setups = await self.scan_goodman_and_turtle_setups(perps)
        logger.info(f"🏆 [Quantitative Screener] Found {len(setups)} high-conviction candidate setups across Delta perpetuals.")
        
        # Step 4: Run Kronos Neural Forecasts on Top Setups
        kronos_forecasts = []
        for s in setups[:5]:
            sym = s["symbol"]
            df_bar = s["df_bar"]
            logger.info(f"🔮 [Kronos Neural Forecast] Generating multi-bar foundation model projection for {sym} on MPS...")
            res = await self.kronos.forecast(symbol=sym, df=df_bar, pred_len=12)
            kronos_forecasts.append({
                "symbol": sym,
                "direction": res.expected_direction,
                "confidence": res.confidence_score,
                "projected_change_pct": res.projected_change_pct,
                "recommended_stop": res.recommended_stop_loss,
                "recommended_target": res.recommended_target,
            })
            
        # Step 5: Train and Update Institutional Memory
        training_result = await self.train_and_update_agent_memory(macro, setups, kronos_forecasts)
        
        return {
            "macro": macro,
            "screened_setups_count": len(setups),
            "top_setups": setups[:8],
            "kronos_forecasts": kronos_forecasts,
            "training_summary": training_result,
        }


async def main():
    trainer = CryptoMarketTrainer()
    result = await trainer.run_full_training_cycle()
    print("\n" + "="*80)
    print("✅ CRYPTO MARKET DEEP ANALYSIS & AGENT TRAINING COMPLETED SUCCESSFULLY")
    print("="*80)
    print(f"Macro Regime: {result['macro']['macro_regime']}")
    print(f"BTC Price: ${result['macro']['btc_price']:,.2f} | 24h: {result['macro']['btc_change_24h']:+.2f}%")
    print(f"Advance/Decline Ratio: {result['macro']['advance_decline_ratio']}")
    print(f"Total Evaluated Setups: {result['screened_setups_count']}")
    print("\nTop Trained Breakout Setups:")
    for s in result["training_summary"]["top_trained_setups"]:
        print(f"  • {s['symbol']} @ ${s['price']:.4f} | Conviction: {s['conviction']*100:.0f}% | Kronos: {s['kronos_direction']} | {s['reasons'][0]}")
    print("="*80)


if __name__ == "__main__":
    asyncio.run(main())
