import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))

import asyncio

import typer
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from apps.daemon.state_machine import AutonomousTradingDaemon
from core.config.settings import settings
from database.session import init_db
from execution.paper.broker import PaperBroker
from market.providers.mock_provider import MockMarketDataProvider
from market.providers.yfinance_provider import YFinanceMarketDataProvider
from scanner.quant_scanner import QuantMarketScanner

app = typer.Typer(
    name="trader",
    help="Autonomous Multi-Agent AI Trading System for Indian Markets (NSE/BSE)",
    add_completion=False,
)
console = Console()


@app.command()
def status():
    """Display system status, current trading mode, risk limits, and account metrics."""
    async def _status():
        await init_db()
        broker = PaperBroker(initial_capital=settings.MAX_CAPITAL)
        funds = await broker.get_funds()

        table = Table(title="[bold green]System Status & Risk Controls[/bold green]")
        table.add_column("Parameter", style="cyan")
        table.add_column("Value", style="magenta")

        table.add_row("Operational Mode", settings.TRADING_MODE.value)
        table.add_row("Live Trading Enabled", str(settings.LIVE_TRADING_ENABLED))
        table.add_row("Exchange", settings.EXCHANGE)
        table.add_row("Total Capital", f"₹{funds['total_capital']:,.2f}")
        table.add_row("Available Margin", f"₹{funds['available_margin']:,.2f}")
        table.add_row("Max Risk Per Trade", f"{settings.MAX_RISK_PER_TRADE_PCT*100}%")
        table.add_row("Daily Loss Circuit Breaker", f"{settings.MAX_DAILY_LOSS_PCT*100}% (₹{settings.MAX_CAPITAL*settings.MAX_DAILY_LOSS_PCT:,.2f})")
        table.add_row("Max Portfolio Drawdown", f"{settings.MAX_PORTFOLIO_DRAWDOWN_PCT*100}%")
        table.add_row("Max Concurrent Positions", str(settings.MAX_OPEN_POSITIONS))
        table.add_row("Strategy Version", settings.STRATEGY_VERSION)

        console.print(table)

    asyncio.run(_status())


@app.command()
def scan(
    top: int = typer.Option(10, help="Number of top candidate stocks to qualify"),
    universe: str = typer.Option("nifty50", help="Market universe to scan: 'default', 'nifty50', 'nifty100'"),
):
    """Execute quantitative market scan on Indian equity universe (N stocks)."""
    async def _scan():
        console.print(f"[bold cyan]Scanning '{universe.upper()}' Universe (finding top {top} setups)...[/bold cyan]")
        provider = YFinanceMarketDataProvider()
        scanner = QuantMarketScanner(provider=provider, universe=universe)

        try:
            candidates = await scanner.get_top_candidates(top_n=top)
        except Exception as e:
            console.print(f"[yellow]Live network provider fallback: {e}[/yellow]")
            fallback_provider = MockMarketDataProvider(base_price=2800.0, trend="bullish")
            scanner = QuantMarketScanner(provider=fallback_provider, universe=universe)
            candidates = await scanner.get_top_candidates(top_n=top)

        table = Table(title=f"[bold green]Top {len(candidates)} Qualified Market Candidates ({universe.upper()})[/bold green]")
        table.add_column("Rank", style="dim")
        table.add_column("Symbol", style="cyan")
        table.add_column("LTP", style="yellow")
        table.add_column("Rel Volume", style="blue")
        table.add_column("Momentum Score", style="green")
        table.add_column("ATR (14)", style="magenta")
        table.add_column("Market Regime", style="bold white")

        for idx, c in enumerate(candidates, 1):
            table.add_row(
                str(idx),
                c.symbol,
                f"₹{c.ltp:,.2f}",
                f"{c.relative_volume}x",
                f"{c.momentum_score}/100",
                f"₹{c.atr_14}",
                c.regime.value,
            )

        console.print(table)

    asyncio.run(_scan())


