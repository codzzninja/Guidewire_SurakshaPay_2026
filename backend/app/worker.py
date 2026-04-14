from celery import Celery
from celery.schedules import crontab
from app.config import settings

# Initialize Celery app
celery_app = Celery(
    "surakshapay_worker",
    broker=settings.redis_url,
    backend=settings.redis_url,
    include=["app.tasks"]
)

# Configure Celery
celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="Asia/Kolkata",
    enable_utc=True,
)

# Schedule the continuous monitoring job properly
celery_app.conf.beat_schedule = {
    "run-parametric-triggers-every-15-minutes": {
        "task": "app.tasks.evaluate_all_triggers_task",
        "schedule": crontab(minute="*/15"),
        "args": (False,),
    },
    "refresh-environment-cache-every-5-minutes": {
        "task": "app.tasks.refresh_environment_snapshots_task",
        "schedule": crontab(minute="*/5"),
    },
}
