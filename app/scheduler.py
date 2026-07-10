"""Background feed polling on a fixed interval."""
from apscheduler.schedulers.background import BackgroundScheduler

from . import config, db, feeds, images

_scheduler: BackgroundScheduler | None = None


def _prune() -> None:
    try:
        n, orphans = db.prune_read(config.PRUNE_DAYS)
        m = images.delete_local(orphans)
        if n:
            print(f"[prune] removed {n} read articles >{config.PRUNE_DAYS}d, {m} images", flush=True)
    except Exception as e:
        print(f"[prune] failed: {e}", flush=True)


def start() -> None:
    global _scheduler
    if config.READONLY or _scheduler is not None:
        return
    _scheduler = BackgroundScheduler(daemon=True)
    _scheduler.add_job(
        feeds.poll_all, "interval", minutes=config.POLL_INTERVAL,
        next_run_time=None, id="poll_all", max_instances=1,
    )
    if config.PRUNE_DAYS > 0:
        _scheduler.add_job(
            _prune, "interval", hours=24, id="prune", max_instances=1,
        )
    _scheduler.start()


def stop() -> None:
    global _scheduler
    if _scheduler is not None:
        _scheduler.shutdown(wait=False)
        _scheduler = None
