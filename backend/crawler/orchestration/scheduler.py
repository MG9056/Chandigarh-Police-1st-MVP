import asyncio
from datetime import datetime, timezone, timedelta
import logging
from sqlalchemy.orm import Session
from database import SessionLocal
from crawler.models.source import Source
from crawler.models.crawler_run import CrawlerRun
from crawler.orchestration.flows import run_crawl

logger = logging.getLogger(__name__)


class CrawlerScheduler:
    """
    Schedules and triggers crawler runs based on source poll_interval_minutes.
    """

    def __init__(self):
        self.is_running = False

    async def start(self):
        self.is_running = True
        logger.info("CrawlerScheduler starting background loop...")

        while self.is_running:
            try:
                db = SessionLocal()
                try:
                    active_sources = db.query(Source).filter(Source.is_active == True).all()
                    now = datetime.now(timezone.utc)

                    for source in active_sources:
                        last_run = db.query(CrawlerRun).filter(
                            CrawlerRun.source_id == source.id
                        ).order_by(CrawlerRun.started_at.desc()).first()

                        should_run = False
                        if not last_run:
                            should_run = True
                        else:
                            interval_td = timedelta(minutes=source.poll_interval_minutes or 60)
                            if (now - last_run.started_at) >= interval_td:
                                should_run = True

                        if should_run:
                            logger.info(f"Triggering scheduled crawl for source {source.name} ({source.id})")
                            asyncio.create_task(run_crawl(source_id=source.id, db=db))
                finally:
                    db.close()
            except Exception as e:
                logger.error(f"Error in CrawlerScheduler loop: {e}")

            await asyncio.sleep(60)  # Check interval every 60 seconds

    def stop(self):
        self.is_running = False