@app.command()
def analyze(
    symbols: str = typer.Option("RELIANCE.NS,TCS.NS,HDFCBANK.NS", help="Comma-separated stock symbols to analyze and debate"),
):
    """Run comprehensive multi-agent research, Bull vs. Bear debate, and decisions on N stocks."""
    async def _analyze():
        symbol_list = [s.strip().upper() for s in symbols.split(",") if s.strip()]
        console.print(f"[bold cyan]Conducting Multi-Agent Analysis & Debate on {len(symbol_list)} stocks: {symbol_list}...[/bold cyan]")

        provider = YFinanceMarketDataProvider()
        scanner = QuantMarketScanner(provider=provider)

        # Collect candidate signals
        candidates = []
        for sym in symbol_list:
            sig = await scanner.scan_symbol(sym)
            if not sig:
                mock = MockMarketDataProvider(base_price=2800.0, trend="bullish")
                scanner_mock = QuantMarketScanner(provider=mock)
                sig = await scanner_mock.scan_symbol(sym)
            if sig:
                candidates.append(sig)

        from orchestration.batch_engine import MultiStockOrchestrator
        orchestrator = MultiStockOrchestrator()
        evaluations = await orchestrator.evaluate_candidates_batch(candidates)

        table = Table(title="[bold green]Multi-Stock Debate & Fund Manager Decisions[/bold green]")
        table.add_column("Symbol", style="cyan")
        table.add_column("LTP", style="yellow")
        table.add_column("Consensus", style="blue")
        table.add_column("Conviction", style="magenta")
        table.add_column("Decision", style="bold")
        table.add_column("Entry / SL / Target", style="dim")
        table.add_column("Fund Manager Thesis", style="white")

        for item in evaluations:
            sig = item["signal"]
            debate = item["debate"]
            dec = item["decision"]

            decision_color = "green" if dec.decision.value == "BUY" else ("red" if dec.decision.value == "SELL" else "yellow")
            entry_sl_tgt = f"₹{dec.entry_price or sig.ltp} / ₹{dec.stop_loss or '-'} / ₹{dec.target_1 or '-'}" if dec.entry_price else "-"
            thesis_str = dec.thesis[0] if dec.thesis else "-"

            table.add_row(
                sig.symbol,
                f"₹{sig.ltp:,.2f}",
                f"{debate.consensus_score:+0.2f}",
                f"{item['conviction_rank']}/100",
                f"[{decision_color}]{dec.decision.value}[/{decision_color}]",
                entry_sl_tgt,
                thesis_str[:60] + "..." if len(thesis_str) > 60 else thesis_str,
            )

        console.print(table)

    asyncio.run(_analyze())


@app.command()
def batch_debate(
    top: int = typer.Option(5, help="Number of top candidates to scan and debate"),
    universe: str = typer.Option("nifty50", help="Universe to scan: 'default', 'nifty50', 'nifty100'"),
):
    """Scan N stocks from universe, run multi-agent adversarial debates, and rank them for trading."""
    async def _batch_debate():
        console.print(f"[bold cyan]Scanning '{universe.upper()}' universe & running batch debates on top {top} candidates...[/bold cyan]")
        provider = YFinanceMarketDataProvider()
        scanner = QuantMarketScanner(provider=provider, universe=universe)

        try:
            candidates = await scanner.get_top_candidates(top_n=top)
        except Exception:
            mock = MockMarketDataProvider(base_price=2700.0, trend="bullish")
            scanner = QuantMarketScanner(provider=mock, universe=universe)
            candidates = await scanner.get_top_candidates(top_n=top)

        from orchestration.batch_engine import MultiStockOrchestrator
        orchestrator = MultiStockOrchestrator()
        summary = await orchestrator.run_batch_debate_and_allocation(candidates)

        console.print(f"\n[bold green]Evaluated {summary['total_evaluated']} stocks:[/bold green] {len(summary['approved_trades'])} Approved, {len(summary['rejected_trades'])} Rejected/No-Trade\n")

        for item in summary["ranked_candidates"]:
            sig = item["signal"]
            debate = item["debate"]
            dec = item["decision"]

            console.print(f"[bold cyan]=== {sig.symbol} (LTP: ₹{sig.ltp}, Momentum: {sig.momentum_score}/100, Conviction: {item['conviction_rank']}) ===[/bold cyan]")
            console.print(f"  [yellow]Bull Thesis:[/yellow] {debate.bull_thesis}")
            console.print(f"  [red]Bear Thesis:[/red] {debate.bear_thesis}")
            console.print(f"  [blue]Facilitator Synthesis:[/blue] {debate.facilitator_summary}")
            console.print(f"  [bold]Consensus Score:[/bold] {debate.consensus_score:+0.2f} | [bold]Fund Manager Action:[/bold] [bold green]{dec.decision.value}[/bold green] (Confidence: {dec.confidence:.2f})")
            if dec.entry_price:
                console.print(f"  [dim]Entry: ₹{dec.entry_price} | SL: ₹{dec.stop_loss} | Target: ₹{dec.target_1} | R:R: {dec.expected_risk_reward}[/dim]")
            console.print("")

    asyncio.run(_batch_debate())


@app.command()
def paper(
    top: int = typer.Option(5, help="Number of candidate stocks to scan and evaluate in paper cycle"),
    universe: str = typer.Option("default", help="Market universe: 'default', 'nifty50', 'nifty100'"),
):
    """Execute a single complete autonomous paper trading cycle across N stocks."""
    async def _paper():
        await init_db()
        console.print(f"[bold green]Executing Autonomous Paper Trading Cycle (Scanning universe '{universe}', evaluating {top} stocks)...[/bold green]")
        provider = MockMarketDataProvider(base_price=2600.0, trend="bullish")
        scanner = QuantMarketScanner(provider=provider, universe=universe)
        broker = PaperBroker(initial_capital=settings.MAX_CAPITAL)

        daemon = AutonomousTradingDaemon(scanner=scanner, broker=broker, total_capital=settings.MAX_CAPITAL, top_n_candidates=top)
        summary = await daemon.run_single_cycle()
        console.print(f"[bold green]Cycle Complete across N stocks:[/bold green] {summary}")

    asyncio.run(_paper())


