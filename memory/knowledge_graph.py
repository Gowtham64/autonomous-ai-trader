import json
import os
import uuid
from datetime import UTC, datetime
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


class EntityType(str, Enum):
    COMPANY = "COMPANY"
    SECTOR = "SECTOR"
    MARKET = "MARKET"
    STRATEGY = "STRATEGY"
    SIGNAL = "SIGNAL"
    TRADE = "TRADE"
    OUTCOME = "OUTCOME"
    AGENT = "AGENT"
    DECISION = "DECISION"
    RISK_EVENT = "RISK_EVENT"


class RelationType(str, Enum):
    BELONGS_TO = "BELONGS_TO"
    GENERATED = "GENERATED"
    ANALYZED = "ANALYZED"
    TRIGGERED = "TRIGGERED"
    RESULTED_IN = "RESULTED_IN"
    VETOED_BY = "VETOED_BY"
    WARNED_ABOUT = "WARNED_ABOUT"
    EXECUTED = "EXECUTED"
    CORRELATED_WITH = "CORRELATED_WITH"


class GraphNode(BaseModel):
    node_id: str
    entity_type: EntityType
    name: str
    attributes: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class GraphEdge(BaseModel):
    edge_id: str = Field(default_factory=lambda: f"edge_{uuid.uuid4().hex[:8]}")
    source_id: str
    target_id: str
    relation: RelationType
    weight: float = 1.0
    properties: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class KnowledgeGraph:
    """Interconnected Organizational Knowledge Graph (Section 54).
    
    Models multi-dimensional relationships connecting Companies, Sectors, Strategies,
    Trades, Outcomes, AI Agents, Decisions, and Risk Events.
    """

    def __init__(self, persistence_file: str = "data/knowledge_graph.json"):
        self.persistence_file = persistence_file
        self.nodes: dict[str, GraphNode] = {}
        self.edges: list[GraphEdge] = []
        self._seed_default_graph()
        self.load_from_file(self.persistence_file)

    def _seed_default_graph(self) -> None:
        """Seeds standard NSE sectors, companies, and strategies."""
        # Sectors
        self.add_node("sec_it", EntityType.SECTOR, "Information Technology", {"nifty_weight": 14.5})
        self.add_node("sec_auto", EntityType.SECTOR, "Automobile", {"nifty_weight": 6.8})
        self.add_node("sec_banking", EntityType.SECTOR, "Banking & Financials", {"nifty_weight": 34.2})
        self.add_node("sec_energy", EntityType.SECTOR, "Energy & Oil", {"nifty_weight": 12.0})

        # Core Companies
        self.add_node("comp_infy", EntityType.COMPANY, "INFY.NS", {"sector": "Information Technology"})
        self.add_node("comp_tcs", EntityType.COMPANY, "TCS.NS", {"sector": "Information Technology"})
        self.add_node("comp_tatamotors", EntityType.COMPANY, "TATAMOTORS.NS", {"sector": "Automobile"})
        self.add_node("comp_hdfcbank", EntityType.COMPANY, "HDFCBANK.NS", {"sector": "Banking & Financials"})
        self.add_node("comp_reliance", EntityType.COMPANY, "RELIANCE.NS", {"sector": "Energy & Oil"})

        # Relationships
        self.add_edge("comp_infy", "sec_it", RelationType.BELONGS_TO)
        self.add_edge("comp_tcs", "sec_it", RelationType.BELONGS_TO)
        self.add_edge("comp_tatamotors", "sec_auto", RelationType.BELONGS_TO)
        self.add_edge("comp_hdfcbank", "sec_banking", RelationType.BELONGS_TO)
        self.add_edge("comp_reliance", "sec_energy", RelationType.BELONGS_TO)

        # Strategies
        self.add_node("strat_momentum", EntityType.STRATEGY, "Momentum Breakout", {"timeframe": "Intraday"})
        self.add_node("strat_trend", EntityType.STRATEGY, "Trend Following", {"timeframe": "Swing"})
        self.add_node("strat_reversion", EntityType.STRATEGY, "Mean Reversion", {"timeframe": "Intraday"})

    def add_node(self, node_id: str, entity_type: EntityType, name: str, attributes: dict | None = None) -> GraphNode:
        node = GraphNode(
            node_id=node_id,
            entity_type=entity_type,
            name=name,
            attributes=attributes or {},
        )
        self.nodes[node_id] = node
        return node

    def add_edge(
        self,
        source_id: str,
        target_id: str,
        relation: RelationType,
        weight: float = 1.0,
        properties: dict | None = None,
    ) -> GraphEdge:
        edge = GraphEdge(
            source_id=source_id,
            target_id=target_id,
            relation=relation,
            weight=weight,
            properties=properties or {},
        )
        self.edges.append(edge)
        return edge

    def record_trade_chain(
        self,
        symbol: str,
        strategy_name: str,
        signal_id: str,
        agent_name: str,
        trade_id: str,
        outcome_pnl: float,
        risk_veto: bool = False,
        regime: str = "High Volatility",
    ) -> None:
        """Constructs an interconnected trade graph link from Signal -> Agent -> Decision -> Trade -> Outcome."""
        comp_id = f"comp_{symbol.lower().replace('.', '_')}"
        if comp_id not in self.nodes:
            self.add_node(comp_id, EntityType.COMPANY, symbol)

        strat_id = f"strat_{strategy_name.lower().replace(' ', '_')}"
        if strat_id not in self.nodes:
            self.add_node(strat_id, EntityType.STRATEGY, strategy_name)

        sig_node_id = f"sig_{signal_id}"
        self.add_node(sig_node_id, EntityType.SIGNAL, f"Signal {signal_id}", {"symbol": symbol, "regime": regime})

        agent_node_id = f"agent_{agent_name.lower().replace(' ', '_')}"
        if agent_node_id not in self.nodes:
            self.add_node(agent_node_id, EntityType.AGENT, agent_name)

        trade_node_id = f"trade_{trade_id}"
        self.add_node(trade_node_id, EntityType.TRADE, f"Trade {trade_id}", {"pnl": outcome_pnl})

        outcome_id = f"out_{trade_id}"
        self.add_node(
            outcome_id,
            EntityType.OUTCOME,
            "Profit" if outcome_pnl > 0 else "Loss",
            {"pnl": outcome_pnl, "regime": regime}
        )

        # Connect edges
        self.add_edge(agent_node_id, sig_node_id, RelationType.GENERATED)
        self.add_edge(sig_node_id, comp_id, RelationType.ANALYZED)
        self.add_edge(sig_node_id, strat_id, RelationType.BELONGS_TO)
        self.add_edge(sig_node_id, trade_node_id, RelationType.TRIGGERED)
        self.add_edge(trade_node_id, outcome_id, RelationType.RESULTED_IN)

        if risk_veto:
            risk_event_id = f"risk_{trade_id}"
            self.add_node(risk_event_id, EntityType.RISK_EVENT, "Risk Veto Warning", {"symbol": symbol})
            self.add_edge(risk_event_id, trade_node_id, RelationType.VETOED_BY)

    def find_connected_entities(self, node_id: str) -> dict[str, list[dict]]:
        """Traverses outgoing and incoming edges for any given entity."""
        outgoing = [
            {"target": self.nodes.get(e.target_id), "relation": e.relation.value, "properties": e.properties}
            for e in self.edges if e.source_id == node_id and e.target_id in self.nodes
        ]
        incoming = [
            {"source": self.nodes.get(e.source_id), "relation": e.relation.value, "properties": e.properties}
            for e in self.edges if e.target_id == node_id and e.source_id in self.nodes
        ]
        return {"node": self.nodes.get(node_id), "outgoing": outgoing, "incoming": incoming}

    def get_graph_summary(self) -> dict:
        return {
            "total_nodes": len(self.nodes),
            "total_edges": len(self.edges),
            "node_types": {
                t.value: sum(1 for n in self.nodes.values() if n.entity_type == t)
                for t in EntityType
            },
        }


    def save_to_file(self, file_path: str | None = None) -> bool:
        """Persists knowledge graph nodes and edges to JSON disk storage."""
        target_path = file_path or self.persistence_file
        try:
            os.makedirs(os.path.dirname(os.path.abspath(target_path)), exist_ok=True)
            data = {
                "nodes": {k: v.model_dump(mode="json") for k, v in self.nodes.items()},
                "edges": [e.model_dump(mode="json") for e in self.edges],
            }
            with open(target_path, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2)
            return True
        except Exception:
            return False

    def load_from_file(self, file_path: str | None = None) -> bool:
        """Loads persisted knowledge graph nodes and edges from JSON disk storage."""
        target_path = file_path or self.persistence_file
        if not os.path.exists(target_path):
            return False
        try:
            with open(target_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            for n_id, n_data in data.get("nodes", {}).items():
                self.nodes[n_id] = GraphNode(**n_data)
            existing_edge_ids = {e.edge_id for e in self.edges}
            for e_data in data.get("edges", []):
                edge = GraphEdge(**e_data)
                if edge.edge_id not in existing_edge_ids:
                    self.edges.append(edge)
                    existing_edge_ids.add(edge.edge_id)
            return True
        except Exception:
            return False


# Global Knowledge Graph singleton
knowledge_graph = KnowledgeGraph()
