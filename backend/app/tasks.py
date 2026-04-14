import asyncio
from typing import Any

from sqlalchemy.orm import Session

from app.database import SessionLocal
from app.models.user import User
from app.services.environment_cache import fetch_env_rss_live, upsert_environment_snapshot
from app.services.triggers import run_pipeline_all_users
from app.worker import celery_app


def _run_async(coro) -> Any:
    """Helper to run async code synchronously inside a Celery task."""
    loop = asyncio.get_event_loop()
    return loop.run_until_complete(coro)


@celery_app.task(name="app.tasks.evaluate_all_triggers_task")
def evaluate_all_triggers_task(force_mock: bool = False) -> dict[str, Any]:
    """
    Celery task that runs the full parametric trigger pipeline for all users.
    Executed periodically by celery-beat.
    """
    db: Session = SessionLocal()
    try:
        results = _run_async(run_pipeline_all_users(db, force_mock=force_mock))
        total = len(results)
        claimed = sum(1 for r in results if r.get("claim_created"))
        return {"total_users_evaluated": total, "claims_created": claimed}
    except Exception as e:
        return {"error": str(e)}
    finally:
        db.close()


@celery_app.task(name="app.tasks.refresh_environment_snapshots_task")
def refresh_environment_snapshots_task() -> dict[str, Any]:
    """Refresh cached OpenWeather/WAQI/RSS per user (keeps pricing + /live warm)."""
    db: Session = SessionLocal()
    try:
        users = db.query(User).all()

        async def _refresh_all() -> None:
            for u in users:
                try:
                    env, rss = await fetch_env_rss_live(u)
                    upsert_environment_snapshot(db, u, env, rss)
                except Exception:
                    continue

        asyncio.run(_refresh_all())
        return {"users_seen": len(users)}
    except Exception as e:
        return {"error": str(e)}
    finally:
        db.close()