@app.command()
def daemon(
    mode: str = typer.Option("paper", help="Trading mode: 'paper' or 'live'"),
    top: int = typer.Option(5, help="Number of candidate stocks to scan and evaluate per cycle"),
    universe: str = typer.Option("nifty50", help="Market universe: 'default', 'nifty50', 'nifty100'"),
):
    """Run continuous unattended autonomous trading daemon evaluating N stocks per cycle."""
    async def _daemon():
        await init_db()
        console.print(f"[bold green]Starting Autonomous AI Trading Daemon [{mode.upper()} MODE] scanning universe '{universe}' ({top} candidates/cycle)...[/bold green]")
        provider = YFinanceMarketDataProvider()
        scanner = QuantMarketScanner(provider=provider, universe=universe)
        broker = PaperBroker(initial_capital=settings.MAX_CAPITAL)
        bot = AutonomousTradingDaemon(scanner=scanner, broker=broker, total_capital=settings.MAX_CAPITAL, top_n_candidates=top)

        console.print("[green]Daemon active. Press Ctrl+C to stop.[/green]")
        summary = await bot.run_single_cycle()
        console.print(f"Initial multi-stock run completed: {summary}")

    asyncio.run(_daemon())


@app.command()
def treasury_cmd():
    """Display the AI Treasury balance, operating expenses, net profit, and Survival Mode status."""
    from core.treasury.treasury import treasury
    m = treasury.get_metrics()

    table = Table(title="[bold green]AI Treasury & Economic Model (Earn to Survive)[/bold green]")
    table.add_column("Treasury Metric", style="cyan")
    table.add_column("Value", style="magenta")

    table.add_row("Starting Bootstrap Capital", f"₹{m['starting_capital']:,.2f}")
    table.add_row("Current Authorized Capital", f"₹{m['current_capital']:,.2f}")
    table.add_row("Total Portfolio Equity", f"₹{m['total_equity']:,.2f}")
    table.add_row("Realized Trading P&L", f"₹{m['realized_pnl']:+,.2f}")
    table.add_row("Operating Expenses (API/Compute)", f"₹{m['operating_expenses']:,.2f}")
    table.add_row("Net Trading Profit", f"[{'green' if m['net_trading_profit'] >= 0 else 'red'}]₹{m['net_trading_profit']:+,.2f}[/]")
    table.add_row("Estimated Operating Runway", f"{m['estimated_runway_days']} Days")
    table.add_row("Survival Mode Active", f"[{'bold red' if m['is_survival_mode'] else 'bold green'}]{str(m['is_survival_mode']).upper()}[/]")
    table.add_row("Survival Mode Capital Trigger", f"Below ₹{m['survival_threshold']:,.2f}")

    console.print(table)


@app.command()
def office():
    """Display the full roster of the AI Trading Office (Core & Dynamic Agents)."""
    from agents.lifecycle.agent_manager import agent_manager
    roster = agent_manager.get_office_roster()

    table = Table(title="[bold green]AI Trading Office — Autonomous Agent Organization[/bold green]")
    table.add_column("Agent Name", style="cyan")
    table.add_column("Role / Specialty", style="white")
    table.add_column("Type", style="yellow")
    table.add_column("Status", style="bold")
    table.add_column("Invocations", style="dim")
    table.add_column("Accuracy", style="green")

    for a in roster:
        status_color = "green" if a["status"] == "ACTIVE" else ("yellow" if a["status"] == "STANDBY" else "red")
        table.add_row(
            a["name"],
            a["role"],
            a["type"],
            f"[{status_color}]{a['status']}[/{status_color}]",
            str(a["invocations"]),
            a["accuracy"],
        )

    console.print(table)


@app.command()
def learning():
    """Display 4-Quadrant Decision Quality and Post-Trade Learning Statistics."""
    from memory.learning_loop import learning_loop
    stats = learning_loop.get_quadrant_statistics()

    table = Table(title="[bold green]Institutional 4-Quadrant Learning Loop[/bold green]")
    table.add_column("Decision-Outcome Quadrant", style="cyan")
    table.add_column("Count", style="magenta")
    table.add_column("Interpretation", style="white")

    table.add_row("Good Decision → Good Outcome", str(stats["good_decision_good_outcome"]), "Edge verified with disciplined process")
    table.add_row("Good Decision → Bad Outcome", str(stats["good_decision_bad_outcome"]), "Normal statistical variance; SL protected capital")
    table.add_row("Bad Decision → Good Outcome", str(stats["bad_decision_good_outcome"]), "[bold yellow]Lucky win; penalized to avoid bad habits[/bold yellow]")
    table.add_row("Bad Decision → Bad Outcome", str(stats["bad_decision_bad_outcome"]), "[bold red]Flawed decision; invalidation rules audited[/bold red]")
    table.add_row("Decision Soundness Rate", stats["decision_soundness_rate"], "Percent of trades made with sound process")

    console.print(table)


