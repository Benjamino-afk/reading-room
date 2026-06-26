"""Background feed polling on a fixed interval."""
from apscheduler.schedulers.background import BackgroundScheduler

from . import config, feeds

_scheduler: BackgroundScheduler | None = None


def start() -> None:
    global _scheduler
    if config.READONLY or _scheduler is not None:
        return
    _scheduler = BackgroundScheduler(daemon=True)
    _scheduler.add_job(
        feeds.poll_all, "interval", minutes=config.POLL_INTERVAL,
        next_run_time=None, id="poll_all", max_instances=1,
    )
    _scheduler.start()


def stop() -> None:
    global _scheduler
    if _scheduler is not None:
        _scheduler.shutdown(wait=False)
        _scheduler = None
