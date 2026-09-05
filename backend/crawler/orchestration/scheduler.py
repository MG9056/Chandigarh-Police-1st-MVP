import asyncio
from datetime import datetime, timedelta
import logging

from database import SessionLocal
from crawler.models.source import Source
from crawler.models.crawler_run import CrawlerRun
from crawler.orchestration.flows import run_crawl

logger = logging.getLogger(__name__)


class CrawlerScheduler:
    """
    Continuously schedules crawler runs for active sources.

    The browser/frontend is not involved in this loop. As long as the
    FastAPI backend process is running, active sources continue to run.
    """

    def __init__(self):
        self.is_running = False
        self._source_tasks = {}

    async def start(self):
        if self.is_running:
            return

        self.is_running = True
        logger.info("CrawlerScheduler starting background loop...")

        while self.is_running:
            db = SessionLocal()

            try:
                active_sources = (
                    db.query(Source)
                    .filter(Source.is_active == True)
                    .all()
                )

                for source in active_sources:
                    source_key = str(source.id)

                    # Don't start another crawl for the same source while
                    # one is already running/scheduled.
                    existing_task = self._source_tasks.get(source_key)

                    if existing_task and not existing_task.done():
                        continue

                    last_run = (
                        db.query(CrawlerRun)
                        .filter(CrawlerRun.source_id == source.id)
                        .order_by(CrawlerRun.started_at.desc())
                        .first()
                    )

                    should_run = False

                    if not last_run:
                        should_run = True
                    elif last_run.status == "STOPPED":
                        # Re-enabled source can start again immediately.
                        should_run = True
                    else:
                        interval_seconds = source.poll_interval_seconds or 60
                        interval_td = timedelta(seconds=interval_seconds)

                        # SQLite may return timezone-naive datetimes, so use
                        # datetime.utcnow() here for a consistent comparison.
                        now = datetime.utcnow()

                        if last_run.started_at:
                            started_at = last_run.started_at.replace(tzinfo=None)

                            if (now - started_at) >= interval_td:
                                should_run = True

                    if should_run:
                        logger.info(
                            f"Triggering scheduled crawl for source "
                            f"{source.name} ({source.id})"
                        )

                        task = asyncio.create_task(
                            run_crawl(source_id=source.id)
                        )

                        self._source_tasks[source_key] = task

                        def cleanup_task(
                            completed_task,
                            source_key=source_key,
                        ):
                            current = self._source_tasks.get(source_key)

                            if current is completed_task:
                                self._source_tasks.pop(source_key, None)

                            try:
                                completed_task.result()
                            except asyncio.CancelledError:
                                pass
                            except Exception:
                                logger.exception(
                                    f"Scheduled crawl task failed for source "
                                    f"{source_key}"
                                )

                        task.add_done_callback(cleanup_task)

            except Exception as e:
                logger.error(
                    f"Error in CrawlerScheduler loop: {e}",
                    exc_info=True,
                )

            finally:
                db.close()

            # Check the scheduler frequently so a source being stopped or
            # re-enabled is noticed quickly. The source's own
            # poll_interval_seconds controls how often it actually crawls.
            await asyncio.sleep(5)

        logger.info("CrawlerScheduler stopped.")

    def stop(self):
        self.is_running = False