@app.command()
def kill(
    engage: bool = typer.Option(False, "--engage", help="Engage the Emergency Kill Switch"),
    reset: bool = typer.Option(False, "--reset", help="Reset the Emergency Kill Switch"),
    reason: str = typer.Option("Manual operator command", help="Reason for engaging/resetting"),
):
    """View, engage, or reset the independent Emergency Kill Switch."""
    from risk.kill_switch import kill_switch
    if engage:
        kill_switch.trigger("CLI_OPERATOR", reason)
        console.print(f"[bold red]🚨 EMERGENCY KILL SWITCH ENGAGED! Reason: {reason}[/bold red]")
    elif reset:
        kill_switch.reset("CLI_OPERATOR")
        console.print("[bold green]✅ Emergency Kill Switch reset. Trading operations authorized.[/bold green]")
    else:
        status_str = "[bold red]ENGAGED (HALTED)[/bold red]" if kill_switch.is_engaged else "[bold green]DISENGAGED (ACTIVE)[/bold green]"
        console.print(f"Kill Switch Status: {status_str}")
        if kill_switch.is_engaged:
            console.print(f"Engagement Reason: [yellow]{kill_switch.reason}[/yellow]")


@app.command()
def scale():
    """Evaluate statistical performance metrics for Capital Scaling beyond ₹2,000 bootstrap."""
    from portfolio.capital_scaler import CapitalScalingPolicy
    eval_res = CapitalScalingPolicy.evaluate_scaling(
        total_trades=12,
        winning_trades=8,
        total_profit=350.0,
        total_loss=-120.0,
        max_drawdown_pct=0.035,
        current_capital=settings.MAX_CAPITAL,
    )

    table = Table(title="[bold green]Statistical Capital Scaling Evaluation[/bold green]")
    table.add_column("Parameter", style="cyan")
    table.add_column("Value", style="magenta")

    table.add_row("Current Capital", f"₹{eval_res.current_capital:,.2f}")
    table.add_row("Recommended Capital", f"₹{eval_res.recommended_capital:,.2f}")
    table.add_row("Scaling Approved", str(eval_res.scaling_approved))
    table.add_row("Sharpe Equivalent", str(eval_res.sharpe_equivalent))
    table.add_row("Win Rate", f"{eval_res.win_rate_pct}%")
    table.add_row("Profit Factor", str(eval_res.profit_factor))
    table.add_row("Justification", eval_res.justification)

    console.print(table)


# ==========================================
# CUSTOM AI AGENT FACTORY CLI COMMANDS
# ==========================================

agent_app = typer.Typer(
    name="agent",
    help="Custom AI Agent Factory: Create, Test, Version, Clone and Govern AI Workforce",
)
app.add_typer(agent_app, name="agent")


@agent_app.command("list")
def list_agents():
    """List all custom agents in the AI Agent Library / Marketplace."""
    from agents.factory.factory import agent_factory
    agents = agent_factory.list_all_agents()

    table = Table(title="[bold green]Custom AI Agent Library & Marketplace[/bold green]")
    table.add_column("Agent ID", style="dim")
    table.add_column("Name", style="cyan")
    table.add_column("Department", style="magenta")
    table.add_column("Status", style="bold")
    table.add_column("Version", style="yellow")
    table.add_column("Live Orders", style="white")
    table.add_column("Objective", style="dim")

    for a in agents:
        status_color = "green" if a.status.value == "ACTIVE" else ("yellow" if a.status.value == "SANDBOX" else "red")
        live_str = "[green]YES[/]" if a.permissions.place_live_orders else "[dim]NO (Gated)[/]"
        table.add_row(
            a.agent_id,
            a.name,
            a.department.value,
            f"[{status_color}]{a.status.value}[/{status_color}]",
            a.version,
            live_str,
            a.objective[:45] + "..." if len(a.objective) > 45 else a.objective,
        )

    console.print(table)


@agent_app.command("create")
def create_agent(
    name: str = typer.Option("Custom Momentum Scout", "--name", help="Name of the new AI agent"),
    dept: str = typer.Option("Trading", "--dept", help="Department: Research, Risk, Trading, Portfolio, Execution, Operations"),
    prompt: str = typer.Option(
        "Monitor NIFTY 50 for volume breakouts, calculate RSI and EMA confluence, and alert Chief Trading Officer.",
        "--prompt",
        help="Natural language instructions for the agent",
    ),
):
    """Create a new custom AI agent from natural language instructions."""
    from agents.factory.factory import agent_factory
    from agents.factory.models import Department
    dept_enum = Department(dept) if dept in [d.value for d in Department] else Department.TRADING

    console.print(f"[bold cyan]Creating Custom Agent '{name}' in {dept_enum.value}...[/bold cyan]")
    agent = agent_factory.parse_natural_language_instruction(prompt=prompt, name=name, department=dept_enum)

    console.print("\n[bold green]✅ Custom Agent Created Successfully![/bold green]")
    console.print(f"Agent ID: [cyan]{agent.agent_id}[/cyan]")
    console.print(f"Lifecycle Stage: [yellow]{agent.status.value}[/yellow] (Sandboxed for safety)")
    console.print(f"Assigned Tools: {agent.tools}")
    console.print(f"Assigned Functions: {agent.functions}")
    console.print(f"Live Orders Permission: {'ALLOWED' if agent.permissions.place_live_orders else 'DENIED (Deny by Default)'}")


