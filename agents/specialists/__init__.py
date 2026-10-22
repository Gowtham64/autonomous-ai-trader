"""
Specialist Trading Masters Package
"""

from agents.specialists.bnf_agent import BNFAgent, bnf_agent
from agents.specialists.jhunjhunwala_agent import JhunjhunwalaAgent, jhunjhunwala_agent
from agents.specialists.livermore_agent import LivermoreAgent, livermore_agent
from agents.specialists.turtle_trend_agent import TurtleTrendSpecialistAgent, turtle_trend_agent

__all__ = [
    "BNFAgent",
    "bnf_agent",
    "JhunjhunwalaAgent",
    "jhunjhunwala_agent",
    "LivermoreAgent",
    "livermore_agent",
    "TurtleTrendSpecialistAgent",
    "turtle_trend_agent",
]
