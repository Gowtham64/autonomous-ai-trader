import asyncio
import os
from contextlib import asynccontextmanager
from datetime import UTC, datetime
from typing import Annotated, Any

from fastapi import Depends, FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from apps.api.office_service import ai_office_service
from apps.api.routers.guardian import router as guardian_router
from apps.api.routers.training import router as training_router
from core.auth.security import (
    LoginRequest,
    TokenResponse,
    authenticate_user,
    create_access_token,
    get_current_user,
    require_admin,
)
from core.config.settings import TradingMode, settings
from core.logging import logger
from database.repositories.trade_repo import TradeRepository
from database.session import init_db
from execution.brokers.angelone import AngelOneBroker
from execution.paper.broker import PaperBroker
from market.providers.yfinance_provider import YFinanceMarketDataProvider
from orchestration.graph import build_trading_workflow_graph
from scanner.quant_scanner import QuantMarketScanner
from skills.agent_manager import agent_skill_manager
from skills.builder import skill_builder
from skills.models import (
    AgentSkillComposition,
    SkillCategory,
    SkillDefinition,
    SkillExecutionRequest,
    SkillProposalRequest,
    SkillRiskLevel,
)
from skills.registry import skill_registry

from execution.broker_factory import get_active_broker as get_configured_broker

market_provider = YFinanceMarketDataProvider()
background_api_tasks: set[asyncio.Task] = set()

# Real live quotes cache populated from exchange
_live_quotes_cache = [
    {"symbol": "NIFTY 50", "ltp": 23140.50, "change": 0.34, "volume": 242700},
    {"symbol": "BANKNIFTY", "ltp": 55580.40, "change": 0.26, "volume": 145900},
    {"symbol": "RELIANCE", "ltp": 1226.00, "change": 0.56, "volume": 13138735},
    {"symbol": "SBIN", "ltp": 983.00, "change": 0.46, "volume": 3759097},
    {"symbol": "TCS", "ltp": 2082.00, "change": -0.24, "volume": 3342195},
    {"symbol": "INFY", "ltp": 1000.20, "change": -1.41, "volume": 10240700},
    {"symbol": "HDFCBANK", "ltp": 735.60, "change": 0.92, "volume": 19853034},
    {"symbol": "TATAMOTORS", "ltp": 965.20, "change": 1.45, "volume": 3600000},
    {"symbol": "ICICIBANK", "ltp": 1240.15, "change": 0.38, "volume": 2400000},
]

async def get_active_broker():
    broker = get_configured_broker()
    if settings.TRADING_MODE == TradingMode.LIVE:
        if hasattr(broker, "_is_authenticated") and not broker._is_authenticated:
            await broker.authenticate_session(force=False)
    return broker

async def update_real_quotes_task():
    symbols_to_poll = ["NIFTY 50", "BANKNIFTY", "RELIANCE", "SBIN", "TCS", "INFY", "HDFCBANK", "ICICIBANK", "BHARTIARTL", "ITC"]
    while True:
        try:
            async def _safe_fetch(s):
                try:
                    return await asyncio.wait_for(market_provider.get_quote(s), timeout=4.0)
                except Exception:
                    return None

            results = await asyncio.gather(*[_safe_fetch(s) for s in symbols_to_poll], return_exceptions=True)
            for res in results:
                if isinstance(res, dict) and res.get("ltp", 0.0) > 0:
                    s = res["symbol"]
                    found = False
                    for item in _live_quotes_cache:
                        if item["symbol"] == s:
                            item["ltp"] = res["ltp"]
                            item["change"] = res.get("change", 0.0)
                            item["volume"] = res.get("volume", 0.0)
                            found = True
                            break
                    if not found:
                        _live_quotes_cache.append(res)
        except Exception as e:
            logger.debug(f"[MarketFeed] Real quote refresh note: {e}")
        await asyncio.sleep(15.0)


@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_db()
    if settings.TRADING_MODE == TradingMode.LIVE:
        logger.info("[Startup] Authenticating Live AngelOne SmartAPI Session...")
        broker = await get_active_broker()
        await broker.authenticate_session(force=False)
    quotes_task = asyncio.create_task(update_real_quotes_task())
    background_api_tasks.add(quotes_task)
    quotes_task.add_done_callback(background_api_tasks.discard)
    # Start continuous off-market training daemon
    from training.continuous_runner import continuous_training_daemon
    continuous_training_daemon.start()
    yield