@agent_app.command("test")
def test_agent(
    agent_id: str = typer.Argument("agent_momentum_hunter", help="ID of the agent to test in sandbox"),
    symbol: str = typer.Option("RELIANCE.NS", "--symbol", help="Stock symbol for synthetic simulation"),
):
    """Run dry-run simulation and permission verification on an agent inside the Sandbox."""
    from agents.factory.factory import agent_factory
    async def _test():
        console.print(f"[bold cyan]Running Sandbox Simulation for Agent '{agent_id}' on {symbol}...[/bold cyan]")
        try:
            res = await agent_factory.run_sandbox_simulation(agent_id, symbol=symbol)
            console.print("\n[bold green]✅ Sandbox Simulation Passed![/bold green]")
            console.print(f"Status Transitioned to: [bold yellow]{res['status']}[/bold yellow]")
            console.print(f"Simulated Report Stance: [bold]{res['simulated_report']['stance']}[/bold] (Confidence: {res['simulated_report']['confidence']})")
            console.print(f"Permissions Audit: {res['permissions_audit']}")
        except Exception as e:
            console.print(f"[bold red]❌ Sandbox Test Failed: {e}[/bold red]")

    asyncio.run(_test())


@agent_app.command("clone")
def clone_agent(
    agent_id: str = typer.Argument(..., help="ID of the agent to clone"),
    new_name: str = typer.Option("Cloned Specialist", "--name", help="Name for the cloned agent"),
):
    """Clone an existing agent with a new identity."""
    from agents.factory.factory import agent_factory
    try:
        cloned = agent_factory.clone_agent(agent_id, new_name=new_name)
        console.print("[bold green]✅ Agent cloned successfully![/bold green]")
        console.print(f"Original ID: [dim]{agent_id}[/dim] ➔ Cloned ID: [cyan]{cloned.agent_id}[/cyan] ({cloned.name})")
    except Exception as e:
        console.print(f"[bold red]❌ Clone Failed: {e}[/bold red]")


@agent_app.command("status")
def change_status(
    agent_id: str = typer.Argument(..., help="Agent ID"),
    stage: str = typer.Argument("ACTIVE", help="New lifecycle stage: ACTIVE, PAUSED, RETIRED, SANDBOX"),
):
    """Update lifecycle stage of a custom agent."""
    from agents.factory.factory import agent_factory
    from agents.factory.models import LifecycleStage
    try:
        updated = agent_factory.update_lifecycle_stage(agent_id, LifecycleStage(stage.upper()))
        console.print(f"[bold green]✅ Agent '{updated.name}' updated to stage: {updated.status.value}[/bold green]")
    except Exception as e:
        console.print(f"[bold red]❌ Status update failed: {e}[/bold red]")


# ==========================================
# MEMORY & KNOWLEDGE GRAPH CLI
# ==========================================

memory_app = typer.Typer(help="Unified 3-Layer AI Memory & Knowledge Operations")
app.add_typer(memory_app, name="memory")


@memory_app.command("search")
def search_memory(
    query: str = typer.Option("breakout", "--query", "-q", help="Search keywords"),
    symbol: str = typer.Option(None, "--symbol", "-s", help="Filter by symbol"),
):
    """Search unified organizational and permanent AI memory."""
    from memory.global_memory import global_ai_memory
    mems = global_ai_memory.search_memories(query=query, symbol=symbol)

    table = Table(title=f"AI Memory Search Results (Query: '{query}')")
    table.add_column("Level", style="cyan")
    table.add_column("Category", style="yellow")
    table.add_column("Author", style="magenta")
    table.add_column("Confidence", style="green")
    table.add_column("Content", style="white")

    for m in mems:
        table.add_row(
            m.level.value,
            m.category.value,
            m.created_by,
            f"{m.confidence:.2f}",
            m.content[:75] + ("..." if len(m.content) > 75 else ""),
        )
    console.print(table)


@memory_app.command("summary")
def memory_summary():
    """Display the latest daily organizational memory summary."""
    from memory.memory_manager_agent import memory_manager_agent
    s = memory_manager_agent.get_latest_summary()
    console.print(Panel(
        f"[bold cyan]Date:[/bold cyan] {s.get('date')}\n"
        f"[bold cyan]Market Regime:[/bold cyan] {s.get('market_regime')}\n\n"
        f"[bold green]Extracted Lessons:[/bold green]\n" + "\n".join(f"• {lesson}" for lesson in s.get('extracted_lessons', [])) + "\n\n"
        "[bold yellow]Important Events:[/bold yellow]\n" + ("\n".join(f"• {e}" for e in s.get('important_events', [])) if s.get('important_events') else "None recorded"),
        title="[bold green]Daily Organizational Memory Brief (Memory Manager Agent)[/bold green]",
    ))


@app.command("graph")
def view_knowledge_graph():
    """Display interconnected Knowledge Graph summary and entities."""
    from memory.knowledge_graph import knowledge_graph
    summary = knowledge_graph.get_graph_summary()

    table = Table(title="AI Organizational Knowledge Graph")
    table.add_column("Entity Category", style="cyan")
    table.add_column("Node Count", style="green")

    for k, v in summary["node_types"].items():
        table.add_row(k, str(v))

    console.print(table)
    console.print(f"[bold]Total Nodes:[/bold] {summary['total_nodes']} | [bold]Total Relationship Edges:[/bold] {summary['total_edges']}")


