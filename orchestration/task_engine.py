import uuid
from datetime import UTC, datetime
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field

from core.logging import logger


class TaskPriority(str, Enum):
    LOW = "LOW"
    NORMAL = "NORMAL"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"


class TaskStatus(str, Enum):
    PENDING = "PENDING"
    IN_PROGRESS = "IN_PROGRESS"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"


class AgentTask(BaseModel):
    task_id: str = Field(default_factory=lambda: f"task_{uuid.uuid4().hex[:8]}")
    title: str
    description: str
    creator_agent: str
    assigned_agent: str
    priority: TaskPriority = TaskPriority.NORMAL
    symbol: str | None = None
    deadline: datetime | None = None
    status: TaskStatus = TaskStatus.PENDING
    result: dict[str, Any] | None = None
    evidence: list[str] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    completed_at: datetime | None = None


class TaskHandoffEngine:
    """Inter-Agent Task Delegation & Handoff Hub (Section 53).
    
    Coordinates structured multi-agent investigation workflows without unmonitored agent sprawling.
    """

    def __init__(self):
        self.tasks: dict[str, AgentTask] = {}

    def create_task(
        self,
        title: str,
        description: str,
        creator_agent: str,
        assigned_agent: str,
        priority: TaskPriority = TaskPriority.NORMAL,
        symbol: str | None = None,
    ) -> AgentTask:
        """Creates and assigns a structured work task to another agent."""
        task = AgentTask(
            title=title,
            description=description,
            creator_agent=creator_agent,
            assigned_agent=assigned_agent,
            priority=priority,
            symbol=symbol,
        )
        self.tasks[task.task_id] = task
        logger.info(f"[Task Engine] '{creator_agent}' assigned Task '{title}' to '{assigned_agent}' [{task.priority.value}]")
        return task

    def complete_task(
        self,
        task_id: str,
        result: dict[str, Any],
        evidence: list[str] | None = None,
    ) -> AgentTask:
        """Marks task as completed with intelligence artifacts and evidence."""
        if task_id not in self.tasks:
            raise ValueError(f"Task '{task_id}' not found.")

        task = self.tasks[task_id]
        task.status = TaskStatus.COMPLETED
        task.result = result
        task.evidence = evidence or []
        task.completed_at = datetime.now(UTC)
        logger.info(f"[Task Engine] Task '{task.title}' [{task_id}] completed by '{task.assigned_agent}'.")
        return task

    def get_agent_tasks(self, agent_name: str) -> list[AgentTask]:
        return [t for t in self.tasks.values() if t.assigned_agent == agent_name]

    def list_all_tasks(self, limit: int = 25) -> list[dict]:
        return [t.model_dump() for t in list(self.tasks.values())[-limit:]]


# Global Task Handoff Engine singleton
task_handoff_engine = TaskHandoffEngine()