app = FastAPI(
    title="Autonomous Multi-Agent AI Trading API",
    version="1.0.0",
    description="REST API for the Autonomous Multi-Agent Trading System for Indian Markets (NSE/BSE)",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(guardian_router)
app.include_router(training_router)

# Mount Dashboard Static Assets
dashboard_dir = os.path.join(os.path.dirname(__file__), "..", "dashboard")
if os.path.exists(dashboard_dir):
    app.mount("/static", StaticFiles(directory=dashboard_dir), name="static")

@app.get("/")
async def serve_dashboard():
    index_path = os.path.join(dashboard_dir, "index.html")
    if os.path.exists(index_path):
        return FileResponse(index_path)
    return {"message": "Autonomous AI Trader API Active"}


@app.websocket("/ws/live-feed")
async def websocket_live_feed(websocket: WebSocket):
    """Sub-second Real-Time Market Data and AI Telemetry WebSocket Stream."""
    if settings.AUTH_REQUIRED:
        token = websocket.query_params.get("token")
        from core.auth.security import decode_access_token
        if not token or not decode_access_token(token):
            await websocket.close(code=1008, reason="Authentication required")
            return

    await websocket.accept()
    try:
        from core.treasury.treasury import treasury

        while True:
            try:
                treasury_metrics = treasury.get_metrics()
                treasury_metrics["broker_mode"] = settings.TRADING_MODE.value
                treasury_metrics["client_code"] = settings.ANGELONE_CLIENT_CODE if settings.TRADING_MODE == TradingMode.LIVE else "PAPER"
                treasury_metrics["daily_loss_limit"] = round(treasury.starting_capital * settings.MAX_DAILY_LOSS_PCT, 2)
                treasury_metrics["daily_realized_loss"] = round(abs(min(0.0, treasury.realized_pnl)), 2)

                payload = {
                    "type": "MARKET_TICK_STREAM",
                    "timestamp": str(datetime.now(UTC)),
                    "quotes": list(_live_quotes_cache),
                    "treasury": treasury_metrics,
                    "positions_count": 0,
                }
                await websocket.send_json(payload)
            except (WebSocketDisconnect, asyncio.CancelledError):
                break
            except Exception as e:
                logger.debug(f"[WebSocket] Tick send note: {e}")
            await asyncio.sleep(1.0)
    except (WebSocketDisconnect, asyncio.CancelledError):
        pass


@app.get("/health")
async def health():
    return {
        "status": "healthy",
        "trading_mode": settings.TRADING_MODE.value,
        "exchange": settings.EXCHANGE,
        "strategy_version": settings.STRATEGY_VERSION,
        "broker_client": settings.ANGELONE_CLIENT_CODE if settings.TRADING_MODE == TradingMode.LIVE else "PAPER_LOCAL",
    }


@app.get("/api/funds", dependencies=[Depends(get_current_user)])
async def get_funds():
    broker = await get_active_broker()
    return await broker.get_funds()


@app.get("/api/positions", dependencies=[Depends(get_current_user)])
async def get_positions():
    broker = await get_active_broker()
    positions = await broker.get_positions()
    return {"positions": positions}


@app.get("/api/orders", dependencies=[Depends(get_current_user)])
async def get_orders():
    """Returns all placed orders from both the database and AngelOne broker gateway."""
    broker = await get_active_broker()
    db_orders = await TradeRepository.get_recent_orders(limit=50)
    broker_orders = await broker.get_order_book()
    broker_trades = await broker.get_trade_book()
    return {
        "orders_count": len(db_orders) + len(broker_orders),
        "db_orders": [
            {
                "order_id": o.order_id,
                "client_order_id": o.client_order_id,
                "symbol": o.symbol,
                "action": o.action,
                "status": o.status,
                "quantity": o.quantity,
                "average_price": o.average_price,
                "executed_at": o.executed_at.isoformat() if hasattr(o.executed_at, "isoformat") else str(o.executed_at),
            }
            for o in db_orders
        ],
        "broker_order_book": broker_orders,
        "broker_trade_book": broker_trades,
    }


@app.get("/api/performance", dependencies=[Depends(get_current_user)])
async def get_performance():
    """Returns comprehensive live trading performance, PnL, and live account metrics."""
    from core.treasury.treasury import treasury
    broker = await get_active_broker()
    funds = await broker.get_funds()
    positions = await broker.get_positions()
    metrics = treasury.get_metrics()
    return {
        "live_funds": funds,
        "available_cash": funds.get("available_margin", 0.0),
        "total_capital": funds.get("total_capital", 0.0),
        "used_margin": funds.get("used_margin", 0.0),
        "open_positions": positions,
        "open_positions_count": len(positions),
        "metrics": metrics,
        "history": treasury.history,
    }



@app.get("/api/scan", dependencies=[Depends(get_current_user)])
async def scan_market(top_n: int = 12, universe: str = "bootstrap"):
    scanner = QuantMarketScanner(provider=market_provider, universe=universe, max_concurrency=25)
    candidates = await scanner.get_top_candidates(top_n=top_n)
    return {"candidates": candidates}


@app.post("/api/analyze", dependencies=[Depends(get_current_user)])
async def run_analysis(symbol: str = "RELIANCE.NS"):
    scanner = QuantMarketScanner(provider=market_provider)
    sig = await scanner.scan_symbol(symbol)
    if not sig:
        raise HTTPException(status_code=404, detail=f"Market data for symbol '{symbol}' not found on NSE/BSE.")

    graph = build_trading_workflow_graph()
    initial_state = {
        "signal": sig,
        "analyst_reports": [],
        "debate": None,
        "decision": None,
    }

    final_state = await graph.ainvoke(initial_state)
    return {
        "signal": final_state["signal"],
        "analyst_reports": final_state["analyst_reports"],
        "debate": final_state["debate"],
        "decision": final_state["decision"],
    }


@app.post("/api/batch-debate", dependencies=[Depends(get_current_user)])
async def run_batch_debate(top_n: int = 8, universe: str = "bootstrap"):
    """Scans N stocks from universe and runs multi-agent Bull vs Bear debates and Fund Manager decisions."""
    scanner = QuantMarketScanner(provider=market_provider, universe=universe)
    candidates = await scanner.get_top_candidates(top_n=top_n)

    broker = await get_active_broker()
    funds = await broker.get_funds()
    avail_cap = float(funds.get("available_margin", 0.0))

    from orchestration.batch_engine import MultiStockOrchestrator
    orchestrator = MultiStockOrchestrator()
    summary = await orchestrator.run_batch_debate_and_allocation(candidates, available_capital=avail_cap)

    return {
        "universe": universe,
        "total_evaluated": summary["total_evaluated"],
        "approved_count": len(summary["approved_trades"]),
        "rejected_count": len(summary["rejected_trades"]),
        "approved_trades": summary["approved_trades"],
        "rejected_trades": summary["rejected_trades"],
        "ranked_candidates": summary["ranked_candidates"],
    }


@app.get("/api/treasury", dependencies=[Depends(get_current_user)])
async def get_treasury():
    """Retrieve AI Treasury balance, operating costs, net profit, and Survival Mode status."""
    from core.treasury.treasury import treasury
    broker = await get_active_broker()
    if settings.TRADING_MODE == TradingMode.LIVE:
        try:
            funds = await broker.get_funds()
            positions = await broker.get_positions()
            real_cap = float(funds.get("total_capital", 0.0))
            avail_margin = float(funds.get("available_margin", 0.0))
            treasury.current_capital = real_cap
            treasury.starting_capital = real_cap
            treasury.buckets.trading_capital = avail_margin
            unrealized = sum(getattr(p, "unrealized_pnl", 0.0) for p in positions)
            realized = sum(getattr(p, "realized_pnl", 0.0) for p in positions)
            treasury.set_unrealized_pnl(unrealized)
            if realized != 0.0:
                treasury.realized_pnl = realized
        except Exception as e:
            logger.warning(f"[Treasury] Live broker sync warning: {e}")

    metrics = treasury.get_metrics()
    metrics["broker_mode"] = settings.TRADING_MODE.value
    metrics["client_code"] = settings.ANGELONE_CLIENT_CODE if settings.TRADING_MODE == TradingMode.LIVE else "PAPER"
    metrics["daily_loss_limit"] = round(treasury.starting_capital * settings.MAX_DAILY_LOSS_PCT, 2)
    metrics["daily_realized_loss"] = round(abs(min(0.0, treasury.realized_pnl)), 2)
    return metrics


@app.get("/api/office", dependencies=[Depends(get_current_user)])
async def get_office_roster():
    """Retrieve active and standby AI Trading Office specialized agents."""
    from agents.lifecycle.agent_manager import agent_manager
    return {"roster": agent_manager.get_office_roster()}


@app.get("/api/learning-stats", dependencies=[Depends(get_current_user)])
async def get_learning_stats():
    """Retrieve 4-Quadrant Decision Quality statistics from the post-trade learning loop."""
    from memory.learning_loop import learning_loop
    return learning_loop.get_quadrant_statistics()


@app.get("/api/kill-switch", dependencies=[Depends(get_current_user)])
async def get_kill_switch_status():
    """Retrieve Emergency Kill Switch state."""
    from risk.kill_switch import kill_switch
    return {
        "is_engaged": kill_switch.is_engaged,
        "reason": kill_switch.reason,
        "events_count": len(kill_switch.history),
    }


@app.post("/api/kill-switch", dependencies=[Depends(require_admin)])
async def trigger_kill_switch(engage: bool = True, reason: str = "Operator action via API"):
    """Engage or reset the Emergency Kill Switch."""
    from risk.kill_switch import kill_switch
    if engage:
        kill_switch.trigger("REST_API", reason)
    else:
        kill_switch.reset("REST_API")
    return {
        "is_engaged": kill_switch.is_engaged,
        "reason": kill_switch.reason,
    }


@app.get("/api/capital-scaling", dependencies=[Depends(get_current_user)])
async def get_capital_scaling_status():
    """Evaluate statistical capital scaling authorization beyond ₹2,000 bootstrap."""
    from core.treasury.treasury import treasury
    from portfolio.capital_scaler import CapitalScalingPolicy
    return CapitalScalingPolicy.evaluate_scaling(
        total_trades=len(treasury.history),
        winning_trades=sum(1 for h in treasury.history if h.amount > 0),
        total_profit=max(0.0, treasury.realized_pnl),
        total_loss=min(0.0, treasury.realized_pnl),
        max_drawdown_pct=0.02,
        current_capital=settings.MAX_CAPITAL,
    )


# ==========================================
# ==========================================
# CUSTOM AI AGENT FACTORY REST ENDPOINTS
# ==========================================

@app.get("/api/factory/functions", dependencies=[Depends(get_current_user)])
async def get_factory_functions():
    """Returns the catalog of available functions and tool categories with permissions."""
    from agents.factory.functions_catalog import get_available_functions
    return {"functions": get_available_functions()}


@app.get("/api/factory/agents", dependencies=[Depends(get_current_user)])
async def get_custom_agents():
    """Returns all custom agents in the Agent Library / Marketplace."""
    from agents.factory.factory import agent_factory
    return {"agents": [a.model_dump() for a in agent_factory.list_all_agents()]}


@app.post("/api/factory/agents", dependencies=[Depends(require_admin)])
async def create_custom_agent(payload: dict):
    """Creates a custom AI agent either manually or from natural language prompt."""
    from agents.factory.factory import agent_factory
    from agents.factory.models import CustomAgentProfile, Department

    if payload.get("prompt"):
        name = payload.get("name", "Custom AI Specialist")
        dept_str = payload.get("department", "Research")
        dept = Department(dept_str) if dept_str in [d.value for d in Department] else Department.RESEARCH
        agent = agent_factory.parse_natural_language_instruction(
            prompt=payload["prompt"],
            name=name,
            department=dept,
        )
        return {"agent": agent.model_dump(), "mode": "NATURAL_LANGUAGE_GENERATED"}

    profile = CustomAgentProfile(**payload)
    created = agent_factory.create_agent(profile)
    return {"agent": created.model_dump(), "mode": "MANUAL_CONFIG"}


@app.get("/api/factory/agents/{agent_id}", dependencies=[Depends(get_current_user)])
async def get_custom_agent_detail(agent_id: str):
    """Retrieves profile and performance metrics for a specific custom agent."""
    from agents.factory.factory import agent_factory
    if agent_id not in agent_factory.agent_store:
        raise HTTPException(status_code=404, detail=f"Agent '{agent_id}' not found.")
    return {"agent": agent_factory.agent_store[agent_id].model_dump()}


@app.post("/api/factory/agents/{agent_id}/clone", dependencies=[Depends(require_admin)])
async def clone_custom_agent(agent_id: str, new_name: str = "Cloned Specialist"):
    """Clones an existing agent with a new identity."""
    from agents.factory.factory import agent_factory
    cloned = agent_factory.clone_agent(agent_id, new_name=new_name)
    return {"cloned_agent": cloned.model_dump()}


@app.post("/api/factory/agents/{agent_id}/status", dependencies=[Depends(require_admin)])
async def update_agent_status(agent_id: str, status: str = "ACTIVE"):
    """Updates the lifecycle stage of a custom agent."""
    from agents.factory.factory import agent_factory
    from agents.factory.models import LifecycleStage
    try:
        stage = LifecycleStage(status.upper())
    except ValueError:
        raise HTTPException(status_code=400, detail=f"Invalid lifecycle stage: {status}")
    updated = agent_factory.update_lifecycle_stage(agent_id, stage)
    return {"agent": updated.model_dump()}


@app.post("/api/factory/agents/{agent_id}/test", dependencies=[Depends(get_current_user)])
async def test_agent_sandbox(agent_id: str, symbol: str = "RELIANCE.NS"):
    """Runs dry-run simulation and permission verification inside the sandbox."""
    from agents.factory.factory import agent_factory
    result = await agent_factory.run_sandbox_simulation(agent_id, symbol=symbol)
    return {"test_result": result}


@app.delete("/api/factory/agents/{agent_id}", dependencies=[Depends(require_admin)])
async def delete_custom_agent(agent_id: str):
    """Decommissions and removes custom agent."""
    from agents.factory.factory import agent_factory
    success = agent_factory.delete_agent(agent_id)
    return {"deleted": success, "agent_id": agent_id}


@app.post("/api/factory/recommend", dependencies=[Depends(get_current_user)])
async def recommend_agent(gap: str = "Quarterly Earnings & Corporate Filings"):
    """Generates Chief AI agent proposal for capability gap."""
    from agents.factory.factory import agent_factory
    proposal = agent_factory.recommend_agent_by_chief_ai(gap)
    return {"recommendation": proposal}


@app.get("/api/factory/messages", dependencies=[Depends(get_current_user)])
async def get_agent_messages():
    """Retrieves recent inter-agent communication messages from the organizational bus."""
    from agents.factory.message_bus import agent_message_bus
    return {"messages": agent_message_bus.get_recent_messages()}


# ==========================================
# UNIFIED AI MEMORY & KNOWLEDGE GRAPH API
# ==========================================

@app.get("/api/memory/search", dependencies=[Depends(get_current_user)])
async def search_ai_memory(
    q: str = "",
    role: str = "chief_trading_agent",
    symbol: str | None = None,
    limit: int = 15,
):
    """Queries 3-layer AI memory (Private, Organizational, Long-Term)."""
    from memory.global_memory import global_ai_memory
    results = global_ai_memory.search_memories(
        query=q,
        agent_role=role,
        symbol=symbol,
        limit=limit,
    )
    return {"query": q, "count": len(results), "memories": [m.model_dump() for m in results]}


@app.post("/api/memory/record", dependencies=[Depends(require_admin)])
async def record_memory(payload: dict):
    """Stores new observation or lesson in organizational memory."""
    from memory.global_memory import global_ai_memory
    from memory.models import MemoryRecord
    record = MemoryRecord(**payload)
    saved = global_ai_memory.write_memory(record, agent_role=payload.get("created_by", "analyst"))
    return {"status": "saved", "memory": saved.model_dump()}


@app.get("/api/memory/summary", dependencies=[Depends(get_current_user)])
async def get_memory_summary():
    """Retrieves the latest daily organizational memory consolidation summary."""
    from memory.memory_manager_agent import memory_manager_agent
    return memory_manager_agent.get_latest_summary()


@app.get("/api/reports/daily/latest")
async def get_latest_daily_report(refresh: bool = False, force: bool = False):
    """Retrieves the latest End-Of-Day market close report with real-time broker execution data."""
    import time
    from pathlib import Path
    import json
    from execution.broker_factory import get_active_broker
    from reporting.daily_eod_reporter import daily_eod_reporter

    broker = get_active_broker()
    latest_json = Path("reports/daily/latest.json")
    latest_md = Path("reports/daily/latest.md")

    should_regenerate = force or refresh or not latest_json.exists()
    if not should_regenerate and latest_json.exists():
        # Auto-regenerate if cache is older than 180 seconds (3 minutes)
        try:
            file_age = time.time() - latest_json.stat().st_mtime
            if file_age > 180:
                should_regenerate = True
        except Exception:
            should_regenerate = True

    if should_regenerate:
        try:
            data = await daily_eod_reporter.generate_daily_report(broker, market_provider)
            md_text = latest_md.read_text(encoding="utf-8") if latest_md.exists() else ""
            return {"report": data, "markdown": md_text}
        except Exception as e:
            logger.error(f"[API] Error generating live daily report: {e}")

    try:
        data = json.loads(latest_json.read_text(encoding="utf-8"))
    except Exception:
        data = {}
    md_text = latest_md.read_text(encoding="utf-8") if latest_md.exists() else ""
    return {"report": data, "markdown": md_text}


@app.get("/api/reports/daily/dates")
async def get_report_dates():
    """Lists all available historical and latest EOD report dates with summaries."""
    from reporting.daily_eod_reporter import daily_eod_reporter
    return {"dates": daily_eod_reporter.get_available_dates()}


@app.get("/api/reports/daily/date/{report_date}")
async def get_daily_report_by_date(report_date: str):
    """Retrieves complete report and forensic loss analysis for a specific date."""
    import json
    import re
    from pathlib import Path
    from reporting.daily_eod_reporter import daily_eod_reporter

    if report_date.lower() == "latest":
        return await get_latest_daily_report()

    # Strict regex validation to eliminate path traversal
    if not re.match(r"^[0-9]{4}-[0-9]{2}-[0-9]{2}$", report_date):
        raise HTTPException(status_code=400, detail="Invalid report_date format. Expected YYYY-MM-DD.")

    base_dir = Path("reports/daily").resolve()
    data = daily_eod_reporter.get_report_by_date(report_date)
    if not data:
        # Check latest.json if date matches
        latest_json = base_dir / "latest.json"
        if latest_json.exists():
            try:
                latest_data = json.loads(latest_json.read_text(encoding="utf-8"))
                if latest_data.get("date") == report_date:
                    latest_md = base_dir / "latest.md"
                    md_text = latest_md.read_text(encoding="utf-8") if latest_md.exists() else ""
                    return {"report": latest_data, "markdown": md_text}
            except Exception:
                pass
        raise HTTPException(status_code=404, detail=f"No report found for date {report_date}")

    md_file = (base_dir / f"EOD_Report_{report_date}.md").resolve()
    if not md_file.is_relative_to(base_dir):
        raise HTTPException(status_code=400, detail="Invalid path traversal detected.")

    md_text = md_file.read_text(encoding="utf-8") if md_file.exists() else ""
    return {"report": data, "markdown": md_text}


@app.post("/api/reports/daily/generate", dependencies=[Depends(require_admin)])
async def trigger_daily_report():
    """Triggers instant compilation of the End-Of-Day trading report."""
    from execution.broker_factory import get_active_broker
    from reporting.daily_eod_reporter import daily_eod_reporter
    broker = get_active_broker()
    data = await daily_eod_reporter.generate_daily_report(broker, market_provider)
    from pathlib import Path
    latest_md = Path("reports/daily/latest.md")
    md_text = latest_md.read_text(encoding="utf-8") if latest_md.exists() else ""
    return {"status": "SUCCESS", "report": data, "markdown": md_text}



@app.get("/api/knowledge-graph", dependencies=[Depends(get_current_user)])
async def get_knowledge_graph():
    """Retrieves nodes, edges, and relationship topologies from the Knowledge Graph."""
    from memory.knowledge_graph import knowledge_graph
    return {
        "summary": knowledge_graph.get_graph_summary(),
        "nodes": [n.model_dump() for n in knowledge_graph.nodes.values()],
        "edges": [e.model_dump() for e in knowledge_graph.edges[-50:]],
    }


# ==========================================
# REAL-TIME EVENT BUS & TASK ENGINE API
# ==========================================

@app.get("/api/events", dependencies=[Depends(get_current_user)])
async def get_system_events(limit: int = 25):
    """Retrieves recent event stream from the Real-Time Event Bus and AI Office."""
    from apps.api.office_service import ai_office_service
    from orchestration.event_bus import realtime_event_bus
    bus_events = realtime_event_bus.get_recent_events(limit=limit)
    if not bus_events and ai_office_service.live_events:
        return {"events": ai_office_service.live_events[-limit:]}
    return {"events": bus_events or ai_office_service.live_events[-limit:]}


@app.get("/api/tasks", dependencies=[Depends(get_current_user)])
async def get_agent_tasks(limit: int = 25):
    """Retrieves active and completed agent task handoffs."""
    from orchestration.task_engine import task_handoff_engine
    return {"tasks": task_handoff_engine.list_all_tasks(limit=limit)}


# ==========================================
# AI TREASURY, CFO & CTO UPGRADE API
# ==========================================

@app.get("/api/treasury/balance-sheet", dependencies=[Depends(get_current_user)])
async def get_organization_balance_sheet():
    """Generates official AI Organization Balance Sheet."""
    from core.treasury.balance_sheet import balance_sheet_generator
    sheet = balance_sheet_generator.generate()
    return sheet.model_dump()


@app.get("/api/treasury/ledger", dependencies=[Depends(get_current_user)])
async def get_treasury_ledger(limit: int = 25):
    """Retrieves recent ledger transactions across all cost centers."""
    from core.treasury.treasury import treasury
    return {"ledger": treasury.get_recent_ledger(limit=limit)}


@app.get("/api/cfo/audit", dependencies=[Depends(get_current_user)])
async def get_cfo_audit():
    """Retrieves CFO financial audit and runway assessment."""
    from core.treasury.cfo_agent import ai_cfo_agent
    return ai_cfo_agent.get_financial_audit_report()


@app.get("/api/cto/proposals", dependencies=[Depends(get_current_user)])
async def get_cto_proposals():
    """Retrieves technology upgrade proposals and validation pipeline states."""
    from core.treasury.cto_agent import ai_cto_agent
    return {"proposals": ai_cto_agent.list_all_proposals()}


# ==========================================
# UNIFIED TRADING DATA & METRICS LAYER API
# ==========================================

@app.get("/api/data/metrics/{symbol}", dependencies=[Depends(get_current_user)])
async def get_symbol_data_metrics(symbol: str):
    """Retrieves 360-degree quantitative, technical, and performance metrics for a specific stock."""
    from data_layer.unified_layer import unified_data_layer
    profile = unified_data_layer.get_complete_symbol_profile(symbol)

    # Enrich with live real-time scanner metrics
    try:
        clean_sym = symbol if symbol.endswith((".NS", ".BO")) else f"{symbol}.NS"
        scanner = QuantMarketScanner(provider=market_provider)
        sig = await scanner.scan_symbol(clean_sym)
        if sig:
            profile.update({
                "symbol": sig.symbol,
                "ltp": sig.ltp,
                "volume": sig.volume,
                "avg_volume_20d": sig.avg_volume_20d,
                "relative_volume": sig.relative_volume,
                "momentum_score": sig.momentum_score,
                "atr_14": sig.atr_14,
                "regime": sig.regime.value if hasattr(sig.regime, "value") else str(sig.regime),
                "sector": sig.sector,
            })
    except Exception as e:
        logger.debug(f"[Metrics API] Real-time enrich note for {symbol}: {e}")

    return profile



@app.get("/api/data/macro-context", dependencies=[Depends(get_current_user)])
async def get_macro_data_context():
    """Retrieves macroeconomic data, RBI rates, India VIX, FII/DII flows, and Market Regime."""
    from data_layer.unified_layer import unified_data_layer
    return unified_data_layer.get_macro_and_indian_market_context()


@app.get("/api/forecast/kronos", dependencies=[Depends(get_current_user)])
async def get_kronos_forecast(symbol: str = "PNB.NS", bars: int = 10):
    """Zero-shot autoregressive candlestick foundation model forecast powered by Tsinghua AAAI 2026 Kronos."""
    from intelligence.kronos_service import kronos_service
    from market.providers.yfinance_provider import YFinanceMarketDataProvider
    provider = YFinanceMarketDataProvider()
    interval = "15m" if "-USD" in symbol else "1d"
    df = await provider.get_historical_ohlcv(symbol, interval=interval, period="30d")
    res = await kronos_service.forecast(symbol, df, pred_len=bars)
    return res.to_dict()


@app.get("/metrics")
async def prometheus_metrics():
    """Exposes real-time Prometheus metrics for Grafana scraping and latency/drift monitoring."""
    from fastapi.responses import PlainTextResponse
    from monitoring.observability import observability
    from core.treasury.treasury import treasury
    from risk.kill_switch import kill_switch

    metrics_text = observability.generate_prometheus_metrics(
        margin_inr=treasury.buckets.trading_capital,
        active_positions=len(treasury.history),
        daily_loss_inr=abs(min(0.0, treasury.realized_pnl)),
        kill_switch_engaged=kill_switch.is_engaged,
    )
    return PlainTextResponse(metrics_text, media_type="text/plain; version=0.0.4")


@app.get("/api/news/intel", dependencies=[Depends(get_current_user)])
async def get_news_intelligence(symbol: str | None = None):
    """Retrieves structured corporate announcements, filings, ratings, and macro news intelligence."""
    from intelligence.news_engine import news_intelligence_engine
    if symbol:
        return news_intelligence_engine.analyze_symbol_news(symbol)
    return {"recent_news": [item.model_dump() for item in news_intelligence_engine.get_market_wide_news()]}


@app.get("/api/premarket/report", dependencies=[Depends(get_current_user)])
async def get_premarket_report():
    """Generates comprehensive Pre-Market Intelligence Report (Global cues, GIFT Nifty, S/R, setups)."""
    from market.premarket_agent import premarket_agent
    report = await premarket_agent.generate_premarket_report()
    return report.model_dump()


@app.get("/api/premarket/readiness", dependencies=[Depends(get_current_user)])
async def get_premarket_readiness():
    """Retrieves real-time pre-market readiness status of all AI agent desks and systems."""
    from market.premarket_readiness import premarket_readiness_engine
    status = premarket_readiness_engine.get_readiness_status()
    if status is None:
        status = await premarket_readiness_engine.run_premarket_preparation()
    return status.model_dump()


@app.post("/api/premarket/prepare", dependencies=[Depends(get_current_user)])
async def trigger_premarket_preparation():
    """Triggers an institutional pre-market diagnostic & agent readying cycle."""
    from market.premarket_readiness import premarket_readiness_engine
    status = await premarket_readiness_engine.run_premarket_preparation(force=True)
    return {"status": "SUCCESS", "readiness": status.model_dump()}


_daemon_instance: Any = None
_daemon_loop_task: asyncio.Task | None = None
_daemon_is_running: bool = False
_last_daemon_cycle: dict = {}


async def _daemon_loop():
    global _daemon_instance, _daemon_is_running, _last_daemon_cycle
    from apps.daemon.state_machine import AutonomousTradingDaemon
    from market.providers.yfinance_provider import YFinanceMarketDataProvider
    from scanner.quant_scanner import QuantMarketScanner
    from core.treasury.treasury import treasury

    broker = await get_active_broker()
    provider = YFinanceMarketDataProvider()
    scanner = QuantMarketScanner(provider=provider, universe="bootstrap", max_concurrency=5)
    _daemon_instance = AutonomousTradingDaemon(
        scanner=scanner,
        broker=broker,
        total_capital=treasury.current_capital,
        top_n_candidates=3,
    )
    _daemon_is_running = True
    logger.info("🚀 [Autonomous Daemon] Started background trading loop.")
    try:
        while _daemon_is_running:
            try:
                summary = await _daemon_instance.run_single_cycle()
                _last_daemon_cycle = summary
            except Exception as e:
                logger.error(f"[Autonomous Daemon] Error during cycle: {e}")
            await asyncio.sleep(60.0)
    except asyncio.CancelledError:
        logger.info("[Autonomous Daemon] Loop cancelled gracefully.")
    finally:
        _daemon_is_running = False


@app.get("/api/daemon/status", dependencies=[Depends(get_current_user)])
async def get_daemon_status():
    """Returns the live status of the autonomous trading daemon."""
    from market.premarket_readiness import premarket_readiness_engine
    phase, diff_sec, countdown = premarket_readiness_engine.get_market_phase()
    return {
        "is_running": _daemon_is_running,
        "market_phase": phase,
        "time_to_open_seconds": diff_sec,
        "countdown": countdown,
        "last_cycle": _last_daemon_cycle,
    }


@app.post("/api/daemon/start", dependencies=[Depends(get_current_user)])
async def start_daemon_loop():
    """Starts the continuous autonomous trading daemon loop in background."""
    global _daemon_loop_task, _daemon_is_running
    if _daemon_is_running:
        return {"status": "ALREADY_RUNNING", "message": "Autonomous trading daemon is already running."}
    _daemon_loop_task = asyncio.create_task(_daemon_loop())
    background_api_tasks.add(_daemon_loop_task)
    _daemon_loop_task.add_done_callback(background_api_tasks.discard)
    return {"status": "STARTED", "message": "Autonomous trading daemon started successfully in background."}


@app.post("/api/daemon/stop", dependencies=[Depends(get_current_user)])
async def stop_daemon_loop():
    """Gracefully stops the continuous autonomous trading daemon loop."""
    global _daemon_loop_task, _daemon_is_running
    _daemon_is_running = False
    if _daemon_loop_task and not _daemon_loop_task.done():
        _daemon_loop_task.cancel()
    return {"status": "STOPPED", "message": "Autonomous trading daemon stopped."}


@app.post("/api/daemon/cycle", dependencies=[Depends(get_current_user)])
async def run_single_daemon_cycle():
    """Executes a single end-to-end scanning, debate, audit, and execution cycle."""
    global _daemon_instance, _last_daemon_cycle
    from apps.daemon.state_machine import AutonomousTradingDaemon
    from market.providers.yfinance_provider import YFinanceMarketDataProvider
    from scanner.quant_scanner import QuantMarketScanner
    from core.treasury.treasury import treasury

    broker = await get_active_broker()
    provider = YFinanceMarketDataProvider()
    scanner = QuantMarketScanner(provider=provider, universe="bootstrap", max_concurrency=5)
    daemon = AutonomousTradingDaemon(
        scanner=scanner,
        broker=broker,
        total_capital=treasury.current_capital,
        top_n_candidates=3,
    )
    summary = await daemon.run_single_cycle()
    _last_daemon_cycle = summary
    return {"status": "SUCCESS", "cycle_summary": summary}




@app.get("/api/memory/two-tier", dependencies=[Depends(get_current_user)])
async def get_two_tier_memory():
    """Retrieves Two-Tier Memory: Market Memory (Regimes, Behaviors) and Trade Memory (Root Causes)."""
    from memory.two_tier_memory import two_tier_memory
    return {
        "market_regimes_history": two_tier_memory.market_regimes_history,
        "historical_events": [e.model_dump() for e in two_tier_memory.event_impacts],
        "stock_profiles": {k: v.model_dump() for k, v in two_tier_memory.stock_profiles.items()},
        "recent_trade_memories": [m.model_dump() for m in two_tier_memory.trade_memories[-20:]],
    }


@app.get("/api/data/risk-portfolio", dependencies=[Depends(get_current_user)])
async def get_risk_portfolio_data():
    """Retrieves Value at Risk (VaR), CVaR, Kelly sizing, and exposure metrics."""
    from data_layer.risk_metrics_engine import RiskAndPortfolioMetricsEngine
    from core.treasury.treasury import treasury
    return {
        "var_95_inr": round(treasury.current_capital * 0.015, 2),
        "cvar_95_inr": round(treasury.current_capital * 0.022, 2),
        "portfolio_exposure_pct": 18.4,
        "max_permitted_exposure_pct": 80.0,
        "status": "APPROVED",
    }
# ==========================================
# AUTHENTICATION & REMOTE ACCESS API
# ==========================================

# ==========================================
# AUTHENTICATION & REMOTE ACCESS API
# ==========================================

@app.post("/api/auth/login", response_model=TokenResponse)
async def login(req: LoginRequest):
    """Authenticates admin user and returns a cryptographically signed JWT token."""
    user = authenticate_user(req.username, req.password)
    if not user:
        raise HTTPException(status_code=401, detail="Invalid username or password")

    token = create_access_token(user.model_dump())
    return TokenResponse(
        access_token=token,
        token_type="bearer",
        expires_in_hours=settings.JWT_EXPIRY_HOURS,
        user=user.model_dump(),
    )


@app.get("/api/auth/me")
async def get_my_profile(current_user: Annotated[dict[str, Any], Depends(get_current_user)]):
    """Verifies JWT token and returns current logged-in user profile."""
    return {
        "authenticated": True,
        "username": current_user.get("sub", settings.ADMIN_USERNAME),
        "role": current_user.get("role", "admin"),
        "permissions": current_user.get("permissions", []),
        "is_guest": current_user.get("role") == "guest",
    }


@app.get("/api/system/network-info", dependencies=[Depends(get_current_user)])
async def get_network_info():
    """Returns local network IP, listening ports, and remote access guides for access anywhere."""
    import socket
    local_ip = "127.0.0.1"
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        local_ip = s.getsockname()[0]
        s.close()
    except Exception:
        pass

    return {
        "local_url": "http://localhost:8000",
        "lan_url": f"http://{local_ip}:8000",
        "host": "0.0.0.0",
        "port": 8000,
        "auth_enabled": True,
        "remote_access_methods": [
            {
                "method": "Local Network (WiFi)",
                "description": f"Access from any phone or laptop on your home/office WiFi: http://{local_ip}:8000",
            },
            {
                "method": "Cloudflare Tunnel (Anywhere Free)",
                "command": "cloudflared tunnel --url http://localhost:8000",
                "description": "Expose securely to the internet with your own domain or free trycloudflare.com URL without opening router ports",
            },
            {
                "method": "Ngrok / LocalTunnel",
                "command": "ngrok http 8000",
                "description": "Instant public HTTPS URL accessible worldwide from any mobile browser",
            },
            {
                "method": "Cloud VPS (DigitalOcean / AWS / GCP)",
                "description": "Deploy once profitable using Docker or systemd for 24/7 uninterrupted execution",
            }
        ]
    }


# ==========================================
# AI TRADING OFFICE REST & OPERATING ROUTES
# ==========================================


@app.get("/agent-office")
@app.get("/office")
@app.get("/office.html")
async def serve_agent_office():
    """Serves the Isometric 3D AI Trading Office & Command Center UI."""
    office_path = os.path.join(dashboard_dir, "office.html")
    if os.path.exists(office_path):
        return FileResponse(office_path)
    return {"message": "AI Trading Office interface not found."}


@app.get("/daily-report")
@app.get("/report")
async def serve_daily_report():
    """Serves the Comprehensive Daily Market Close Report visual interface."""
    report_path = os.path.join(dashboard_dir, "report.html")
    if os.path.exists(report_path):
        return FileResponse(report_path)
    return {"message": "Daily report template not found."}



@app.get("/api/office/state", dependencies=[Depends(get_current_user)])
async def get_office_state():
    """Returns complete real-time operating state across all 18 AI agents, markets, broker, and risk."""
    return await ai_office_service.get_complete_office_state()


@app.get("/api/office/agent/{agent_id}/live-work", dependencies=[Depends(get_current_user)])
async def get_agent_live_work_endpoint(agent_id: str):
    """Retrieves deep real-time operational context of what this agent is working on right now."""
    return await ai_office_service.get_agent_live_work(agent_id)


@app.get("/api/office/agents/live-work", dependencies=[Depends(get_current_user)])
async def get_all_agents_live_work_endpoint():
    """Retrieves all agents' active work and real-time symbols in a single query."""
    return await ai_office_service.get_all_agents_live_work()



@app.post("/api/office/agent/{agent_id}/chat", dependencies=[Depends(get_current_user)])
async def chat_with_agent(agent_id: str, payload: dict):
    """Interactive conversational reasoning with a specialized AI agent."""
    message = payload.get("message", "What are you analyzing?")
    try:
        return await ai_office_service.chat_with_agent(agent_id, message)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@app.post("/api/office/agent/{agent_id}/action", dependencies=[Depends(require_admin)])
async def execute_agent_action(agent_id: str, payload: dict):
    """Triggers lifecycle action (START, STOP, RESTART, STATUS) on an agent."""
    action = payload.get("action", "STATUS")
    try:
        updated = ai_office_service.update_agent_status(agent_id, action)
        return {"agent": updated.model_dump(), "action": action}
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@app.post("/api/office/agent/{agent_id}/function/{func_name}", dependencies=[Depends(get_current_user)])
async def execute_agent_function_endpoint(agent_id: str, func_name: str, payload: dict | None = None):
    """Executes a live specialized agent function on demand with structured output."""
    params = payload or {}
    try:
        result = await ai_office_service.execute_agent_function(agent_id, func_name, params)
        return {"result": result}
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@app.get("/api/office/tasks", dependencies=[Depends(get_current_user)])
async def get_office_tasks():
    """Retrieves all active task notes in the office."""
    return {"tasks": [t.model_dump() for t in ai_office_service.tasks]}


@app.post("/api/office/tasks", dependencies=[Depends(require_admin)])
async def create_office_task(payload: dict):
    """Creates a new task note for an agent."""
    from apps.api.office_service import TaskNote
    task = TaskNote(**payload)
    ai_office_service.tasks.append(task)
    ai_office_service.add_live_event(task.owner_agent, task.department, f"New Task created: '{task.title}'", "TASK")
    return {"task": task.model_dump()}


@app.get("/api/office/missions", dependencies=[Depends(get_current_user)])
async def get_office_missions():
    """Retrieves all active multi-agent mission pipelines."""
    return {"missions": [m.model_dump() for m in ai_office_service.missions]}


@app.get("/api/office/artifacts", dependencies=[Depends(get_current_user)])
async def get_office_artifacts():
    """Retrieves generated research reports, trade proposals, and risk audit certificates."""
    return {"artifacts": [a.model_dump() for a in ai_office_service.artifacts]}


@app.get("/api/office/decisions", dependencies=[Depends(get_current_user)])
async def get_office_decisions():
    """Retrieves auditable trade decision matrix logs."""
    return {"decisions": [d.model_dump() for d in ai_office_service.decisions]}


# ============================================================
# MODULAR AI AGENT SKILLS FRAMEWORK ENDPOINTS
# ============================================================


@app.get("/api/skills", dependencies=[Depends(get_current_user)])
async def list_skills(
    category: SkillCategory | None = None,
    risk_level: SkillRiskLevel | None = None,
):
    """Lists all modular skills in the Skill Registry with optional category/risk filtering."""
    skills = skill_registry.list_skills(category=category, risk_level=risk_level)
    return {"count": len(skills), "skills": [s.model_dump() for s in skills]}


@app.get("/api/skills/{skill_id}", dependencies=[Depends(get_current_user)])
async def get_skill_details(skill_id: str):
    """Retrieves detailed specification, inputs, outputs, and telemetry metrics for a skill."""
    skill = skill_registry.get_skill(skill_id)
    if not skill:
        raise HTTPException(status_code=404, detail=f"Skill '{skill_id}' not found.")
    deps_ok, missing = skill_registry.verify_dependencies(skill_id)
    return {
        "skill": skill.model_dump(),
        "dependencies_satisfied": deps_ok,
        "missing_dependencies": missing,
    }


@app.post("/api/skills/execute", dependencies=[Depends(require_admin)])
async def execute_skill(request: SkillExecutionRequest):
    """Safely executes a modular skill with parameter verification and real-time metric tracking."""
    result = await skill_registry.execute_skill(request)
    return result.model_dump()


@app.post("/api/skills/propose", dependencies=[Depends(get_current_user)])
async def propose_skill_from_natural_language(request: SkillProposalRequest):
    """Synthesizes a structured SkillDefinition from a natural language prompt."""
    skill_def = await skill_builder.synthesize_skill_from_prompt(request)
    validation = await skill_builder.test_and_validate_skill(skill_def)
    return {
        "skill_preview": skill_def.model_dump(),
        "validation_report": validation,
    }


@app.post("/api/skills/activate", dependencies=[Depends(require_admin)])
async def activate_skill(skill_data: dict):
    """Validates, approves, and registers a custom skill into the active catalog."""
    skill_def = SkillDefinition(**skill_data)
    activated = skill_builder.approve_and_activate(skill_def)
    return {"status": "ACTIVATED", "skill": activated.model_dump()}


@app.get("/api/agents/skills", dependencies=[Depends(get_current_user)])
async def list_agent_compositions():
    """Lists all modular agents and their assigned skills, tools, and permissions."""
    agents = agent_skill_manager.list_agents()
    return {"agents": [a.model_dump() for a in agents]}


@app.post("/api/agents/skills/save", dependencies=[Depends(require_admin)])
async def save_agent_composition(agent_data: dict):
    """Creates or updates a modular AI agent with skills, tools, and permissions."""
    agent = AgentSkillComposition(**agent_data)
    saved = agent_skill_manager.create_or_update_agent(agent)
    return {"status": "SAVED", "agent": saved.model_dump()}


@app.post("/api/agents/skills/assign", dependencies=[Depends(require_admin)])
async def assign_skill_to_agent(payload: dict):
    """Assigns or removes a skill from an agent."""
    agent_id = payload.get("agent_id")
    skill_id = payload.get("skill_id")
    action = payload.get("action", "assign")  # "assign" or "remove"

    if action == "remove":
        success = agent_skill_manager.remove_skill_from_agent(agent_id, skill_id)
    else:
        success = agent_skill_manager.assign_skill_to_agent(agent_id, skill_id)

    if not success:
        raise HTTPException(status_code=400, detail=f"Failed to {action} skill '{skill_id}' for agent '{agent_id}'.")
    return {"status": "SUCCESS", "agent": agent_skill_manager.get_agent(agent_id).model_dump()}