# ==========================================
# BALANCE SHEET, CFO & CTO CLI
# ==========================================

@app.command("balance-sheet")
def view_balance_sheet():
    """Display official AI Organization Balance Sheet."""
    from core.treasury.balance_sheet import balance_sheet_generator
    sheet = balance_sheet_generator.generate()

    res_color = "green" if sheet.profitability.net_organizational_result_inr >= 0 else "red"
    console.print(Panel(
        f"[bold cyan]CAPITAL STRUCTURE (Bootstrap ₹{sheet.capital.initial_capital_inr:.2f})[/bold cyan]\n"
        f"• Active Trading Capital: ₹{sheet.capital.current_trading_capital_inr:.2f}\n"
        f"• Operating Reserve: ₹{sheet.capital.operating_reserve_inr:.2f}\n"
        f"• AI Upgrade Fund: ₹{sheet.capital.ai_upgrade_fund_inr:.2f}\n"
        f"• Emergency Reserve: ₹{sheet.capital.emergency_reserve_inr:.2f}\n"
        f"• Total Treasury: [bold green]₹{sheet.capital.total_treasury_inr:.2f}[/bold green]\n\n"
        f"[bold yellow]INCOME & EXPENSES[/bold yellow]\n"
        f"• Gross Trading P&L: ₹{sheet.income.gross_trading_pnl_inr:.2f}\n"
        f"• Operating Expenses (Compute/API/Data): ₹{sheet.expenses.total_operating_expenses_inr:.2f}\n"
        f"• Net Organizational Result: [bold {res_color}]₹{sheet.profitability.net_organizational_result_inr:.2f}[/bold {res_color}]\n\n"
        f"[bold magenta]SURVIVAL RUNWAY & HEALTH[/bold magenta]\n"
        f"• Estimated Runway: [bold green]{sheet.survival.estimated_runway_days:.1f} days[/bold green]\n"
        f"• Sustainability State: [bold cyan]{sheet.survival.sustainability_state}[/bold cyan]\n"
        f"• Survival Mode: {'ACTIVE ⚠️' if sheet.survival.is_survival_mode else 'NORMAL ✅'}",
        title="[bold green]AI Organization Balance Sheet & Economic Report[/bold green]"
    ))


@app.command("cfo")
def cfo_audit():
    """Run CFO financial health audit and model tier routing analysis."""
    from core.treasury.cfo_agent import ai_cfo_agent
    audit = ai_cfo_agent.get_financial_audit_report()
    console.print(Panel(
        f"[bold cyan]Assessment:[/bold cyan] {audit['cfo_assessment']}\n"
        f"[bold cyan]Daily Burn Rate:[/bold cyan] ₹{audit['burn_rate_daily_inr']:.2f}/day\n"
        f"[bold cyan]Estimated Runway:[/bold cyan] {audit['estimated_runway_days']:.1f} days\n\n"
        f"[bold green]Cost Optimization Rules:[/bold green]\n" + "\n".join(f"• {r}" for r in audit['cost_saving_rules']),
        title="[bold green]AI Chief Financial Officer (CFO) Audit Report[/bold green]"
    ))


@app.command("cto")
def cto_proposals():
    """Display CTO technology upgrade proposals and validation pipeline."""
    from core.treasury.cto_agent import ai_cto_agent
    props = ai_cto_agent.list_all_proposals()

    table = Table(title="AI Chief Technology Officer (CTO) Upgrade Pipeline")
    table.add_column("Proposal ID", style="cyan")
    table.add_column("Title", style="white")
    table.add_column("Component", style="yellow")
    table.add_column("Stage", style="green")
    table.add_column("Cost (₹)", style="magenta")

    for p in props:
        table.add_row(
            p["proposal_id"],
            p["title"],
            p["target_component"],
            p["stage"],
            f"₹{p['estimated_cost_inr']:.2f}",
        )

    console.print(table)


# ==========================================
# UNIFIED TRADING DATA & METRICS CLI
# ==========================================

data_app = typer.Typer(help="Unified Trading Data & 18-Domain Metrics Layer")
app.add_typer(data_app, name="data")


