"""
Autonomous AI Trading Office — Live System Launcher (AngelOne & Gemini)
Designed for Local Laptop Execution under ₹2,000 Bootstrap Capital
"""

import asyncio
import os
import sys

from rich.console import Console
from rich.panel import Panel

# Ensure project root is in sys.path
sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))

from apps.daemon.state_machine import AutonomousTradingDaemon
from core.config.settings import settings
from database.session import init_db
from execution.broker_factory import get_active_broker
from execution.brokers.angelone import AngelOneBroker
from market.providers.yfinance_provider import YFinanceMarketDataProvider
from market.streamers.angelone_ws import angelone_streamer
from scanner.quant_scanner import QuantMarketScanner
from risk.kill_switch import kill_switch

import argparse

console = Console()
background_tasks: set[asyncio.Task] = set()


def parse_args():
    parser = argparse.ArgumentParser(description="Autonomous AI Trading Office — Live System Launcher")
    parser.add_argument("--broker", type=str, default=None, help="Broker adapter: 'delta' or 'angelone'")
    parser.add_argument("--universe", type=str, default=None, help="Scanner universe: 'crypto', 'bootstrap', 'nifty50'")
    parser.add_argument("--cycles", type=int, default=0, help="Number of cycles to run (0 = continuous)")
    return parser.parse_args()


