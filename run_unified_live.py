"""
Autonomous AI Trading Office — Unified 24/7 Crypto & Indian Market Live Orchestrator
Runs 24/7 Crypto Perpetuals continuously, and automatically starts Indian Equity (NSE/BSE) trading the instant the market opens.
"""

import argparse
import asyncio
import json
import os
import sys
import time
from datetime import UTC, datetime
from dotenv import load_dotenv

# Ensure .env is loaded before anything else
load_dotenv()

from rich.console import Console
from rich.panel import Panel

# Ensure project root is in sys.path
sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))

from apps.daemon.state_machine import AutonomousTradingDaemon
from core.config.settings import settings
from database.session import init_db
from execution.broker_factory import get_active_broker
from execution.brokers.angelone import AngelOneBroker
from market.calendar import IndianMarketCalendar
from market.providers.yfinance_provider import YFinanceMarketDataProvider
from market.streamers.angelone_ws import angelone_streamer
from portfolio.broker_truth_verifier import BrokerTruthVerifier
from risk.kill_switch import kill_switch
from scanner.quant_scanner import QuantMarketScanner

console = Console()
background_tasks: set[asyncio.Task] = set()

BASELINE_STATE_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data", "baseline_state.json")


def resolve_baseline(broker_key: str, current_equity: float, env_var: str) -> float:
    """Fully automatic profit-target baseline: env override > persisted state > self-initialize.

    On the very first run the live broker equity is captured and persisted, so nobody
    has to hand-edit baseline env values as the account grows or shrinks.
    """
    env_val = os.getenv(env_var)
    if env_val:
        try:
            return float(env_val)
        except ValueError:
            pass
    state: dict = {}
    try:
        with open(BASELINE_STATE_PATH) as f:
            state = json.load(f) or {}
    except Exception:
        state = {}
    if float(state.get(broker_key, 0.0) or 0.0) > 0:
        return float(state[broker_key])
    if current_equity > 0:
        state[broker_key] = round(float(current_equity), 2)
        try:
            os.makedirs(os.path.dirname(BASELINE_STATE_PATH), exist_ok=True)
            with open(BASELINE_STATE_PATH, "w") as f:
                json.dump(state, f, indent=2)
            console.print(f"[cyan]📌 [Baseline Auto-Init] {broker_key} profit baseline captured at {state[broker_key]} and persisted.[/cyan]")
        except Exception:
            pass
        return float(state[broker_key])
    return 0.0


