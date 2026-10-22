from typing import TypedDict

from langgraph.graph import END, StateGraph

from agents.facilitator.facilitator import AdversarialDebateDesk
from agents.research_desk import AIResearchDesk
from agents.trader.fund_manager import FundManagerAgent
from core.schemas.trade import AnalystReport, CandidateSignal, DebateTranscript, TradeDecision


class AgentWorkflowState(TypedDict):
    signal: CandidateSignal
    analyst_reports: list[AnalystReport]
    debate: DebateTranscript | None
    decision: TradeDecision | None


async def research_node(state: AgentWorkflowState) -> AgentWorkflowState:
    desk = AIResearchDesk()
    reports = await desk.conduct_research(state["signal"])
    return {**state, "analyst_reports": reports}


async def debate_node(state: AgentWorkflowState) -> AgentWorkflowState:
    debate_desk = AdversarialDebateDesk()
    debate = await debate_desk.conduct_debate(state["signal"], state["analyst_reports"])
    return {**state, "debate": debate}


async def fund_manager_node(state: AgentWorkflowState) -> AgentWorkflowState:
    fund_mgr = FundManagerAgent()
    decision = await fund_mgr.decide(state["signal"], state["analyst_reports"], state["debate"])
    return {**state, "decision": decision}


def build_trading_workflow_graph():
    """Builds and compiles the multi-agent LangGraph workflow for a single symbol."""
    workflow = StateGraph(AgentWorkflowState)

    workflow.add_node("research", research_node)
    workflow.add_node("debate", debate_node)
    workflow.add_node("fund_manager", fund_manager_node)

    workflow.set_entry_point("research")
    workflow.add_edge("research", "debate")
    workflow.add_edge("debate", "fund_manager")
    workflow.add_edge("fund_manager", END)

    return workflow.compile()


class MultiStockWorkflowState(TypedDict):
    candidates: list[CandidateSignal]
    evaluations: list[dict]
    approved_trades: list[dict]
    rejected_trades: list[dict]


async def batch_evaluation_node(state: MultiStockWorkflowState) -> MultiStockWorkflowState:
    from orchestration.batch_engine import MultiStockOrchestrator
    orchestrator = MultiStockOrchestrator()
    summary = await orchestrator.run_batch_debate_and_allocation(state["candidates"])
    return {
        **state,
        "evaluations": summary["ranked_candidates"],
        "approved_trades": summary["approved_trades"],
        "rejected_trades": summary["rejected_trades"],
    }


def build_batch_trading_workflow_graph():
    """Builds and compiles the multi-stock LangGraph workflow for evaluating N candidates simultaneously."""
    workflow = StateGraph(MultiStockWorkflowState)
    workflow.add_node("batch_evaluator", batch_evaluation_node)
    workflow.set_entry_point("batch_evaluator")
    workflow.add_edge("batch_evaluator", END)
    return workflow.compile()