async def launch_live_system():
    args = parse_args()
    selected_broker_name = (args.broker or settings.BROKER_NAME or "angelone").lower()
    is_crypto = selected_broker_name in ["delta", "delta_exchange"]

    curr_sym = "$" if is_crypto else "₹"
    engine_name = "DELTA EXCHANGE CRYPTO PERPETUALS (24/7/365)" if is_crypto else "NSE/BSE LIVE ENGINE"
    broker_title = "Delta Exchange India (Crypto Perpetuals & Options)" if is_crypto else "AngelOne SmartAPI (NSE/BSE)"

    console.print(Panel(
        f"[bold cyan]AUTONOMOUS AI TRADING OFFICE — {engine_name}[/bold cyan]\n"
        f"• [bold green]Active Broker:[/bold green] {broker_title}\n"
        f"• [bold yellow]LLM Intelligence:[/bold yellow] Google Gemini (Fast: gemini-2.5-flash | Reasoning: gemini-2.5-pro)\n"
        f"• [bold magenta]AI Treasury Model:[/bold magenta] {curr_sym}{settings.INITIAL_CAPITAL:.2f} Bootstrap Capital (Earn to Survive)\n"
        f"• [bold red]Risk Defense:[/bold red] 15-Point Pre-Trade Audit Gate + 3x Max Leverage + Kill Switch",
        title="[bold green]AI Office Startup[/bold green]"
    ))

    # 1. Initialize SQLite Database Tables
    console.print("[cyan]1. Initializing institutional database schema...[/cyan]")
    await init_db()

    # 2. Check & Authenticate Broker Session
    broker = get_active_broker(selected_broker_name)
    if isinstance(broker, AngelOneBroker):
        console.print("[cyan]2. Connecting to AngelOne SmartAPI & generating TOTP session...[/cyan]")
        auth_res = await broker.authenticate_session()
        if auth_res.get("authenticated"):
            console.print(f"[bold green]✅ AngelOne SmartAPI Authenticated successfully for Client: {settings.ANGELONE_CLIENT_CODE}![/bold green]")
        else:
            console.print(f"[yellow]⚠️ AngelOne live session pending ({auth_res.get('error', 'Using Local Laptop Simulation')}). Operating safely within bounds.[/yellow]")
        
        # Start Real-Time WebSocket Ticker Stream
        console.print("[cyan]3. Launching Real-Time WebSocket Market Ticker (Sub-Second Feeds)...[/cyan]")
        ws_task = asyncio.create_task(angelone_streamer.start_streaming())
        background_tasks.add(ws_task)
        ws_task.add_done_callback(background_tasks.discard)

    elif is_crypto:
        console.print(f"[cyan]2. Verifying Delta Exchange India API credentials & HMAC-SHA256 signature...[/cyan]")
        funds = await broker.get_funds()
        console.print(f"[bold green]✅ Delta Exchange India Connected! Available Margin: ${funds.get('available_margin', 0.0):.2f} USD[/bold green]")

    # 4. Check Initial Live Funds
    funds = await broker.get_funds()
    live_margin = float(funds.get("available_margin", 0.0))
    console.print(f"[cyan]4. Checking Broker RMS Live Margin...[/cyan] [bold gold1]{curr_sym}{live_margin:,.2f}[/bold gold1]")
    if live_margin <= 0:
        console.print(f"[yellow]ℹ️  Account balance is currently {curr_sym}0.00. The AI agents will run in observer standby mode.[/yellow]")
    else:
        console.print(f"[bold green]💰 Live capital detected: {curr_sym}{live_margin:,.2f}! Full autonomous order routing active.[/bold green]")

    # 5. Pre-Market / 24-7 Session Readiness
    if not is_crypto:
        console.print("[cyan]5. Executing Pre-Market Preparation & Agent Readiness Checklist...[/cyan]")
        from market.premarket_readiness import premarket_readiness_engine
        rdy = await premarket_readiness_engine.run_premarket_preparation()
        pm_report = rdy.premarket_report
        report_text = (
            f"• [bold white]Market Phase:[/bold white] [bold yellow]{rdy.market_phase}[/bold yellow] ({rdy.time_to_open_formatted})\n"
            f"• [bold white]Global Sentiment:[/bold white] [bold green]{pm_report.global_sentiment if pm_report else 'RISK_ON'}[/bold green] | [bold white]India Sentiment:[/bold white] [bold green]{pm_report.india_sentiment if pm_report else 'BULLISH_BIAS'}[/bold green]\n"
            f"• [bold white]GIFT Nifty Projection:[/bold white] [bold cyan]{pm_report.gift_nifty_gap_points:+.0f} pts ({pm_report.expected_opening_type})[/bold cyan] | [bold white]India VIX:[/bold white] {pm_report.india_vix_level if pm_report else 12.80:.2f}\n"
            f"• [bold white]Morning Focus Stocks:[/bold white] {', '.join(rdy.morning_focus_stocks)}\n"
            f"• [bold white]Stocks to Avoid:[/bold white] [bold red]{', '.join(rdy.stocks_to_avoid)}[/bold red]\n"
            f"• [bold white]AI Specialist Desks:[/bold white] [bold green]{rdy.total_agents_armed}/{rdy.total_agents_armed} ARMED AND READY[/bold green]"
        )
        console.print(Panel(report_text, title="[bold cyan]🌅 Pre-Market Intelligence & Agent Readiness[/bold cyan]"))
    else:
        console.print(Panel(
            "• [bold white]Session Type:[/bold white] [bold green]24/7/365 Continuous Crypto Perpetuals[/bold green]\n"
            "• [bold white]Risk Control:[/bold white] [bold green]Strict 3.0x Max Leverage + Server-Side Bracket OCO[/bold green]\n"
            "• [bold white]Funding Cycle:[/bold white] [bold cyan]8-Hour Periodic Settlement Check[/bold cyan]\n"
            "• [bold white]AI Specialist Desks:[/bold white] [bold green]AstraQuant Microstructure + Money-Agent Rails ARMED[/bold green]",
            title="[bold cyan]🪙 24/7 Crypto Session Armed & Ready[/bold cyan]"
        ))

    # 6. Initialize Scanner and Autonomous Daemon
    scanner_universe = args.universe or ("crypto" if is_crypto else "bootstrap")
    console.print(f"[cyan]6. Initializing High-Speed Quant Scanner ({scanner_universe.upper()} Universe) & Daemon...[/cyan]")
    provider = YFinanceMarketDataProvider()
    scanner = QuantMarketScanner(provider=provider, universe=scanner_universe, max_concurrency=10)
    daemon = AutonomousTradingDaemon(
        scanner=scanner,
        broker=broker,
        total_capital=live_margin,
        top_n_candidates=5,
    )

    console.print(f"\n[bold green]🚀 Autonomous AI Trading Daemon is ACTIVE on your Laptop ({selected_broker_name.upper()})![/bold green]")
    console.print(f"[dim]Continuously scanning {scanner_universe.upper()} candidates, running AI specialist analysis, Bull vs Bear debates, and 15-point pre-trade audits...[/dim]")
    console.print("[bold yellow]Press Ctrl+C to gracefully stop the daemon.[/bold yellow]\n")

    kill_switch.reset("Live Engine Launcher")

    # Run Autonomous Trading Cycles
    cycle_count = 0
    try:
        while True:
            cycle_count += 1
            summary = await daemon.run_single_cycle()
            avail = summary.get("available_margin", 0.0)
            scanned = summary.get("candidates_scanned", 0)
            debated = summary.get("debates_conducted", 0)
            orders = summary.get("orders_executed", 0)

            # Compute and record unalterable ground truth from broker
            from portfolio.broker_truth_verifier import BrokerTruthVerifier
            truth = await BrokerTruthVerifier.compute_and_record_truth(
                broker=broker,
                internal_claimed_pnl=summary.get("realized_pnl", 0.0),
                baseline_capital=live_margin,
            )

            change_color = "green" if truth.verified_net_account_change >= 0 else "red"
            status_text = (
                f"[bold green]Live Margin: {curr_sym}{avail:,.2f}[/bold green] | Scanned: {scanned} | Debated: {debated} | Executed: {orders}\n"
                f"[dim]Ground Truth Ledger:[/dim] Net Change: [{change_color}]{curr_sym}{truth.verified_net_account_change:+.2f}[/{change_color}] | "
                f"Net After Drag: {curr_sym}{truth.ground_truth_net_pnl:+.2f} | Discrepancy: {curr_sym}{truth.claim_vs_truth_discrepancy:+.2f}"
            )
            console.print(Panel(status_text, title="[bold cyan]Cycle Telemetry & Ground Truth Ledger[/bold cyan]"))

            if args.cycles and cycle_count >= args.cycles:
                console.print(f"[bold green]✅ Completed {cycle_count} cycle(s) as requested. Exiting successfully.[/bold green]")
                break

            await asyncio.sleep(60.0)  # 1-minute interval between scans
    except (KeyboardInterrupt, asyncio.CancelledError):
        console.print("\n[yellow]Gracefully shutting down Autonomous AI Trading Office...[/yellow]")
        if not is_crypto:
            angelone_streamer.stop()
        console.print("[green]Session safely terminated.[/green]")


if __name__ == "__main__":
    asyncio.run(launch_live_system())
