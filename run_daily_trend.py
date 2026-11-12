"""Run the daily trend-following strategy (the one with a backtested edge).

    python run_daily_trend.py            # loop forever, checking every DAILY_TREND_POLL_MINUTES
    python run_daily_trend.py --once     # one cycle, print what happened, exit

PAPER FIRST. Real orders are sent only when ALL of these are set in .env:
    TRADING_MODE=live
    LIVE_TRADING_ENABLED=true
    DAILY_TREND_ALLOW_LIVE=true
Otherwise it trades an isolated paper account of DAILY_TREND_PAPER_CAPITAL (default $500),
stored in data/daily_trend_paper_broker.json, so the paper record is realistic in size.

Before going live: run paper for 2-3 months and compare with
    python tools/backtest_trend_daily.py --majors --source binance
"""

import argparse
import asyncio
import json
import os
import sys

from dotenv import load_dotenv

load_dotenv()
sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))

from apps.daemon.daily_trend_engine import STRATEGY_TAG, DailyTrendEngine  # noqa: E402
from core.config.settings import TradingMode, settings  # noqa: E402
from core.logging import logger  # noqa: E402
from portfolio.position_sizer import get_delta_contract_multiplier  # noqa: E402
from risk.kill_switch import kill_switch  # noqa: E402

COMMAND_POLL_SECONDS = 2


def live_allowed() -> bool:
    return (
        settings.TRADING_MODE == TradingMode.LIVE
        and bool(settings.LIVE_TRADING_ENABLED)
        and bool(settings.DAILY_TREND_ALLOW_LIVE)
    )


def build_engine() -> DailyTrendEngine:
    from market.providers.yfinance_provider import YFinanceMarketDataProvider

    provider = YFinanceMarketDataProvider()
    is_live = live_allowed()
    if is_live:
        from execution.broker_factory import get_active_broker
        broker = get_active_broker("delta")
        logger.warning("💰 [Daily Trend] LIVE MODE: real orders on Delta Exchange.")
    else:
        from execution.paper.delta_paper import DeltaPaperBroker
        broker = DeltaPaperBroker(
            initial_capital=settings.DAILY_TREND_PAPER_CAPITAL,
            state_file="data/daily_trend_paper_broker.json",
        )
        logger.info(
            f"📝 [Daily Trend] PAPER MODE (${settings.DAILY_TREND_PAPER_CAPITAL:.0f} isolated paper account). "
            f"Live requires TRADING_MODE=live, LIVE_TRADING_ENABLED=true and DAILY_TREND_ALLOW_LIVE=true."
        )

    async def candles(sym: str):
        # ~200 completed days covers the 55-day breakout, 20-day exit and ATR(20) warm-up.
        return await provider._get_delta_historical_ohlcv(sym, interval="1d", period="200d")

    async def mark(sym: str) -> float:
        return await provider.get_ltp(sym)

    async def journal(**kw):
        from database.repositories.trade_repo import TradeRepository
        await TradeRepository.save_journal(**kw)

    async def stats() -> dict:
        from database.repositories.trade_repo import TradeRepository
        return await TradeRepository.get_journal_win_stats(
            hours=24 * 3650, limit=settings.EDGE_GATE_LOOKBACK_TRADES, strategy_tag=STRATEGY_TAG,
        )

    return DailyTrendEngine(
        broker=broker,
        candles_fn=candles,
        mark_fn=mark,
        multiplier_fn=get_delta_contract_multiplier,
        journal_fn=journal,
        stats_fn=stats,
        is_live=is_live,
        state_path="data/daily_trend_state.json",
    )


async def main(once: bool) -> None:
    from database.session import init_db
    await init_db()

    if os.getenv("KILL_SWITCH_RESET_ON_START", "").lower() in ("1", "true", "yes"):
        kill_switch.reset("Daily Trend Launcher (KILL_SWITCH_RESET_ON_START)")
    elif kill_switch.is_engaged:
        logger.critical(f"🛑 Kill switch ENGAGED: {kill_switch.reason}. Exits are still managed; no new entries until reset.")

    engine = build_engine()
    stuck = engine.store.requeue_stuck_commands()
    if stuck:
        logger.warning(f"[Daily Trend] {stuck} terminal command(s) were mid-execution at the last shutdown; "
                       f"marked FAILED (check positions before retrying).")
    cycle_every = settings.DAILY_TREND_POLL_MINUTES * 60
    next_cycle = 0.0
    loop = asyncio.get_running_loop()
    while True:
        if loop.time() >= next_cycle:
            try:
                summary = await engine.run_cycle()
                if once or summary["entries"] or summary["exits"] or summary["stops_moved"]:
                    print(json.dumps(summary, indent=2, default=str))
                else:
                    logger.info(
                        f"[Daily Trend] {summary['mode']} equity ${summary['equity']:.2f} | "
                        f"open: {list(summary['open_positions'])} | next check in {settings.DAILY_TREND_POLL_MINUTES}m"
                    )
            except Exception as e:
                logger.error(f"[Daily Trend] Cycle error: {e}")
                if once:
                    raise
            next_cycle = loop.time() + cycle_every
            if once:
                return
        # Terminal commands (close, move stop, ...) are handled within seconds, between cycles.
        try:
            for r in await engine.process_commands():
                logger.info(f"[Daily Trend] Terminal command {r['id'][:8]}: {r.get('message') or r.get('error')}")
            engine.write_heartbeat()
        except Exception as e:
            logger.error(f"[Daily Trend] Command processing error: {e}")
        await asyncio.sleep(COMMAND_POLL_SECONDS)


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--once", action="store_true", help="Run one cycle and exit")
    asyncio.run(main(ap.parse_args().once))