async def run_unified_trading_office(duration_hours: float | None = None, focus_broker: str = "all"):
    console.print(Panel(
        "[bold cyan]AUTONOMOUS AI TRADING OFFICE — DUAL-MARKET INDEPENDENT TARGET ENGINE[/bold cyan]\n"
        "• [bold green]Crypto Engine (Delta Exchange):[/bold green] 24/7 Perpetuals | Target: [bold yellow]+$25.00 USD Net Profit ($15–$25 Milestone)[/bold yellow]\n"
        "• [bold green]Equity Engine (AngelOne SmartAPI):[/bold green] NSE/BSE Equities | Target: [bold yellow]+$12.00 USD (₹1,050.00 INR) Net Profit[/bold yellow]\n"
        "• [bold magenta]Target Invariant:[/bold magenta] Targets are completely isolated per brokerage (not combined)\n"
        "• [bold yellow]Intelligence:[/bold yellow] Google Gemini (2.5 Pro / Flash) + Kronos MPS Candlestick Foundation Model\n"
        "• [bold red]Safeguards:[/bold red] 15-Point Pre-Trade Audit Gate + Delta Native Brackets + SmartAPI RMS Limits",
        title="[bold green]Unified AI Trading Office Startup[/bold green]"
    ))

    # 1. Initialize SQLite Database Tables
    console.print("[cyan]1. Initializing institutional database schema...[/cyan]")
    await init_db()

    provider = YFinanceMarketDataProvider()

    # 2. Initialize Delta Exchange (Crypto Perpetuals)
    console.print("[cyan]2. Connecting to Delta Exchange India (Crypto 24/7/365)...[/cyan]")
    crypto_broker = get_active_broker("delta")
    crypto_funds = await crypto_broker.get_funds()
    crypto_margin = float(crypto_funds.get("available_margin", 0.0))
    console.print(f"[bold green]💰 Delta Available Margin: ${crypto_margin:.2f} USD[/bold green]")
    delta_baseline_equity = resolve_baseline("delta", float(crypto_funds.get("total_capital", crypto_margin)), "DELTA_BASELINE_EQUITY")

    crypto_scanner = QuantMarketScanner(provider=provider, universe="delta", max_concurrency=25)
    crypto_daemon = AutonomousTradingDaemon(
        scanner=crypto_scanner,
        broker=crypto_broker,
        total_capital=float(crypto_funds.get("total_capital", crypto_margin)),
        top_n_candidates=10,
    )

    equity_daemon = None
    equity_broker = None
    equity_ws_active = False
    angel_auth = False

    if focus_broker != "delta":
        # 3. Initialize Angel One (NSE/BSE)
        console.print("[cyan]3. Connecting to AngelOne SmartAPI (NSE/BSE Equities)...[/cyan]")
        equity_broker = get_active_broker("angelone")
        eq_funds: dict = {}
        equity_margin = 0.0  # defined up-front: referenced below even when authentication fails
        angel_baseline_equity = 0.0
        if isinstance(equity_broker, AngelOneBroker):
            auth_res = await equity_broker.authenticate_session()
            angel_auth = auth_res.get("authenticated", False)
            if angel_auth:
                console.print(f"[bold green]✅ AngelOne SmartAPI Authenticated for Client: {settings.ANGELONE_CLIENT_CODE}![/bold green]")
                eq_funds = await equity_broker.get_funds()
                equity_margin = float(eq_funds.get("available_margin", 0.0))
                console.print(f"[bold green]💰 AngelOne Live Margin: ₹{equity_margin:,.2f}[/bold green]")
                angel_baseline_equity = resolve_baseline("angelone", float(eq_funds.get("total_capital", equity_margin)), "ANGEL_BASELINE_EQUITY")
            else:
                console.print(f"[yellow]⚠️ AngelOne live session pending ({auth_res.get('error', 'Using Paper/Simulation')}). Ready for market open.[/yellow]")

        equity_scanner = QuantMarketScanner(provider=provider, universe="all", max_concurrency=25)
        equity_daemon = AutonomousTradingDaemon(
            scanner=equity_scanner,
            broker=equity_broker,
            total_capital=float(eq_funds.get("total_capital", equity_margin)) if angel_auth else equity_margin,
            top_n_candidates=10,
        )
    else:
        console.print("[bold yellow]⚡ [Delta Exclusive Mode Active] 100% compute & velocity focused solely on Delta Exchange ($25 USD target).[/bold yellow]")

    kill_switch.reset("Unified Live Launcher")
    console.print(f"\n[bold green]🚀 AI Trading Engine ({'Delta 24/7 Exclusive' if focus_broker == 'delta' else 'Unified'}) is fully ARMED and ACTIVE![/bold green]\n")

    cycle_count = 0
    start_monotonic = time.monotonic()

    try:
        while True:
            # Check duration limit if specified
            if duration_hours is not None and duration_hours > 0:
                elapsed_seconds = time.monotonic() - start_monotonic
                if elapsed_seconds >= (duration_hours * 3600.0):
                    console.print(
                        f"\n[bold green]🏁 Completed requested {duration_hours:.1f}-hour autonomous session "
                        f"({elapsed_seconds / 60:.1f} minutes elapsed). Exiting cleanly.[/bold green]"
                    )
                    break

            cycle_count += 1
            now_ist = IndianMarketCalendar.now_ist()
            now_str = now_ist.strftime("%H:%M:%S")

            # -----------------------------------------------------------------
            # A) 24/7 CRYPTO ENGINE CYCLE (Runs Continuously on Delta Exchange)
            # -----------------------------------------------------------------
            try:
                console.print(f"\n[bold magenta]🪙 [Cycle #{cycle_count} | {now_str} IST] Executing 24/7 Crypto Cycle (Delta Exchange)...[/bold magenta]")
                # Auto-cancel stale unfilled limit orders older than 3 minutes to prevent blocked margin
                if hasattr(crypto_broker, "cancel_stale_orders"):
                    await crypto_broker.cancel_stale_orders(max_age_seconds=180)
                crypto_summary = await crypto_daemon.run_single_cycle()
                crypto_avail = crypto_summary.get("available_margin", 0.0)
                crypto_orders = crypto_summary.get("orders_executed", 0)

                DELTA_BASELINE_EQUITY = delta_baseline_equity
                target_equity_env = os.getenv("DELTA_TARGET_EQUITY")
                if target_equity_env:
                    DELTA_TARGET_EQUITY = float(target_equity_env)
                    DELTA_TARGET_PROFIT = round(max(0.01, DELTA_TARGET_EQUITY - DELTA_BASELINE_EQUITY), 2)
                else:
                    DELTA_TARGET_PROFIT = float(os.getenv("DELTA_TARGET_PROFIT", "15.88"))
                    DELTA_TARGET_EQUITY = DELTA_BASELINE_EQUITY + DELTA_TARGET_PROFIT

                # Ground truth ledger for Crypto
                crypto_truth = await BrokerTruthVerifier.compute_and_record_truth(
                    broker=crypto_broker,
                    internal_claimed_pnl=crypto_summary.get("realized_pnl", 0.0),
                    baseline_capital=DELTA_BASELINE_EQUITY,
                )

                funds_now = await crypto_broker.get_funds()
                current_delta_equity = float(funds_now.get("total_capital", crypto_avail))
                delta_profit_made = round(current_delta_equity - DELTA_BASELINE_EQUITY, 2)
                remaining_needed = round(max(0.0, DELTA_TARGET_PROFIT - delta_profit_made), 2)
                progress_pct = max(0.0, min(100.0, (delta_profit_made / DELTA_TARGET_PROFIT) * 100.0))

                console.print(
                    f"  🪙 [bold cyan]Crypto (Delta):[/bold cyan] Equity: ${current_delta_equity:.2f} | Margin: ${crypto_avail:.2f} | "
                    f"Scanned: {crypto_summary.get('candidates_scanned', 0)} | "
                    f"Debated: {crypto_summary.get('debates_conducted', 0)} | "
                    f"Executed: {crypto_orders}"
                )
                console.print(
                    f"  🎯 [bold yellow]Delta $25 Target (Wednesday Goal):[/bold yellow] "
                    f"Net Realized/Unrealized: ${delta_profit_made:+.2f} / +${DELTA_TARGET_PROFIT:.2f} ({progress_pct:.1f}%) | "
                    f"Target Equity: ${DELTA_TARGET_EQUITY:.2f} USD | Remaining: ${remaining_needed:.2f}"
                )
                if delta_profit_made >= DELTA_TARGET_PROFIT:
                    console.print(
                        f"\n[bold green]🎉🏆 [TARGET REACHED] Delta Exchange achieved +${delta_profit_made:.2f} USD profit! "
                        f"Current Equity: ${current_delta_equity:.2f} USD >= ${DELTA_TARGET_EQUITY:.2f} USD![/bold green]\n"
                    )
            except Exception as crypto_err:
                console.print(f"[bold red]⚠️ [Crypto Cycle Notice] {crypto_err}[/bold red]")

            if focus_broker != "delta" and equity_daemon is not None:
                # -----------------------------------------------------------------
                # B) INDIAN EQUITY ENGINE (NSE / BSE) (Active During Market Hours on AngelOne)
                # -----------------------------------------------------------------
                is_open = IndianMarketCalendar.is_market_open(now_ist)
                is_pre = IndianMarketCalendar.is_pre_market(now_ist)

                if is_open:
                    try:
                        # Start AngelOne WebSocket if not already streaming
                        if angel_auth and not equity_ws_active:
                            console.print("[cyan]📈 Indian Market is OPEN! Starting AngelOne Sub-Second WebSocket...[/cyan]")
                            ws_task = asyncio.create_task(angelone_streamer.start_streaming())
                            background_tasks.add(ws_task)
                            ws_task.add_done_callback(background_tasks.discard)
                            equity_ws_active = True

                        console.print(f"[bold green]📈 [Indian Market: OPEN] Executing NSE/BSE Equity Cycle (AngelOne)...[/bold green]")
                        equity_summary = await equity_daemon.run_single_cycle()
                        eq_avail = equity_summary.get("available_margin", 0.0)
                        eq_orders = equity_summary.get("orders_executed", 0)

                        if angel_baseline_equity <= 0:
                            angel_baseline_equity = resolve_baseline("angelone", float(eq_avail or 0.0), "ANGEL_BASELINE_EQUITY")
                        ANGEL_BASELINE_EQUITY = angel_baseline_equity if angel_baseline_equity > 0 else float(os.getenv("ANGEL_BASELINE_EQUITY", "395.23"))
                        ANGEL_TARGET_PROFIT_USD = float(os.getenv("ANGEL_TARGET_PROFIT_USD", "12.00"))
                        USD_INR_RATE = float(os.getenv("USD_INR_RATE", "87.50"))
                        ANGEL_TARGET_PROFIT_INR = round(ANGEL_TARGET_PROFIT_USD * USD_INR_RATE, 2)
                        ANGEL_TARGET_EQUITY_INR = round(ANGEL_BASELINE_EQUITY + ANGEL_TARGET_PROFIT_INR, 2)

                        # Ground truth ledger for Equity
                        equity_truth = await BrokerTruthVerifier.compute_and_record_truth(
                            broker=equity_broker,
                            internal_claimed_pnl=equity_summary.get("realized_pnl", 0.0),
                            baseline_capital=ANGEL_BASELINE_EQUITY,
                        )

                        funds_now_angel = await equity_broker.get_funds()
                        current_angel_equity = float(funds_now_angel.get("total_capital", eq_avail))
                        angel_profit_made = round(current_angel_equity - ANGEL_BASELINE_EQUITY, 2)
                        angel_profit_made_usd = round(angel_profit_made / USD_INR_RATE, 2)
                        remaining_needed_inr = round(max(0.0, ANGEL_TARGET_PROFIT_INR - angel_profit_made), 2)
                        remaining_needed_usd = round(remaining_needed_inr / USD_INR_RATE, 2)
                        angel_progress_pct = max(0.0, min(100.0, (angel_profit_made / ANGEL_TARGET_PROFIT_INR) * 100.0))

                        console.print(
                            f"  📈 [bold green]Equity (AngelOne):[/bold green] Equity: ₹{current_angel_equity:,.2f} | Margin: ₹{eq_avail:,.2f} | "
                            f"Scanned: {equity_summary.get('candidates_scanned', 0)} | "
                            f"Debated: {equity_summary.get('debates_conducted', 0)} | "
                            f"Executed: {eq_orders}"
                        )
                        console.print(
                            f"  🎯 [bold yellow]AngelOne $12 (₹{ANGEL_TARGET_PROFIT_INR:,.0f}) Profit Target:[/bold yellow] "
                            f"Net Realized/Unrealized: ₹{angel_profit_made:+,.2f} (${angel_profit_made_usd:+.2f} USD) / +₹{ANGEL_TARGET_PROFIT_INR:,.2f} (+${ANGEL_TARGET_PROFIT_USD:.2f} USD) ({angel_progress_pct:.1f}%) | "
                            f"Target Equity: ₹{ANGEL_TARGET_EQUITY_INR:,.2f} | Remaining: ₹{remaining_needed_inr:,.2f} (${remaining_needed_usd:.2f} USD)"
                        )
                        if angel_profit_made >= ANGEL_TARGET_PROFIT_INR:
                            console.print(
                                f"\n[bold green]🎉🏆 [TARGET REACHED] AngelOne achieved +₹{angel_profit_made:,.2f} (+${angel_profit_made_usd:.2f} USD) profit! "
                                f"Current Equity: ₹{current_angel_equity:,.2f} >= ₹{ANGEL_TARGET_EQUITY_INR:,.2f}![/bold green]\n"
                            )
                    except Exception as eq_err:
                        console.print(f"[bold red]⚠️ [Equity Cycle Notice] {eq_err}[/bold red]")
                elif is_pre:
                    console.print(f"[bold yellow]🌅 [Indian Market: PRE-OPEN (09:00 - 09:15 IST)] Armed and waiting for 09:15 AM opening tick.[/bold yellow]")
                else:
                    if equity_ws_active:
                        angelone_streamer.stop()
                        equity_ws_active = False
                    console.print(f"[dim]⏸️  [Indian Market: CLOSED ({now_str} IST)]. Opens at 09:15 AM IST. Crypto remains actively trading 24/7.[/dim]")

            # Loop interval: 30s in single-market mode, 45s in dual mode
            sleep_sec = 30.0 if focus_broker == "delta" else 45.0
            await asyncio.sleep(sleep_sec)

    except (KeyboardInterrupt, asyncio.CancelledError):
        console.print("\n[yellow]Gracefully shutting down Autonomous Trading Office...[/yellow]")
        if equity_ws_active:
            angelone_streamer.stop()
        console.print("[green]Session safely terminated.[/green]")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Autonomous Live Orchestrator")
    parser.add_argument("--duration-hours", type=float, default=None, help="Stop automatically after N hours (e.g. 1.0)")
    parser.add_argument("--focus-broker", type=str, default=os.getenv("FOCUS_BROKER", "all"), choices=["delta", "angelone", "all"], help="Focus execution on a single broker or all (default: 'all')")
    args = parser.parse_args()
    asyncio.run(run_unified_trading_office(duration_hours=args.duration_hours, focus_broker=args.focus_broker))
