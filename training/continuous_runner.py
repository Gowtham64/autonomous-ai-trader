"""
Continuous Off-Market Training Daemon
Runs periodic reinforcement learning and strategy simulation episodes in the background.
"""

from __future__ import annotations

import asyncio
from core.logging import logger


class ContinuousTrainingDaemon:
    def __init__(self):
        self.is_running: bool = False
        self._task: asyncio.Task | None = None

    def start(self):
        if self.is_running:
            return
        self.is_running = True
        logger.info("🧠 [Continuous Training] Daemon activated for autonomous off-market skill mastery.")

    def stop(self):
        self.is_running = False
        if self._task and not self._task.done():
            self._task.cancel()
            self._task = None
        logger.info("🛑 [Continuous Training] Daemon stopped.")


continuous_training_daemon = ContinuousTrainingDaemon()
