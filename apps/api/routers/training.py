"""
AI Agent Training & Skill Mastery - API Router.
Exposes endpoints for training progress, curriculum mastery, live simulation episodes,
and manual/background training control.
"""

from fastapi import APIRouter, Depends

from core.auth.security import get_current_user
from training.continuous_runner import continuous_training_daemon
from training.trainer import ai_trainer

router = APIRouter(prefix="/api/training", tags=["AI Agent Training"], dependencies=[Depends(get_current_user)])



@router.get("/status")
async def get_training_status():
    """Returns real-time summary of AI agent training, skill mastery levels, and win rates."""
    return ai_trainer.get_summary()


@router.post("/start")
async def start_training():
    """Starts the continuous off-market training daemon."""
    continuous_training_daemon.start()
    return {
        "status": "TRAINING_STARTED",
        "message": "Continuous off-market AI agent skill training daemon activated.",
    }


@router.post("/stop")
async def stop_training():
    """Stops the continuous training daemon."""
    continuous_training_daemon.stop()
    return {
        "status": "TRAINING_STOPPED",
        "message": "Continuous training daemon stopped.",
    }


@router.get("/curriculum")
async def get_curriculum():
    """Returns detailed competency levels across all institutional trading skills."""
    summary = ai_trainer.get_summary()
    return {
        "modules_count": len(summary.modules),
        "modules": [m.model_dump() for m in summary.modules],
    }


@router.get("/episodes")
async def get_recent_episodes(limit: int = 50):
    """Returns recent simulated training episodes and post-trade reflections."""
    return {
        "total_episodes": len(ai_trainer.episodes),
        "episodes": [e.model_dump() for e in ai_trainer.episodes[-limit:]],
    }