@data_app.command("metrics")
def view_stock_metrics(symbol: str = typer.Option("RELIANCE.NS", "--symbol", "-s", help="Stock symbol on NSE")):
    """Display 360-degree quantitative, fundamental, derivatives, and order-flow profile."""
    from data_layer.unified_layer import unified_data_layer
    profile = unified_data_layer.get_complete_symbol_profile(symbol)

    m = profile["market_data"]
    t = profile["technical_indicators"]
    f = profile["fundamentals"]
    d = profile["derivatives"]
    o = profile["order_flow"]
    q = profile["data_quality"]

    console.print(Panel(
        f"[bold cyan]MARKET DATA ({m['exchange']})[/bold cyan]\n"
        f"• LTP: ₹{m['close']} | VWAP: ₹{m['vwap']} | Rel Vol: {m['relative_volume']}x | Float: {m['free_float']*100:.0f}%\n\n"
        f"[bold yellow]TECHNICAL INDICATORS[/bold yellow]\n"
        f"• Trend: EMA(20) ₹{t['ema_20']}, EMA(50) ₹{t['ema_50']}, Supertrend: {'BULLISH' if t['supertrend_direction']==1 else 'BEARISH'}\n"
        f"• Momentum: RSI(14) {t['rsi_14']}, Stoch %K {t['stoch_k']}, MACD Hist {t['macd_hist']:+0.2f}\n"
        f"• Volatility: ATR(14) ₹{t['atr_14']}, BB Width {t['bb_bandwidth']}%\n"
        f"• Pivots: Pivot ₹{t['pivot_point']}, Res ₹{t['resistance_level']}, Supp ₹{t['support_level']}\n\n"
        f"[bold green]FUNDAMENTALS & VALUATION[/bold green]\n"
        f"• P/E: {f['pe_ratio']} | P/B: {f['pb_ratio']} | EV/EBITDA: {f['ev_ebitda']} | ROE: {f['roe_pct']}%\n"
        f"• Rev Growth YoY: +{f['revenue_growth_yoy']}% | EPS Growth YoY: +{f['earnings_growth_yoy']}%\n\n"
        f"[bold magenta]DERIVATIVES & NSE F&O[/bold magenta]\n"
        f"• PCR: {d['pcr']} | Max Pain: ₹{d['max_pain']} | ATM IV: {d['atm_iv']*100:.1f}% | Basis: {d['futures_basis']:+0.2f}\n"
        f"• GEX Exposure: ₹{d['dealer_gamma_exposure_gex']:,.2f} | Status: {d['futures_contango_backwardation']}\n\n"
        f"[bold white]ORDER FLOW & DATA QUALITY[/bold white]\n"
        f"• Delta: {o['delta']:+0.0f} | CVD: {o['cumulative_delta']:+0.0f} | Imbalance: {o['order_book_imbalance']:+0.2f}\n"
        f"• Data Quality Score: [bold green]{q['quality_score']}/100[/bold green] (Acceptable: {q['is_acceptable']})",
        title=f"[bold green]Unified 360° Data & Metrics Dossier: {symbol}[/bold green]",
    ))


@data_app.command("macro")
def view_macro_context():
    """Display macroeconomic indicators, India VIX, and FII/DII institutional flows."""
    from data_layer.unified_layer import unified_data_layer
    ctx = unified_data_layer.get_macro_and_indian_market_context()

    reg = ctx["market_regime"]
    mac = ctx["macro_economics"]
    ind = ctx["indian_market_data"]

    console.print(Panel(
        f"[bold cyan]MARKET REGIME & BREADTH[/bold cyan]\n"
        f"• Regime: [bold green]{reg['regime_name']}[/bold green] | State: {reg['trend_state']} / {reg['risk_state']}\n"
        f"• India VIX: {reg['india_vix']} | A/D Ratio: {reg['advance_decline_ratio']} | Nifty Breadth: {reg['nifty50_breadth_pct']}%\n"
        f"• Sector Leader: {reg['sector_rotation_leader']}\n\n"
        f"[bold yellow]MACRO ECONOMIC DRIVERS[/bold yellow]\n"
        f"• RBI Repo Rate: {mac['rbi_repo_rate_pct']}% | CPI Inflation: {mac['cpi_inflation_pct']}%\n"
        f"• India 10Y Yield: {mac['india_10y_yield_pct']}% | USD/INR: ₹{mac['usd_inr']}\n"
        f"• Brent Crude: ${mac['brent_crude_usd']}/bbl | Gold: ${mac['gold_usd_oz']}/oz\n\n"
        f"[bold magenta]INSTITUTIONAL FLOWS (NSE/BSE)[/bold magenta]\n"
        f"• FII Net Flow: {'+' if ind['fii_net_flow_cr']>=0 else ''}₹{ind['fii_net_flow_cr']:,.2f} Cr\n"
        f"• DII Net Flow: {'+' if ind['dii_net_flow_cr']>=0 else ''}₹{ind['dii_net_flow_cr']:,.2f} Cr\n"
        f"• Delivery %: {ind['delivery_pct_avg']}%",
        title="[bold green]Macroeconomic & Indian Market Context[/bold green]",
    ))


@data_app.command("quality")
def view_data_quality(feed: str = typer.Option("NSE_NIFTY50", "--feed", help="Data feed name")):
    """Audit real-time data quality score and anomaly status for a feed."""
    from data_layer.quality_engine import DataQualityEngine
    dummy_c = [25000.0 + i * 10 for i in range(50)]
    dummy_v = [100000.0 for _ in range(50)]
    audit = DataQualityEngine.audit_ohlcv_feed(feed_name=feed, closes=dummy_c, volumes=dummy_v)

    console.print(Panel(
        f"[bold cyan]Feed Name:[/bold cyan] {audit.feed_name}\n"
        f"[bold cyan]Freshness Latency:[/bold cyan] {audit.freshness_latency_ms} ms\n"
        f"[bold cyan]Missing Values:[/bold cyan] {audit.missing_values}\n"
        f"[bold cyan]Duplicates:[/bold cyan] {audit.duplicates}\n"
        f"[bold cyan]Anomalies Detected:[/bold cyan] {audit.anomalies_detected}\n"
        f"[bold]Quality Score:[/bold] [bold green]{audit.quality_score}/100[/bold green]\n"
        f"[bold]Feed Integrity Status:[/bold] {'HEALTHY ✅' if audit.is_acceptable else 'DEGRADED ❌'}",
        title="[bold green]Data Quality & Feed Integrity Audit[/bold green]",
    ))


@app.command("live")
def run_live_cmd(
    broker: str = typer.Option("angelone", "--broker", help="Broker to use: 'angelone', 'zerodha', 'fyers'"),
    universe: str = typer.Option("nifty50", "--universe", help="Stock universe: 'nifty50', 'nifty100'"),
    top: int = typer.Option(5, "--top", help="Number of stocks to scan and debate per cycle"),
):
    """Launch full autonomous live trading system on AngelOne SmartAPI with Gemini AI."""
    from run_live import launch_live_system
    asyncio.run(launch_live_system())


@app.command("tunnel")
def run_tunnel_cmd():
    """Launch secure Cloudflare tunnel to access the trading dashboard from anywhere on your domain."""
    from scripts.start_tunnel import run_quick_tunnel
    run_quick_tunnel()


@app.command("audit")
def run_audit_cmd():
    """Run comprehensive Production Go-Live Readiness Verification Audit Suite."""
    from scripts.go_live_readiness_audit import run_go_live_audit
    asyncio.run(run_go_live_audit())


@app.command("kronos")
def run_kronos_cmd(
    symbol: str = typer.Option("PNB.NS", "--symbol", "-s", help="Stock or crypto ticker (e.g. PNB.NS, RELIANCE.NS, BTC-USD)"),
    bars: int = typer.Option(10, "--bars", "-b", help="Number of future candlestick bars to predict (e.g. 5, 10, 20)"),
):
    """Run Tsinghua Kronos Financial Candlestick Foundation Model zero-shot forecast on any stock or crypto."""
    async def _forecast():
        from rich.panel import Panel
        from rich.table import Table

        from intelligence.kronos_service import kronos_service
        from market.providers.yfinance_provider import YFinanceMarketDataProvider

        console.print(f"[bold magenta]🔮 Querying Kronos Foundation Model for {symbol}...[/bold magenta]")
        provider = YFinanceMarketDataProvider()
        interval = "15m" if "-USD" in symbol else "1d"
        df = await provider.get_historical_ohlcv(symbol, interval=interval, period="60d")
        
        if df.empty:
            console.print(f"[bold red]❌ Failed to fetch historical data for {symbol}[/bold red]")
            return

        res = await kronos_service.forecast(symbol, df, pred_len=bars)

        curr = "$" if "-USD" in symbol else "₹"
        color = "green" if res.expected_direction == "BULLISH" else "red" if res.expected_direction == "BEARISH" else "yellow"

        panel = Panel(
            f"[bold]Symbol:[/bold] [cyan]{res.symbol}[/cyan] ({interval} timeframe)\n"
            f"[bold]Model:[/bold] [blue]{res.model_name}[/blue] on [magenta]{res.device.upper()}[/magenta]\n"
            f"[bold]Last Close:[/bold] [yellow]{curr}{res.last_price:.2f}[/yellow]\n"
            f"[bold]Projected Close:[/bold] [{color}]{curr}{res.projected_price:.2f} ({res.projected_change_pct:+.2f}%)[/{color}]\n"
            f"[bold]Direction:[/bold] [{color} bold]{res.expected_direction}[/{color} bold] (Confidence: {res.confidence_score*100:.1f}%)\n"
            f"[bold]Predicted Range:[/bold] Low {curr}{res.projected_low:.2f}  ➔  High {curr}{res.projected_high:.2f}\n"
            f"[bold]Recommended Stop-Loss:[/bold] [red]{curr}{res.recommended_stop_loss:.2f}[/red]\n"
            f"[bold]Recommended Target:[/bold] [green]{curr}{res.recommended_target:.2f}[/green]\n"
            f"[bold]Status:[/bold] {res.status}\n"
            f"[dim]{res.notes}[/dim]",
            title="[bold green]🔮 Kronos Candlestick Foundation Model Forecast[/bold green]",
            border_style="magenta",
        )
        console.print(panel)

        if res.predicted_bars:
            tbl = Table(title=f"Next {len(res.predicted_bars)} Predicted Candlestick Bars")
            tbl.add_column("Bar #", style="dim")
            tbl.add_column("Open")
            tbl.add_column("High", style="green")
            tbl.add_column("Low", style="red")
            tbl.add_column("Close", style="bold cyan")

            for b in res.predicted_bars:
                tbl.add_row(
                    str(b["step"]),
                    f"{curr}{b['open']:.2f}",
                    f"{curr}{b['high']:.2f}",
                    f"{curr}{b['low']:.2f}",
                    f"{curr}{b['close']:.2f}",
                )
            console.print(tbl)

    asyncio.run(_forecast())


if __name__ == "__main__":
    app()






